from scrapers.base_scraper import BaseScraper
from utils.logger import logger

class TwoDehandsScraper(BaseScraper):
    def __init__(self):
        super().__init__(site_name="2dehands", base_url="https://www.2dehands.be/l/autos/")
        
    def run(self):
        self.start_session()
        current_url = self.base_url
        current_page = 1
        
        while len(self.listings) < 100:
            logger.info(f"Loading Page {current_page}...", extra={'site': self.site_name})
            soup = self.get_page(current_url)
            
            if not soup:
                logger.warning(f"Failed to retrieve soup for {current_url}. Stopping.", extra={'site': self.site_name})
                break
                
            # TODO: Add soup.find_all logic here and populate `data` dict
            # data = {"make": "Toyota", "model": "Corolla", "price": "€ 15.000", ...}
            # self.parse_listing(data)
            
            # TODO: Next page pagination logic
            # Handle stop condition if no Next button exists.
            
            break # Skeleton break
            
        logger.info(f"Scraper completed. Extracted {len(self.listings)} total listings.", extra={'site': self.site_name})
        self.save_data()
        self.close_session()
