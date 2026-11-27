"""Join platform evidence and apply external simulation assumptions."""

import csv
from collections import defaultdict
from datetime import date, datetime

from timetable_gtfs import DAY, normalized, platform_code
from timetable_sources import read_json


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def load_evidence(index_path, station, day, feeds, documents):
    if index_path is None:
        return {}, {"status": "disabled"}
    index = read_json(index_path)
    if normalized(index["station"]) != normalized(station) or index["date"] != day.isoformat():
        return {}, {"status": "no_review_for_selected_station_and_date"}
    sources = {**feeds, **documents}
    if not index["source_sha256"] or any(
        (sources.get(key) or {}).get("sha256") != digest for key, digest in index["source_sha256"].items()
    ):
        return {}, {"status": "source_snapshots_missing_or_different",
                    "expected_source_sha256": index["source_sha256"]}
    evidence = defaultdict(list)
    for row in csv_rows(index_path.with_name(index["matches_file"])):
        document = documents.get(row["document"])
        if (not document or not row["page"].isdecimal() or int(row["page"]) < 1
            or not day - DAY <= date.fromisoformat(row["operating_date"]) <= day + DAY
            or row["status"] not in {"matched", "ambiguous", "source_disagreement"}
            or (row["status"] == "matched" and not platform_code(row["platform"]))):
            raise ValueError(f"Invalid station poster evidence for {row['train_id']}")
        evidence[row["train_id"]].append(row)
    return evidence, {"status": "applied", "date": index["date"], "index": index_path.name,
                      "matches_file": index["matches_file"], "row_count": sum(map(len, evidence.values())),
                      "review": index["review"], "completeness_review": index.get("completeness_review", [])}


def apply_evidence(row, matches, documents):
    if not matches:
        return
    # Evidence keys include the original service date even for after-midnight calls.
    departure = datetime.fromisoformat(row["departure_timestamp"]) if row["departure_timestamp"] else None
    dep = departure.strftime("%H:%M") if departure and departure.second == 0 else ""
    for match in matches:
        if (dep != match["gtfs_departure_local"] or row["line"] != match["gtfs_line"]
            or row["next_station"] != match["gtfs_next_station"]
            or row["destination"] != match["gtfs_destination"]
            or departure.date().isoformat() != match["operating_date"]):
            raise ValueError(f"Stale station poster evidence for {row['train_id']}")
    row["platform_evidence"] = " | ".join(
        f"{documents[match['document']]['url']}#page={match['page']} ({match['basis']})" for match in matches
    )
    assignments = {platform_code(match["platform"]) for match in matches if match["status"] == "matched"}
    numbers = {match["train_number"] for match in matches if match["train_number"]}
    if row["train_number"] and numbers and numbers != {row["train_number"]}:
        row.update(planned_platform="", platform_status="conflict", platform_source="conflicting train identities")
        return
    if not row["train_number"] and len(numbers) == 1:
        row["train_number"] = next(iter(numbers))
        row["train_number_source"] = "DB station poster"
    status = row["platform_status"]
    if any(match["status"] != "matched" for match in matches) or len(assignments) > 1 or (
        row["planned_platform"] and assignments != {row["planned_platform"]}
    ) or status == "conflict":
        row.update(planned_platform="", platform_status="conflict", platform_source="conflicting scheduled evidence")
    elif assignments:
        document_names = sorted({match["document"] for match in matches})
        row.update(planned_platform=next(iter(assignments)), platform_status="matched_db_poster",
                   platform_source="DB " + "+".join(document_names))


def duplicates(rows):
    """Only collapse cross-feed calls with matching train identity and full schedules."""
    by_pattern = defaultdict(list)
    for row in rows:
        key = (row["_pattern"], row["scheduled_arrival_min"], row["scheduled_departure_min"])
        by_pattern[key].append(row)
        row["duplicate_status"] = "distinct"
        row["source_aliases"] = ""
    canonical, findings = [], []
    for group in by_pattern.values():
        if len(group) == 1:
            canonical.extend(group)
            continue
        numbers = {row["train_number"] for row in group}
        feeds = {row["source_feed"] for row in group}
        platforms = {row["planned_platform"] for row in group} - {""}
        if (len(feeds) == len(group) and len(numbers) == 1 and "" not in numbers and len(platforms) <= 1
            and not any(row["platform_status"] == "conflict" for row in group)):
            first, *others = sorted(group, key=lambda row: (not row["planned_platform"], row["train_id"]))
            first["source_aliases"] = "|".join(row["train_id"] for row in others)
            first["duplicate_status"] = "confirmed_cross_feed"
            canonical.append(first)
            findings.append(("confirmed_cross_feed", first["train_id"], first["source_aliases"]))
        else:
            canonical.extend(group)
            ids = [row["train_id"] for row in group]
            for row in group:
                row["duplicate_status"] = "ambiguous_exact_schedule"
            findings.append(("ambiguous_exact_schedule", ids[0], "|".join(ids[1:])))

    # Similar times alone are common. Flag partial agreement only across sources and
    # retain all such records unless the full-schedule and identity test above passes.
    by_call = defaultdict(list)
    for row in canonical:
        row_number = row["train_number"]
        line = normalized(row["line"])
        call = (row["scheduled_arrival_min"], row["scheduled_departure_min"],
                normalized(row["previous_station"]), normalized(row["next_station"]))
        by_call[("call", line, call)].append(row)
        if row_number:
            by_call[("identity", row_number, row["observation_timestamp"])].append(row)
    reported = set()
    for group in by_call.values():
        if len({row["source_feed"] for row in group}) < 2:
            continue
        ids = tuple(sorted(row["train_id"] for row in group))
        if ids in reported or all(row["duplicate_status"] == "ambiguous_exact_schedule" for row in group):
            continue
        reported.add(ids)
        if len({row["train_number"] for row in group} - {""}) == len(group):
            continue
        findings.append(("ambiguous_cross_feed_call", ids[0], "|".join(ids[1:])))
        for row in group:
            if row["duplicate_status"] == "distinct":
                row["duplicate_status"] = "ambiguous_cross_feed_call"
    return canonical, findings


def classify_route(row, rules, modeled):
    found = []
    for rule in rules:
        if all(normalized(row[field]) in {normalized(item) for item in values}
               for field, values in rule["match"].items()):
            found.append(rule)
    platform = row["planned_platform"]
    fixed = [platform] if platform in modeled else []
    if len(found) != 1:
        return ("AMBIGUOUS" if found else "UNCLASSIFIED", fixed,
                "fixed_only_ambiguous_route" if found else "fixed_only_unknown_route")
    rule = found[0]
    eligible = [value for value in rule["allowed_platforms"] if value in modeled]
    if not platform:
        return rule["group"], [], "platform_unknown"
    if platform not in modeled:
        return rule["group"], [], "outside_modeled_platforms"
    if platform not in eligible:
        return rule["group"], fixed, "fixed_only_planned_outside_rule"
    if not rule["enable_alternatives"]:
        return rule["group"], fixed, "fixed_only_unverified_model_rule"
    return rule["group"], eligible, rule["basis"]


def apply_model(row, routes, dwell, modeled):
    group, platforms, compatibility = classify_route(row, routes, modeled)
    row.update(route_group=group, allowed_platforms="|".join(platforms), compatibility_status=compatibility)
    row["model_scope"] = ("unknown" if not row["planned_platform"] else "modeled"
                          if row["planned_platform"] in modeled else "other_platform")
    minimum = dwell["categories"].get(row["train_category"], dwell["default_through_minutes"])
    row["min_dwell_min"] = minimum if row["stop_kind"] == "through" else None
    blockers, flags = [], []
    if row["stop_kind"] != "through":
        blockers.append("terminal_occupation_unknown" if row["stop_kind"] in ("originating", "terminating")
                        else "isolated_journey")
    scheduled = row["scheduled_dwell_min"]
    if scheduled is None:
        blockers.append("missing_arrival_or_departure")
    elif scheduled < 0:
        blockers.append("negative_scheduled_dwell")
    elif scheduled == 0:
        flags.append("zero_scheduled_dwell")
        if row["stop_kind"] == "through":
            blockers.append("zero_through_occupation")
    if row["min_dwell_min"] is not None and scheduled is not None and 0 <= scheduled < minimum:
        blockers.append("minimum_dwell_exceeds_schedule")
    if row["model_scope"] == "unknown":
        blockers.append("platform_conflict" if row["platform_status"] == "conflict" else "platform_missing")
    if row["duplicate_status"].startswith("ambiguous"):
        blockers.append("possible_duplicate")
    if row["cohort"] == "boundary_review":
        blockers.append("boundary_handling_required")
    if row["arrival_timestamp"] and row["departure_timestamp"] and row["stop_kind"] == "through" and scheduled > 0:
        row["occupancy_status"] = "scheduled_passenger_dwell"
    else:
        row["occupancy_status"] = "unknown"
    if compatibility.startswith("fixed_only") and row["model_scope"] == "modeled":
        flags.append("compatibility_review")
    if group in {"UNCLASSIFIED", "AMBIGUOUS"}:
        flags.append("route_group_unclassified")
    if row["stop_kind"] == "through" and not dwell["reviewed"]:
        flags.append("provisional_minimum_dwell")
    if not row["train_number"]:
        flags.append("train_number_unavailable")
    if row["cohort"] == "initial":
        flags.append("seed_initial_occupancy")
    row["blocking_reasons"] = "|".join(blockers)
    row["review_flags"] = "|".join(flags)
    row["readiness_status"] = (
        "excluded" if row["_excluded"] or row["model_scope"] == "other_platform"
        else "unresolved" if blockers
        else "provisional" if set(flags) - {"train_number_unavailable"}
        else "ready"
    )
    row["exclusion_reason"] = row["_excluded"] or (
        "outside_modeled_platforms" if row["model_scope"] == "other_platform" else "")
