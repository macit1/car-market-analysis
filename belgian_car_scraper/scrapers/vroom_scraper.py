import json
from scrapers.base_scraper import BaseScraper
from utils.logger import logger

class VroomScraper(BaseScraper):
    def __init__(self):
        super().__init__(site_name="vroom", base_url="https://www.vroom.be/fr/voitures-occasion")
        
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
                a = art.find('a')
                if a and a.get('href'):
                    href = a.get('href')
                    full_url = f"https://www.vroom.be{href}" if href.startswith('/') else href
                    detail_urls.append(full_url)
            
            # Step 2: Crawl Detail Pages
            for url in detail_urls:
                if len(self.listings) >= self.target_limit:
                    break
                    
                logger.debug(f"Fetching detail page: {url}", extra={'site': self.site_name})
                detail_soup = self.get_page(url)
                if not detail_soup:
                    continue
                    
                # Step 3: Extract JSON-LD
                scripts = detail_soup.find_all('script', type='application/ld+json')
                ld_data = None
                for script in scripts:
                    if script.string and '"offers"' in script.string and '"itemOffered"' in script.string:
                        try:
                            ld_data = json.loads(script.string)
                            break
                        except:
                            pass
                
                if not ld_data or 'offers' not in ld_data:
                    logger.warning(f"Skipped {url} - No JSON-LD offers data found (likely Sold/404).", extra={'site': self.site_name})
                    continue
                    
                offers = ld_data['offers']
                item = offers.get('itemOffered', {})
                
                # Check Availability
                availability = offers.get('availability', '')
                if 'InStock' not in str(availability):
                    logger.info(f"Skipped {url} - Car is marked as not in stock ({availability}).", extra={'site': self.site_name})
                    continue
                    
                # Safe JSON Extraction
                try:
                    make = ld_data.get('brand', {}).get('name', item.get('manufacturer', 'Unknown'))
                    model = item.get('model', 'Unknown')
                    
                    prod_date = item.get('productionDate', '')
                    year = int(prod_date.split('-')[0]) if prod_date and '-' in prod_date else 0
                    
                    price = offers.get('price', 0)
                    mileage = item.get('mileageFromOdometer', {}).get('value', 0)
                    
                    engines = item.get('vehicleEngine', [])
                    fuel = engines[0].get('fuelType', 'Unknown') if engines and isinstance(engines, list) else 'Unknown'
                    
                    trans = item.get('vehicleTransmission', 'Unknown')
                    
                    dealer = offers.get('offeredBy', {})
                    loc_addr = dealer.get('address', {})
                    loc = f"{loc_addr.get('postalCode', '')} {loc_addr.get('addressLocality', '')}".strip()
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
                        "listing_url": url,
                        "posted_date": "N/A"
                    }
                    self.parse_listing(data)
                except Exception as e:
                    logger.debug(f"Row parse error on JSON-LD: {e}", extra={'site': self.site_name})
                
            current_page += 1
            
        logger.info(f"Scraper completed. Extracted {len(self.listings)} total listings.", extra={'site': self.site_name})
        self.save_data()
        self.close_session()
