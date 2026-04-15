# Belgium Car Market — Cleanup & Scalability Tasks

> Full project audit completed. Tasks grouped by area, ordered by impact.

---

## Section A: Scraper — Data Quality & Cleanup

- [ ] **A1. Deduplicate CSV data in `build_dashboard.py`**
  - 6 CSV files in `data/raw/` from 3 separate scraper runs → same listings appear 2–3×
  - Add `clean.drop_duplicates(subset=['listing_url'], keep='last')` before export
  - Impact: 🔴 High — removes ~40% bloat from `data.json`
  - Effort: 2 min

- [ ] **A2. Multi-model `config.json` support**
  - Currently `config.json` only supports **one** make/model at a time (`"skoda"/"karoq"`)
  - Ran scraper 3× manually (Tucson, Qashqai, Karoq) = 6 CSV files, duplicates, messy
  - **Change to array format:**
    ```json
    {
      "targets": [
        { "make": "hyundai", "model": "tucson" },
        { "make": "nissan", "model": "qashqai" },
        { "make": "skoda", "model": "karoq" }
      ],
      "extraction_limit": 300
    }
    ```
  - Update `main.py` + `base_scraper.py` to loop through targets
  - Impact: 🔴 High — single command scrapes all models
  - Effort: 30 min

- [ ] **A3. Remove dead `twodehands_scraper.py`**
  - File is a skeleton (33 lines, `# TODO` comments, `break` on line 28)
  - Not imported in `main.py`, never produces data
  - Either implement it or delete it to avoid confusion
  - Impact: 🟡 Medium (code hygiene)
  - Effort: 1 min to delete, 2–3 hours to implement

- [ ] **A4. Activate `vroom_scraper.py` in `main.py`**
  - Fully implemented (118 lines) but **not imported** in `main.py`
  - Add `from scrapers.vroom_scraper import VroomScraper` and add to scrapers list
  - Verify it still works (vroom.be may have changed since April 8)
  - Impact: 🟡 Medium — adds a 3rd data source
  - Effort: 5 min

- [ ] **A5. Fix `year` validator upper bound in `models.py`**
  - `year: int = Field(..., ge=1990, le=2026)` — hardcoded max year
  - Will reject 2027+ listings next year
  - Use `datetime.now().year + 1` dynamically
  - Impact: 🟢 Low (future-proofing)
  - Effort: 2 min

---

## Section B: Scraper — Architecture & Robustness

- [ ] **B1. Add `pandas` to `requirements.txt`**
  - `build_dashboard.py` requires pandas but it's not listed in requirements
  - Impact: 🟡 Medium — new users get `ModuleNotFoundError`
  - Effort: 1 min

- [ ] **B2. Scraper `save_data()` overwrites on each run — no append mode**
  - Each run creates a new timestamped CSV (good!) but old files accumulate
  - Consider: archive old CSVs, or add a `--clean` flag to remove previous files
  - Impact: 🟢 Low
  - Effort: 15 min

- [ ] **B3. Bare `except` clauses in scrapers**
  - `cardoen_scraper.py:64` and `vroom_scraper.py:59` use `except:` (no exception type)
  - Should be `except (json.JSONDecodeError, ValueError):` at minimum
  - Impact: 🟢 Low (hides bugs silently)
  - Effort: 5 min

- [ ] **B4. Centralize scraper URL construction**
  - All 3 scrapers duplicate the same `if self.make: self.base_url = ...` pattern
  - Move to `BaseScraper.__init__()` or a `build_url()` method
  - Impact: 🟢 Low (DRY principle)
  - Effort: 15 min

- [ ] **B5. Add `--dry-run` mode to scraper**
  - Print which pages/URLs would be scraped without making HTTP requests
  - Useful for debugging config changes
  - Impact: 🟢 Low
  - Effort: 20 min

---

## Section C: Dashboard — Quick Fixes

- [ ] **C1. Add `<meta name="viewport">` for mobile**
  - Dashboard has no viewport tag → broken on phones/tablets
  - Add: `<meta name="viewport" content="width=device-width, initial-scale=1">`
  - Impact: 🟡 Medium
  - Effort: 1 min

- [ ] **C2. Dynamic year/price/mileage ranges in `resetFilters()`**
  - Currently hardcoded: `fYearMin.value = 2005; fYearMax.value = 2026`
  - Should compute from actual `RAW` data after load
  - Impact: 🟡 Medium
  - Effort: 5 min

- [ ] **C3. Dynamic slider `min`/`max` attributes from data**
  - Range inputs have hardcoded `min="2005" max="2026"` etc. in HTML
  - After `fetch()`, update these from actual data bounds
  - Impact: 🟡 Medium (sliders won't match new data otherwise)
  - Effort: 10 min

- [ ] **C4. Replace implicit global IDs with explicit `getElementById`**
  - Code uses `fModel.value` instead of `document.getElementById('fModel').value`
  - Works but fragile — a future element ID collision breaks everything silently
  - Impact: 🟢 Low
  - Effort: 10 min

---

## Section D: Project-Level

- [ ] **D1. Update `PROJECT_README.md`**
  - Still says "Next Steps: DOM Inspection" — that's done
  - Doesn't mention `dashboard/` folder at all
  - Doesn't mention `config.json` or how to run
  - Add: project structure, setup instructions, run commands
  - Impact: 🟡 Medium
  - Effort: 15 min

- [ ] **D2. Write `dashboard/README.md`**
  - Currently just `# Dashboard — TODO` (one line)
  - Document: how to build `data.json`, how to serve, tech stack
  - Impact: 🟡 Medium
  - Effort: 10 min

- [ ] **D3. Add a one-command `run_all.py` or Makefile**
  - Currently 2 manual steps: run scraper → run build_dashboard.py
  - Create a script that does both: scrape → build → optionally serve
  - Impact: 🟡 Medium
  - Effort: 15 min

- [ ] **D4. Track scraped CSVs in git (or keep ignoring?)**
  - `.gitignore` ignores all `data/` — scraped data is not version-controlled
  - Decision: keep ignoring (data changes constantly) or track a sample snapshot
  - Impact: 🟢 Low (personal preference)
  - Effort: 2 min

---

## Priority Summary

| Priority | Tasks | Description |
|----------|-------|-------------|
| **Do first** | A1, A2, C1 | Dedup data, multi-model config, viewport |
| **Do next** | A4, B1, D1, D2 | Activate vroom, fix requirements, update docs |
| **Nice to have** | A3, A5, B3, B4, C2, C3, C4, D3 | Code hygiene, DRY, dynamic ranges |
| **Decide later** | B2, B5, D4 | Archiving, dry-run, git tracking |
