"""Scraper for one of the large pan-European classifieds portals.

Every target is described in ``config.json``; there is no per-model script.
Two crawl strategies are available, chosen per target with ``"strategy"``:

``detail``  Walk the result pages, collect the ad ids, then open every ad and
            read its embedded ``__NEXT_DATA__`` payload. Slow (one request per
            listing) but returns every field the schema has.

``search``  Read the listings straight out of the result page's own
            ``__NEXT_DATA__`` payload. Roughly 20x fewer requests; use it
            whenever the fields it exposes are enough.

Both strategies can be segmented by first-registration year, which is how a
query larger than the site's pagination cap (200 pages) is recovered.
"""

import csv
import json
import re
import time
from datetime import datetime

from scrapers.base_scraper import BaseScraper
from utils.logger import logger

# Country code -> (site root, listing path prefix, single-ad path prefix).
# Only the Belgian ad path is verified against the live site; the detail
# strategy has never been run against the German one.
DOMAINS = {
    "be": ("https://www.autoscout24.be", "/fr/lst", "/fr/offres/--"),
    "de": ("https://www.autoscout24.de", "/lst", "/angebote/--"),
}
COUNTRY_PARAM = {"be": "B", "de": "D"}

# The site stops paginating after this many pages, ~20 listings each.
MAX_PAGES = 200

# Offer-type codes -> readable condition (also flags brand-new stock).
OFFER_TYPES = {"U": "Used", "N": "New", "D": "Demo", "J": "Nearly new", "O": "Oldtimer"}

# A dropped connection shouldn't end a long run: wait these intervals and retry
# the page before giving up (get_page() burns its own 3 fast retries first).
OUTAGE_WAITS = [60, 120, 300, 600]


class AutoScoutScraper(BaseScraper):
    def __init__(self, config_path: str = "config.json", site_name: str = "autoscout24"):
        super().__init__(
            site_name=site_name,
            base_url="https://www.autoscout24.be/fr/lst",
            config_path=config_path,
        )
        self.skipped_by_variant = 0

    # ---- URL building ------------------------------------------------------

    @staticmethod
    def _domain(target):
        return DOMAINS.get(str(target.get("country", "be")).lower(), DOMAINS["be"])

    def list_url(self, target, page, year=None):
        """Result-page URL for one target, optionally pinned to a single year."""
        root, prefix, _ = self._domain(target)
        country = str(target.get("country", "be")).lower()
        path = f"{root}{prefix}/{target['make']}/{target['model']}"
        if target.get("category"):
            path += f"/c/{target['category']}"

        params = [f"page={page}"]
        if target.get("strategy", "detail") == "search":
            params = [f"atype=C", f"cy={COUNTRY_PARAM.get(country, 'B')}", "sort=age", "desc=1"] + params
            if target.get("body"):
                params.insert(2, f"body={target['body']}")
        if year is not None:
            params.append(f"fregfrom={year}&fregto={year}")
        return f"{path}?{'&'.join(params)}"

    # ---- Shared parsing helpers -------------------------------------------

    @staticmethod
    def _next_data(soup):
        """The page's embedded JSON state, or None if it isn't there."""
        if not soup:
            return None
        tag = soup.find("script", id="__NEXT_DATA__")
        if not tag or not tag.string:
            return None
        try:
            return json.loads(tag.string)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _hp_from_details(vehicle_details):
        """Pull PS out of the speedometer detail, e.g. '140 kW (190 PS)'."""
        for d in vehicle_details or []:
            if d.get("iconName") == "speedometer":
                m = re.search(r"\(?(\d+)\s*PS", d.get("data", "") or "")
                if m:
                    return int(m.group(1))
        return None

    def _row_from_detail_page(self, detail_soup, url):
        """Map one ad's detail payload onto the CarListing schema. None = skip."""
        nd = self._next_data(detail_soup)
        if not nd:
            return None
        listing = nd.get("props", {}).get("pageProps", {}).get("listingDetails", {})
        if not listing or listing.get("status", "Active") != "Active":
            return None

        vehicle = listing.get("vehicle", {})
        make = vehicle.get("make", "Unknown")
        model = vehicle.get("model", "Unknown")

        year_raw = vehicle.get("firstRegistrationDateRaw", "")
        year = int(year_raw.split("-")[0]) if year_raw and "-" in year_raw else 0

        price = listing.get("prices", {}).get("public", {}).get("priceRaw", 0)
        if not price:
            price = listing.get("prices", {}).get("dealer", {}).get("priceRaw", 0)

        loc_data = listing.get("location", {})
        loc = f"{loc_data.get('zip', '')} {loc_data.get('city', '')}".strip() or "Unknown"

        # Full raw ad title (make + variant + version), often carries extra
        # info (trim, options) not present in any other structured field.
        title = listing.get("imgAltText") or " ".join(
            filter(None, [make, vehicle.get("variant"), vehicle.get("modelVersionInput")])
        )

        return {
            "make": make,
            "model": model,
            "year": year,
            "price": str(price),
            "mileage": str(vehicle.get("mileageInKmRaw", 0)),
            "fuel_type": vehicle.get("fuelCategory", {}).get("formatted", "Unknown"),
            "transmission": vehicle.get("transmissionType", "Unknown"),
            "location": loc,
            "listing_url": listing.get("webPage", url),
            "posted_date": "N/A",
            "title": title,
            "horsepower": vehicle.get("rawPowerInHp") or 0,
        }

    def _row_from_search_item(self, item, target):
        """Map one result-page item onto the CarListing schema. None = skip."""
        root, _, _ = self._domain(target)
        v = item.get("vehicle") or {}
        tr = item.get("tracking") or {}

        variant = (v.get("variant") or "").strip()
        version = (v.get("modelVersionInput") or "").strip()

        # Optional body-style guard: some result sets mix neighbouring variants
        # (e.g. a long-wheelbase car filed under the same body code).
        keep_variant = target.get("variant")
        if keep_variant and variant and variant.lower() != keep_variant.lower():
            self.skipped_by_variant += 1
            return None
        reject = target.get("reject_title")
        if reject and re.search(reject, f"{variant} {version}", re.IGNORECASE):
            self.skipped_by_variant += 1
            return None

        # Brand-new, never-registered cars report firstRegistration == "new" and
        # have no year at all. Rather than drop them (CarListing requires a real
        # year), stamp them with the current year and mark condition, so they
        # stay filterable instead of silently vanishing from the dataset.
        first_reg = (tr.get("firstRegistration") or "").strip()
        condition = OFFER_TYPES.get(v.get("offerType"), "Unknown")
        year = 0
        m = re.search(r"(\d{4})", first_reg)
        if m:
            year = int(m.group(1))
        elif first_reg.lower() == "new":
            year = datetime.now().year
            condition = "New (unregistered)"

        loc = item.get("location") or {}
        location = " ".join(filter(None, [loc.get("zip"), loc.get("city")])).strip() or "Unknown"

        url = item.get("url") or ""
        if url.startswith("/"):
            url = root + url

        # A few ads carry a non-numeric mileage ("unknown"); treat as 0 km
        # rather than letting the row fail validation and drop out.
        mileage = str(tr.get("mileage") or 0)
        if not mileage.isdigit():
            mileage = "0"

        return {
            "make": v.get("make") or "Unknown",
            "model": v.get("model") or v.get("modelGroup") or "Unknown",
            "year": year,
            "price": str((item.get("price") or {}).get("priceRaw") or tr.get("price") or 0),
            "mileage": mileage,
            "fuel_type": v.get("fuel") or "Unknown",
            "transmission": v.get("transmission") or "Unknown",
            "location": location,
            "listing_url": url,
            "posted_date": "N/A",
            # Full raw ad headline — carries trim/equipment info the structured
            # fields don't (kept raw as its own column, not parsed).
            "title": " ".join(filter(None, [v.get("make"), v.get("model"), version])).strip(),
            "body_type": variant or target.get("variant"),
            "horsepower": self._hp_from_details(item.get("vehicleDetails")),
            "condition": condition,
            "first_registration": first_reg or "N/A",
        }

    # ---- Fetching ----------------------------------------------------------

    def fetch_search_page(self, target, page, year=None):
        """get_page() plus a slow-retry ladder, so a dropped connection pauses
        a long run instead of ending it. Returns the parsed page state."""
        for attempt, wait in enumerate([0] + OUTAGE_WAITS):
            if wait:
                logger.warning(
                    f"Page {page} unreachable — waiting {wait}s for the connection to come back "
                    f"(outage retry {attempt}/{len(OUTAGE_WAITS)}).",
                    extra={'site': self.site_name})
                time.sleep(wait)
            nd = self._next_data(self.get_page(self.list_url(target, page, year)))
            if nd:
                if wait:
                    logger.info(f"Connection recovered, resuming at page {page}.",
                                extra={'site': self.site_name})
                return nd
        return None

    def _seed_dedup_from(self, resume_file):
        """Append to an interrupted run's CSV and re-seed the dedup set from it,
        so overlapping pages don't produce duplicate rows."""
        self.current_export_file = resume_file
        with open(resume_file, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("listing_url"):
                    self.seen_urls.add(row["listing_url"])
        logger.info(f"Resuming into {resume_file} — {len(self.seen_urls)} existing listings "
                    f"loaded for deduplication.", extra={'site': self.site_name})

    # ---- Crawl strategies --------------------------------------------------

    def crawl_detail(self, target, limit, year=None):
        """Walk result pages, then open each ad for the full field set."""
        label = f"{target['make']}/{target['model']}" + (f" [{year}]" if year else "")
        extracted = 0
        page = 1
        max_pages = target.get("max_pages", MAX_PAGES)

        while extracted < limit and page <= max_pages:
            soup = self.get_page(self.list_url(target, page, year))
            if not soup:
                logger.warning(f"[{label}] Failed to retrieve page {page}. Stopping target.",
                               extra={'site': self.site_name})
                break

            if page == 1:
                h1 = soup.find("h1")
                if h1:
                    digits = re.findall(r"\d+", h1.text.replace(" ", "").replace("\xa0", ""))
                    if digits:
                        logger.info(f"[{label}] \033[96m>>> Total listings found in filter: "
                                    f"{''.join(digits)} <<<\033[0m", extra={'site': self.site_name})

            logger.info(f"[{label}] Loading Page {page}...", extra={'site': self.site_name})

            detail_urls = []
            root, _, offer_path = self._domain(target)
            for art in soup.find_all("article"):
                guid = art.get("data-guid")
                if guid:
                    detail_urls.append(f"{root}{offer_path}{guid}")

            if not detail_urls:
                logger.info(f"[{label}] No articles found. Reached end of results.",
                            extra={'site': self.site_name})
                break

            for url in detail_urls:
                if extracted >= limit:
                    break
                logger.debug(f"Fetching detail page: {url}", extra={'site': self.site_name})
                detail_soup = self.get_page(url)
                if not detail_soup:
                    continue
                try:
                    row = self._row_from_detail_page(detail_soup, url)
                except Exception as e:
                    logger.debug(f"Row parse error on detail page: {e}", extra={'site': self.site_name})
                    continue
                if row and self.parse_listing(row):
                    extracted += 1

            page += 1

        return extracted

    def crawl_search(self, target, limit, year=None):
        """Read listings straight out of the result page state."""
        label = f"{target['make']}/{target['model']}" + (f" [{year}]" if year else "")
        max_pages = min(target.get("max_pages", MAX_PAGES), MAX_PAGES)
        extracted = 0
        page = target.get("start_page", 1)
        first_page = True

        while page <= max_pages and extracted < limit:
            nd = self.fetch_search_page(target, page, year)
            if not nd:
                logger.error(f"[{label}] Page {page} still unreachable after all retries. "
                             f"Stopping. Resume by setting \"start_page\": {page} and "
                             f"\"resume_file\": \"{self.current_export_file}\" on this target.",
                             extra={'site': self.site_name})
                break

            pp = nd.get("props", {}).get("pageProps", {})
            listings = pp.get("listings", [])

            if first_page:
                first_page = False
                total = pp.get("numberOfResults", 0)
                pages = min(pp.get("numberOfPages", 0), max_pages)
                logger.info(f"[{label}] \033[96m>>> {total} listings found, crawling {pages} "
                            f"pages <<<\033[0m", extra={'site': self.site_name})
                if total > MAX_PAGES * 20:
                    logger.warning(f"[{label}] {total} exceeds the {MAX_PAGES * 20} pagination cap — "
                                   f"results will be truncated; segment the query by year to get "
                                   f"the rest.", extra={'site': self.site_name})

            if not listings:
                logger.info(f"[{label}] No listings on page {page}. Reached end of results.",
                            extra={'site': self.site_name})
                break

            for item in listings:
                if extracted >= limit:
                    break
                row = self._row_from_search_item(item, target)
                if row and self.parse_listing(row):
                    extracted += 1

            logger.info(f"[{label}] Page {page}/{max_pages} done — running total {extracted}.",
                        extra={'site': self.site_name})

            # Flush to disk every 10 pages so a mid-run block doesn't lose work.
            if page % 10 == 0:
                self.save_data()

            page += 1

        return extracted

    # ---- Entry point -------------------------------------------------------

    def run(self):
        self.start_session()

        for target in self.targets:
            if not target.get("enabled", True):
                logger.debug(f"Target disabled, skipping: {target.get('make')}/{target.get('model')}",
                             extra={'site': self.site_name})
                continue
            if not target.get("make") or not target.get("model"):
                logger.warning(f"Skipping target without make/model: {target}",
                               extra={'site': self.site_name})
                continue

            strategy = target.get("strategy", "detail")
            crawl = self.crawl_search if strategy == "search" else self.crawl_detail
            limit = target.get("limit", self.target_limit)

            # Targets that name their own output keep their CSV prefix stable,
            # which is what the dashboard matches files on.
            if target.get("resume_file"):
                self._seed_dedup_from(target["resume_file"])
            elif target.get("output_basename"):
                self.set_export_file(target["output_basename"])

            logger.info(f"--- Target: {target['make'].upper()} {target['model'].upper()} "
                        f"({target.get('country', 'be').upper()}, {strategy}) ---",
                        extra={'site': self.site_name})

            if target.get("segment_by_year"):
                year_from = target.get("year_from", datetime.now().year)
                year_to = target.get("year_to", year_from - 10)
                logger.info(f"Strategy: year segmentation ({year_from} down to {year_to})",
                            extra={'site': self.site_name})
                total = 0
                for year in range(year_from, year_to - 1, -1):
                    total += crawl(target, limit - total, year=year)
                    self.save_data()  # save after each year segment
                    if total >= limit:
                        logger.info(f"Reached limit of {limit}. Stopping target.",
                                    extra={'site': self.site_name})
                        break
            else:
                total = crawl(target, limit)

            logger.info(f"[{target['make']}/{target['model']}] Complete. Total: {total} items.",
                        extra={'site': self.site_name})
            # Incremental save per target (precautionary save)
            self.save_data()

        if self.skipped_by_variant:
            logger.info(f"{self.skipped_by_variant} listings skipped by variant/title filters.",
                        extra={'site': self.site_name})
        self.close_session()
