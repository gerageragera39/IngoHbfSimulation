"""Validate and reconcile local DB OpenBoards board snapshots."""

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime
from hashlib import sha256
import json
import re

from download_ingo_openboards import EVA, LIMIT, dt, text
from timetable_gtfs import BERLIN, DAY, window
from timetable_model import csv_rows


FIRST_DAY = date(2026, 10, 30)
LAST_DAY = date(2026, 11, 26)
BOARD_TYPES = ("arrivals", "departures")
FILES = {
    "all_events.csv": "station_events",
    "all_station_calls.csv": "station_calls",
    "target_calls.csv": "target_calls",
    "candidates_gleis_2_5.csv": "candidate_count",
    "needs_review.csv": "review_count",
    "event_issues.csv": "event_issue_count",
}


def days_between(first, last):
    return [first + DAY * i for i in range((last - first).days + 1)]


def local(value):
    return value.astimezone(BERLIN).isoformat() if value else ""


def track(platform):
    """Parse an Ingolstadt track and optional explicitly labelled platform sectors."""
    match = re.fullmatch(r"(?:Gleis\s+)?([1-7])(?:\s+[A-G](?:\s*[-–]\s*[A-G])?)?",
                         platform.strip(), re.IGNORECASE)
    return int(match[1]) if match else None


def consensus(values):
    candidates = {v for v in values if v is not None and v != ""}
    return next(iter(candidates)) if len(candidates) == 1 else None


@dataclass(frozen=True)
class Event:
    journey: str
    kind: str
    eva: str
    planned: datetime
    reported: datetime | None
    time_type: str
    planned_raw: str
    reported_raw: str
    category: str
    line: str
    number: str
    transport: str
    origin_id: str
    destination_id: str
    via_ids: tuple
    cancelled: bool
    journey_cancelled: bool
    additional: bool
    no_passenger_change: bool
    replacement: bool
    journey_type: str
    administration: str
    links: tuple
    source_id: str
    source: str
    raw_digest: str
    actual_origin_id: str = ""
    actual_destination_id: str = ""
    actual_via_ids: tuple = ()

    @property
    def key(self):
        # Board arrivalId/departureId values are reused across different journeys.
        return self.journey, self.kind, self.eva, self.planned

    @property
    def planned_platform(self):
        return track(self.planned_raw)

    @property
    def reported_platform(self):
        return track(self.reported_raw)

    @property
    def plan_signature(self):
        return self.category, self.line, self.number, self.origin_id, self.destination_id

    @property
    def real(self):
        return (self.time_type == "REAL" and self.reported is not None
                and not self.cancelled and not self.journey_cancelled)


def reference(record):
    return text((record or {}).get("evaNumber"))


def parse_event(entry, kind, source):
    journey = entry.get("journeyInfo") or {}
    transport = entry.get("transport") or {}
    scheduled = dt(entry.get("timeSchedule"))
    if not scheduled or not entry.get("journeyId"):
        raise ValueError("missing journey identifier or scheduled timestamp")
    try:
        reported = dt(entry.get("time"))
    except (ValueError, TypeError, AttributeError):
        reported = None
    via = transport.get("via") or []
    return Event(
        text(entry["journeyId"]), kind, reference(entry), scheduled, reported,
        text(entry.get("timeType")), text((entry.get("platformSchedule") or {}).get("name")),
        text((entry.get("platform") or {}).get("name")), text(transport.get("category")),
        text((transport.get("line") or {}).get("name")), text(transport.get("journeyNumber")),
        text(transport.get("type")), reference(journey.get("origin")),
        reference(journey.get("destination")), tuple(map(reference, via)),
        entry.get("cancelled") is True, journey.get("journeyCancelled") is True,
        entry.get("additional") is True, entry.get("noPassengerChange") is True,
        bool(transport.get("replacementTransport")), text(journey.get("type")),
        text(journey.get("headerAdministrationId")),
        tuple(sorted({text(link.get("journeyID") or link.get("journeyId"))
                      for link in entry.get("travelsWith") or []} - {""})),
        text(entry.get("arrivalId") or entry.get("departureId")), source,
        sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest(),
        reference(journey.get("differingOrigin") or journey.get("origin")),
        reference(journey.get("differingDestination") or journey.get("destination")),
        tuple(reference(stop) for stop in via if not stop.get("cancelled")),
    )


def covers(intervals, start, end):
    if start is None or end is None or start >= end:
        return False
    cursor = start
    for left, right in sorted(intervals):
        if left > cursor:
            break
        cursor = max(right, cursor)
    return cursor >= end


def file_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


@dataclass
class History:
    coverage: list
    issues: list
    snapshots: dict
    names: dict
    platform_fields: set
    raw_entries: int = 0
    parent_entries: int = 0


def read_history(root, first, last):
    history = History([], [], defaultdict(list), {}, set())
    for day in days_between(first, last):
        validate_day(root / day.isoformat(), day, history)
    return history


def validate_day(folder, day, history):
    counts = Counter()
    required_inventory = {}

    def issue(reason, source="", details="", severity="error"):
        history.issues.append(dict(date=day, severity=severity, issue=reason,
                                   source=source, details=details))
        counts[severity] += 1

    manifest = summary = {}
    if not folder.is_dir():
        issue("missing_day")
    else:
        for name in ("manifest.json", "summary.json", *FILES):
            filename = folder / name
            try:
                if name == "manifest.json":
                    manifest = file_json(filename)
                elif name == "summary.json":
                    summary = file_json(filename)
                else:
                    rows = list(csv_rows(filename))
                    required_inventory[name] = len(rows)
                    for row in rows if name == "event_issues.csv" else ():
                        issue("downloader_" + row["reason"], row["source_file"], row["journey_id"], "warning")
                    for row in rows if name == "all_events.csv" else ():
                        if row.get("eva") != EVA or row.get("event_kind") not in BOARD_TYPES:
                            issue("derived_event_station_or_kind", name, row.get("journey_id"))
            except (OSError, ValueError, KeyError) as exc:
                issue("required_file_unreadable", name, str(exc))
    start, end = window(day)
    intervals = defaultdict(list)
    truncated = []
    seen = set()
    capture_start, capture_end = start, end
    if manifest:
        if (manifest.get("status") != "retrieved_for_review" or manifest.get("error")
                or not manifest.get("finished_utc")):
            issue("acquisition_manifest_status", "manifest.json", manifest.get("error") or manifest.get("status"))
        if (manifest.get("date"), str(manifest.get("eva")), manifest.get("timezone")) != (
                day.isoformat(), EVA, "Europe/Berlin"):
            issue("manifest_station_date_or_timezone", "manifest.json")
        try:
            capture_start, capture_end = dt(manifest["capture_start"]), dt(manifest["capture_end"])
            if (dt(manifest["day_start"]), dt(manifest["day_end"])) != (start, end) or not (
                    capture_start <= start < end <= capture_end):
                raise ValueError("manifest does not cover expected local midnight boundaries")
        except (ValueError, KeyError, TypeError) as exc:
            issue("manifest_window", "manifest.json", str(exc))
            capture_start, capture_end = start, end
        if summary != manifest.get("summary"):
            issue("summary_manifest_mismatch", "summary.json")
        for name, key in FILES.items():
            if name in required_inventory and required_inventory[name] != summary.get(key):
                issue("derived_row_count_mismatch", name, f"{required_inventory[name]} != {summary.get(key)}")
        for receipt in manifest.get("requests", []):
            counts["receipts"] += 1
            name = receipt.get("file", "")
            kind = receipt.get("endpoint")
            source = f"{day}/raw/{name}"
            try:
                if not name or name in seen or "/" in name or "\\" in name or kind not in BOARD_TYPES:
                    raise ValueError("duplicate or invalid request receipt")
                seen.add(name)
                left, right = dt(receipt["start"]), dt(receipt["end"])
                if not capture_start <= left < right <= capture_end:
                    raise ValueError("request outside capture range")
                raw = (folder / "raw" / name).read_bytes()
                if sha256(raw).hexdigest() != receipt["sha256"]:
                    raise ValueError("raw checksum mismatch")
                response = json.loads(raw)
                meta = response["meta"]
                if {str(eva) for eva in meta["consideredStopPlaces"]} != {EVA}:
                    raise ValueError("response station differs from station in scope")
                entries = response.get(kind, [])
                if not isinstance(entries, list) or len(entries) != receipt["entries"]:
                    raise ValueError("response entry count mismatch")
                per_type = Counter(e.get("transport", {}).get("type") for e in entries)
                truncation = meta.get("truncatedTransportTypes") or []
                saturated = bool(truncation) or any(n >= LIMIT for n in per_type.values())
                if (saturated != receipt["subdivided"]
                        or truncation != receipt["truncated_types"]):
                    raise ValueError("truncation indicators disagree with receipt")
                if saturated:
                    history.parent_entries += len(entries)
                    truncated.append((kind, left, right, source))
                    continue
                intervals[kind].append((left, right))
                counts["raw_entries"] += len(entries)
                for place in response.get("stopPlaces", []):
                    names = place.get("localizedNames") or []
                    label = next((n["name"] for n in names if n["language"] == "deu"), None)
                    if label:
                        history.names.setdefault(reference(place), label)
                for index, entry in enumerate(entries):
                    entry_source = f"{source}#{index}"
                    if reference(entry) != EVA:
                        issue("event_station_mismatch", entry_source, reference(entry))
                        continue
                    try:
                        event = parse_event(entry, kind, entry_source)
                    except (ValueError, TypeError, AttributeError) as exc:
                        issue("invalid_event", entry_source, str(exc), "warning")
                        continue
                    history.snapshots[event.key].append(event)
                    if entry.get("time") and event.reported is None:
                        issue("invalid_reported_timestamp", entry_source, text(entry.get("time")), "warning")
                    for field, value in (("platformSchedule", event.planned_raw), ("platform", event.reported_raw)):
                        history.platform_fields.update((entry.get(field) or {}).keys())
                        if value and track(value) is None:
                            issue("invalid_" + field, entry_source, value, "warning")
                        if not value:
                            counts["missing_" + field] += 1
                    if event.time_type not in {"REAL", "PREVIEW", "SCHEDULE"} or (
                            event.time_type == "REAL" and event.reported is None):
                        issue("unusable_event_time_type", entry_source, event.time_type, "warning")
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                issue("request_validation_failed", source, str(exc))
        for kind, left, right, source in truncated:
            if not covers(intervals[kind], left, right):
                issue("unresolved_truncation", source)
        for kind in BOARD_TYPES:
            if not covers(intervals[kind], capture_start, capture_end):
                issue("capture_window_gap", kind)
        unlisted = {path.name for path in (folder / "raw").glob("*.json")} - seen
        for filename in sorted(unlisted):
            issue("raw_file_without_receipt", filename, severity="warning")
    status = "missing" if not folder.is_dir() else "failed" if counts["error"] else "validated"
    history.raw_entries += counts["raw_entries"]
    history.coverage.append(dict(
        date=day, status=status, manifest_status=manifest.get("status", ""),
        arrivals_cover_day=covers(intervals["arrivals"], start, end),
        departures_cover_day=covers(intervals["departures"], start, end),
        receipts=counts["receipts"], split_windows=len(truncated), raw_entries=counts["raw_entries"],
        daily_unique_events=required_inventory.get("all_events.csv"),
        daily_station_calls=required_inventory.get("all_station_calls.csv"),
        missing_scheduled_platform_snapshots=counts["missing_platformSchedule"],
        missing_reported_platform_snapshots=counts["missing_platform"],
        acquisition_errors=counts["error"], warnings=counts["warning"],
    ))


@dataclass
class Reconciled:
    event: Event
    snapshots: list
    conflicts: tuple
    planned_platform_source: str
    reported_source: str


def reconcile(snapshots):
    """Resolve material fields without inventing a latest-updated timestamp."""
    result = []
    for versions in snapshots.values():
        first = versions[0]
        own_day = first.planned.astimezone(BERLIN).date().isoformat()
        preferred = sorted(versions, key=lambda e: (not e.source.startswith(own_day), e.source))
        ref = preferred[0]
        real = [e for e in preferred if e.real]
        conflicts = []
        for name, values in {
            "planned_platform": [e.planned_raw for e in preferred],
            "identity": [e.plan_signature for e in preferred],
            "via": [e.via_ids for e in preferred],
            "operational_itinerary": [(e.actual_origin_id, e.actual_destination_id, e.actual_via_ids)
                                      for e in preferred],
            "real_time": [e.reported for e in real],
            "real_platform": [e.reported_raw for e in real],
            "reported_time": [e.reported for e in preferred],
            "reported_platform": [e.reported_raw for e in preferred],
            "time_type": [e.time_type for e in preferred],
            "flags": [(e.cancelled, e.journey_cancelled, e.additional, e.replacement,
                       e.no_passenger_change) for e in preferred],
            "travels_with": [e.links for e in preferred],
        }.items():
            if len(set(values)) > 1:
                conflicts.append(name)
        tracks = {e.planned_platform for e in preferred if e.planned_raw}
        p = next(iter(tracks)) if len(tracks) == 1 else None
        actual_time = consensus(e.reported for e in real)
        actual_tracks = {e.reported_platform for e in real if e.reported_raw}
        actual_track = next(iter(actual_tracks)) if len(actual_tracks) == 1 else None
        if actual_track and not any(e.reported == actual_time and e.reported_platform == actual_track for e in real):
            actual_track = None
        if real:
            actual = next((e for e in real if e.reported == actual_time and e.reported_platform == actual_track),
                          real[0])
        else:
            actual = ref
        plan_source = next((e for e in preferred if p and e.planned_platform == p), None)
        selected = replace(
            ref, planned_raw=plan_source.planned_raw if plan_source else "",
            reported=actual_time if real else actual.reported,
            reported_raw=actual.reported_raw if (not real or actual_track) else "",
            time_type=actual.time_type, cancelled=any(e.cancelled for e in preferred),
            journey_cancelled=any(e.journey_cancelled for e in preferred),
            additional=any(e.additional for e in preferred),
            no_passenger_change=any(e.no_passenger_change for e in preferred),
            replacement=any(e.replacement for e in preferred),
            links=tuple(sorted({link for e in preferred for link in e.links})),
        )
        result.append(Reconciled(selected, preferred, tuple(conflicts),
                                 plan_source.source if plan_source else "",
                                 actual.source if selected.reported else ""))
    return result


def conflict_rows(events):
    for entry in events:
        if not entry.conflicts:
            continue
        for snapshot in entry.snapshots:
            e = entry.event
            yield dict(
                journey_id=e.journey, event_kind=e.kind, eva=e.eva, scheduled_time=local(e.planned),
                conflict_fields="|".join(entry.conflicts), raw_source=snapshot.source,
                raw_digest=snapshot.raw_digest, snapshot_platform_schedule=snapshot.planned_raw,
                snapshot_platform=snapshot.reported_raw, snapshot_time=local(snapshot.reported),
                snapshot_time_type=snapshot.time_type, snapshot_category=snapshot.category,
                snapshot_line=snapshot.line, snapshot_train_number=snapshot.number,
                snapshot_origin_eva=snapshot.origin_id, snapshot_destination_eva=snapshot.destination_id,
                snapshot_via_evas="|".join(snapshot.via_ids),
                snapshot_actual_origin_eva=snapshot.actual_origin_id,
                snapshot_actual_destination_eva=snapshot.actual_destination_id,
                snapshot_actual_via_evas="|".join(snapshot.actual_via_ids),
                snapshot_cancelled=snapshot.cancelled, snapshot_journey_cancelled=snapshot.journey_cancelled,
                snapshot_additional=snapshot.additional, snapshot_replacement=snapshot.replacement,
                snapshot_no_passenger_change=snapshot.no_passenger_change,
                snapshot_travels_with="|".join(snapshot.links), preferred_reference=e.source,
                resolved_planned_platform_source=entry.planned_platform_source,
                resolved_reported_source=entry.reported_source,
                resolved_scheduled_platform=e.planned_raw, resolved_reported_platform=e.reported_raw,
                resolved_reported_time=local(e.reported), resolved_time_type=e.time_type,
                resolved_cancelled=e.cancelled or e.journey_cancelled,
            )
