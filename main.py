"""Pipeline entry point — runs the stages you ask for, in order.

    python main.py                      # scrape, then build the dashboard data
    python main.py scrape               # collect listings into car_scraper/data/raw/
    python main.py dashboard            # turn the collected CSVs into dashboard JSON
    python main.py serve                # serve the dashboard on localhost
    python main.py scrape dashboard serve

Stage-specific options pass straight through:

    python main.py scrape --site cardoen
    python main.py dashboard --dataset bmw320touring
    python main.py serve --port 9000

The stages are deliberately independent — each one only reads what the previous
one left on disk, so any of them can be run on its own.
"""

import argparse
import importlib.util
import os
import sys
from pathlib import Path

# Log lines carry arrows and the odd umlaut; the default Windows console
# codepage would rather crash than render them.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
SCRAPER_DIR = ROOT / "car_scraper"
DASHBOARD_DIR = ROOT / "dashboard"

STAGES = ("scrape", "dashboard", "serve")


def _load(path: Path, module_name: str):
    """Import a file by path under an explicit name.

    The scraper and the dashboard builder are both scripts meant to be run from
    their own directory; loading them this way keeps them runnable standalone
    without a package rename.
    """
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def run_scrape(args):
    """Collect listings → car_scraper/data/raw/*.csv"""
    # The scrapers resolve config.json and data/raw relative to their own
    # directory, so run this stage from there and restore the cwd afterwards.
    previous = Path.cwd()
    sys.path.insert(0, str(SCRAPER_DIR))
    os.chdir(SCRAPER_DIR)
    try:
        scraper_main = _load(SCRAPER_DIR / "main.py", "car_scraper_main")
        sites = args.site
        if not sites:
            import json
            try:
                sites = json.loads((SCRAPER_DIR / "config.json").read_text(encoding="utf-8")).get("sites")
            except Exception:
                sites = None
        scraper_main.main(sites)
    finally:
        os.chdir(previous)
        sys.path.remove(str(SCRAPER_DIR))


def run_dashboard(args):
    """Clean the scraped CSVs → dashboard/<dataset>.json"""
    builder = _load(DASHBOARD_DIR / "build_dashboard.py", "build_dashboard")
    if args.dataset not in builder.DATASETS:
        raise SystemExit(f"Unknown dataset '{args.dataset}'. "
                         f"Available: {', '.join(sorted(builder.DATASETS))}")
    dataset = builder.DATASETS[args.dataset]
    builder.build(
        prefixes=dataset["prefixes"],
        output_file=DASHBOARD_DIR / dataset["output"],
        **dataset["bounds"],
    )


def run_serve(args):
    """Serve dashboard/ over HTTP (it fetches its JSON, so file:// won't do)."""
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    handler = partial(SimpleHTTPRequestHandler, directory=str(DASHBOARD_DIR))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"\n  Dashboard → http://localhost:{args.port}\n  Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Stopped.")


RUNNERS = {"scrape": run_scrape, "dashboard": run_dashboard, "serve": run_serve}


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("stages", nargs="*", metavar="STAGE",
                    help=f"stages to run, in order: {', '.join(STAGES)} "
                         f"(default: scrape dashboard)")
    ap.add_argument("--site", action="append",
                    help="scrape stage: run only this site (repeatable)")
    ap.add_argument("--dataset", default="de_market",
                    help="dashboard stage: which named dataset to build")
    ap.add_argument("--port", type=int, default=8000,
                    help="serve stage: port to listen on (default: 8000)")
    args = ap.parse_args()

    stages = args.stages or ["scrape", "dashboard"]
    unknown = [s for s in stages if s not in STAGES]
    if unknown:
        ap.error(f"unknown stage(s): {', '.join(unknown)}. Choose from: {', '.join(STAGES)}")
    # De-duplicate while keeping the order the user asked for.
    seen = set()
    stages = [s for s in stages if not (s in seen or seen.add(s))]

    for stage in stages:
        print(f"\n=== {stage.upper()} ===")
        RUNNERS[stage](args)


if __name__ == "__main__":
    main()
