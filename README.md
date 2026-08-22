# 🚗 Used Car Market Analysis — Data Pipeline

An end-to-end project that **scrapes**, **cleans**, and **visualises** used car listings from public classifieds sites: a configurable Python scraping pipeline feeding a single-file interactive dashboard.

**What gets collected is configuration, not code** — makes, models, country and crawl strategy all live in `car_scraper/config.json`. Adding a target is a JSON entry, never a new script.

---

## ⚡ Quick Start

```bash
pip install -r requirements.txt

python main.py                      # scrape, then build the dashboard data
python main.py scrape dashboard serve   # ...and serve it at localhost:8000
```

`main.py` in the project root is the single entry point: name the stages you
want and it runs them in that order.

| Command | What runs |
|---|---|
| `python main.py` | `scrape` → `dashboard` (the default) |
| `python main.py scrape` | Collect listings into `car_scraper/data/raw/*.csv` |
| `python main.py dashboard` | Turn the collected CSVs into dashboard JSON |
| `python main.py serve` | Serve the dashboard on `http://localhost:8000` |
| `python main.py dashboard serve` | Rebuild the data and view it, no scraping |

Stage options pass straight through:

```bash
python main.py scrape --site cardoen
python main.py dashboard --dataset bmw320touring
python main.py serve --port 9000
```

```
                    python main.py [stages...]
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
     scrape               dashboard               serve
  car_scraper/         dashboard/              dashboard/
  scrape.py            build_dashboard.py      index.html
        │                     │                     │
        └──► data/raw/*.csv ──┴──► data.json ───────┘
```

The stages are deliberately independent — each one only reads what the previous
one left on disk, so any of them runs on its own, and a failed scrape never
costs you the dashboard. `main.py` is the only entry point: the stages are
modules, not scripts.

---

## 🗂️ Structure

```
car_market_analysis/
│
├── main.py                      # Pipeline entry point — scrape / dashboard / serve
├── requirements.txt             # Python dependencies (scraper + dashboard)
│
├── car_scraper/                 # Scraping pipeline
│   ├── scrape.py                # Scrape stage — runs the enabled site scrapers
│   ├── config.json              # What to scrape (targets, limits, strategy)
│   ├── models.py                # Pydantic schema (CarListing)
│   │
│   ├── scrapers/                # One class per site
│   │   ├── base_scraper.py      # HTTP session, retry, validation, CSV export
│   │   ├── autoscout_scraper.py # Config-driven scraper, two crawl strategies
│   │   ├── scrape_de_market.py  # Market-wide sweep with brand excludes
│   │   └── cardoen_scraper.py   # Dealer stock scraper (JSON-LD)
│   │
│   ├── utils/                   # Logger + price/mileage formatters
│   ├── data/raw/                # Output CSVs land here (git-ignored)
│   └── logs/                    # Run logs
│
└── dashboard/
    ├── index.html               # The entire dashboard (HTML + CSS + JS)
    ├── build_dashboard.py       # CSV → data.json builder
    └── data.json                # Generated — do not edit
```

---

## 🕷️ The Scraper

### Sources

| Source | Status | Method |
|---|---|---|
| Large pan-European classifieds portal (BE + DE) | ✅ Active | Embedded `__NEXT_DATA__` JSON |
| Belgian dealer stock site | ✅ Working, off by default | JSON-LD structured data |

```bash
python main.py scrape                 # every enabled target
python main.py scrape --site cardoen  # just one site

# market-wide sweep: every make on the market bar an exclude list
cd car_scraper && python -m scrapers.scrape_de_market
```

### Two crawl strategies, per target

`detail` — paginate the result pages, collect the ad ids, then fetch each **detail page** and read its server-side JSON payload. One request per listing, but every schema field is present.

`search` — read listings straight out of the result page's own payload. ~20 listings per request instead of one, with a slightly narrower field set. Use it whenever those fields suffice.

Both read the page's own server-side JSON state rather than scraping HTML, so a site redesign doesn't break the parser.

### Configuration

```json
{
  "extraction_limit_per_target": 300,
  "targets": [
    { "make": "opel", "model": "astra", "country": "be", "strategy": "detail",
      "category": "suv-pick-up", "enabled": true },

    { "make": "bmw", "model": "320", "country": "de", "strategy": "search",
      "body": 5, "variant": "touring", "limit": 100000,
      "output_basename": "my_bmw320_touring", "enabled": false }
  ]
}
```

| Key | Meaning |
|---|---|
| `make` / `model` | URL slugs for the target vehicle (required, e.g. `"t-roc"`) |
| `country` | `be` or `de` — picks the domain and country filter |
| `strategy` | `detail` or `search` (see above) |
| `category` | Optional body-category path segment, e.g. `suv-pick-up` |
| `body` | Optional body-style code (`search` strategy only) |
| `variant` / `reject_title` | Keep only a named variant / drop titles matching a regex |
| `segment_by_year` + `year_from` / `year_to` | Split a query exceeding the site's 200-page cap into per-year queries |
| `limit` / `max_pages` | Listings and page caps for this target |
| `output_basename` | Give this target its own CSV prefix |
| `start_page` / `resume_file` | Resume an interrupted run, deduplicating against the existing CSV |
| `enabled` | `false` keeps a target on file without running it |

Optional top-level `"sites": ["autoscout", "cardoen"]` picks which scrapers the scrape stage runs.

The market-wide sweep is a query shape rather than a target list, so its parameters — price/mileage filters, the `exclude_makes` list, year-segmentation bounds — are class defaults on `GermanMarketScraper`. Override them with keyword arguments, or by adding an optional `"sweep"` object to `config.json`.

### Data schema

Every row is validated against the `CarListing` Pydantic model: `make`, `model`, `year`, `price`, `mileage`, `fuel_type`, `transmission`, `location`, `listing_url`, `posted_date` — plus `title`, `body_type`, `doors`, `horsepower`, `first_registration` and `condition` when the source exposes them.

Rows missing make/model/price, or with out-of-range years, are skipped during validation; duplicate listing URLs are dropped within a run.

### Architecture

```
car_scraper/scrape.py
  └── AutoScoutScraper.run()          ← autoscout_scraper.py
  │     ├── crawl_detail()            ← one request per ad, full field set
  │     └── crawl_search()            ← result-page payload, ~20x fewer requests
  │           └── GermanMarketScraper ← scrape_de_market.py (sweeps every make)
  └── CardoenScraper.run()            ← cardoen_scraper.py
        └── BaseScraper               ← base_scraper.py
              ├── HTTP session + retry logic + UA rotation
              ├── Pydantic validation + URL deduplication
              └── CSV export (timestamped)
```

Every scraper inherits from `BaseScraper` and implements only the site-specific parsing, keeping platform concerns isolated. Requests carry randomised 1–3s delays, realistic headers, exponential backoff and User-Agent rotation every 50 requests. Long runs survive connection outages via a slow-retry ladder (60s → 600s) and flush to disk periodically, so an interrupted crawl never loses more than a few pages.

---

## 📊 The Dashboard

A single-page dashboard — vanilla HTML, CSS and JavaScript with Chart.js, no build step, no backend.

### Build the data

```bash
python main.py dashboard                        # default dataset
python main.py dashboard --dataset bmw320touring
```

The builder reads matching CSVs by filename prefix from `car_scraper/data/raw/`, normalises fuel and transmission labels to English, applies per-dataset sanity bounds, deduplicates by URL, and writes a JSON file.

| `--dataset` | Source CSVs | Output |
|---|---|---|
| `belgium` *(default)* | `autoscout24_*.csv`, `cardoen_*.csv` | `data.json` |
| `de_market` | `autoscout_de_market_*.csv` | `de_market.json` |
| `bmw320touring` | `autoscout24_de_bmw320_touring_*.csv` | `bmw320_touring.json` |

`belgium` is what the configured targets produce, and it writes `data.json` —
the file `index.html` loads when no `?data=` is given. So a plain
`python main.py` ends with your own scrape on screen; the other datasets are a
query parameter away.

Sanity bounds are per-dataset on purpose: a broad market scrape uses tight limits to strip junk rows, while a targeted single-model scrape needs wider ones, since cheap high-mileage cars are a real part of that market. To add a dataset, add an entry to `DATASETS` in `build_dashboard.py`.

> ⚠️ CSV filename prefixes and the `source` column are **functional identifiers** — the dashboard matches files and filters rows on them. Renaming them breaks the pipeline.

### Serve it

The dashboard fetches its JSON, so it must be served over HTTP rather than opened as a file:

```bash
python main.py serve
# → http://localhost:8000
# → http://localhost:8000/index.html?data=de_market.json
```

### Features

- **Six KPI cards** — total listings, average price, median mileage, year range, cheapest, priciest
- **Seven live filters** — multi-select model, source, fuel, transmission, plus dual-handle year/price/mileage sliders that size themselves to the loaded dataset
- **Four interactive charts** — price vs mileage scatter, average price by year, listings by model, price histogram. Clicking any chart cross-filters the whole dashboard
- **Sortable table** of individual listings, each linking to the original ad
- **Dark / light mode**, persisted in `localStorage`

---

## 🛠️ Tech Stack

| Layer | Tools |
|---|---|
| Scraping | Python, `requests`, `BeautifulSoup` |
| Validation | `Pydantic` |
| Data processing | `pandas` |
| Dashboard | HTML, CSS, Vanilla JS, Chart.js |

---

## 📌 Notes

Listings come from large public classifieds portals covering the Belgian and German markets. Each source has its own scraper class behind a shared `BaseScraper` interface, so adding another site means one new class and one config entry — nothing else in the pipeline changes.

Scraped CSVs are git-ignored: this repository ships code, not collected data.

> ⚖️ Scraping here is deliberately polite — rate-limited, request-based, no parallel hammering. Check a site's terms before pointing the pipeline at it.
