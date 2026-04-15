# 📊 SUV Market Dashboard

An interactive, single-page analytics dashboard for the Belgian used SUV market. Built with vanilla HTML, CSS, and JavaScript — no build step required.

---

## 🚀 Overview

Visualises scraped listings for **Hyundai Tucson**, **Nissan Qashqai**, and **Škoda Karoq** sourced from AutoScout24 and Cardoen. All charts are interactive; clicking on a data point or chart segment applies a filter across the entire dashboard instantly.

---

## 📁 Files

| File | Description |
|---|---|
| `index.html` | The entire dashboard — HTML structure, CSS styles, and JS logic in one file |
| `build_dashboard.py` | Python script that reads raw CSV files and generates `data.json` |
| `data.json` | Pre-built dataset consumed by `index.html` via `fetch()` |

---

## 🔨 How to Build the Data

Before serving the dashboard, you need to generate `data.json` from the scraped CSV files.

**Requirements:** Python 3.8+, pandas

```bash
# From the project root
pip install pandas

# Generate data.json
python dashboard/build_dashboard.py
```

The script reads all `autoscout24_*.csv` and `cardoen_*.csv` files from `car_scraper/data/raw/`, deduplicates by listing URL, normalises fuel/transmission values, and outputs `dashboard/data.json`.

---

## 🌐 How to Serve

The dashboard loads `data.json` via `fetch()`, so it must be served over HTTP (not opened directly as a file).

**Option 1 — Python (quickest):**
```bash
cd dashboard
python -m http.server 8000
```
Then open 👉 [http://localhost:8000](http://localhost:8000)

**Option 2 — VS Code:** Install the *Live Server* extension and click **Go Live**.

**Option 3 — Static host:** Deploy the `dashboard/` folder to GitHub Pages, Netlify, Vercel, etc.

---

## ✨ Features

### 🔢 KPI Cards
Six at-a-glance metrics that update dynamically as filters are applied:
- Total listings, Average price, Median mileage, Year range, Cheapest, Most expensive

### 🎛️ Filters
All filters interact with each other in real time:
- **Model** — Tucson / Qashqai / Karoq
- **Source** — AutoScout24 / Cardoen
- **Fuel type** — Petrol, Diesel, Hybrid, Electric, etc.
- **Transmission** — Automatic / Manual
- **Year range** — Dual-handle slider
- **Price range** — Dual-handle slider
- **Mileage range** — Dual-handle slider

### 📈 Charts
| Chart | Interaction |
|---|---|
| **Price vs Mileage** (scatter) | Click a dot to filter by that model |
| **Price by Year** (bar) | Click a bar to filter by that year |
| **By Model** (doughnut) | Click a segment to filter by that model |
| **Price Distribution** (histogram) | Click a bar to filter by that price range |

### 📋 Listings Table
Sortable table showing individual records. Clicking a column header sorts ascending/descending. Each row links directly to the original listing.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Structure | HTML5 |
| Styling | Vanilla CSS (CSS custom properties, Flexbox, Grid) |
| Logic | Vanilla JavaScript (ES2020) |
| Charts | [Chart.js 4](https://www.chartjs.org/) via CDN |
| Font | [Inter](https://fonts.google.com/specimen/Inter) via Google Fonts |

> 💡 No npm, no bundler, no framework. Open `index.html` and it works.

---

## 🎨 Design

The dashboard follows a **light-mode Slate** theme inspired by Vercel's design language:
- 🎭 Background `#eef2f6` → Panels `#f8fafc` — subtle depth without harsh contrast
- 🖋️ Typography: Inter, `slate-700` (`#334155`) text palette
- 🎨 Chart colours: Sky Blue, Violet, Emerald — tuned for legibility on light backgrounds
- ✨ Micro-animations on card hover (`translateY(-3px)`)

---

## 🔄 Updating the Data

```
1. 🕷️  Run the scraper    →  cd car_scraper && python main.py
2. 🔨  Rebuild the JSON   →  python dashboard/build_dashboard.py
3. 🌐  Refresh browser    →  data.json is re-fetched on each page load
```

---

## 📌 Notes

- The dashboard is fully **client-side** — no backend, no database.
- `data.json` is ~560 KB covering ~3,000+ deduplicated listings across 3 models and 2 sources.
- Filters are composed with `&&` logic — all active filters apply simultaneously.
