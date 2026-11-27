"""Prepare a full local calendar day of station calls from archived GTFS feeds."""

import argparse
from collections import Counter
from datetime import date
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import BadZipFile
from zoneinfo import ZoneInfoNotFoundError

from timetable_gtfs import DAY, platform_code, read_feed, select_date, window, minutes
from timetable_model import apply_evidence, apply_model, duplicates, load_evidence
from timetable_quality import (COLUMNS, CONFLICT_COLUMNS, DUPLICATE_COLUMNS, SUBSETS,
                               audit_rows, quality_summary, write_csv)
from timetable_report import charts, report
from timetable_sources import CONFIG, RAW, SOURCES, SPEC, TIMETABLE, local_source, provenance, read_json, sha256, write_json


def date_arg(value):
    day = date.fromisoformat(value)
    if day.isoformat() != value:
        raise argparse.ArgumentTypeError("Use YYYY-MM-DD")
    return day


def input_arguments(parser):
    parser.add_argument("--raw-dir", type=Path, default=RAW)
    for key in SOURCES:
        parser.add_argument(f"--{key}", type=Path, metavar="PATH", help=f"Override the {SOURCES[key][0]} path")
    parser.add_argument("--output-dir", type=Path, default=TIMETABLE / "processed")
    parser.add_argument("--station", default="Ingolstadt Hbf", help="Exact GTFS station name")
    parser.add_argument("--fv-station-id", help="Disambiguate the station in the long-distance archive")
    parser.add_argument("--rv-station-id", help="Disambiguate the station in the regional archive")
    parser.add_argument("--date", type=date_arg)
    parser.add_argument("--modeled-platforms", default="2,3,4,5")
    parser.add_argument("--route-config", type=Path, default=CONFIG / "routes.json")
    parser.add_argument("--dwell-config", type=Path, default=CONFIG / "minimum_dwell.json")
    evidence = parser.add_mutually_exclusive_group()
    evidence.add_argument("--platform-evidence", type=Path, default=CONFIG / "station_poster_review.json")
    evidence.add_argument("--no-platform-evidence", dest="platform_evidence", action="store_const", const=None)


def load_configuration(args):
    platforms = [value.strip() for value in args.modeled_platforms.split(",")]
    if not all(platform_code(value) == value and value for value in platforms) or len(set(platforms)) != len(platforms):
        raise ValueError("Supply unique, valid platform values such as 2,3,4,5")
    routes = read_json(args.route_config)["rules"]
    for rule in routes:
        if not rule["group"] or not rule["basis"] or not isinstance(rule["enable_alternatives"], bool):
            raise ValueError(f"Invalid route rule {rule}")
        if not rule["match"] or set(rule["match"]) - {"line", "train_category", "previous_station", "next_station",
                                                    "origin", "destination", "gtfs_direction_id", "stop_kind"}:
            raise ValueError(f"Invalid match fields for route rule {rule['group']}")
        if any(not isinstance(values, list) or not values or not all(isinstance(v, str) for v in values)
               for values in rule["match"].values()):
            raise ValueError(f"Invalid match values for route rule {rule['group']}")
        allowed = rule["allowed_platforms"]
        if len(allowed) != len(set(allowed)) or any(not value or platform_code(value) != value for value in allowed):
            raise ValueError(f"Invalid allowed platforms for route rule {rule['group']}")
        if rule["enable_alternatives"] and (not allowed or rule["basis"] not in {
            "verified_infrastructure", "reviewed_model_assumption"
        }):
            raise ValueError(f"Enabled alternatives require a recorded review basis for {rule['group']}")
    dwell = read_json(args.dwell_config)
    values = [dwell["default_through_minutes"], *dwell["categories"].values()]
    if not isinstance(dwell["reviewed"], bool) or any(type(value) not in (int, float)
        or not math.isfinite(value) or value < 0 for value in values
    ):
        raise ValueError("Minimum dwell parameters must be finite, non-negative numbers")
    return set(platforms), routes, dwell


def build(args):
    modeled, routes, dwell = load_configuration(args)
    paths = {key: getattr(args, key) or local_source(args.raw_dir, key) for key in SOURCES}
    missing = [f"{paths[key]} (download {SOURCES[key][1]})" for key in ("fv", "rv") if not paths[key].is_file()]
    if missing:
        raise ValueError("Missing required source archive: " + "; ".join(missing))
    for key in ("regel", "aenderung"):
        if getattr(args, key) and not paths[key].is_file():
            raise ValueError(f"Missing specified PDF {paths[key]}")
    feeds = [read_feed(key, paths[key], args.station, getattr(args, f"{key}_station_id")) for key in ("fv", "rv")]
    day, selection = select_date(feeds, args.date)
    feed_metadata = {feed.key: feed.metadata for feed in feeds}
    documents = {key: provenance(key, paths[key]) for key in ("regel", "aenderung") if paths[key].is_file()}
    evidence, evidence_metadata = load_evidence(args.platform_evidence, args.station, day, feed_metadata, documents)
    if evidence:
        evidence_path = args.platform_evidence
        evidence_metadata.update(index_sha256=sha256(evidence_path),
                                 matches_sha256=sha256(evidence_path.with_name(evidence_metadata["matches_file"])))

    station, nonpassenger = [], []
    for feed in feeds:
        calls = list(feed.extract(day))
        feed.metadata["passenger_calls_before_deduplication"] = sum(not row["_excluded"] for row in calls)
        feed.metadata["excluded_nonpassenger_calls"] = sum(bool(row["_excluded"]) for row in calls)
        feed.metadata["service_dates_examined_from"] = str(day - feed.lookback * DAY)
        feed.metadata["service_dates_examined_through"] = str(day + DAY)
        feed.metadata["service_calendar_rules"] = dict(Counter(row["calendar_rule"] for row in calls))
        for row in calls:
            row["platform_evidence"] = ""
            if row["_excluded"]:
                row.update(duplicate_status="not_applicable", source_aliases="")
                nonpassenger.append(row)
            else:
                apply_evidence(row, evidence.pop(row["train_id"], []), documents)
                station.append(row)
    if evidence:
        raise ValueError(f"Station poster evidence references deleted or out-of-window calls: {sorted(evidence)}")
    station, duplicate_findings = duplicates(station)
    for row in station + nonpassenger:
        apply_model(row, routes, dwell, modeled)
    station.sort(key=lambda row: (row["_sort"], row["train_id"]))
    nonpassenger.sort(key=lambda row: (row["_sort"], row["train_id"]))
    return day, selection, station, nonpassenger, modeled, feed_metadata, documents, evidence_metadata, duplicate_findings


def prepare(args):
    day, selection, station, nonpassenger, modeled, feeds, documents, evidence, duplicate_findings = build(args)
    start, end = window(day)
    length = minutes(end - start)
    counts, intervals, conflicts, dwell_values = quality_summary(station, nonpassenger, length)
    errors = audit_rows(station, day, modeled)
    if nonpassenger:
        errors.extend(audit_rows(nonpassenger, day, modeled))
    warnings, blockers = [], []
    if evidence["status"] != "applied":
        warnings.append("No reviewed DB station poster evidence was applicable to these inputs.")
    if counts["unknown_platforms"]:
        blockers.append(f"{counts['unknown_platforms']} calls have unknown or conflicting platforms.")
    scoped = [row for row in station if row["model_scope"] == "modeled"]
    unresolved_scoped = sum(bool(row["blocking_reasons"]) for row in scoped)
    if unresolved_scoped:
        blockers.append(f"{unresolved_scoped} known modeled-platform calls have blocking issues.")
    if counts["fixed_only_modeled"]:
        blockers.append(f"{counts['fixed_only_modeled']} modeled-platform calls need compatibility review.")
    provisional_dwell = sum("provisional_minimum_dwell" in row["review_flags"] for row in scoped)
    if provisional_dwell:
        blockers.append(f"{provisional_dwell} modeled-platform calls use a provisional minimum dwell.")
    if counts["modeled_occupancy_conflicts"]:
        blockers.append(f"{counts['modeled_occupancy_conflicts']} pairs overlap on modeled platforms.")
    if evidence.get("completeness_review"):
        blockers.append(f"{len(evidence['completeness_review'])} DB poster entries need a GTFS completeness review.")
    if counts["scheduled_occupancy_conflicts"] > counts["modeled_occupancy_conflicts"]:
        warnings.append("Published through intervals also overlap on other platforms.")
    if counts["initial_occupancy"]:
        blockers.append("The initial-occupancy cohort needs a Phase 2.2 initialization decision.")
    if not counts["timetable_rows"]:
        blockers.append("No main-day call currently meets the modeled timetable export criteria.")
    if any(feed["exact_duplicate_stop_times"] for feed in feeds.values()):
        warnings.append("Identical duplicate stop_time rows were collapsed and counted in the source audit.")
    if counts["by_review_flag"].get("train_number_unavailable"):
        warnings.append("Some passenger train numbers are unavailable. Deterministic source IDs are retained.")
    if counts["unclassified_routes"]:
        warnings.append(f"{counts['unclassified_routes']} calls have an unclassified or ambiguous route group.")
    meta = {
        "schema_version": 1, "readiness": "invalid" if errors else "provisional" if blockers else "ready",
        "integration_ready": not (errors or blockers), "errors": errors, "warnings": blockers + warnings,
        "station": args.station, "timezone": "Europe/Berlin", "selected_date": day.isoformat(),
        "date_selection": selection, "window_start": start.isoformat(), "window_end_exclusive": end.isoformat(),
        "observation_minutes": length, "modeled_platforms": sorted(modeled), "gtfs_specification": SPEC,
        "feeds": feeds, "station_posters": documents, "platform_evidence": evidence,
        "configs": {key: {"file": path.name, "sha256": sha256(path)}
                    for key, path in (("routes", args.route_config), ("minimum_dwell", args.dwell_config))},
        "counts": counts, "duplicate_findings": dict(Counter(item[0] for item in duplicate_findings)),
    }
    files = ["normalized_timetable.csv", *SUBSETS, "duplicate_review.csv", "scheduled_occupancy_conflicts.csv",
             "validation_report.md", "timetable_overview.png", "scheduled_occupancy.png"]
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output, prefix=".prepare-") as staging:
        temporary = Path(staging)
        write_csv(temporary / "normalized_timetable.csv", COLUMNS, station)
        for name, predicate in SUBSETS.items():
            selected = sorted(station + nonpassenger, key=lambda row: (row["_sort"], row["train_id"])) if (
                name == "excluded_trains.csv") else station
            write_csv(temporary / name, COLUMNS, (row for row in selected if predicate(row)))
        write_csv(temporary / "duplicate_review.csv", DUPLICATE_COLUMNS,
                  (dict(zip(DUPLICATE_COLUMNS, row)) for row in duplicate_findings))
        write_csv(temporary / "scheduled_occupancy_conflicts.csv", CONFLICT_COLUMNS, conflicts)
        (temporary / "validation_report.md").write_text(report(meta), encoding="utf-8", newline="\n")
        charts(temporary, meta, intervals, dwell_values)
        meta["output_sha256"] = {name: sha256(temporary / name) for name in files}
        write_json(temporary / "dataset_metadata.json", meta)
        for name in [*files, "dataset_metadata.json"]:
            (temporary / name).replace(output / name)
    return meta


def exit_code(meta):
    return {"ready": 0, "invalid": 1, "provisional": 2}[meta["readiness"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    input_arguments(parser)
    try:
        args = parser.parse_args()
        meta = prepare(args)
    except (OSError, KeyError, ValueError, ImportError, BadZipFile, ZoneInfoNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"{meta['selected_date']} | {meta['counts']['station_stops']} station stops | "
          f"{meta['readiness'].upper()} | {args.output_dir / 'validation_report.md'}")
    return exit_code(meta)


if __name__ == "__main__":
    sys.exit(main())
