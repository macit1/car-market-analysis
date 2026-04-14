# Car Market Scraper

## 🎯 Project Objective
A modular, robust web scraping pipeline designed to extract used car listings from the Belgian automotive market. The goal is to scrape at least 100 listings per target site, rigorously validate the extracted data, and export it safely to timestamped CSV format for analysis.

## 🏢 Target Websites
1. **2dehands.be**
2. **AutoScout24.be**
3. **vroom.be**

## 🏗️ Technical Architecture & Stack
The project is built entirely in Python using modern, anti-detection techniques and strict data modeling.

*   **Browser Automation & Anti-Detection:** `undetected-chromedriver` is utilized to bypass common bot-mitigation systems. It incorporates randomized request delays, dynamic `User-Agent` rotation (via `fake_useragent`), and automatic cookie-clearing every 50 requests.
*   **Data Validation:** `Pydantic` models (`models.py`) rigidly validate every extracted listing. Prices and mileages are automatically parsed into integers (stripping out currency symbols and whitespace). Listings missing critical fields (make, model, price) or featuring invalid years are dynamically skipped.
*   **Modular Design:** 
    *   `base_scraper.py`: Handles all the complex, shared browser management tasks, robust error handling, and CSV exporting.
    *   `scrapers/*.py`: Individual boilerplate files for 2dehands, AutoScout24, and vroom, keeping site-specific logic isolated.
    *   `main.py`: The orchestrator that initializes and executes all scrapers in sequence.

## 🗂️ Current File Structure
```
belgian_car_scraper/
│
├── main.py                     # Pipeline orchestrator
├── models.py                   # Pydantic schema for validation (CarListing)
├── requirements.txt            # Python dependencies
│
├── scrapers/
│   ├── base_scraper.py         # Shared scraping logic (browser, Pydantic, CSV save)
│   ├── autoscout_scraper.py    # Target: AutoScout24
│   ├── twodehands_scraper.py   # Target: 2dehands
│   └── vroom_scraper.py        # Target: vroom
│
└── utils/
    ├── formatters.py           # Functions for data cleaning (price, mileage)
    └── logger.py               # Custom logging configuration
```

## ⏭️ Next Steps (Pending Implementation)
The primary scaffold is 100% complete. The next development phase involves:
1.  **DOM Inspection:** Navigating to each target site to map out the specific CSS/XPath selectors for properties like `price`, `make`, `model`, `mileage`, and pagination components.
2.  **Logic Injection:** Filling out the `run()` methods within `autoscout_scraper.py`, `twodehands_scraper.py`, and `vroom_scraper.py` using the identified DOM selectors to parse the HTML and populate the Pydantic models.
