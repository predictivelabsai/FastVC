"""Build and inspect FastVC's real-company universe.

Examples:
    python -m scripts.ingest_companies registry --limit 500 --dry-run
    python -m scripts.ingest_companies registry --limit 500 --replace
    python -m scripts.ingest_companies pilot --provider companies_house --limit 5
    python -m scripts.ingest_companies status
"""

from __future__ import annotations

import argparse
import json

from ingestion.pilots import run_quality_pilot
from ingestion.backfill import run_backfill
from ingestion.public_directories import scrape_public_directory
from ingestion.service import (
    load_registry_candidates, replace_company_universe, select_registry_cohort, source_status,
)


def _print(value) -> None:
    print(json.dumps(value, indent=2, default=str, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    registry = commands.add_parser("registry", help="select and load the cached LT/EE/LV cohort")
    registry.add_argument("--registry-dir")
    registry.add_argument("--limit", type=int, default=500)
    registry.add_argument("--dry-run", action="store_true")
    registry.add_argument("--replace", action="store_true")

    pilot = commands.add_parser("pilot", help="run a small provider quality comparison")
    pilot.add_argument("--provider", required=True,
                       choices=["pappers", "scoris", "companies_house", "sirene", "prh"])
    pilot.add_argument("--limit", type=int, default=5)
    pilot.add_argument("--no-persist", action="store_true")

    backfill = commands.add_parser("backfill", help="bulk-discover and upsert real companies")
    backfill.add_argument("--provider", required=True,
                          choices=["pappers", "scoris", "companies_house", "sirene", "prh"])
    backfill.add_argument("--limit", type=int, default=1000)
    backfill.add_argument("--max-credits", type=float)
    backfill.add_argument("--dry-run", action="store_true")

    commands.add_parser("status", help="show ingested provider/source counts")
    directory = commands.add_parser("directory", help="ingest an approved public portfolio page")
    directory.add_argument("--source", required=True, choices=["seedcamp", "startup_wise_guys"])
    directory.add_argument("--limit", type=int, default=100)
    directory.add_argument("--headed", action="store_true")
    directory.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.command == "registry":
        if not args.dry_run and not args.replace:
            parser.error("registry writes require --replace; use --dry-run to inspect")
        candidates = load_registry_candidates(args.registry_dir)
        cohort = select_registry_cohort(candidates, limit=args.limit)
        _print(replace_company_universe(cohort, dry_run=args.dry_run))
    elif args.command == "pilot":
        _print(run_quality_pilot(args.provider, limit=args.limit, persist=not args.no_persist))
    elif args.command == "backfill":
        _print(run_backfill(args.provider, limit=args.limit, max_credits=args.max_credits,
                            dry_run=args.dry_run))
    elif args.command == "directory":
        _print(scrape_public_directory(args.source, limit=args.limit, headed=args.headed,
                                       persist=not args.dry_run))
    else:
        _print(source_status())


if __name__ == "__main__":
    main()
