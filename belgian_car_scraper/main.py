import sys
import os
from scrapers.autoscout_scraper import AutoScoutScraper
from scrapers.cardoen_scraper import CardoenScraper
from utils.logger import logger

def main():
    logger.info("Initializing Belgian Car Listings Scraper Pipeline...", extra={'site': 'SYSTEM'})
    
    # Instantiate scrapers
    scrapers = [
        AutoScoutScraper(),
        CardoenScraper()
    ]
    
    for scraper in scrapers:
        try:
            logger.info(f"Executing {scraper.site_name} scraper...", extra={'site': 'SYSTEM'})
            scraper.run()
        except Exception as e:
            logger.error(f"Critical error executing {scraper.site_name}: {e}", extra={'site': scraper.site_name})

if __name__ == "__main__":
    # Ensure logs/raw directories exist just in case
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data/raw", exist_ok=True)
    main()
