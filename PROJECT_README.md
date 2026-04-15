# 🚗 Belgium SUV Market — Data Pipeline

An end-to-end project that **scrapes**, **cleans**, and **visualises** used SUV listings from the Belgian automotive market. The pipeline runs automatically across multiple sources and models, delivering a polished interactive dashboard for market analysis.

---

## 🎯 What This Project Does

1. 🕷️ **Scrapes** live listings from Belgian car platforms (AutoScout24, Cardoen)
2. 🧹 **Cleans & deduplicates** raw data into a single structured dataset
3. 📊 **Visualises** the results in an interactive browser-based dashboard

**Target models:** Hyundai Tucson · Nissan Qashqai · Škoda Karoq

---

## 🗂️ Project Structure

```
Belgium_Car_Market/
│
├── 📄 PROJECT_README.md          # You are here
│
├── 🕷️ car_scraper/               # Scraping pipeline
│   ├── main.py                   # Run this to scrape
│   ├── README.md                 # Scraper docs
│   └── ...
│
└── 📊 dashboard/                 # Analytics dashboard
    ├── index.html                # Open this in a browser
    ├── build_dashboard.py        # Run this to build data.json
    └── README.md                 # Dashboard docs
```

---

## ⚡ Quick Start

```bash
# 1. Install scraper dependencies
pip install -r car_scraper/requirements.txt

# 2. Scrape listings (writes CSV files to car_scraper/data/raw/)
cd car_scraper && python main.py

# 3. Build the dashboard dataset
python dashboard/build_dashboard.py

# 4. Serve and open the dashboard
cd dashboard && python -m http.server 8000
# → open http://localhost:8000
```

---

## 📦 Components

### 🕷️ [Scraper](./car_scraper/README.md)
Request-based scraping pipeline targeting AutoScout24.be and Cardoen.be. Extracts price, mileage, year, fuel type, transmission, and listing URL for each vehicle. Exports timestamped CSV files per source. See [`car_scraper/README.md`](./car_scraper/README.md) for full details.

### 📊 [Dashboard](./dashboard/README.md)
A single-file HTML dashboard powered by Chart.js. Loads `data.json` and renders four interactive charts, seven real-time filters, six KPI cards, and a sortable listings table. See [`dashboard/README.md`](./dashboard/README.md) for full details.

---

## 🛠️ Tech Stack

| Layer | Tools |
|---|---|
| Scraping | Python, `requests`, `BeautifulSoup` |
| Validation | `Pydantic` |
| Data processing | `pandas` |
| Dashboard | HTML, CSS, Vanilla JS, Chart.js |

---

## 📌 Data Sources

| Source | Type | URL |
|---|---|---|
| AutoScout24.be | Request-based | [autoscout24.be](https://www.autoscout24.be) |
| Cardoen.be | Request-based | [cardoen.be](https://www.cardoen.be) |
