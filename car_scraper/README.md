# 🕷️ Car Scraper

Request-based web scraping pipeline for the Belgian used car market. Extracts structured listings from multiple platforms and exports them as timestamped CSV files.

---

## 🎯 What It Scrapes

| Platform | Status | Method |
|---|---|---|
| AutoScout24.be | ✅ Active | `__NEXT_DATA__` JSON extraction |
| Cardoen.be | ✅ Active | JSON-LD structured data |
| vroom.be | 🟡 Implemented, inactive | JSON-LD structured data |
| 2dehands.be | ⚠️ Skeleton only | Not implemented |

**Target models:** Hyundai Tucson · Nissan Qashqai · Škoda Karoq

---

## ⚡ Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run all scrapers
python main.py
```

Output CSV files are saved to `data/raw/` with timestamps, e.g.:
```
data/raw/autoscout24_2026-04-15_143022.csv
data/raw/cardoen_2026-04-15_143055.csv
```

---

## ⚙️ Configuration

Edit `config.json` to control what gets scraped:

```json
{
  "make": "hyundai",
  "model": "tucson",
  "extraction_limit": 300
}
```

> 💡 Only one make/model target at a time in the current version.

---

## 🗂️ File Structure

```
car_scraper/
│
├── main.py                    # Orchestrator — runs all scrapers in sequence
├── models.py                  # Pydantic schema for data validation (CarListing)
├── config.json                # Scraping target configuration
├── requirements.txt           # Python dependencies
│
├── scrapers/
│   ├── base_scraper.py        # Shared logic: HTTP session, retry, CSV export
│   ├── autoscout_scraper.py   # AutoScout24.be scraper
│   ├── cardoen_scraper.py     # Cardoen.be scraper
│   ├── vroom_scraper.py       # vroom.be scraper (implemented, not yet active)
│   └── twodehands_scraper.py  # 2dehands.be scraper (skeleton)
│
├── utils/
│   ├── formatters.py          # Price/mileage string → int helpers
│   └── logger.py              # Structured logging configuration
│
├── data/
│   └── raw/                   # Output CSV files land here
│
└── logs/                      # Scraper run logs
```

---

## 🔍 Data Schema

Each scraped listing is validated against a `CarListing` Pydantic model:

| Field | Type | Example |
|---|---|---|
| `make` | `str` | `hyundai` |
| `model` | `str` | `tucson` |
| `year` | `int` | `2021` |
| `price` | `int` | `24900` |
| `mileage` | `int` | `45000` |
| `fuel_type` | `str` | `Diesel` |
| `transmission` | `str` | `Automatic` |
| `location` | `str` | `Brussels` |
| `listing_url` | `str` | `https://...` |

Listings missing `make`, `model`, or `price`, or with out-of-range years/prices, are automatically skipped during validation.

---

## 🧱 Architecture

```
main.py
  └── AutoScoutScraper.run()    ← autoscout_scraper.py
  └── CardoenScraper.run()      ← cardoen_scraper.py
        └── BaseScraper         ← base_scraper.py
              ├── HTTP session + retry logic
              ├── Pydantic validation
              └── CSV export (timestamped)
```

Each scraper inherits from `BaseScraper` and only implements the site-specific parsing logic (`run()` method), keeping platform concerns fully isolated.

---

## 📦 Dependencies

```
requests
beautifulsoup4
pydantic
fake-useragent
pandas
```

Install with:
```bash
pip install -r requirements.txt
```

---

## 🔄 Output → Dashboard

After scraping, pass the raw CSVs through the dashboard builder to produce `data.json`:

```bash
python ../dashboard/build_dashboard.py
```

See [`dashboard/README.md`](../dashboard/README.md) for full details.
