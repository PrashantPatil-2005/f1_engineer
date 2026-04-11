#!/usr/bin/env python3
"""
F1 AI Race Engineer — Bulk Ingest Script

Pre-processes F1 race data into chunks + FAISS indices so the app
never hits cold-cache misses at query time.

Usage:
    python scripts/ingest.py                          # ingest everything
    python scripts/ingest.py --years 2024             # just 2024 season
    python scripts/ingest.py --years 2024 --races Monza Monaco  # specific races
    python scripts/ingest.py --years 2024 --force     # rebuild even if cached
    python scripts/ingest.py --years 2024 --dry-run   # preview only
"""

import sys
import time
import argparse
import logging
from pathlib import Path

# Add project root to path so src.* and config.* imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fastf1
from config import config
from src.data_loader.load_race import load_session
from src.data_processor.process_data import process_session, save_chunks, load_chunks
from src.retrieval.retriever import Retriever

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("ingest")


def get_races_for_year(year: int) -> list[str]:
    """Fetch all race event names for a season from FastF1."""
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    races = []
    for _, row in schedule.iterrows():
        if row["EventFormat"] == "testing":
            continue
        races.append(row["EventName"])
    return races


def build_plan(
    years: list[int],
    races: list[str] | None,
    session_type: str,
) -> list[tuple[int, str, str]]:
    """Build the list of (year, race, session_type) triples to process."""
    plan = []
    for year in years:
        if races:
            year_races = races
        else:
            try:
                year_races = get_races_for_year(year)
            except Exception as e:
                logger.warning(f"Could not fetch schedule for {year}: {e}")
                continue
        for race in year_races:
            plan.append((year, race, session_type))
    return plan


def main():
    parser = argparse.ArgumentParser(
        description="F1 Race Engineer — Bulk Ingest",
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=config.SUPPORTED_YEARS,
        help="Years to ingest (default: all supported years)",
    )
    parser.add_argument(
        "--races",
        nargs="+",
        type=str,
        default=None,
        help="Race names to ingest (default: all races for the given years)",
    )
    parser.add_argument(
        "--session",
        type=str,
        default="R",
        help="Session type: R, Q, S, FP1, FP2, FP3 (default: R)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process and rebuild FAISS even if files already exist",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be processed without doing it",
    )
    args = parser.parse_args()

    # ── Header ──
    print()
    print("=" * 60)
    print("  F1 Race Engineer — Bulk Ingest")
    print("=" * 60)

    # ── Build plan ──
    plan = build_plan(args.years, args.races, args.session)

    if not plan:
        print("\nNo sessions to process. Check your --years / --races arguments.")
        return

    unique_years = sorted(set(y for y, _, _ in plan))
    print(f"\nWill process {len(plan)} sessions across {len(unique_years)} year(s)")
    print(f"Years: {unique_years}")
    print(f"Session type: {args.session}")
    if args.force:
        print("Mode: FORCE (rebuilding all)")
    if args.dry_run:
        print("Mode: DRY RUN (no changes)")
    print()

    if args.dry_run:
        for year, race, st in plan:
            print(f"  — {year} {race} ({st})")
        print(f"\n{len(plan)} sessions would be processed.")
        return

    # ── Process each session ──
    retriever = Retriever()
    succeeded = 0
    skipped = 0
    failed = 0
    failures = []

    for i, (year, race, session_type) in enumerate(plan, 1):
        label = f"{year} {race} ({session_type})"
        try:
            # Check if FAISS index already exists
            if not args.force:
                existing = retriever.load_index(year, race, session_type)
                if existing is not None:
                    print(f"  — SKIP  [{i}/{len(plan)}] {label} (already indexed)")
                    skipped += 1
                    continue

            # Load or build chunks
            chunks = load_chunks(year, race, session_type)
            if chunks is None or args.force:
                session_data = load_session(year, race, session_type)
                chunks = process_session(session_data)
                save_chunks(chunks, year, race, session_type)

            # Build FAISS index
            retriever.build_index(chunks, year, race, session_type)

            print(f"  \u2713 OK    [{i}/{len(plan)}] {label} \u2014 {len(chunks)} chunks indexed")
            succeeded += 1

            # Small delay to respect Gemini embedding API rate limits
            if i < len(plan):
                time.sleep(2)

        except Exception as e:
            print(f"  \u2717 FAIL  [{i}/{len(plan)}] {label}: {e}")
            failed += 1
            failures.append(label)

    # ── Summary ──
    print()
    print("=" * 60)
    print("  Summary")
    print("=" * 60)
    print(f"  Succeeded: {succeeded}")
    print(f"  Skipped:   {skipped}")
    print(f"  Failed:    {failed}")
    if failures:
        print()
        print("  Failed sessions:")
        for f in failures:
            print(f"    \u2717 {f}")
    print()


if __name__ == "__main__":
    main()
