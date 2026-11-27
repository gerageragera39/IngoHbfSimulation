#!/usr/bin/env python3
"""Validate the archived OpenBoards history and generate the Phase 2.1.2 bundle offline."""

import argparse
from collections import Counter
from datetime import date
from hashlib import sha256
from pathlib import Path
import re

from download_ingo_openboards import dump
from openboards_analysis import LIMITATION, analyze, delay_tables
from openboards_baseline import TIMETABLE_FIELDS, pack, prepare_baseline
from openboards_history import (FIRST_DAY, LAST_DAY, conflict_rows, days_between, file_json,
                                read_history, reconcile)
from openboards_report import legacy_platforms, make_charts, report
from openboards_services import Routes, call_row, make_calls, review_linked_calls
from timetable_gtfs import BERLIN
from timetable_model import csv_rows
from timetable_quality import CONFLICT_COLUMNS, write_csv


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "timetable"


def export_csv(path, rows, required=()):
    rows = list(rows)
    columns = list(dict.fromkeys([*required, *(key for row in rows for key in row)]))
    write_csv(path, columns, rows)


def digest(path):
    return sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def test_record(path, output):
    if path is None:
        return "Use the separate test command to verify this build. This run has no supplied test log."
    log = path.read_text(encoding="utf-8-sig")
    match = re.search(r"^Ran (\d+) tests? in [\d.]+s\s+(.+)$", log, flags=re.MULTILINE)
    if not match:
        raise ValueError("Test log does not contain a unittest summary")
    count, result = match.groups()
    (output / "validation" / "test_results.txt").write_text(log, encoding="utf-8")
    return f"The repository unittest suite ran **{count} tests**. Result **{result}**. [Test log](../validation/test_results.txt)"


def build(args):
    inputs = [args.history, args.route_config, args.dwell_config, args.gtfs_timetable]
    if any(p.resolve() == args.output.resolve() or args.output.resolve() in p.resolve().parents
           for p in inputs) or args.history.resolve() in args.output.resolve().parents:
        raise ValueError("Choose an output directory separate from source data and configuration")
    for folder in ("validation", "compatibility", "delays", "charts", "reports", "timetable"):
        (args.output / folder).mkdir(parents=True, exist_ok=True)
    valid_dir = args.output / "validation"
    settings = file_json(args.route_config)
    dwell = file_json(args.dwell_config)
    dates = days_between(args.first, args.last)
    history = read_history(args.history, args.first, args.last)
    events = reconcile(history.snapshots)
    conflicts = [r for r in events if r.conflicts]
    export_csv(valid_dir / "dataset_coverage.csv", history.coverage)
    export_csv(valid_dir / "acquisition_and_event_issues.csv", history.issues,
               "date severity issue source details".split())
    export_csv(valid_dir / "conflicting_snapshots.csv", conflict_rows(conflicts), (
        "journey_id event_kind eva scheduled_time conflict_fields raw_source raw_digest "
        "snapshot_platform_schedule snapshot_platform snapshot_time snapshot_time_type snapshot_category "
        "snapshot_line snapshot_train_number snapshot_origin_eva snapshot_destination_eva snapshot_via_evas "
        "snapshot_actual_origin_eva snapshot_actual_destination_eva snapshot_actual_via_evas snapshot_cancelled "
        "snapshot_journey_cancelled snapshot_additional snapshot_replacement snapshot_no_passenger_change "
        "snapshot_travels_with preferred_reference resolved_planned_platform_source resolved_reported_source "
        "resolved_scheduled_platform resolved_reported_platform "
        "resolved_reported_time resolved_time_type resolved_cancelled"
    ).split())
    coverage = dict(
        expected_days=len(dates), validated_days=sum(r["status"] == "validated" for r in history.coverage),
        request_receipts=sum(r["receipts"] for r in history.coverage),
        split_windows=sum(r["split_windows"] for r in history.coverage),
        parent_window_entries_excluded=history.parent_entries, raw_event_snapshots=history.raw_entries,
        valid_event_snapshots=sum(len(v) for v in history.snapshots.values()), deduplicated_events=len(events),
        deduplicated_events_in_days=sum(args.first <= r.event.planned.astimezone(BERLIN).date() <= args.last
                                       for r in events),
        duplicate_snapshots=sum(len(v) - 1 for v in history.snapshots.values()),
        material_conflict_keys=len(conflicts), acquisition_issue_counts=dict(Counter(r["issue"] for r in history.issues)),
    )
    dump(valid_dir / "coverage_summary.json", coverage)
    baseline_validated = any(r["date"] == args.baseline and r["status"] == "validated" for r in history.coverage)
    if not baseline_validated or not events:
        print(f"Baseline acquisition could not be validated. See {valid_dir.resolve()}.")
        return 2

    gtfs = (list(csv_rows(args.gtfs_timetable)) if args.gtfs_timetable.is_file() else [])
    gtfs = [r for r in gtfs if r["service_date"] == args.baseline.isoformat()]
    routes = Routes(settings, history.names)
    calls = make_calls(events, routes)
    links, aliases = review_linked_calls(calls, gtfs, args.baseline)
    analysis = analyze(calls, dates, routes, aliases)
    analysis["modeled_platforms"] = settings["modeled_platforms"]
    analysis["date_label"] = f"{args.first.isoformat()} to {args.last.isoformat()}"
    baseline = prepare_baseline(calls, args.baseline, routes, analysis, aliases, gtfs, dwell)
    metadata = baseline["metadata"]
    legacy = legacy_platforms(ROOT / "route_catalog.csv")

    csv_dir = args.output / "compatibility"
    for filename, key in (
        ("scheduled_platform_matrix", "scheduled_matrix"), ("scheduled_platform_usage_by_day", "scheduled_by_day"),
        ("scheduled_route_summary", "scheduled_route_summary"),
        ("observed_platform_matrix", "observed_matrix"), ("observed_platform_usage_by_day", "observed_by_day"),
        ("platform_evidence_records", "platform_records"), ("platform_reassignments", "reassignment_records"),
        ("reassignment_matrix", "reassignment_matrix"), ("reassignment_summary", "reassignment_summary"),
        ("platform_compatibility_evidence", "evidence"),
    ):
        fields = ("train_id", "source_journey_id", "train_number", "observation_quality", "observed_platform",
                  "observation_timestamp", "arrival_delay_min", "departure_delay_min") if key in {
                      "platform_records", "reassignment_records"} else ()
        if key == "reassignment_records":
            fields += ("reassignment_route_group", "original_planned_platform", "final_reported_platform")
        export_csv(csv_dir / f"{filename}.csv", analysis[key], fields)
        if key in {"scheduled_matrix", "observed_matrix"}:
            export_csv(csv_dir / f"{filename}_gleis_2_5.csv",
                       (r for r in analysis[key] if r["platform"] in settings["modeled_platforms"]))

    compatibility_rows = []
    for group, (incoming, outgoing) in analysis["catalog"].items():
        compatibility_rows.append(dict(
            route_group=group, incoming_corridor=incoming, outgoing_corridor=outgoing,
            legacy_platforms=pack(legacy.get(group, ())),
            research_platforms=pack(settings["research_reference_platforms"].get(group, ())),
            conservative=pack(analysis["conservative"].get(group, ())),
            expanded=pack(analysis["expanded"].get(group, ())), limitations=LIMITATION,
        ))
    # Configuration CSVs expose only the selected matrix. The evidence export
    # and research report contain the comparison.
    columns = ("route_group", "incoming_corridor", "outgoing_corridor", "allowed_platforms", "limitations")
    for config in ("conservative", "expanded"):
        write_csv(csv_dir / f"platform_compatibility_{config}.csv", columns,
                  (dict(r, allowed_platforms=r[config]) for r in compatibility_rows))

    export_csv(valid_dir / "route_service_review.csv", analysis["route_review"],
               ("train_id", "source_journey_id", "route_group", "route_basis", "actual_route_basis",
                "identity_issue", "pair_issue"))
    export_csv(valid_dir / "station_call_inventory.csv",
               (dict(call_row(c, routes), linked_extra_alias=c.id in aliases) for c in calls))
    export_csv(valid_dir / "historical_terminal_services.csv",
               (call_row(c, routes) for c in calls if c.day in dates and c.category
                and c.stop_kind in {"originating", "terminating", "station_only"}),
               ("train_id", "source_journey_id", "train_number", "stop_kind"))
    delay_dir = args.output / "delays"
    export_csv(delay_dir / "historical_arrival_delays.csv", analysis["delays"],
               "train_id source_journey_id train_number train_category route_group service_date scheduled_hour "
               "scheduled_arrival reported_arrival arrival_delay_min".split())
    tables = delay_tables(analysis["delays"], dates)
    for name, rows in tables.items():
        export_csv(delay_dir / f"{name}.csv", rows)

    tt_dir = args.output / "timetable"
    output_names = ("timetable", "terminal_services", "excluded_services", "unresolved_services",
                    "initial_occupancy", "gtfs_review", "scheduled_occupancy_conflicts")
    simulation_fields = [
        *TIMETABLE_FIELDS, "allowed_platforms_expanded", "scheduled_local_call_date", "boundary_status",
        "normalized_service", "original_arrival_category", "original_departure_category",
        "original_arrival_line", "original_departure_line", "origin", "destination", "arrival_via",
        "departure_via", "route_basis", "scheduled_cancelled", "planned_platform_exception",
        "platform_exception_basis", "dwell_review", "arrival_source", "departure_source",
        "arrival_scheduled_platform_source", "departure_scheduled_platform_source",
        "supplementary_gtfs_train_id", "supplementary_gtfs_train_number", "line_source",
    ]
    for name in output_names:
        if name in {"timetable", "initial_occupancy"}:
            write_csv(tt_dir / f"{name}.csv", simulation_fields, baseline[name])
            continue
        filename = "gtfs_baseline_review" if name == "gtfs_review" else name
        fields = CONFLICT_COLUMNS if name == "scheduled_occupancy_conflicts" else ()
        if name in {"terminal_services", "excluded_services", "unresolved_services"}:
            fields = ["train_id", "source_journey_id", "train_number", "train_category"]
        elif name == "gtfs_review":
            fields = ("gtfs_train_id", "status")
        export_csv(tt_dir / f"{filename}.csv", baseline[name], fields)
    export_csv(tt_dir / "duplicate_service_review.csv", (r for r in links if r["service_date"] == args.baseline))
    export_csv(valid_dir / "historical_linked_journey_review.csv", links)
    scheduled_calls = [c for c in calls if args.first <= c.day <= args.last and c.category
                       and c.is_planned_through and c.id not in aliases]
    metadata.update(
        first_day=args.first.isoformat(), last_day=args.last.isoformat(), coverage=coverage,
        infrastructure_research="data/timetable/research/platform_compatibility_research.md",
        construction_period={"start": settings["closure_start"], "end_inclusive": settings["closure_end"],
                             "limitation": LIMITATION},
        station_eva=settings["station_eva"], station=settings["station"],
        source_provenance={k: {"file": p.name, "sha256": digest(p)} for k, p in {
            "route_config": args.route_config, "dwell_config": args.dwell_config,
            "supplementary_gtfs_extraction": args.gtfs_timetable, "legacy_routes": ROOT / "route_catalog.csv",
            "infrastructure_research": DATA / "research" / "platform_compatibility_research.md",
        }.items()},
        raw_platform_fields=sorted(history.platform_fields), modeled_platforms=settings["modeled_platforms"],
        min_repeat_days=settings["min_repeat_days"], min_repeat_train_numbers=settings["min_repeat_train_numbers"],
        valid_scheduled_through_calls=len(scheduled_calls),
        cancelled_valid_scheduled_through_calls=sum(c.cancelled for c in scheduled_calls),
        unmapped_valid_scheduled_through_calls=sum(not c.route_group for c in scheduled_calls),
        strong_actual_platform_observations=sum(r["strong_count"] for r in analysis["observed_matrix"]),
        weaker_actual_platform_observations=sum(r["weaker_count"] for r in analysis["observed_matrix"]),
        reassignments=analysis["reassignment_summary"][0],
        reassignments_into_scope_from_other_platforms=sum(
            r["original_planned_platform"] not in settings["modeled_platforms"]
            and r["final_reported_platform"] in settings["modeled_platforms"]
            for r in analysis["reassignment_records"]),
        linked_extra_aliases_historical=len(aliases), historical_delay_summary=tables["delay_summary"][0],
        legacy_platforms=legacy, research_reference_platforms=settings["research_reference_platforms"],
    )
    blockers = []
    if coverage["validated_days"] != coverage["expected_days"]:
        blockers.append("history has incomplete acquisition coverage")
    if metadata["unresolved_outside_timetable"]:
        blockers.append("potentially eligible baseline calls are missing usable planned fields")
    if not gtfs or metadata["gtfs_unmatched_or_disagree_known_modeled_platform"]:
        blockers.append("supplementary GTFS coverage or planned-track agreement needs review")
    if not metadata["modeled_trains"]:
        blockers.append("no baseline trains satisfy the selected operating scope")
    if blockers:
        metadata["readiness"] = "Review required before AnyLogic integration"
        metadata["readiness_detail"] = "Open items include " + ", ".join(blockers) + "."
    else:
        metadata["readiness"] = "Ready for a controlled AnyLogic timetable import"
        metadata["readiness_detail"] = (
            "Use the conservative timetable and its fixed-only exceptions for the through-only closure-period "
            "cohort. Carry scheduled conflicts into the dispatch queue and account for the day boundary. "
            "A station-wide or normal-SFS experiment needs terminal occupation and routing evidence. "
            "The dwell and expanded platform assumptions remain subject to sensitivity analysis."
        )
    metadata["output_csv_sha256"] = {
        str(path.relative_to(args.output)).replace("\\", "/"): digest(path)
        for path in sorted(args.output.glob("*/*.csv"))
    }
    dump(tt_dir / "dataset_metadata.json", metadata)
    test_summary = test_record(args.test_log, args.output)
    (args.output / "reports" / "historical_platform_report.md").write_text(
        report(metadata, analysis, baseline, compatibility_rows, history.issues, links, test_summary),
        encoding="utf-8",
    )
    if not args.no_charts:
        make_charts(args.output / "charts", analysis)
    print(f"{coverage['validated_days']}/{coverage['expected_days']} validated days, "
          f"{metadata['modeled_trains']} baseline trains, "
          f"{metadata['strong_actual_platform_observations']} strong platform observations.")
    print(f"{metadata['readiness']}. Outputs in {args.output.resolve()}")
    return 2 if blockers else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DATA / "openboards")
    parser.add_argument("--first", type=date.fromisoformat, default=FIRST_DAY)
    parser.add_argument("--last", type=date.fromisoformat, default=LAST_DAY)
    parser.add_argument("--baseline", type=date.fromisoformat, default=date(2026, 11, 24))
    parser.add_argument("--route-config", type=Path, default=DATA / "config" / "openboards_history.json")
    parser.add_argument("--dwell-config", type=Path, default=DATA / "config" / "minimum_dwell.json")
    parser.add_argument("--gtfs-timetable", type=Path, default=DATA / "processed" / "normalized_timetable.csv")
    parser.add_argument("--output", type=Path, default=DATA / "historical_analysis")
    parser.add_argument("--test-log", type=Path, help="Optional captured unittest output for the report")
    parser.add_argument("--no-charts", action="store_true")
    args = parser.parse_args()
    if not args.first <= args.baseline <= args.last:
        parser.error("--baseline must be inside --first through --last")
    return build(args)


if __name__ == "__main__":
    raise SystemExit(main())
