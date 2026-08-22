"""The scrape stage: runs every site scraper enabled in config.json.

Which makes/models get collected is config, not code — see the "targets" list
there. This module is a stage, not an entry point: drive it from the project
root with `python main.py scrape` (add `--site cardoen` for a single site).
"""

import json
import os

from scrapers.autoscout_scraper import AutoScoutScraper
from scrapers.cardoen_scraper import CardoenScraper
from utils.logger import logger

# Site key -> scraper class. Add a site here once and it is selectable from the
# command line and from config.json's "sites" list.
SCRAPERS = {
    "autoscout": AutoScoutScraper,
    "cardoen": CardoenScraper,
}

# Sites run when config.json says nothing. Cardoen is off by default: it has no
# target filtering, so it sweeps the whole stock list.
DEFAULT_SITES = ["autoscout"]


def resolve_sites(explicit=None):
    """Sites to run: what was asked for, else config.json's "sites", else the default."""
    if explicit:
        return explicit
    try:
        with open("config.json", encoding="utf-8") as f:
            return json.load(f).get("sites") or DEFAULT_SITES
    except Exception:
        return DEFAULT_SITES


def run(sites=None):
    logger.info("Initializing car listings scraper pipeline...", extra={'site': 'SYSTEM'})
    # utils.logger already creates logs/ on import; the scrapers need this one.
    os.makedirs("data/raw", exist_ok=True)

    for key in sites or DEFAULT_SITES:
        scraper_cls = SCRAPERS.get(key)
        if not scraper_cls:
            logger.error(f"Unknown site '{key}'. Known sites: {', '.join(SCRAPERS)}",
                         extra={'site': 'SYSTEM'})
            continue

        scraper = scraper_cls()
        try:
            logger.info(f"Executing {scraper.site_name} scraper...", extra={'site': 'SYSTEM'})
            scraper.run()
        except Exception as e:
            logger.error(f"Critical error executing {scraper.site_name}: {e}",
                         extra={'site': scraper.site_name})
