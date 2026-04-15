"""
build_dashboard.py
Reads scraped CSV files from the car_scraper/data/ directory,
cleans and normalises the data, and writes a JSON file that
the dashboard's index.html can load via fetch().
"""

import json
from pathlib import Path
from glob import glob

import pandas as pd


# ── Paths ───────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "car_scraper" / "data" / "raw"
OUTPUT_FILE = SCRIPT_DIR / "data.json"

# ── Fuel-type mapping (French scraper values → English dashboard labels) ─
FUEL_MAP = {
    "Essence": "Petrol",
    "Diesel": "Diesel",
    "Electrique/Essence": "Hybrid (Petrol)",
    "Electrique/Diesel": "Hybrid (Diesel)",
    "Micro-hybride essence": "Mild Hybrid (Petrol)",
    "Micro-hybride diesel": "Mild Hybrid (Diesel)",
    "GPL": "LPG",
    "Electrique": "Electric",
}


def normalise_transmission(val):
    """Map raw transmission strings to Automatic / Manual / Unknown."""
    if pd.isna(val):
        return "Unknown"
    v = str(val).lower()
    if "auto" in v or "dct" in v:
        return "Automatic"
    if "manu" in v:
        return "Manual"
    return "Unknown"


def build():
    # ── 1. Collect CSV files ────────────────────────────────────────
    patterns = [
        str(DATA_DIR / "autoscout24_*.csv"),
        str(DATA_DIR / "cardoen_*.csv"),
    ]
    files = []
    for pat in patterns:
        files.extend(glob(pat))

    if not files:
        print(f"ERROR: No CSV files found in {DATA_DIR}")
        print("Make sure car_scraper/data/raw/ contains autoscout24_*.csv or cardoen_*.csv files.")
        return

    print(f"Found {len(files)} CSV file(s):")
    for f in files:
        print(f"  • {Path(f).name}")

    # ── 2. Read & tag source ────────────────────────────────────────
    frames = []
    for f in files:
        df = pd.read_csv(f)
        fname = Path(f).name.lower()
        if fname.startswith("autoscout24"):
            df["source"] = "AutoScout24"
        elif fname.startswith("cardoen"):
            df["source"] = "Cardoen"
        else:
            df["source"] = "Other"
        frames.append(df)

    raw = pd.concat(frames, ignore_index=True)
    print(f"\nRaw rows (before cleaning): {len(raw)}")

    raw = raw.drop_duplicates(subset=["listing_url"], keep="last")
    print(f"Unique rows after deduplication: {len(raw)}")

    # ── 3. Normalise model ──────────────────────────────────────────
    raw["model"] = raw["model"].astype(str).str.title()

    # ── 4. Map fuel_type → fuel ─────────────────────────────────────
    raw["fuel"] = raw["fuel_type"].map(FUEL_MAP).fillna(
        raw["fuel_type"].where(raw["fuel_type"].notna(), "Unknown")
    )

    # ── 5. Normalise transmission → trans ───────────────────────────
    raw["trans"] = raw["transmission"].apply(normalise_transmission)

    # ── 6. Coerce numeric & filter ──────────────────────────────────
    raw["price"] = pd.to_numeric(raw["price"], errors="coerce")
    raw["mileage"] = pd.to_numeric(raw["mileage"], errors="coerce")
    raw["year"] = pd.to_numeric(raw["year"], errors="coerce")

    clean = raw[
        (raw["price"] >= 1000) & (raw["price"] <= 100_000)
        & (raw["mileage"] >= 0) & (raw["mileage"] <= 400_000)
    ].copy()

    print(f"Clean rows (after filtering): {len(clean)}")

    # ── 7. Select & rename columns ──────────────────────────────────
    cols = {
        "make": "make",
        "model": "model",
        "year": "year",
        "price": "price",
        "mileage": "mileage",
        "fuel": "fuel",
        "trans": "trans",
        "source": "source",
        "location": "location",
        "listing_url": "url",
    }
    out = clean[list(cols.keys())].rename(columns=cols)

    # Cast year to int (drop any NaN rows first)
    out = out.dropna(subset=["year", "price", "mileage"])
    out["year"] = out["year"].astype(int)
    out["price"] = out["price"].astype(int)
    out["mileage"] = out["mileage"].astype(int)

    # ── 8. Write JSON ───────────────────────────────────────────────
    records = out.to_dict(orient="records")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as fp:
        json.dump(records, fp, ensure_ascii=False)

    size_kb = OUTPUT_FILE.stat().st_size / 1024

    # ── 9. Summary ──────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  Output: {OUTPUT_FILE.name}  ({size_kb:.1f} KB)")
    print(f"  Total records: {len(records)}")
    print(f"{'='*50}")

    print("\n  By model:")
    for model, count in out["model"].value_counts().items():
        print(f"    {model:20s} {count:>5}")

    print("\n  By source:")
    for src, count in out["source"].value_counts().items():
        print(f"    {src:20s} {count:>5}")

    print()


if __name__ == "__main__":
    build()
