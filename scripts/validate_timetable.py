"""Audit a prepared bundle and optionally replay source calendars and extraction."""

import argparse
from datetime import date
import sys
from zipfile import BadZipFile

from prepare_timetable import build, exit_code, input_arguments
from timetable_model import csv_rows
from timetable_quality import COLUMNS, read_bundle


def replay(args, meta):
    args.date = date.fromisoformat(meta["selected_date"])
    _, _, station, _, modeled, feeds, documents, evidence, _ = build(args)
    expected = list(csv_rows(args.output_dir / "normalized_timetable.csv"))
    actual = [{field: str(row[field]) if row.get(field) is not None else "" for field in COLUMNS}
              for row in station]
    if actual != expected or set(meta["modeled_platforms"]) != modeled:
        return ["Replay differs from normalized_timetable.csv or its modeled scope"]
    keys = ("sha256", "station_stop_ids", "service_calendar_rules", "passenger_calls_before_deduplication",
            "excluded_nonpassenger_calls")
    if any(meta["feeds"][feed][key] != item[key] for feed, item in feeds.items() for key in keys):
        return ["Replay source archive, station or calendar audit differs"]
    if ({key: item["sha256"] for key, item in documents.items()}
        != {key: item["sha256"] for key, item in meta["station_posters"].items()}
        or evidence["status"] != meta["platform_evidence"]["status"]
    ):
        return ["Replay station poster inputs differ"]
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    input_arguments(parser)
    parser.add_argument("--replay", action="store_true", help="Replay GTFS extraction using the same input arguments")
    try:
        args = parser.parse_args()
        meta, errors = read_bundle(args.output_dir)
        if args.replay and not errors:
            errors.extend(replay(args, meta))
    except (OSError, ValueError, TypeError, KeyError, BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for message in sorted(set(errors + meta["errors"])):
        print(f"ERROR: {message}", file=sys.stderr)
    for message in meta["warnings"]:
        print(f"WARNING: {message}")
    if errors:
        return 1
    print(f"Bundle audit passed{' with source replay' if args.replay else ''}. "
          f"Integration readiness: {meta['readiness']}.")
    return exit_code(meta)


if __name__ == "__main__":
    sys.exit(main())
