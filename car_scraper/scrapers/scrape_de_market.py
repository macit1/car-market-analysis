"""Market-wide sweep of a single country, with brand-exclude filtering.

Where AutoScoutScraper crawls a named make/model, this one sweeps *every* make
on the market except a configured exclude list. The portal has no native
"exclude brands" filter, so the make taxonomy is fetched (or read from
``makes_de.txt``) and each remaining make is queried on its own id.

Result pages are read through the shared ``search`` helpers on AutoScoutScraper
— page fetching, JSON extraction and horsepower parsing all come from there.
What stays local is the make discovery, the exclude list and the narrower
seven-column output, which the dashboard reads by filename prefix.

Filters, exclude list and output name live in ``config_de_market.json``.

Run:
    cd car_scraper
    python -m scrapers.scrape_de_market
"""

import csv
import json
import os
import re
from datetime import datetime

from scrapers.autoscout_scraper import AutoScoutScraper, DOMAINS
from utils.logger import logger

BASE = f"{DOMAINS['de'][0]}{DOMAINS['de'][1]}"
COUNTRY_CODE = {"germany": "D", "belgium": "B"}


class GermanMarketScraper(AutoScoutScraper):
    def __init__(self, config_path: str = "config_de_market.json"):
        super().__init__(config_path=config_path, site_name="autoscout_de")

        cfg = self.config
        f_ = cfg.get("filters", {})
        self.price_from = f_.get("price_from", 17000)
        self.price_to = f_.get("price_to", 23000)
        self.mileage_to = f_.get("mileage_to", 150000)
        self.year_min = f_.get("year_min")  # min first-registration year, e.g. 2016
        self.country = COUNTRY_CODE.get(cfg.get("country", "germany"), "D")
        self.exclude = {m.strip().lower() for m in cfg.get("exclude_makes", [])}
        self.max_pages = cfg.get("max_pages_per_make", 200)
        self.save_every = cfg.get("save_every", 500)
        self._last_saved = 0
        self.segment_big = cfg.get("segment_big_makes_by_year", True)
        self.year_from = cfg.get("year_segment_from", 2026)
        self.year_to = cfg.get("year_segment_to", 2005)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = cfg.get("output_basename", "autoscout_de_market")
        self.csv_file = f"data/raw/{base}_{ts}.csv"
        self.json_file = f"data/raw/{base}_{ts}.json"
        self.rows = []  # list of dicts (our 7-column schema)

    # ---- URL building -------------------------------------------------------

    def _common_params(self):
        return (
            f"pricefrom={self.price_from}&priceto={self.price_to}"
            f"&kmto={self.mileage_to}&cy={self.country}&sort=age&desc=1"
        )

    def make_url(self, make_id, page, year=None):
        url = f"{BASE}?{self._common_params()}&mmvmk0={make_id}&page={page}"
        if year is not None:
            # year-segment query overrides the global year_min floor
            url += f"&fregfrom={year}&fregto={year}"
        elif self.year_min:
            url += f"&fregfrom={self.year_min}"
        return url

    # ---- Parsing ------------------------------------------------------------

    def _market_row(self, item):
        """Map one result item onto this scraper's narrower output schema.

        Deliberately not the shared CarListing row: the market sweep keeps only
        the seven comparison columns, and skips rows missing a price or year
        rather than substituting defaults.
        """
        v = item.get("vehicle", {}) or {}
        tr = item.get("tracking", {}) or {}

        make = (v.get("make") or "").strip()
        # model can be null in the source data → fall back to modelGroup / variant
        model = (v.get("model") or v.get("modelGroup") or v.get("variant") or "").strip()
        if not make or not model:
            return None

        # year from "MM-YYYY" tracking.firstRegistration
        year = 0
        m = re.search(r"(\d{4})", tr.get("firstRegistration", ""))
        if m:
            year = int(m.group(1))

        try:
            price = int(tr.get("price") or 0)
        except (TypeError, ValueError):
            price = 0
        try:
            mileage = int(tr.get("mileage") or 0)
        except (TypeError, ValueError):
            mileage = 0

        url = item.get("url", "")
        if url and url.startswith("/"):
            url = DOMAINS["de"][0] + url

        if not price or not year:
            return None
        if self.year_min and year < self.year_min:
            return None

        return {
            "make": make,
            "model": model,
            "year": year,
            "price": price,
            "mileage": mileage,
            "fuel_type": v.get("fuel", "") or "Unknown",
            "horsepower": self._hp_from_details(item.get("vehicleDetails")) or 0,
            "listing_url": url,
        }

    # ---- Make discovery -----------------------------------------------------

    def load_makes_from_file(self, path="makes_de.txt"):
        """Return [(make_id, label), ...] from an editable list file (skips # lines)."""
        if not os.path.exists(path):
            return None
        out = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t") if "\t" in line else line.split(None, 1)
                if len(parts) < 2:
                    continue
                try:
                    out.append((int(parts[0]), parts[1].strip()))
                except ValueError:
                    continue
        logger.info(f"Loaded {len(out)} makes from {path}.", extra={"site": self.site_name})
        return out

    def fetch_all_makes(self):
        """Use the editable makes_de.txt if present; otherwise pull the full
        taxonomy and drop the configured exclude list."""
        from_file = self.load_makes_from_file()
        if from_file:
            return from_file

        nd = self._next_data(self.get_page(f"{BASE}?{self._common_params()}&page=1"))
        if not nd:
            logger.error("Could not load taxonomy to discover makes.", extra={"site": self.site_name})
            return []
        tax = nd.get("props", {}).get("pageProps", {}).get("taxonomy", {})
        makes_sorted = tax.get("makesSorted", [])
        result = []
        for m in makes_sorted:
            label = m.get("label", "")
            mid = m.get("value")
            if label.lower() in self.exclude or mid is None:
                continue
            result.append((mid, label))
        logger.info(
            f"Discovered {len(makes_sorted)} makes, {len(result)} after excluding "
            f"{sorted(self.exclude)}.",
            extra={"site": self.site_name},
        )
        return result

    # ---- Crawl one query (paginated) ---------------------------------------

    def crawl_query(self, make_id, label, year=None):
        """Paginate a single make (optionally year-segmented). Returns count added."""
        added = 0
        page = 1
        while page <= self.max_pages:
            nd = self._next_data(self.get_page(self.make_url(make_id, page, year)))
            if not nd:
                break
            pp = nd.get("props", {}).get("pageProps", {})
            listings = pp.get("listings", [])
            if not listings:
                break
            if page == 1:
                seg = f" [{year}]" if year else ""
                logger.info(
                    f"{label}{seg}: {pp.get('numberOfResults', 0)} results, "
                    f"{min(pp.get('numberOfPages', 0), self.max_pages)} pages to crawl.",
                    extra={"site": self.site_name},
                )
            for item in listings:
                row = self._market_row(item)
                if not row:
                    continue
                key = row["listing_url"] or f"{row['make']}-{row['model']}-{row['price']}-{row['mileage']}"
                if key in self.seen_urls:
                    continue
                self.seen_urls.add(key)
                self.rows.append(row)
                added += 1
                if len(self.rows) - self._last_saved >= self.save_every:
                    self.save()
                    self._last_saved = len(self.rows)
            page += 1
        return added

    def crawl_make(self, make_id, label):
        # Probe page 1 to decide whether year-segmentation is needed.
        nd = self._next_data(self.get_page(self.make_url(make_id, 1)))
        if not nd:
            return 0
        total = nd.get("props", {}).get("pageProps", {}).get("numberOfResults", 0)
        cap = self.max_pages * 20

        if self.segment_big and total > cap:
            logger.info(
                f"{label}: {total} > {cap} cap → segmenting by year "
                f"({self.year_from}..{self.year_to}).",
                extra={"site": self.site_name},
            )
            added = 0
            for year in range(self.year_from, self.year_to - 1, -1):
                added += self.crawl_query(make_id, label, year=year)
            return added
        return self.crawl_query(make_id, label)

    # ---- Output -------------------------------------------------------------

    def save(self):
        os.makedirs("data/raw", exist_ok=True)
        cols = ["make", "model", "year", "price", "mileage", "fuel_type", "horsepower", "listing_url"]
        with open(self.csv_file, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(self.rows)
        with open(self.json_file, "w", encoding="utf-8") as f:
            json.dump(self.rows, f, ensure_ascii=False, indent=1)
        logger.info(
            f"Saved {len(self.rows)} listings → {self.csv_file} (+ .json)",
            extra={"site": self.site_name},
        )

    # ---- Entry point --------------------------------------------------------

    def run(self):
        self.start_session()
        logger.info(
            f"=== Market-wide scrape | price {self.price_from}-{self.price_to}€ "
            f"| max {self.mileage_to} km ===",
            extra={"site": self.site_name},
        )
        makes = self.fetch_all_makes()
        for i, (mid, label) in enumerate(makes, 1):
            logger.info(f"--- [{i}/{len(makes)}] {label} (id={mid}) ---", extra={"site": self.site_name})
            try:
                n = self.crawl_make(mid, label)
                logger.info(f"{label} complete: +{n} listings (running total {len(self.rows)}).",
                            extra={"site": self.site_name})
            except Exception as e:
                logger.error(f"{label} failed: {e}", extra={"site": self.site_name})
            self.save()  # incremental safety save

        logger.info(f"DONE. Total unique listings: {len(self.rows)}.", extra={"site": self.site_name})
        self.save()
        self.close_session()


if __name__ == "__main__":
    GermanMarketScraper().run()
