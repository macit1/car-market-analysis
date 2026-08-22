import time
import random
import os
import csv
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from utils.logger import logger
from models import CarListing
from pydantic import ValidationError

import json

class BaseScraper:
    def __init__(self, site_name: str, base_url: str, config_path: str = "config.json"):
        self.site_name = site_name
        self.base_url = base_url
        self.config_path = config_path
        self.session = None
        self.request_count = 0
        self.listings = []
        self.seen_urls = set()  # Deduplication barrier
        self.ua = UserAgent()

        # Load configuration
        self.config = {}
        self.targets = []
        self.target_limit = 100

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
                self.targets = self.config.get("targets", [])
                self.target_limit = self.config.get("extraction_limit_per_target", 100)
        except Exception as e:
            logger.warning(f"Failed to load {config_path}: {e}", extra={'site': self.site_name})

        self.set_export_file(self.site_name)

    def set_export_file(self, basename: str):
        """Point subsequent save_data() calls at a fresh timestamped CSV.

        Scrapers that split a run into several outputs (one per configured
        target) call this between targets; the dedup barrier is deliberately
        left intact so the same listing is never written twice in one run.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_export_file = f"data/raw/{basename}_{timestamp}.csv"
        return self.current_export_file

    def start_session(self):
        logger.info(f"Scraper session started.", extra={'site': self.site_name})
        self.session = requests.Session()
        
        # Set dynamic User-Agent and realistic headers
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'nl,fr;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }
        self.session.headers.update(headers)

    def close_session(self):
        if self.session:
            self.session.close()
            self.session = None

    def get_page(self, url: str, retries: int = 3):
        """Loads a page with random delay, retries with exponential backoff, and tracks requests."""
        # Lower delay for requests compared to Browser (1 to 3 seconds)
        delay = random.uniform(1, 3)
        time.sleep(delay)

        self.request_count += 1
        if self.request_count % 50 == 0:
            if self.session:
                self.session.cookies.clear()
                # Rotate user agent
                self.session.headers.update({'User-Agent': self.ua.random})
                logger.info(f"Cleared session cookies and rotated User-Agent at request {self.request_count}.", extra={'site': self.site_name})

        backoff = [2, 4, 8]
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    return soup
                elif response.status_code in [404, 410]:
                    logger.debug(f"Page is missing or sold (status {response.status_code}): {url}", extra={'site': self.site_name})
                    return None
                elif response.status_code in [403, 429]:
                    logger.warning(f"Received {response.status_code} Forbidden/RateLimit for {url}. Anti-bot mechanisms likely triggered.", extra={'site': self.site_name})
                else:
                    logger.warning(f"Received unexpected status {response.status_code} for {url}.", extra={'site': self.site_name})

            except Exception as e:
                logger.error(f"Failed to load {url}. Error: {e}.", extra={'site': self.site_name})
                
            wait_time = backoff[attempt] if attempt < len(backoff) else 10
            logger.info(f"Retrying in {wait_time}s...", extra={'site': self.site_name})
            time.sleep(wait_time)
                
        logger.warning(f"Page load failed permanently for {url} after {retries} attempts. Skipping this page.", extra={'site': self.site_name})
        return None

    def parse_listing(self, raw_data: dict):
        """Attempts to validate data cleanly via Pydantic logic. Skips if missing make/model/price or invalid year."""
        # Clean string to N/A for None outputs (per spec requirements)
        for key, val in raw_data.items():
            if val is None:
                raw_data[key] = "N/A"

        try:
            listing_model = CarListing(**raw_data)

            # Deduplication: skip if URL already seen this session
            if listing_model.listing_url in self.seen_urls:
                logger.debug(f"Duplicate skipped: {listing_model.listing_url}", extra={'site': self.site_name})
                return False

            self.seen_urls.add(listing_model.listing_url)
            self.listings.append(listing_model)
            logger.info(f"Listing extracted: {listing_model.listing_url}", extra={'site': self.site_name})
            return True
        except ValidationError as e:
            logger.warning(f"Skipped listing {raw_data.get('listing_url')} due to validation error.", extra={'site': self.site_name})
            return False

    def save_data(self):
        """Appends current listings buffer to the cumulative CSV. Header written only once."""
        os.makedirs("data/raw", exist_ok=True)

        if not self.listings:
            logger.debug("No new listings to save; skipping.", extra={'site': self.site_name})
            return

        headers = list(CarListing.model_fields.keys())
        if 'listing_url' in headers:
            headers.remove('listing_url')
            headers.append('listing_url')

        # Write header only if the file doesn't exist yet (first save of this run)
        write_header = not os.path.exists(self.current_export_file)

        with open(self.current_export_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if write_header:
                writer.writeheader()
            for listing in self.listings:
                writer.writerow(listing.model_dump())

        logger.info(f"Saved {len(self.listings)} new listings → {self.current_export_file}", extra={'site': self.site_name})

        # Clear buffer so next save_data call doesn't re-write the same rows
        self.listings.clear()

    def run(self):
        """Entrypoint for scraping logic. Must be implemented by specific site scrapers."""
        raise NotImplementedError
