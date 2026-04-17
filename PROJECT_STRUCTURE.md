# 🚗 Belgium Car Market — Project Structure & Script Reference

> **Purpose:** This document explains every file in the project, what it does, how it fits
> into the pipeline, and when/how to run it.

---

## 📐 High-Level Architecture

```
                       ┌─────────────────────────────────────┐
                       │          config.json                │
                       │   (defines which cars to scrape)    │
                       └────────────────┬────────────────────┘
                                        │ reads
                                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    car_scraper/                             │
│                                                             │
│   main.py  ──►  AutoScoutScraper  ──►  BaseScraper         │
│                 CardoenScraper        (HTTP + parse logic)  │
│                                                             │
│                  saves CSV files to:                        │
│               data/raw/autoscout24_<timestamp>.csv          │
└──────────────────────────┬──────────────────────────────────┘
                           │ CSV files
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              dashboard/build_dashboard.py                   │
│    reads latest CSV  →  cleans data  →  writes data.json   │
└──────────────────────────┬──────────────────────────────────┘
                           │ data.json
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               dashboard/index.html                          │
│         (Browser dashboard — reads data.json via fetch())   │
│   Charts · Filters · Multi-select · Table · KPIs           │
└─────────────────────────────────────────────────────────────┘
```

**Key principle:** The scraper and dashboard are fully **decoupled**.
They communicate only through CSV files and `data.json`. You can update either side
without touching the other.

---

## 📁 Full Directory Tree

```
Belgium_Car_Market/
│
├── PROJECT_README.md           ← Quick-start guide
├── PROJECT_STRUCTURE.md        ← This file
├── .gitignore
│
├── car_scraper/                ← All scraping logic lives here
│   ├── main.py                 ← Entry point: runs all scrapers
│   ├── config.json             ← Target makes/models + limits
│   ├── models.py               ← Pydantic data schema
│   ├── requirements.txt        ← Python dependencies
│   │
│   ├── scrapers/               ← One file per website
│   │   ├── base_scraper.py     ← Shared HTTP, parse, save logic
│   │   ├── autoscout_scraper.py
│   │   ├── cardoen_scraper.py
│   │   ├── vroom_scraper.py    ← (inactive / in-progress)
│   │   └── twodehands_scraper.py ← (inactive / in-progress)
│   │
│   ├── utils/
│   │   ├── logger.py           ← Colored terminal logger
│   │   └── formatters.py       ← Small text/data helpers
│   │
│   ├── data/
│   │   └── raw/                ← All scraped CSVs saved here
│   │       ├── autoscout24_20260416_101808.csv  ← (main dataset)
│   │       ├── audi_q2_20260417_091531.csv
│   │       └── cardoen_*.csv
│   │
│   ├── logs/                   ← Auto-generated log files
│   │
│   └── scratch/                ← One-off / debug scripts
│       ├── scrape_audi_q2.py   ← Single-target scraper (Q2)
│       └── debug_title.py      ← HTML title debug utility
│
└── dashboard/                  ← Frontend dashboard
    ├── index.html              ← The full dashboard UI
    ├── build_dashboard.py      ← CSV → data.json builder
    ├── data.json               ← Generated data file (do not edit)
    └── README.md               ← Dashboard-specific notes
```

---

## 🔧 Script-by-Script Reference

---

### `car_scraper/main.py`
**What:** The main entry point. Instantiates and runs all active scrapers in sequence.

**How to run:**
```bash
cd car_scraper
python main.py
```

**What it does:**
- Creates `AutoScoutScraper` (and optionally `CardoenScraper`)
- Calls `.run()` on each scraper
- Catches top-level errors so one failed scraper doesn't kill others
- Ensures `logs/` and `data/raw/` directories exist

**When to use:** When you want to run the **full pipeline** — scraping all targets
defined in `config.json`.

---

### `car_scraper/config.json`
**What:** Configuration file that defines which cars to scrape and how many per target.

**Structure:**
```json
{
  "targets": [
    { "make": "bmw",      "model": "x1" },
    { "make": "hyundai",  "model": "tucson" }
  ],
  "extraction_limit_per_target": 200
}
```

**Key fields:**
| Field | Description |
|-------|-------------|
| `targets` | List of `{make, model}` pairs to scrape |
| `extraction_limit_per_target` | Max listings per model (e.g. 200) |

**Note:** `make` and `model` must match the URL slugs used by AutoScout24
(lowercase, hyphens for spaces — e.g. `"t-roc"`, `"c-hr"`).

**Currently tracked (14 models):**
BMW X1, BMW X2, Kia Stonic, Citroën C4, Audi Q3, VW Tiguan, VW T-Roc,
VW Taigo, VW T-Cross, Hyundai Kona, Peugeot 3008, Peugeot 2008, Toyota C-HR, Škoda Karoq

---

### `car_scraper/models.py`
**What:** Defines the `CarListing` Pydantic model — the data schema for every row saved.

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `make` | str | Brand (e.g. "Hyundai") |
| `model` | str | Model name (e.g. "Tucson") |
| `year` | int | Registration year |
| `price` | int | Price in EUR |
| `mileage` | int | Mileage in km |
| `fuel_type` | str | Petrol / Diesel / Electric / Hybrid |
| `transmission` | str | Manual / Automatic |
| `location` | str | Belgian city + zip |
| `listing_url` | str | Full AutoScout24 URL |
| `posted_date` | str | Always "N/A" (not available on AS24) |

**Why Pydantic?** Automatically validates and rejects rows that are missing
critical fields (price = 0, year = 0, unknown make, etc.).

---

### `car_scraper/scrapers/base_scraper.py`
**What:** The parent class for all scrapers. Contains all shared logic.

**Responsibilities:**
- Loads `config.json` targets and limits
- Sets up an HTTP `requests.Session` with realistic browser headers
- `get_page(url)` — fetches a page with random delays (1–3s), retries with
  exponential backoff (2s → 4s → 8s), rotates User-Agent every 50 requests
- `parse_listing(data)` — validates data via Pydantic, deduplicates by URL
- `save_data()` — appends valid listings to the timestamped CSV file;
  clears the in-memory buffer after each save

**Output file naming:** `data/raw/<site_name>_<YYYYMMDD_HHMMSS>.csv`

---

### `car_scraper/scrapers/autoscout_scraper.py`
**What:** AutoScout24-specific scraper. Inherits from `BaseScraper`.

**How it works:**
1. For each target in `config.json`, builds the URL:
   `https://www.autoscout24.be/fr/lst/<make>/<model>/c/suv-pick-up`
2. Paginates through listing pages, collects `data-guid` attributes from `<article>` tags
3. Fetches each **detail page** individually
4. Extracts structured data from the `<script id="__NEXT_DATA__">` JSON blob
   (this is Next.js server-side data — very reliable, no fragile HTML parsing)
5. Calls `parse_listing()` and `save_data()` after each target completes

**Why detail pages?** The listing cards on search results don't include all fields
(fuel type, transmission, exact mileage). Only the detail page has complete data.

**Anti-bot measures handled:**
- Random 1–3s delay between every request
- Realistic HTTP headers (Accept, Accept-Language, Sec-Fetch-*)
- User-Agent rotation via `fake_useragent`
- Session cookie clearing every 50 requests

---

### `car_scraper/scrapers/cardoen_scraper.py`
**What:** Scraper for Cardoen.be — a large Belgian used car dealer.

**Status:** Active but produces very few results (~8 listings in latest run)
because Cardoen has limited SUV inventory matching the targets.

**How to enable:** Uncomment `CardoenScraper()` in `main.py`.

---

### `car_scraper/scrapers/vroom_scraper.py`
**What:** Scraper stub for Vroom.be. **Currently inactive.**

**Status:** Not integrated into `main.py`. Kept for future development.

---

### `car_scraper/scrapers/twodehands_scraper.py`
**What:** Scraper stub for 2dehands.be. **Currently inactive.**

**Status:** Minimal implementation, not integrated into `main.py`.

---

### `car_scraper/utils/logger.py`
**What:** Configures a color-coded terminal logger using Python's `logging` module.

**Log format:** `2026-04-17 09:15:37 | INFO | AutoScout24 | Message here`

**Color coding:**
- 🟢 Green → INFO (successful extraction)  
- 🟡 Yellow → WARNING (skipped pages, rate limits)  
- 🔴 Red → ERROR (critical failures)  
- ⚪ White → DEBUG (detail page fetches, hidden by default)

---

### `car_scraper/utils/formatters.py`
**What:** Small helper functions for text cleanup and normalization.

---

### `car_scraper/scratch/scrape_audi_q2.py`
**What:** A **standalone one-off scraper** for Audi Q2 only.
Does not read `config.json` — targets and limits are hardcoded at the top of the file.
Saves to `data/raw/audi_q2_<timestamp>.csv`.

**How to run:**
```bash
cd car_scraper
python scratch/scrape_audi_q2.py
```

**Reuse pattern:** Copy this file, change `MAKE`, `MODEL`, and `LIMIT` at the top
to quickly scrape any single model without touching `config.json`.

---

### `car_scraper/scratch/debug_title.py`
**What:** Debug utility that fetches a single AutoScout24 URL and prints the
raw HTML title and `__NEXT_DATA__` keys — useful for checking if the scraper
can reach a page and what data is available.

---

### `dashboard/build_dashboard.py`
**What:** The **bridge** between scraper CSVs and the frontend dashboard.
Reads raw CSV files, cleans the data, and writes `dashboard/data.json`.

**How to run:**
```bash
cd dashboard
python build_dashboard.py
```

**Key settings at the top of the file:**
| Variable | Default | Description |
|----------|---------|-------------|
| `LATEST_ONLY` | `True` | `True` = only use the newest CSV per source; `False` = merge all CSVs |

**What it does:**
1. Finds the latest `autoscout24_*.csv` and `cardoen_*.csv` in `car_scraper/data/raw/`
2. Reads and concatenates them into a single DataFrame
3. Normalizes fuel types (French → English): `"Essence" → "Petrol"`, `"Diesel" → "Diesel"`, etc.
4. Normalizes transmission labels
5. Drops rows with price = 0, year < 2005, or missing make/model
6. Deduplicates by URL
7. Writes clean records to `dashboard/data.json`
8. Prints a summary by model and source

**Output format (each row in data.json):**
```json
{
  "make": "Hyundai", "model": "Kona", "year": 2021,
  "price": 18990, "mileage": 45000,
  "fuel": "Petrol", "trans": "Automatic",
  "source": "AutoScout24",
  "url": "https://www.autoscout24.be/..."
}
```

---

### `dashboard/index.html`
**What:** The complete single-page dashboard UI. No framework — pure HTML + CSS + JavaScript.
Uses **Chart.js** for all charts. Loads data via `fetch('data.json')`.

**Features:**
| Feature | Details |
|---------|---------|
| **KPI cards** | Total listings, avg price, median km, year range, cheapest, priciest |
| **Multi-select model filter** | Custom checkbox dropdown with Select All, colored chips, color swatches |
| **Source / Fuel / Transmission filters** | Standard dropdowns, populated dynamically from data |
| **Year / Price / Mileage sliders** | Dual-handle range sliders, ranges adapt to actual data |
| **Scatter plot** | Price vs Mileage — color by model or by year when 1 model selected |
| **Bar chart (by year)** | Avg price per year — grouped by model or single-model mode |
| **Doughnut chart** | Listings count by model — clickable to toggle filter |
| **Price histogram** | Distribution stacked by model — clickable to set price filter |
| **Data table** | Top 100 rows, sortable by any column, links to live listings |
| **Dark / Light mode** | Persisted in localStorage |
| **Cross-filtering** | Clicking charts applies filters that affect all other charts |

**How to view:**
```bash
cd dashboard
python -m http.server 8000
# then open http://localhost:8000 in browser
```
> ⚠️ Must be served via HTTP — `fetch('data.json')` won't work if opened as a local file.

---

## 🚀 Full Pipeline: Step-by-Step

### First time setup
```bash
cd car_scraper
pip install -r requirements.txt
```

### Step 1 — Scrape data
```bash
# Edit config.json to add/remove targets first
python main.py
# Output: car_scraper/data/raw/autoscout24_<timestamp>.csv
```

### Step 2 — Build dashboard data
```bash
cd ../dashboard
python build_dashboard.py
# Output: dashboard/data.json
```

### Step 3 — View dashboard
```bash
python -m http.server 8000
# Open: http://localhost:8000
```

### To add a new car model
1. Add `{ "make": "...", "model": "..." }` to `config.json`
2. Run `python main.py` (only new model will be at the end of the CSV)
3. Run `python build_dashboard.py`
4. Refresh browser — new model appears automatically in all filters and charts

### To scrape a single model quickly
```bash
# Copy and edit the Q2 script:
cp car_scraper/scratch/scrape_audi_q2.py car_scraper/scratch/scrape_nissan_qashqai.py
# Edit MAKE, MODEL, LIMIT at the top
python car_scraper/scratch/scrape_nissan_qashqai.py
```

---

## 📦 Dependencies

```
requests        # HTTP client
beautifulsoup4  # HTML parser
fake-useragent  # Browser User-Agent rotation
pydantic        # Data validation / schema
pandas          # CSV processing in build_dashboard.py
```

Install: `pip install -r car_scraper/requirements.txt`

---

## 📊 Data Files

| File | Size | Description |
|------|------|-------------|
| `autoscout24_20260416_101808.csv` | ~598 KB | Main dataset — 14 models (~2,360 rows) |
| `autoscout24_20260408_*.csv` | ~154–163 KB | Earlier scrape — contains Tucson & Qashqai |
| `audi_q2_20260417_091531.csv` | ~31 KB | Audi Q2 one-off scrape |
| `cardoen_20260408_192720.csv` | ~1.8 KB | Cardoen dealer data (8 rows) |
| `dashboard/data.json` | ~755 KB | Generated — do not edit manually |

---

*Generated: April 2026 | Belgium Car Market Project*
