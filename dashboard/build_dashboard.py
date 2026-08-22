"""
build_dashboard.py
Reads scraped CSV files from the car_scraper/data/ directory,
cleans and normalises the data, and writes a JSON file that
the dashboard's index.html can load via fetch().
"""

import argparse
import json
import re
from pathlib import Path
from glob import glob

import pandas as pd


# ── Paths ───────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "car_scraper" / "data" / "raw"
OUTPUT_FILE = SCRIPT_DIR / "data.json"

# Set to True to use only the latest CSV per source; False = use all CSVs
LATEST_ONLY = True

# CSV filename prefixes to ingest (newest per prefix when LATEST_ONLY).
PREFIXES = ["autoscout_de_market"]

# Named datasets → (csv prefixes, output json). Lets one dashboard serve several
# scrapes side by side instead of each build overwriting the last one.
# Sanity bounds are per-dataset: the broad market scrape uses tight ones to
# strip junk rows, but on a targeted single-model scrape those same bounds throw
# away real listings (cheap, high-mileage E46s are a legitimate part of that
# market), so it gets wider ones.
DATASETS = {
    "de_market": {
        "prefixes": ["autoscout_de_market"],
        "output": "data.json",
        "bounds": dict(price_min=1000, price_max=100_000, mileage_max=400_000),
    },
    "bmw320touring": {
        "prefixes": ["autoscout24_de_bmw320_touring"],
        "output": "bmw320_touring.json",
        "bounds": dict(price_min=1, price_max=200_000, mileage_max=1_000_000),
    },
}

# ── Fuel-type mapping (French + German scraper values → English labels) ─
FUEL_MAP = {
    # French (legacy Belgian scraper)
    "Essence": "Petrol",
    "Diesel": "Diesel",
    "Electrique/Essence": "Hybrid (Petrol)",
    "Electrique/Diesel": "Hybrid (Diesel)",
    "Micro-hybride essence": "Mild Hybrid (Petrol)",
    "Micro-hybride diesel": "Mild Hybrid (Diesel)",
    "GPL": "LPG",
    "Electrique": "Electric",
    # German (autoscout24.de)
    "Benzin": "Petrol",
    "Elektro/Benzin": "Hybrid (Petrol)",
    "Elektro/Diesel": "Hybrid (Diesel)",
    "Elektro": "Electric",
    "Erdgas (CNG)": "CNG",
    "Autogas (LPG)": "LPG",
    "Wasserstoff": "Hydrogen",
    "Sonstige": "Other",
}

# ── Exclusion lists (small city cars & commercial vans to exclude) ────
EXCLUSIONS = {
    "skoda": {"fabia", "citigo", "rapid/spaceback"},
    "seat": {"ibiza", "mii", "toledo", "altea", "altea xl", "arona", "leon", "leon e-hybrid"},
    "bmw": {"114", "116", "118", "120", "125", "140", "i3", "1er m coupé"},
    "mercedes-benz": {"citan", "vito", "sprinter", "t-klasse"},
    "nissan": {"micra", "nv200", "nv250", "nv300", "nv400", "primastar", "interstar", "townstar", "townstar ev", "e-nv200"},
    "toyota": {"aygo", "aygo x", "yaris", "yaris cross", "proace", "proace city"},
    "honda": {"jazz", "civic"},
    "audi": {"a1"},
    "mazda": {"2", "3"}
}


# ── Region: Nordrhein-Westfalen vs rest of Germany, from the postal code ─
#
# German postal codes don't align cleanly with state borders, so the main NRW
# ranges are listed first and the pockets that actually belong to a neighbouring
# state are carved back out: Grafschaft Bentheim (Niedersachsen) sits inside the
# 48xxx block, and the Ahr valley / Linz area (Rheinland-Pfalz) sits inside 53xxx.
NRW_PLZ_RANGES = [
    (32000, 33999),   # Ostwestfalen-Lippe: Bielefeld, Paderborn, Gütersloh, Minden
    (34400, 34439),   # Warburg, Marsberg, Borgentreich (NRW sliver of the 34xxx zone)
    (37671, 37696),   # Höxter, Beverungen, Marienmünster
    (40000, 48999),   # Düsseldorf, Ruhrgebiet, Münsterland
    (49477, 49549),   # Tecklenburger Land: Ibbenbüren, Lengerich, Tecklenburg
    (50000, 53999),   # Köln, Bonn, Aachen, Euskirchen
    (57000, 57489),   # Siegen-Wittgenstein, Olpe  (57518+ is Rheinland-Pfalz)
    (58000, 59999),   # Hagen, Iserlohn, Hamm, Soest
]
NOT_NRW_PLZ_RANGES = [
    (48455, 48455), (48465, 48465), (48480, 48480), (48488, 48488),
    (48499, 48499), (48527, 48531),   # Grafschaft Bentheim → Niedersachsen
    (53474, 53579), (53619, 53619),   # Ahrweiler / Linz / Unkel → Rheinland-Pfalz
]


def plz_region(location):
    """Classify a 'PLZ City' string as NRW / Other DE / Unknown.

    Returns "" when there is no location at all (datasets that don't scrape it),
    so the dashboard can tell "not available" apart from "couldn't be parsed"
    and simply omit the region filter instead of showing a bogus category.
    """
    if pd.isna(location) or not str(location).strip():
        return ""
    m = re.match(r"\s*(\d{5})\b", str(location))
    if not m:
        return "Unknown"
    plz = int(m.group(1))
    if any(lo <= plz <= hi for lo, hi in NOT_NRW_PLZ_RANGES):
        return "Other DE"
    if any(lo <= plz <= hi for lo, hi in NRW_PLZ_RANGES):
        return "NRW"
    return "Other DE"


def should_exclude(row):
    """Check if the row's make and model combination should be excluded."""
    make_lower = str(row["make"]).lower()
    model_lower = str(row["model"]).lower()
    if make_lower in EXCLUSIONS:
        if model_lower in EXCLUSIONS[make_lower]:
            return True
    return False


def normalise_transmission(val):
    """Map raw transmission strings to Automatic / Manual / Unknown."""
    if pd.isna(val):
        return "Unknown"
    v = str(val).lower()
    # German values first: "Halbautomatik" also contains "auto", and
    # "Schaltgetriebe" (manual) contains neither "auto" nor "manu".
    if "halbautomatik" in v:
        return "Semi-automatic"
    if "schaltgetriebe" in v:
        return "Manual"
    if "auto" in v or "dct" in v:
        return "Automatic"
    if "manu" in v:
        return "Manual"
    return "Unknown"


def build(prefixes=None, output_file=None,
          price_min=1000, price_max=100_000, mileage_max=400_000):
    # ── 1. Collect CSV files ────────────────────────────────────────
    prefixes = prefixes or PREFIXES
    output_file = output_file or OUTPUT_FILE
    all_files = []
    for prefix in prefixes:
        matches = sorted(glob(str(DATA_DIR / f"{prefix}_*.csv")))
        if matches:
            if LATEST_ONLY:
                all_files.append(matches[-1])   # only the most recent per source
            else:
                all_files.extend(matches)

    files = all_files

    if not files:
        print(f"ERROR: No CSV files found in {DATA_DIR}")
        print("Make sure car_scraper/data/raw/ contains autoscout24_*.csv or cardoen_*.csv files.")
        return

    mode = "LATEST ONLY" if LATEST_ONLY else "ALL FILES"
    print(f"[{mode}] Using {len(files)} CSV file(s):")
    for f in files:
        print(f"  • {Path(f).name}")

    # ── 2. Read & tag source ────────────────────────────────────────
    frames = []
    for f in files:
        df = pd.read_csv(f)
        fname = Path(f).name.lower()
        if fname.startswith("autoscout"):
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

    # ── 3. Normalise model (some DE listings have no model → "(Other)") ──
    raw["model"] = raw["model"].astype(str).str.strip()
    raw.loc[raw["model"].str.lower().isin(["nan", "none", ""]), "model"] = "(Other)"
    raw["model"] = raw["model"].str.title()

    # ── 4. Map fuel_type → fuel ─────────────────────────────────────
    raw["fuel"] = raw["fuel_type"].map(FUEL_MAP).fillna(
        raw["fuel_type"].where(raw["fuel_type"].notna(), "Unknown")
    )

    # ── 5. Normalise transmission → trans (column may be absent) ────
    if "transmission" in raw.columns:
        raw["trans"] = raw["transmission"].apply(normalise_transmission)
    else:
        raw["trans"] = "Unknown"

    # location is optional (not scraped for the DE dataset)
    if "location" not in raw.columns:
        raw["location"] = ""

    # Region derived from the postal code (NRW vs rest of Germany)
    raw["region"] = raw["location"].apply(plz_region)

    # ── 6. Coerce numeric & filter ──────────────────────────────────
    raw["price"] = pd.to_numeric(raw["price"], errors="coerce")
    raw["mileage"] = pd.to_numeric(raw["mileage"], errors="coerce")
    raw["year"] = pd.to_numeric(raw["year"], errors="coerce")

    clean = raw[
        (raw["price"] >= price_min) & (raw["price"] <= price_max)
        & (raw["mileage"] >= 0) & (raw["mileage"] <= mileage_max)
    ].copy()

    dropped = len(raw) - len(clean)
    if dropped:
        print(f"Dropped {dropped} rows outside the sanity bounds "
              f"(price {price_min}-{price_max}, mileage ≤ {mileage_max}).")

    # Filter out excluded makes and models
    exclude_mask = clean.apply(should_exclude, axis=1)
    clean = clean[~exclude_mask].copy()

    print(f"Clean rows (after filtering and model exclusions): {len(clean)}")

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
        "region": "region",
    }
    # Carried through only when the scraper provides them (the DE market
    # scrape has no title column, the BMW 320 Touring one does).
    for optional in ("title", "horsepower"):
        if optional in clean.columns:
            cols[optional] = optional

    out = clean[list(cols.keys())].rename(columns=cols)

    # Cast year to int (drop any NaN rows first)
    out = out.dropna(subset=["year", "price", "mileage"])
    out["year"] = out["year"].astype(int)
    out["price"] = out["price"].astype(int)
    out["mileage"] = out["mileage"].astype(int)

    # ── 8. Write JSON ───────────────────────────────────────────────
    records = out.to_dict(orient="records")
    with open(output_file, "w", encoding="utf-8") as fp:
        json.dump(records, fp, ensure_ascii=False)

    size_kb = Path(output_file).stat().st_size / 1024

    # ── 9. Summary ──────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  Output: {Path(output_file).name}  ({size_kb:.1f} KB)")
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
    ap = argparse.ArgumentParser(description="Build a dashboard JSON from scraped CSVs.")
    ap.add_argument("--dataset", choices=sorted(DATASETS), default="de_market",
                    help="which named dataset to build (default: de_market)")
    args = ap.parse_args()

    ds = DATASETS[args.dataset]
    build(prefixes=ds["prefixes"],
          output_file=SCRIPT_DIR / ds["output"],
          **ds["bounds"])
