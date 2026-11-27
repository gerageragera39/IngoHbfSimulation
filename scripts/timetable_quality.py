"""Summarize scheduled passenger calls and audit the exported dataset."""

from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import math
from statistics import mean, median

from timetable_gtfs import (BERLIN, UTC, WEEKDAYS, boundary_status, gtfs_anchor, minutes,
                            observation_event, platform_code, service_seconds, stable_id, window)
from timetable_model import csv_rows
from timetable_sources import read_json, sha256


COLUMNS = (
    "train_id source_trip_id train_number train_category line origin destination previous_station next_station "
    "route_group scheduled_arrival_min scheduled_departure_min scheduled_dwell_min planned_platform "
    "allowed_platforms min_dwell_min service_date source_feed source_service_id source_route_id source_route_type "
    "source_stop_id stop_sequence gtfs_service_date calendar_rule gtfs_arrival_time gtfs_departure_time "
    "arrival_timestamp departure_timestamp observation_timestamp operator headsign gtfs_direction_id trip_short_name "
    "train_number_source stop_kind platform_status platform_source platform_evidence compatibility_status "
    "boundary_status cohort occupancy_status model_scope duplicate_status source_aliases readiness_status "
    "blocking_reasons review_flags exclusion_reason"
).split()
SUBSETS = {
    "timetable.csv": lambda row: row["cohort"] == "main_day" and row["readiness_status"] in ("ready", "provisional"),
    "unresolved_records.csv": lambda row: bool(row["blocking_reasons"]),
    "excluded_trains.csv": lambda row: bool(row["exclusion_reason"]),
    "initial_occupancy.csv": lambda row: row["cohort"] == "initial" and row["model_scope"] != "other_platform",
    "route_mapping_review.csv": lambda row: "compatibility_review" in row["review_flags"].split("|"),
}
CONFLICT_COLUMNS = ("platform", "first_train_id", "second_train_id", "overlap_start_min", "overlap_end_min",
                    "overlap_min")
DUPLICATE_COLUMNS = ("status", "first_train_id", "other_train_ids")


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def scheduled_occupancy(rows, length):
    intervals = defaultdict(list)
    for row in rows:
        if not row["planned_platform"] or row["occupancy_status"] != "scheduled_passenger_dwell":
            continue
        start = max(0, row["scheduled_arrival_min"])
        end = min(length, row["scheduled_departure_min"])
        if start < end:
            intervals[row["planned_platform"]].append((start, end, row["train_id"]))
    busy, conflicts = {}, []
    for platform, spans in sorted(intervals.items()):
        spans.sort()
        active = []
        covered_until = 0
        occupied = 0
        for start, end, key in spans:
            active = [(left, right, train) for left, right, train in active if right > start]
            for _, right, train in active:
                stop = min(right, end)
                conflicts.append(dict(zip(CONFLICT_COLUMNS, (
                    platform, train, key, start, stop, round(stop - start, 6)))))
            active.append((start, end, key))
            occupied += max(0, end - max(start, covered_until))
            covered_until = max(covered_until, end)
        busy[platform] = round(occupied, 6)
    return intervals, busy, conflicts


def dwell_statistics(values):
    if not values:
        return {}
    return {"count": len(values), "min": min(values), "mean": round(mean(values), 3),
            "median": median(values), "max": max(values), "zero": values.count(0),
            "below_legacy_three_minutes": sum(value < 3 for value in values)}


def quality_summary(rows, nonpassenger, length):
    intervals, busy, conflicts = scheduled_occupancy(rows, length)
    hour_counts = Counter(datetime.fromisoformat(row["observation_timestamp"]).hour
                          for row in rows if row["cohort"] == "main_day" and row["observation_timestamp"])
    scopes = Counter(row["model_scope"] for row in rows)
    through = [row["scheduled_dwell_min"] for row in rows if row["stop_kind"] == "through"
               and row["scheduled_dwell_min"] is not None and row["scheduled_dwell_min"] >= 0]
    resolved = scopes["modeled"] + scopes["other_platform"]
    modeled = {row["planned_platform"] for row in rows if row["model_scope"] == "modeled"}
    counts = {
        "station_stops": len(rows), "main_day_stops": sum(row["cohort"] == "main_day" for row in rows),
        "platform_resolved": resolved, "platform_coverage_pct": round(100 * resolved / len(rows), 2) if rows else 0,
        "modeled_platforms": scopes["modeled"], "other_platforms": scopes["other_platform"],
        "unknown_platforms": scopes["unknown"],
        "platform_conflicts": sum(row["platform_status"] == "conflict" for row in rows),
        "unknown_occupancy": sum(row["occupancy_status"] == "unknown" for row in rows),
        "fixed_only_modeled": sum(SUBSETS["route_mapping_review.csv"](row) for row in rows),
        "unclassified_routes": sum(row["route_group"] in {"UNCLASSIFIED", "AMBIGUOUS"} for row in rows),
        "unresolved_records": sum(SUBSETS["unresolved_records.csv"](row) for row in rows),
        "excluded_trains": sum(SUBSETS["excluded_trains.csv"](row) for row in rows) + len(nonpassenger),
        "nonpassenger_exclusions": len(nonpassenger),
        "initial_occupancy": sum(SUBSETS["initial_occupancy.csv"](row) for row in rows),
        "initial_occupancy_all_platforms": sum(row["cohort"] == "initial" for row in rows),
        "previous_service_date": sum(row["gtfs_service_date"] < row["service_date"] for row in rows),
        "next_service_date": sum(row["gtfs_service_date"] > row["service_date"] for row in rows),
        "ready_main_day": sum(row["cohort"] == "main_day" and row["readiness_status"] == "ready" for row in rows),
        "provisional_main_day": sum(row["cohort"] == "main_day" and row["readiness_status"] == "provisional" for row in rows),
        "timetable_rows": sum(SUBSETS["timetable.csv"](row) for row in rows),
        "scheduled_occupancy_conflicts": len(conflicts),
        "modeled_occupancy_conflicts": sum(r["platform"] in modeled for r in conflicts),
        "hourly_main_day_stops": {f"{hour:02}": hour_counts[hour] for hour in range(24)},
        "peak_local_hours": [f"{hour:02}:00" for hour in sorted(hour_counts)
                             if hour_counts[hour] == max(hour_counts.values())],
        "by_platform": dict(Counter(row["planned_platform"] or "Unknown" for row in rows)),
        "by_category": dict(Counter(row["train_category"] for row in rows)),
        "by_line": dict(Counter(row["line"] or "Unknown" for row in rows)),
        "by_route_group": dict(Counter(row["route_group"] for row in rows)),
        "by_stop_kind": dict(Counter(row["stop_kind"] for row in rows)),
        "by_boundary_status": dict(Counter(row["boundary_status"] for row in rows)),
        "by_platform_status": dict(Counter(row["platform_status"] for row in rows)),
        "by_blocking_reason": dict(Counter(value for row in rows for value in row["blocking_reasons"].split("|")
                                          if value)),
        "by_review_flag": dict(Counter(value for row in rows for value in row["review_flags"].split("|") if value)),
        "scheduled_dwell_all_calls_min": dwell_statistics([row["scheduled_dwell_min"] for row in rows
                                                            if row["scheduled_dwell_min"] is not None
                                                            and row["scheduled_dwell_min"] >= 0]),
        "scheduled_dwell_through_min": dwell_statistics(through),
        "scheduled_occupied_minutes": busy,
    }
    return counts, intervals, conflicts, through


def audit_rows(rows, day, modeled):
    errors = []
    start, end = window(day)
    ids = Counter(row["train_id"] for row in rows)
    errors.extend(f"Duplicate train_id {key}" for key, count in ids.items() if not key or count > 1)
    for row in rows:
        key = row["train_id"]
        try:
            if any(row[field] in ("", None) for field in (
                "source_feed", "source_trip_id", "source_service_id", "source_stop_id", "stop_sequence",
                "calendar_rule", "origin", "destination", "route_group", "train_category"
            )):
                raise ValueError("missing required identity, location or calendar field")
            gtfs_date = date.fromisoformat(row["gtfs_service_date"])
            if (row["service_date"] != day.isoformat()
                or key != stable_id(row["source_feed"], row["source_trip_id"], gtfs_date, int(row["stop_sequence"]))):
                raise ValueError("invalid dates or deterministic identifier")
            if row["calendar_rule"] not in {"calendar_dates:add", f"calendar:{WEEKDAYS[gtfs_date.weekday()]}"}:
                raise ValueError("invalid calendar rule")
            if row["stop_kind"] not in {"through", "terminating", "originating", "isolated"}:
                raise ValueError("invalid stop kind")
            arrival, departure = (datetime.fromisoformat(row[field]).astimezone(UTC) if row[field] else None
                                  for field in ("arrival_timestamp", "departure_timestamp"))
            for point, raw, offset in (
                (arrival, "gtfs_arrival_time", "scheduled_arrival_min"),
                (departure, "gtfs_departure_time", "scheduled_departure_min"),
            ):
                seconds = service_seconds(row[raw])
                if point is None:
                    if seconds is not None or row[offset] not in ("", None):
                        raise ValueError(f"missing timestamp for {raw}")
                elif (seconds is None or seconds != (point - gtfs_anchor(gtfs_date)).total_seconds()
                      or float(row[offset]) != minutes(point - start)):
                    raise ValueError(f"time disagrees with GTFS service clock for {raw}")
            for point, field in ((arrival, "arrival_timestamp"), (departure, "departure_timestamp")):
                if point is not None and row[field] != point.astimezone(BERLIN).isoformat():
                    raise ValueError(f"{field} must use the original Europe/Berlin offset")
            event = observation_event(row["stop_kind"], arrival, departure)
            if row["observation_timestamp"] != (event.astimezone(BERLIN).isoformat() if event else ""):
                raise ValueError("wrong observation timestamp")
            if not (any(start <= point < end for point in (arrival, departure) if point)
                    or (arrival and departure and arrival < start < departure)
                    or (event is None and gtfs_date == day)):
                raise ValueError("outside station observation window")
            boundary = boundary_status(row["stop_kind"], arrival, departure, start, end)
            if row["boundary_status"] != boundary:
                raise ValueError("incorrect boundary status")
            expected_cohort = ("initial" if boundary in {"initial", "initial_and_after_window"} else
                               "main_day" if event and start <= event < end else "boundary_review")
            if row["cohort"] != expected_cohort:
                raise ValueError("incorrect observation cohort")
            if arrival and departure:
                if departure < arrival or float(row["scheduled_dwell_min"]) != minutes(departure - arrival):
                    raise ValueError("invalid scheduled dwell or departure before arrival")
            elif row["scheduled_dwell_min"] not in ("", None):
                raise ValueError("scheduled dwell requires both timestamps")
            planned = row["planned_platform"]
            allowed = row["allowed_platforms"].split("|") if row["allowed_platforms"] else []
            if planned and platform_code(planned) != planned:
                raise ValueError("invalid planned platform value")
            scope = "modeled" if planned in modeled else "other_platform" if planned else "unknown"
            if row["model_scope"] != scope:
                raise ValueError("platform scope mismatch")
            if set(allowed) - modeled or len(allowed) != len(set(allowed)) or (
                (scope == "modeled" and not row["exclusion_reason"] and planned not in allowed)
                or (scope != "modeled" and allowed)
            ):
                raise ValueError("invalid or incompatible allowed platforms")
            if row["min_dwell_min"] not in ("", None) and (
                not math.isfinite(float(row["min_dwell_min"])) or float(row["min_dwell_min"]) < 0
            ):
                raise ValueError("invalid minimum dwell")
            if row["readiness_status"] in ("ready", "provisional") and (
                row["blocking_reasons"] or row["min_dwell_min"] in ("", None)
                or float(row["min_dwell_min"]) > float(row["scheduled_dwell_min"])
                or not planned or row["occupancy_status"] != "scheduled_passenger_dwell"
            ):
                raise ValueError("row status is inconsistent with simulation requirements")
            if scope == "unknown" and not row["exclusion_reason"] and not row["blocking_reasons"]:
                raise ValueError("unknown platform requires review")
        except (TypeError, ValueError, KeyError) as exc:
            errors.append(f"{key}: {exc}")
    if not rows:
        errors.append("No station calls were extracted")
    return errors


def read_bundle(directory):
    meta = read_json(directory / "dataset_metadata.json")
    rows = list(csv_rows(directory / "normalized_timetable.csv"))
    expected_files = {"normalized_timetable.csv", *SUBSETS, "scheduled_occupancy_conflicts.csv",
                      "duplicate_review.csv", "validation_report.md", "timetable_overview.png",
                      "scheduled_occupancy.png"}
    errors = []
    if set(meta["output_sha256"]) != expected_files:
        errors.append("Output checksum inventory does not match expected deliverables")
    for name in sorted(expected_files):
        path = directory / name
        if not path.is_file() or sha256(path) != meta["output_sha256"].get(name):
            errors.append(f"Missing or changed output {name}")
    for name in ["normalized_timetable.csv", *SUBSETS]:
        with (directory / name).open(encoding="utf-8-sig", newline="") as stream:
            if next(csv.reader(stream), []) != COLUMNS:
                errors.append(f"Invalid CSV header in {name}")
    day = date.fromisoformat(meta["selected_date"])
    start, end = window(day)
    if (meta["window_start"], meta["window_end_exclusive"], meta["observation_minutes"]) != (
        start.isoformat(), end.isoformat(), minutes(end - start)
    ):
        errors.append("Observation window does not represent the selected Europe/Berlin calendar day")
    if meta["readiness"] not in {"ready", "provisional", "invalid"} or (
        meta["integration_ready"] != (meta["readiness"] == "ready")
    ):
        errors.append("Inconsistent integration readiness metadata")
    modeled = set(meta["modeled_platforms"])
    errors.extend(audit_rows(rows, day, modeled))
    keys = [row["train_id"] for row in rows]
    ordered = sorted(rows, key=lambda row: (datetime.fromisoformat(row["observation_timestamp"]).astimezone(UTC)
                                           if row["observation_timestamp"] else datetime.max.replace(tzinfo=UTC),
                                           row["train_id"]))
    if keys != [row["train_id"] for row in ordered]:
        errors.append("Normalized timetable is not chronological")
    if len(rows) != meta["counts"]["station_stops"]:
        errors.append("Normalized row count disagrees with the extraction audit")
    extracted = Counter(alias.split(":", 1)[0] for row in rows
                        for alias in [row["train_id"], *filter(None, row["source_aliases"].split("|"))])
    for feed, audit in meta["feeds"].items():
        if extracted[feed] != audit["passenger_calls_before_deduplication"] or not extracted[feed]:
            errors.append(f"Source stop count disagrees with extraction audit for {feed}")
    indexed_rows = {row["train_id"]: row for row in rows}
    others = []
    for name, predicate in SUBSETS.items():
        output = list(csv_rows(directory / name))
        actual = []
        for row in output:
            if name == "excluded_trains.csv" and row["train_id"] not in indexed_rows:
                if row["exclusion_reason"] not in {"non_passenger_rail", "no_passenger_boarding_or_alighting"}:
                    errors.append(f"Unexpected extra excluded record {row['train_id']}")
                others.append(row)
            else:
                actual.append(row)
        if actual != [row for row in rows if predicate(row)]:
            errors.append(f"{name} does not match the normalized timetable")
    if others:
        errors.extend(audit_rows(others, day, modeled))
    for row in rows:
        for column in ("scheduled_arrival_min", "scheduled_departure_min", "scheduled_dwell_min", "min_dwell_min"):
            row[column] = float(row[column]) if row[column] else None
    counts, _, conflicts, _ = quality_summary(rows, others, meta["observation_minutes"])
    if counts != meta["counts"]:
        errors.append("Reported counts disagree with the normalized timetable")
    if meta["readiness"] == "ready" and (
        counts["unknown_platforms"] or counts["fixed_only_modeled"] or counts["provisional_main_day"]
        or counts["initial_occupancy"] or counts["modeled_occupancy_conflicts"]
        or counts["ready_main_day"] != counts["modeled_platforms"] or not counts["timetable_rows"]
    ):
        errors.append("Readiness label ignores unresolved modeled or unknown-platform calls")
    if list(csv_rows(directory / "scheduled_occupancy_conflicts.csv")) != [
        {key: str(value) for key, value in row.items()} for row in conflicts
    ]:
        errors.append("Scheduled occupancy conflicts disagree with the normalized timetable")
    return meta, errors
