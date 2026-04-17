import json
from scrapers.base_scraper import BaseScraper
from utils.logger import logger

class AutoScoutScraper(BaseScraper):
    def __init__(self):
        super().__init__(site_name="autoscout24", base_url="https://www.autoscout24.be/fr/lst")
        
        # Re-construct base URL dynamically after config is loaded
        # URL is constructed dynamically in run() for multiple targets
    def run(self):
        self.start_session()
        
        for target in self.targets:
            make_slug = target.get('make', '')
            model_slug = target.get('model', '')
            if not make_slug or not model_slug:
                continue
                
            target_base_url = f"https://www.autoscout24.be/fr/lst/{make_slug}/{model_slug}/c/suv-pick-up"
            logger.info(f"--- Starting Extraction Target: {make_slug.upper()} {model_slug.upper()} ---", extra={'site': self.site_name})
            
            current_page = 1
            target_extracted = 0
            
            while target_extracted < self.target_limit:
                current_url = f"{target_base_url}?page={current_page}"
                soup = self.get_page(current_url)
                
                if current_page == 1 and soup:
                    h1 = soup.find('h1')
                    if h1:
                        import re
                        h1_text = h1.text.replace('\u202f', '').replace('\xa0', '')
                        digits = re.findall(r'\d+', h1_text)
                        if digits:
                            total_found = "".join(digits)
                            # Log with blue ansi color for the total number
                            logger.info(f"[{make_slug}/{model_slug}] \033[96m>>> Total listings found in filter: {total_found} <<<\033[0m", extra={'site': self.site_name})
                
                logger.info(f"[{make_slug}/{model_slug}] Loading Page {current_page}...", extra={'site': self.site_name})
                
                if not soup:
                    logger.warning(f"Failed to retrieve soup for {current_url}. Stopping target.", extra={'site': self.site_name})
                    break
                    
                articles = soup.find_all('article')
                if not articles:
                    logger.info(f"[{make_slug}/{model_slug}] No articles found. Reached end of results.", extra={'site': self.site_name})
                    break
                    
                # Step 1: Extract URLs
                detail_urls = []
                for art in articles:
                    guid = art.get('data-guid')
                    if guid:
                        detail_urls.append(f"https://www.autoscout24.be/fr/offres/--{guid}")
                
                # Step 2: Crawl Detail Pages
                for url in detail_urls:
                    if target_extracted >= self.target_limit:
                        break
                        
                    logger.debug(f"Fetching detail page: {url}", extra={'site': self.site_name})
                    detail_soup = self.get_page(url)
                    if not detail_soup:
                        continue
                        
                    # Step 3: Extract from __NEXT_DATA__
                    next_data_script = detail_soup.find('script', id='__NEXT_DATA__')
                    if not next_data_script or not next_data_script.string:
                        continue
                        
                    try:
                        nd = json.loads(next_data_script.string)
                        listing = nd.get('props', {}).get('pageProps', {}).get('listingDetails', {})
                        if not listing:
                            continue
                            
                        vehicle = listing.get('vehicle', {})
                        
                        status = listing.get('status', 'Active')
                        if status != 'Active':
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
                        
                        if self.parse_listing(data):
                            target_extracted += 1
                            
                    except Exception as e:
                        logger.debug(f"Row parse error on NEXT_DATA: {e}", extra={'site': self.site_name})
                    
                current_page += 1
            
            logger.info(f"[{make_slug}/{model_slug}] Complete. Total: {target_extracted} items.", extra={'site': self.site_name})
            # Incremental save per target (Precautionary Save)
            self.save_data()
                
        logger.info(f"All targets completed. Total aggregated listings: {len(self.listings)}.", extra={'site': self.site_name})
        self.save_data()
        self.close_session()
