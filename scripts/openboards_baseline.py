"""Build the scheduled simulation cohort and review it against the local GTFS snapshot."""

from collections import Counter, defaultdict
import re

from openboards_history import dt
from openboards_services import call_row
from timetable_gtfs import minutes, normalized, window
from timetable_quality import dwell_statistics, scheduled_occupancy


TIMETABLE_FIELDS = (
    "train_id source_journey_id train_number train_category line route_group incoming_corridor "
    "outgoing_corridor scheduled_arrival_min scheduled_departure_min scheduled_dwell_min "
    "planned_platform allowed_platforms min_dwell_min service_date scheduled_arrival scheduled_departure"
).split()


def pack(platforms):
    return "|".join(map(str, sorted(platforms)))


def timetable_row(call, routes, start, day, conservative, expanded, dwell_config):
    row = call_row(call, routes)
    minimum = dwell_config["categories"].get(call.category, dwell_config["default_through_minutes"])
    conservative_allowed = conservative.get(call.route_group, set())
    expanded_allowed = expanded.get(call.route_group, set())
    # A known planned assignment is applicable to the individual service even
    # when repeated observations do not support a route-wide alternative.
    exception = call.planned_platform not in conservative_allowed
    if exception:
        conservative_allowed = set()
        expanded_allowed = set()
    row.update(
        route_group=call.route_group or "AMBIGUOUS",
        scheduled_arrival_min=minutes(call.start - start),
        scheduled_departure_min=minutes(call.end - start),
        allowed_platforms=pack(conservative_allowed | {call.planned_platform}),
        allowed_platforms_expanded=pack(expanded_allowed | {call.planned_platform}),
        min_dwell_min=minimum, service_date=day, scheduled_local_call_date=call.day,
        planned_platform_exception=exception,
        platform_exception_basis=("Two scheduled event times and a consistent planned platform; fixed-only "
                                  "in both configurations until route-level evidence supports this assignment."
                                  if exception else ""),
        dwell_review="zero_scheduled_dwell" if call.dwell == 0 else (
            "minimum_exceeds_scheduled_dwell" if minimum > call.dwell else ""),
        occupancy_status="scheduled_passenger_dwell",
    )
    return row


def gtfs_review(gtfs, calls, modeled, routes):
    by_clock = defaultdict(list)
    for call in calls:
        if call.arrival and call.departure and call.category and not call.additional:
            by_clock[call.start, call.end].append(call)
    reviewed = []
    matched = defaultdict(list)
    for row in gtfs:
        category = row["train_category"]
        if category not in {"ICE", "RE", "RB"} or row["stop_kind"] != "through":
            continue
        arrive, depart = dt(row["arrival_timestamp"]), dt(row["departure_timestamp"])
        number, line = row["train_number"], re.sub(r"\s+", "", row["line"].upper())
        platform = row["planned_platform"]
        g_platform = int(platform) if platform.isdigit() else None
        compatible = [c for c in by_clock[arrive, depart]
                      if c.category == category and (category == "ICE" or line in c.service.split("|"))]
        candidates = [c for c in compatible if not number or c.ref.number == number]
        crosswalk = ""
        if not candidates and g_platform and row["platform_status"] == "matched_db_poster":
            for entry in routes.config.get("baseline_schedule_number_crosswalk", ()):
                if (row["service_date"], row["train_id"], number) != (
                        entry["date"], entry["gtfs_train_id"], entry["gtfs_train_number"]):
                    continue
                candidates = [c for c in compatible if c.planned_platform == g_platform
                              and c.ref.journey == entry["openboards_journey_id"]
                              and c.ref.number == entry["openboards_train_number"]
                              and normalized(routes.name(c.ref.origin_id)) == normalized(row["origin"])
                              and normalized(routes.name(c.ref.destination_id)) == normalized(row["destination"])]
                if len(candidates) == 1:
                    crosswalk = entry["basis"]
                    break
        if len(candidates) == 1:
            matched[candidates[0].id].append(row)
        board_platform = candidates[0].planned_platform if len(candidates) == 1 else None
        status = "multiple_exact" if len(candidates) > 1 else "no_exact_openboards_match"
        if len(candidates) == 1:
            if g_platform and board_platform:
                status = (("documented_number_discrepancy_schedule_agrees" if crosswalk else "exact_agree")
                          if g_platform == board_platform else "planned_platform_disagrees")
            else:
                status = "exact_platform_not_comparable"
        reviewed.append(dict(
            gtfs_train_id=row["train_id"], gtfs_train_number=number, gtfs_category=category,
            gtfs_line=row["line"], gtfs_previous_station=row["previous_station"],
            gtfs_next_station=row["next_station"], scheduled_arrival=row["arrival_timestamp"],
            scheduled_departure=row["departure_timestamp"], gtfs_planned_platform=platform,
            gtfs_known_modeled_platform=g_platform in modeled, openboards_planned_platform=board_platform,
            candidate_openboards_train_ids="|".join(c.id for c in candidates),
            candidate_openboards_journey_ids="|".join(c.ref.journey for c in candidates),
            candidate_openboards_train_numbers="|".join(c.ref.number for c in candidates),
            status=status, crosswalk_basis=crosswalk, gtfs_platform_evidence=row["platform_evidence"],
        ))
    return reviewed, matched


def prepare_baseline(calls, baseline, routes, evidence, aliases, gtfs, dwell_config):
    start, end = window(baseline)
    modeled = set(routes.config["modeled_platforms"])
    rows, terminal, excluded, unresolved, initial = [], [], [], [], []
    relevant = [c for c in calls if start <= c.start < end or
                (c.arrival and c.departure and c.start < start <= c.end)]
    review, gtfs_matches = gtfs_review(gtfs, relevant, modeled, routes)
    for call in relevant:
        record = call_row(call, routes)
        if call.stop_kind in {"originating", "terminating", "station_only"} and call.category:
            terminal.append(dict(record, exclusion_reason="terminal_occupancy_not_modeled"))
            continue
        if call.id in aliases:
            excluded.append(dict(record, exclusion_reason="linked_extra_representation"))
            continue
        if not call.category or call.identity_issue:
            if call.identity_issue in {"regional_identity_unresolved", "regional_line_unresolved",
                                       "conflicting_service_identity", "unidentified_conflicting_labels"}:
                unresolved.append(dict(record, review_reason=call.identity_issue, included_in_timetable=False))
            else:
                excluded.append(dict(record, exclusion_reason=call.identity_issue or "outside_service_scope"))
            continue
        if call.additional:
            excluded.append(dict(record, exclusion_reason="additional_extra_or_rail_replacement_overlay"))
            continue
        failures = []
        if call.stop_kind != "through":
            failures.append(call.stop_kind)
        if call.pair_issue:
            failures.append(call.pair_issue)
        if call.dwell is None:
            failures.append("missing_scheduled_event")
        elif call.dwell < 0:
            failures.append("departure_before_arrival")
        if not call.planned_platform:
            failures.append("planned_platform_missing_invalid_or_conflicting")
        if call.planned_platform and call.planned_platform not in modeled:
            excluded.append(dict(record, exclusion_reason="outside_modeled_platforms"))
            if failures:
                unresolved.append(dict(record, review_reason="|".join(failures), included_in_timetable=False))
            continue
        if failures:
            unresolved.append(dict(record, review_reason="|".join(failures), included_in_timetable=False))
            continue

        row = timetable_row(call, routes, start, baseline, evidence["conservative"], evidence["expanded"], dwell_config)
        matches = gtfs_matches[call.id]
        if len(matches) == 1:
            row["supplementary_gtfs_train_id"] = matches[0]["train_id"]
            row["supplementary_gtfs_train_number"] = matches[0]["train_number"]
            if not row["line"]:
                row["line"] = matches[0]["line"]
                row["line_source"] = "exact_supplementary_gtfs"
        row.setdefault("supplementary_gtfs_train_id", "")
        row.setdefault("supplementary_gtfs_train_number", "")
        row.setdefault("line_source", "openboards" if row["line"] else "unavailable")
        if row["planned_platform_exception"] or row["dwell_review"]:
            reasons = ["ambiguous_route_fixed_only" if not call.route_group else
                       "planned_platform_exception"] if row["planned_platform_exception"] else []
            if row["dwell_review"]:
                reasons.append(row["dwell_review"])
            unresolved.append(dict(row, review_reason="|".join(reasons), included_in_timetable=True))

        if call.start < start:
            initial.append(dict(row, boundary_status="departure_at_midnight" if call.end == start else
                                "occupied_at_midnight"))
        else:
            rows.append(dict(row, boundary_status="departure_after_day" if call.end > end else "within_day"))

    intervals, busy, conflicts = scheduled_occupancy(rows + initial, minutes(end - start))
    if len({r["train_id"] for r in rows + initial}) != len(rows) + len(initial):
        raise ValueError("Duplicate train identifier in simulation input")
    for row in rows + initial:
        allowed = {int(p) for p in row["allowed_platforms"].split("|")}
        extra = {int(p) for p in row["allowed_platforms_expanded"].split("|")}
        if not ({row["planned_platform"]} <= allowed <= extra <= modeled):
            raise ValueError("Simulation input compatibility invariant failed")
    additional = {
        "cons": sum("|" in r["allowed_platforms"] for r in rows),
        "expanded": sum("|" in r["allowed_platforms_expanded"] for r in rows),
    }
    metadata = {
        "baseline_date": baseline.isoformat(), "window_start": start.isoformat(), "window_end_exclusive": end.isoformat(),
        "timezone": "Europe/Berlin", "length_minutes": minutes(end - start),
        "modeled_trains": len(rows), "modeled_cancelled_scheduled": sum(r["scheduled_cancelled"] for r in rows),
        "baseline_by_category": dict(Counter(r["train_category"] for r in rows)),
        "baseline_by_route": dict(Counter(r["route_group"] for r in rows)),
        "terminal_services": len(terminal),
        "terminal_services_by_kind": dict(Counter(r["stop_kind"] for r in terminal)),
        "terminal_services_on_modeled_platforms": sum(r["planned_platform"] in modeled for r in terminal),
        "excluded_other": len(excluded), "baseline_review_rows": len(unresolved),
        "unresolved_outside_timetable": sum(not r["included_in_timetable"] for r in unresolved
                                           if r["planned_platform"] in modeled or not r["planned_platform"]),
        "initial_occupancy_rows": len(initial), "initial_trains_in_occupation": sum(
            r["boundary_status"] == "occupied_at_midnight" for r in initial),
        "departures_after_end": sum(r["boundary_status"] == "departure_after_day" for r in rows),
        "planned_platform_exceptions": sum(r["planned_platform_exception"] for r in rows + initial),
        "dwell": dwell_statistics([r["scheduled_dwell_min"] for r in rows]),
        "minimum_dwell_exceeds_schedule": sum(r["min_dwell_min"] > r["scheduled_dwell_min"] for r in rows),
        "negative_dwell_review_count": sum("departure_before_arrival" in r["review_reason"] for r in unresolved),
        "provisional_minimum_dwell_config": dwell_config,
        "scheduled_through_overlap_pairs": len(conflicts), "scheduled_busy_minutes_by_platform": busy,
        "dynamic_reassignment": dict(
            conservative_eligible=additional["cons"], expanded_eligible=additional["expanded"],
            expanded_increases_options=sum(r["allowed_platforms_expanded"] != r["allowed_platforms"] for r in rows),
            conservative_pct=100 * additional["cons"] / len(rows) if rows else None,
            expanded_pct=100 * additional["expanded"] / len(rows) if rows else None,
        ),
        "gtfs_review_counts": dict(Counter(r["status"] for r in review)),
        "gtfs_unmatched_or_disagree_known_modeled_platform": sum(
            r["gtfs_known_modeled_platform"] and r["status"] not in {
                "exact_agree", "documented_number_discrepancy_schedule_agrees"} for r in review),
    }
    return dict(timetable=rows, terminal_services=terminal, excluded_services=excluded,
                unresolved_services=unresolved, initial_occupancy=initial, gtfs_review=review,
                scheduled_occupancy_conflicts=conflicts, metadata=metadata)
