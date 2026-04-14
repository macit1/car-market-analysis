import json
from scrapers.base_scraper import BaseScraper
from utils.logger import logger

class CardoenScraper(BaseScraper):
    def __init__(self):
        super().__init__(site_name="cardoen", base_url="https://www.cardoen.be/fr/achat")
        
        # Re-construct base URL dynamically after config is loaded
        if self.make:
            self.base_url = f"{self.base_url}/{self.make}"
            if self.model:
                self.base_url = f"{self.base_url}/{self.model}"
        self.base_url = f"{self.base_url}/offres/"

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
                
            # Step 1: Extract detail URLs from list page
            links = soup.find_all('a', href=True)
            detail_urls = []
            seen = set()
            for a in links:
                href = a['href']
                if '/fr/auto/' in href and 'vehicleId=' in href and href not in seen:
                    seen.add(href)
                    full_url = f"https://www.cardoen.be{href}" if href.startswith('/') else href
                    detail_urls.append(full_url)
            
            if not detail_urls:
                logger.info("No detail links found on this page. Reached end of results.", extra={'site': self.site_name})
                break
                
            # Step 2: Crawl Detail Pages
            for url in detail_urls:
                if len(self.listings) >= self.target_limit:
                    break
                    
                logger.debug(f"Fetching detail page: {url}", extra={'site': self.site_name})
                detail_soup = self.get_page(url)
                if not detail_soup:
                    continue
                    
                # Step 3: Extract JSON-LD @type=Car
                ld_scripts = detail_soup.find_all('script', type='application/ld+json')
                car_data = None
                for script in ld_scripts:
                    if script.string:
                        try:
                            d = json.loads(script.string)
                            if d.get('@type') == 'Car':
                                car_data = d
                                break
                        except:
                            pass
                
                if not car_data:
                    logger.warning(f"Skipped {url} - No JSON-LD Car data found.", extra={'site': self.site_name})
                    continue
                
                # Check availability
                offers = car_data.get('offers', {})
                availability = offers.get('availability', '')
                if 'InStock' not in str(availability):
                    logger.info(f"Skipped {url} - Not in stock ({availability}).", extra={'site': self.site_name})
                    continue
                
                try:
                    make = car_data.get('brand', {}).get('name', 'Unknown')
                    model = car_data.get('model', 'Unknown')
                    
                    prod_date = car_data.get('dateVehicleFirstRegistered', '') or car_data.get('productionDate', '')
                    year = 0
                    if prod_date:
                        date_str = prod_date.split('T')[0]  # Handle "2023-09-28T00:00:00"
                        if '-' in date_str:
                            year = int(date_str.split('-')[0])
                    
                    price = offers.get('price', 0)
                    
                    mileage_obj = car_data.get('mileageFromOdometer', {})
                    mileage = mileage_obj.get('value', 0) if isinstance(mileage_obj, dict) else 0
                    
                    fuel = car_data.get('fuelType', 'Unknown')
                    
                    trans_obj = car_data.get('vehicleTransmission', {})
                    trans = trans_obj.get('name', 'Unknown') if isinstance(trans_obj, dict) else str(trans_obj)
                    
                    engine = car_data.get('vehicleEngine', {})
                    hp_obj = engine.get('enginePower', {}) if isinstance(engine, dict) else {}
                    hp = hp_obj.get('value', None) if isinstance(hp_obj, dict) else None
                    
                    doors = car_data.get('numberOfDoors', None)
                    
                    condition_raw = car_data.get('itemCondition', [])
                    condition = 'Used'
                    if isinstance(condition_raw, list):
                        condition = 'New' if any('New' in str(c) for c in condition_raw) else 'Used'
                    elif 'New' in str(condition_raw):
                        condition = 'New'
                    
                    data = {
                        "make": make,
                        "model": model,
                        "year": year,
                        "price": str(price),
                        "mileage": str(mileage),
                        "fuel_type": fuel,
                        "transmission": trans,
                        "location": "Cardoen Belgium",
                        "listing_url": url,
                        "posted_date": "N/A",
                        "body_type": None,
                        "dealer_or_private": "Dealer",
                        "doors": doors,
                        "horsepower": hp,
                        "first_registration": prod_date,
                        "condition": condition,
                    }
                    self.parse_listing(data)
                except Exception as e:
                    logger.debug(f"Row parse error on JSON-LD: {e}", extra={'site': self.site_name})
                
            current_page += 1
            
        logger.info(f"Scraper completed. Extracted {len(self.listings)} total listings.", extra={'site': self.site_name})
        self.save_data()
        self.close_session()
