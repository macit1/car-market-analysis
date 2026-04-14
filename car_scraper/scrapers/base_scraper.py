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
    def __init__(self, site_name: str, base_url: str):
        self.site_name = site_name
        self.base_url = base_url
        self.session = None
        self.request_count = 0
        self.listings = []
        self.ua = UserAgent()
        
        # Load configuration
        self.make = ""
        self.model = ""
        self.target_limit = 100
        
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
                self.make = config.get("search_parameters", {}).get("make", "")
                self.model = config.get("search_parameters", {}).get("model", "")
                self.target_limit = config.get("extraction_limit", 100)
        except Exception as e:
            logger.warning(f"Failed to load config.json: {e}", extra={'site': self.site_name})

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
            self.listings.append(listing_model)
            # Log carefully avoiding spam, just log successful extraction URL
            logger.info(f"Listing extracted: {listing_model.listing_url}", extra={'site': self.site_name})
            return True
        except ValidationError as e:
            logger.warning(f"Skipped listing {raw_data.get('listing_url')} due to validation error.", extra={'site': self.site_name})
            return False

    def save_data(self):
        """Exports listings array to a strictly formatted timestamped CSV string."""
        os.makedirs("data/raw", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/raw/{self.site_name}_{timestamp}.csv"
        
        if not self.listings:
            logger.info("No listings extracted; skipping CSV generation.", extra={'site': self.site_name})
            return
            
        headers = list(CarListing.model_fields.keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            if 'listing_url' in headers:
                headers.remove('listing_url')
                headers.append('listing_url')
                
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for listing in self.listings:
                writer.writerow(listing.model_dump())
        
        logger.info(f"Saved {len(self.listings)} listings to {filename}", extra={'site': self.site_name})

    def run(self):
        """Entrypoint for scraping logic. Must be implemented by specific site scrapers."""
        raise NotImplementedError
