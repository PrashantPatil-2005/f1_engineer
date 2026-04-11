"""
F1 AI Race Engineer — Bulk Data Ingest Script

Pre-builds all FAISS indices so the app never has cold-cache misses.

Usage:
    python scripts/ingest.py                            # all years, all races
    python scripts/ingest.py --years 2024               # one season
    python scripts/ingest.py --years 2024 --races Monza Monaco
    python scripts/ingest.py --years 2024 --force       # rebuild even if cached
    python scripts/ingest.py --years 2024 --dry-run     # preview only
"""

import sys
import time
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fastf1
from config import config
from src.data_loader.load_race import load_session
from src.data_processor.process_data import process_session, save_chunks, load_chunks
from src.retrieval.retriever import Retriever

logging.basicConfig(
    level=logging.WARNING,  # suppress noisy fastf1 logs
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def get_races_for_year(year: int) -> list[str]:
    """Fetch all race names for a given year using FastF1 schedule."""
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        # Filter out testing events
        races = schedule[schedule["EventFormat"] != "testing"]["EventName"].tolist()
        return races
    except Exception as e:
        print(f"  ✗ Could not fetch schedule for {year}: {e}")
        return []


def ingest_session(
    year: int,
    race: str,
    session_type: str,
    retriever: Retriever,
    force: bool = False,
) -> tuple[str, int]:
    """
    Ingest one session. Returns ("ok", chunk_count), ("skipped", 0), or ("failed", 0).
    """
    # Check if FAISS index already exists
    if not force:
        result = retriever.load_index(year, race, session_type)
        if result is not None:
            return "skipped", 0

    # Load or reuse processed chunks
    chunks = None
    if not force:
        chunks = load_chunks(year, race, session_type)

    if chunks is None:
        session_data = load_session(year, race, session_type)
        chunks = process_session(session_data)
        save_chunks(chunks, year, race, session_type)

    # Build FAISS index
    t_start = time.perf_counter()
    retriever.build_index(chunks, year, race, session_type)
    t_elapsed = time.perf_counter() - t_start
    return "ok", len(chunks)


def main():
    parser = argparse.ArgumentParser(
        description="F1 AI Race Engineer — Bulk Ingest"
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
        help="Race names to ingest (default: all races for given years)",
    )
    parser.add_argument(
        "--session",
        type=str,
        default="R",
        help="Session type to ingest (default: R = Race)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild indices even if they already exist",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be processed without doing it",
    )
    args = parser.parse_args()

    print("\n" + "━" * 52)
    print("  F1 Race Engineer — Bulk Ingest")
    print("━" * 52)

    # Build the full list of (year, race) pairs to process
    plan = []
    for year in args.years:
        if args.races:
            race_list = args.races
        else:
            print(f"  Fetching schedule for {year}...")
            race_list = get_races_for_year(year)
            if not race_list:
                continue
        for race in race_list:
            plan.append((year, race, args.session))

    if not plan:
        print("  Nothing to process. Check your --years and --races arguments.")
        return

    print(f"  Will process {len(plan)} sessions across {len(args.years)} year(s)")
    if args.force:
        print("  --force: rebuilding all indices even if cached")
    if args.dry_run:
        print("  --dry-run: preview only, no files written\n")
        for year, race, session_type in plan:
            print(f"  — {year} {race} ({session_type})")
        print()
        return

    print()

    retriever = Retriever()
    succeeded = []
    skipped = []
    failed = []

    for i, (year, race, session_type) in enumerate(plan, 1):
        label = f"{year} {race} ({session_type})"
        print(f"  [{i}/{len(plan)}] {label}...", end=" ", flush=True)

        try:
            status, chunk_count = ingest_session(year, race, session_type, retriever, args.force)
            if status == "skipped":
                print("— already indexed, skipping")
                skipped.append(label)
            else:
                print(f"✓ done ({chunk_count} chunks)")
                succeeded.append(label)
                # Small delay to avoid rate limits on embedding API
                time.sleep(1)
        except Exception as e:
            print(f"✗ FAILED: {e}")
            failed.append((label, str(e)))

    # Summary
    print()
    print("━" * 52)
    print("  SUMMARY")
    print("━" * 52)
    print(f"  ✓ Succeeded : {len(succeeded)}")
    print(f"  — Skipped   : {len(skipped)}")
    print(f"  ✗ Failed    : {len(failed)}")

    if failed:
        print("\n  Failed sessions:")
        for label, err in failed:
            print(f"    ✗ {label}: {err}")

    if succeeded:
        print()
        print("  Run this to verify retrieval speed:")
        print("  python -c \"")
        print("  import time, sys")
        print("  sys.path.insert(0, '.')")
        print("  from src.retrieval.retriever import Retriever")
        print("  r = Retriever()")
        print("  # load any index that was just built")
        print("  \"")

    print()


if __name__ == "__main__":
    main()
