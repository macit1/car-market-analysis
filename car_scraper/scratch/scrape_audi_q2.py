"""
One-off scraper: Audi Q2 only → saves to data/raw/audi_q2_<timestamp>.csv
Run from car_scraper/ directory:
    python scratch/scrape_audi_q2.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json, time, random, csv
from datetime import datetime
from scrapers.base_scraper import BaseScraper
from utils.logger import logger

# ── Config ──────────────────────────────────────────────────────────────────
MAKE       = "audi"
MODEL      = "q2"
LIMIT      = 150          # max listings to collect
OUTPUT_DIR = "data/raw"
# ────────────────────────────────────────────────────────────────────────────

class Q2Scraper(BaseScraper):
    def __init__(self):
        super().__init__(site_name="autoscout24", base_url="")
        # Override targets & limit — ignore config.json
        self.targets = [{"make": MAKE, "model": MODEL}]
        self.target_limit = LIMIT
        # Custom output file name
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_export_file = f"{OUTPUT_DIR}/audi_q2_{ts}.csv"
        logger.info(f"Output file: {self.current_export_file}", extra={'site': 'Q2'})

    def run(self):
        self.start_session()
        base_url = f"https://www.autoscout24.be/fr/lst/{MAKE}/{MODEL}/c/suv-pick-up"
        extracted = 0
        page = 1

        while extracted < LIMIT:
            url = f"{base_url}?page={page}"
            soup = self.get_page(url)

            if page == 1 and soup:
                h1 = soup.find('h1')
                if h1:
                    import re
                    text = h1.text.replace('\u202f', '').replace('\xa0', '')
                    digits = re.findall(r'\d+', text)
                    if digits:
                        logger.info(f"Total listings on AutoScout24: {''.join(digits)}", extra={'site': 'Q2'})

            if not soup:
                logger.warning(f"Failed to load page {page}. Stopping.", extra={'site': 'Q2'})
                break

            articles = soup.find_all('article')
            if not articles:
                logger.info(f"No more articles on page {page}. Done.", extra={'site': 'Q2'})
                break

            logger.info(f"Page {page} — {len(articles)} listings found", extra={'site': 'Q2'})

            for art in articles:
                if extracted >= LIMIT:
                    break
                guid = art.get('data-guid')
                if not guid:
                    continue
                detail_url = f"https://www.autoscout24.be/fr/offres/--{guid}"
                detail_soup = self.get_page(detail_url)
                if not detail_soup:
                    continue

                script = detail_soup.find('script', id='__NEXT_DATA__')
                if not script or not script.string:
                    continue

                try:
                    nd = json.loads(script.string)
                    listing = nd.get('props', {}).get('pageProps', {}).get('listingDetails', {})
                    if not listing:
                        continue
                    if listing.get('status') != 'Active':
                        continue

                    vehicle = listing.get('vehicle', {})
                    year_raw = vehicle.get('firstRegistrationDateRaw', '')
                    year = int(year_raw.split('-')[0]) if year_raw and '-' in year_raw else 0
                    prices = listing.get('prices', {}).get('public', {})
                    price = prices.get('priceRaw', 0) or \
                            listing.get('prices', {}).get('dealer', {}).get('priceRaw', 0)
                    loc_data = listing.get('location', {})
                    loc = f"{loc_data.get('zip', '')} {loc_data.get('city', '')}".strip() or 'Unknown'

                    data = {
                        "make": vehicle.get('make', 'Unknown'),
                        "model": vehicle.get('model', 'Unknown'),
                        "year": year,
                        "price": str(price),
                        "mileage": str(vehicle.get('mileageInKmRaw', 0)),
                        "fuel_type": vehicle.get('fuelCategory', {}).get('formatted', 'Unknown'),
                        "transmission": vehicle.get('transmissionType', 'Unknown'),
                        "location": loc,
                        "listing_url": listing.get('webPage', detail_url),
                        "posted_date": "N/A"
                    }

                    if self.parse_listing(data):
                        extracted += 1
                        logger.info(f"[{extracted}/{LIMIT}] Extracted: {data['make']} {data['model']} {year} — €{price}", extra={'site': 'Q2'})

                except Exception as e:
                    logger.debug(f"Parse error: {e}", extra={'site': 'Q2'})

            page += 1

        logger.info(f"Scraping complete — {extracted} Audi Q2 listings collected.", extra={'site': 'Q2'})
        self.save_data()
        self.close_session()

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    Q2Scraper().run()
