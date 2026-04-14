import json
from scrapers.base_scraper import BaseScraper
from utils.logger import logger

class AutoScoutScraper(BaseScraper):
    def __init__(self):
        super().__init__(site_name="autoscout24", base_url="https://www.autoscout24.be/fr/lst")
        
        # Re-construct base URL dynamically after config is loaded
        if self.make:
            self.base_url = f"{self.base_url}/{self.make}"
            if self.model:
                self.base_url = f"{self.base_url}/{self.model}"
    def run(self):
        self.start_session()
        current_page = 1
        
        while len(self.listings) < self.target_limit:
            current_url = f"{self.base_url}?page={current_page}"
            logger.info(f"Loading List Page {current_page} to find URLs...", extra={'site': self.site_name})
            soup = self.get_page(current_url)
            
            if not soup:
                logger.warning(f"Failed to retrieve soup for {current_url}. Stopping.", extra={'site': self.site_name})
                break
                
            articles = soup.find_all('article')
            if not articles:
                logger.info("No articles found on this page. Reached end of results.", extra={'site': self.site_name})
                break
                
            # Step 1: Extract URLs
            detail_urls = []
            for art in articles:
                guid = art.get('data-guid')
                if guid:
                    detail_urls.append(f"https://www.autoscout24.be/fr/offres/--{guid}")
            
            # Step 2: Crawl Detail Pages
            for url in detail_urls:
                if len(self.listings) >= self.target_limit:
                    break
                    
                logger.debug(f"Fetching detail page: {url}", extra={'site': self.site_name})
                detail_soup = self.get_page(url)
                if not detail_soup:
                    continue
                    
                # Step 3: Extract from __NEXT_DATA__
                next_data_script = detail_soup.find('script', id='__NEXT_DATA__')
                if not next_data_script or not next_data_script.string:
                    logger.warning(f"Skipped {url} - No __NEXT_DATA__ found.", extra={'site': self.site_name})
                    continue
                    
                try:
                    nd = json.loads(next_data_script.string)
                    listing = nd.get('props', {}).get('pageProps', {}).get('listingDetails', {})
                    if not listing:
                        continue
                        
                    vehicle = listing.get('vehicle', {})
                    
                    # Check if sold/gone
                    status = listing.get('status', 'Active')
                    if status != 'Active':
                        logger.info(f"Skipped {url} - Listing status is {status}.", extra={'site': self.site_name})
                        continue
                    
                    make = vehicle.get('make', 'Unknown')
                    model = vehicle.get('model', 'Unknown')
                    
                    year_raw = vehicle.get('firstRegistrationDateRaw', '')
                    year = int(year_raw.split('-')[0]) if year_raw and '-' in year_raw else 0
                    
                    prices = listing.get('prices', {}).get('public', {})
                    price = prices.get('priceRaw', 0)
                    if not price:
                        price = listing.get('prices', {}).get('dealer', {}).get('priceRaw', 0)
                        
                    mileage = vehicle.get('mileageInKmRaw', 0)
                    
                    fuel = vehicle.get('fuelCategory', {}).get('formatted', 'Unknown')
                    trans = vehicle.get('transmissionType', 'Unknown')
                    
                    loc_data = listing.get('location', {})
                    loc = f"{loc_data.get('zip', '')} {loc_data.get('city', '')}".strip()
                    if not loc:
                        loc = "Unknown"
                        
                    data = {
                        "make": make,
                        "model": model,
                        "year": year,
                        "price": str(price),
                        "mileage": str(mileage),
                        "fuel_type": fuel,
                        "transmission": trans,
                        "location": loc,
                        "listing_url": listing.get('webPage', url),
                        "posted_date": "N/A"
                    }
                    self.parse_listing(data)
                except Exception as e:
                    logger.debug(f"Row parse error on NEXT_DATA: {e}", extra={'site': self.site_name})
                
                
            current_page += 1
            
        logger.info(f"Scraper completed. Extracted {len(self.listings)} total listings.", extra={'site': self.site_name})
        self.save_data()
        self.close_session()
