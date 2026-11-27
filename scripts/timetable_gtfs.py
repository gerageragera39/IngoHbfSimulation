"""Extract dated passenger rail calls from static GTFS schedule archives."""

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from io import TextIOWrapper
import json
import re
import unicodedata
from urllib.parse import quote
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from timetable_sources import provenance


BERLIN = ZoneInfo("Europe/Berlin")
UTC = timezone.utc
DAY = timedelta(days=1)
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
TABLE_COLUMNS = {
    "agency": "agency_name agency_timezone",
    "stops": "stop_id stop_name",
    "routes": "route_id route_type",
    "trips": "trip_id route_id service_id",
    "stop_times": "trip_id stop_id stop_sequence arrival_time departure_time",
    "calendar": "service_id start_date end_date " + " ".join(WEEKDAYS),
    "calendar_dates": "service_id date exception_type",
    "frequencies": "trip_id",
}
RAIL_TYPES = {2, *range(100, 118)} - {110}
REPLACEMENT = re.compile(r"\bersatz(bus|verkehr)\b|\b(SEV|replacement bus|rail replacement)\b",
                         re.IGNORECASE)
CATEGORY = re.compile(r"^([A-Za-z]+)(?=\s|\d|$)")
PLATFORM_NAME = re.compile(r"^(.+?)[ ,(]+(?:Gleis|Platform|Track)\s+(\d+[A-Za-z]?)[)]?$",
                           re.IGNORECASE)
PLATFORM_CODE = re.compile(r"\d+[A-Za-z]?")


def normalized(value):
    return "".join(char for char in unicodedata.normalize("NFKD", value.casefold()) if char.isalnum())


def platform_code(value):
    value = value.strip()
    return value.upper() if PLATFORM_CODE.fullmatch(value) else ""


def service_seconds(value):
    if not value:
        return None
    if not re.fullmatch(r"\d+:[0-5]\d:[0-5]\d", value):
        raise ValueError(f"Invalid GTFS time {value!r}")
    hours, minutes, seconds = map(int, value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def gtfs_anchor(day):
    return datetime.combine(day, time(12), BERLIN).astimezone(UTC) - timedelta(hours=12)


def window(day):
    return tuple(datetime.combine(value, time(), BERLIN).astimezone(UTC)
                 for value in (day, day + DAY))


def minutes(delta):
    return round(delta.total_seconds() / 60, 6)


def observation_event(kind, arrival, departure):
    return (departure or arrival) if kind == "originating" else (arrival or departure)


def boundary_status(kind, arrival, departure, start, end):
    if kind != "through" or arrival is None or departure is None or departure < arrival:
        return "unknown_interval"
    if arrival < start < departure:
        return "initial_and_after_window" if departure > end else "initial"
    if arrival < start == departure:
        return "departure_at_start"
    if arrival < end < departure:
        return "after_window"
    if departure == end and arrival < end:
        return "departure_at_end"
    return "within_window"


class Calendar:
    def __init__(self, weekly, exceptions, feed_info):
        self.weekly = {}
        self.exceptions = defaultdict(dict)
        bounds = []
        for row in weekly:
            key = row["service_id"]
            start, end = (date.fromisoformat(row[field]) for field in ("start_date", "end_date"))
            days = tuple(row[weekday] for weekday in WEEKDAYS)
            if key in self.weekly or end < start or set(days) - {"0", "1"}:
                raise ValueError(f"Invalid or duplicate calendar rule for {key}")
            self.weekly[key] = (start, end, days)
            bounds.extend((start, end))
        for row in exceptions:
            key, day, kind = row["service_id"], date.fromisoformat(row["date"]), row["exception_type"]
            if day in self.exceptions[key] or kind not in ("1", "2"):
                raise ValueError(f"Invalid or duplicate calendar exception for {key} on {day}")
            self.exceptions[key][day] = kind
            if kind == "1":
                bounds.append(day)
        if not bounds:
            raise ValueError("No service dates in calendar.txt or calendar_dates.txt")
        self.start = max(min(bounds), date.fromisoformat(feed_info["feed_start_date"])) if (
            feed_info.get("feed_start_date")) else min(bounds)
        self.end = min(max(bounds), date.fromisoformat(feed_info["feed_end_date"])) if (
            feed_info.get("feed_end_date")) else max(bounds)
        if self.end < self.start:
            raise ValueError("GTFS calendar and feed_info validity do not overlap")

    def knows(self, key):
        return key in self.weekly or key in self.exceptions

    def rule(self, key, day):
        if day < self.start or day > self.end:
            return ""
        kind = self.exceptions.get(key, {}).get(day)
        if kind:
            return "calendar_dates:add" if kind == "1" else ""
        default = self.weekly.get(key)
        if default and default[0] <= day <= default[1] and default[2][day.weekday()] == "1":
            return f"calendar:{WEEKDAYS[day.weekday()]}"
        return ""


def table_reader(archive, table, stream):
    reader = csv.reader(stream)
    header = next(reader, [])
    missing = set(TABLE_COLUMNS.get(table, "").split()) - set(header)
    if missing or len(set(header)) != len(header):
        raise ValueError(f"{archive.filename}: invalid {table}.txt header, missing {sorted(missing)}")
    return header, reader


def table_rows(archive, table, optional=False):
    name = table + ".txt"
    if optional and name not in archive.namelist():
        return
    with TextIOWrapper(archive.open(name), encoding="utf-8-sig", newline="") as stream:
        header, reader = table_reader(archive, table, stream)
        for row in reader:
            if len(row) != len(header):
                raise ValueError(f"{archive.filename}: malformed {name} row {reader.line_num}")
            yield dict(zip(header, row))


def indexed(rows, field):
    result = {}
    for row in rows:
        key = row[field]
        if not key or key in result:
            raise ValueError(f"Missing or duplicate {field}: {key!r}")
        result[key] = row
    return result


def station_stops(stops, name, stop_id=None):
    def matches(stop):
        explicit = PLATFORM_NAME.fullmatch(stop["stop_name"])
        return normalized(explicit[1] if explicit else stop["stop_name"]) == normalized(name)

    matched = {key for key, stop in stops.items() if matches(stop)}
    roots = {key for key in matched if stops[key].get("location_type") == "1"}
    if stop_id:
        if stop_id not in stops:
            raise ValueError(f"GTFS station stop ID {stop_id!r} does not exist")
        roots = {stop_id}
    elif len(roots) > 1:
        raise ValueError(f"Ambiguous station {name!r}: {sorted(roots)}. Supply a feed-specific station ID.")
    elif not roots:
        roots = {key for key in matched if not stops[key].get("parent_station")}
        if len(roots) > 1:
            raise ValueError(f"Ambiguous station {name!r}: {sorted(roots)}. Supply a feed-specific station ID.")
    if not roots:
        raise ValueError(f"Could not identify station {name!r}")

    children = defaultdict(list)
    for key, stop in stops.items():
        children[stop.get("parent_station")].append(key)
    selected = set(roots)
    pending = list(roots)
    while pending:
        for key in children[pending.pop()]:
            if key not in selected and stops[key].get("location_type", "") in ("", "0", "4"):
                selected.add(key)
                pending.append(key)
    return roots, selected


def scheduled_platform(stops, stop_id):
    stop = stops[stop_id]
    explicit = PLATFORM_NAME.fullmatch(stop["stop_name"])
    direct = platform_code(stop.get("platform_code", ""))
    named = platform_code(explicit[2]) if explicit else ""
    if direct and named and direct != named:
        return "", "conflict", "GTFS platform_code conflicts with explicit platform name"
    if direct or named:
        return direct or named, "scheduled_gtfs", "GTFS platform_code" if direct else "GTFS explicit stop_name"
    if stop.get("location_type") == "4" and stop.get("parent_station") in stops:
        parent = stops[stop["parent_station"]]
        if parent.get("location_type", "") in ("", "0"):
            direct = platform_code(parent.get("platform_code", ""))
            if direct:
                return direct, "scheduled_gtfs", "GTFS boarding area parent platform_code"
    return "", "unknown", ""


def stable_id(feed, trip, day, sequence):
    return ":".join((feed, quote(trip, safe=""), day.isoformat(), str(sequence)))


@dataclass
class Feed:
    key: str
    calendar: Calendar
    templates: list
    metadata: dict
    lookback: int

    def extract(self, day):
        start, end = window(day)
        for offset in range(-self.lookback, 2):
            gtfs_date = day + offset * DAY
            anchor = gtfs_anchor(gtfs_date)
            for stop in self.templates:
                rule = self.calendar.rule(stop["source_service_id"], gtfs_date)
                if not rule:
                    continue
                arrival, departure = [anchor + timedelta(seconds=value) if value is not None else None
                                      for value in (stop["_arrival"], stop["_departure"])]
                kind = stop["stop_kind"]
                event = observation_event(kind, arrival, departure)
                has_day_event = any(start <= point < end for point in (arrival, departure) if point)
                covers_day_start = arrival is not None and departure is not None and arrival < start < departure
                if not (has_day_event or covers_day_start or (event is None and gtfs_date == day)):
                    continue
                local = lambda timestamp: timestamp.astimezone(BERLIN).isoformat() if timestamp else ""
                relative = lambda timestamp: minutes(timestamp - start) if timestamp else None
                boundary = boundary_status(kind, arrival, departure, start, end)
                yield {
                    **stop, "train_id": stable_id(self.key, stop["source_trip_id"], gtfs_date,
                                                  stop["stop_sequence"]),
                    "gtfs_service_date": gtfs_date.isoformat(), "service_date": day.isoformat(),
                    "calendar_rule": rule, "arrival_timestamp": local(arrival),
                    "departure_timestamp": local(departure), "observation_timestamp": local(event),
                    "scheduled_arrival_min": relative(arrival), "scheduled_departure_min": relative(departure),
                    "scheduled_dwell_min": minutes(departure - arrival) if arrival and departure else None,
                    "boundary_status": boundary,
                    "cohort": "initial" if boundary in {"initial", "initial_and_after_window"} else (
                        "main_day" if event and start <= event < end else "boundary_review"),
                    "_sort": relative(event) if event is not None else float("inf"),
                    "_pattern": ((anchor + timedelta(seconds=stop["_pattern_start"])).isoformat(),
                                 stop["_pattern"]),
                }


def stop_time_pass(archive, station_ids):
    """Two streaming scans keep memory proportional to the station's trips."""
    trip_ids = set()
    for selected in (False, True):
        with TextIOWrapper(archive.open("stop_times.txt"), encoding="utf-8-sig", newline="") as stream:
            header, reader = table_reader(archive, "stop_times", stream)
            stop_col, trip_col = (header.index(field) for field in ("stop_id", "trip_id"))
            for row in reader:
                if len(row) != len(header):
                    raise ValueError(f"{archive.filename}: malformed stop_times.txt row {reader.line_num}")
                if selected:
                    if row[trip_col] in trip_ids:
                        yield dict(zip(header, row))
                elif row[stop_col] in station_ids:
                    trip_ids.add(row[trip_col])


def build_templates(archive, key, stops, station_ids, agencies, routes, trips, calendar):
    journeys = defaultdict(dict)
    exact_duplicates = Counter()
    for row in stop_time_pass(archive, station_ids):
        trip_id, sequence = row["trip_id"], int(row["stop_sequence"])
        if sequence < 0 or row["stop_id"] not in stops or trip_id not in trips:
            raise ValueError(f"{archive.filename}: invalid stop_times record {trip_id}/{sequence}")
        previous = journeys[trip_id].get(sequence)
        if previous is None:
            journeys[trip_id][sequence] = row
        elif previous == row:
            exact_duplicates[trip_id] += 1
        else:
            raise ValueError(f"{archive.filename}: conflicting duplicate stop_times {trip_id}/{sequence}")
    for row in table_rows(archive, "frequencies", optional=True):
        if row["trip_id"] in journeys:
            raise ValueError(f"{archive.filename}: station trip {row['trip_id']} needs frequency expansion")

    def station_name(stop_id):
        stop = stops[stop_id]
        if stop.get("location_type") == "4":
            stop = stops.get(stop.get("parent_station"), stop)
        return stops.get(stop.get("parent_station"), stop)["stop_name"] or stop["stop_name"]

    templates = []
    for trip_id, journey in sorted(journeys.items()):
        trip = trips[trip_id]
        route = routes[trip["route_id"]]
        agency_id = route.get("agency_id") or (next(iter(agencies)) if len(agencies) == 1 else "")
        agency = agencies[agency_id]
        service = trip["service_id"]
        if not calendar.knows(service):
            raise ValueError(f"{archive.filename}: unknown service_id {service} for {trip_id}")
        ordered = [journey[sequence] for sequence in sorted(journey)]
        names = [station_name(row["stop_id"]) for row in ordered]
        times = [tuple(service_seconds(row[field]) for field in ("arrival_time", "departure_time"))
                 for row in ordered]
        pattern_start = min((value for pair in times for value in pair if value is not None), default=0)
        offsets = [tuple(value - pattern_start if value is not None else None for value in pair) for pair in times]
        pattern_data = list(zip(map(normalized, names), offsets))
        pattern = sha256(json.dumps(pattern_data).encode()).hexdigest()
        line = route.get("route_short_name", "")
        label = trip.get("trip_short_name", "").strip()
        category_match = CATEGORY.match(line.strip())
        category = trip.get("train_category") or route.get("train_category") or (
            category_match[1].upper() if category_match else "UNKNOWN")
        number = trip.get("train_number") or (label if label.isdecimal() else "")
        route_type = int(route["route_type"])
        replacement = any(REPLACEMENT.search(value) for value in
                          (line, route.get("route_long_name", ""), agency["agency_name"]))
        for index, row in enumerate(ordered):
            if row["stop_id"] not in station_ids:
                continue
            first, last = index == 0, index == len(ordered) - 1
            kind = "isolated" if first and last else "originating" if first else "terminating" if last else "through"
            planned, status, source = scheduled_platform(stops, row["stop_id"])
            templates.append({
                "source_feed": key, "source_trip_id": trip_id, "source_service_id": service,
                "source_stop_id": row["stop_id"], "stop_sequence": int(row["stop_sequence"]),
                "train_number": number, "train_number_source": "GTFS" if number else "",
                "trip_short_name": label, "train_category": category, "line": line,
                "source_route_id": trip["route_id"], "source_route_type": route_type,
                "operator": agency["agency_name"], "gtfs_direction_id": trip.get("direction_id", ""),
                "headsign": row.get("stop_headsign") or trip.get("trip_headsign", ""),
                "origin": names[0], "destination": names[-1],
                "previous_station": "" if first else names[index - 1],
                "next_station": "" if last else names[index + 1],
                "stop_kind": kind, "gtfs_arrival_time": row["arrival_time"],
                "gtfs_departure_time": row["departure_time"], "planned_platform": planned,
                "platform_status": status, "platform_source": source,
                "_arrival": times[index][0], "_departure": times[index][1],
                "_pattern": pattern, "_pattern_start": pattern_start,
                "_duplicate_source_rows": exact_duplicates[trip_id],
                "_excluded": "non_passenger_rail" if route_type not in RAIL_TYPES or replacement else (
                    "no_passenger_boarding_or_alighting" if row.get("pickup_type") == row.get("drop_off_type") == "1"
                    else ""),
            })
    return templates, exact_duplicates


def read_feed(key, path, station, stop_id=None):
    with ZipFile(path) as archive:
        info = next(table_rows(archive, "feed_info", optional=True), {})
        calendar = Calendar(table_rows(archive, "calendar", optional=True),
                            table_rows(archive, "calendar_dates", optional=True), info)
        stops = indexed(table_rows(archive, "stops"), "stop_id")
        roots, station_ids = station_stops(stops, station, stop_id)
        agencies = indexed(({**row, "agency_id": row.get("agency_id", "") or "_single"}
                            for row in table_rows(archive, "agency")), "agency_id")
        if not agencies or {row["agency_timezone"] for row in agencies.values()} != {"Europe/Berlin"}:
            raise ValueError(f"{path}: expected Europe/Berlin agency timezone")
        routes = indexed(table_rows(archive, "routes"), "route_id")
        trips = indexed(table_rows(archive, "trips"), "trip_id")
        templates, duplicates = build_templates(archive, key, stops, station_ids, agencies, routes, trips, calendar)
        if not any(not row["_excluded"] for row in templates):
            raise ValueError(f"{path}: no passenger rail stops at {station}")
        max_seconds = max((value for row in templates for value in (row["_arrival"], row["_departure"])
                           if value is not None), default=0)
        metadata = {
            **provenance(key, path), "archive_members": sorted(archive.namelist()), "feed_info": info,
            "attributions": list(table_rows(archive, "attributions", optional=True)),
            "valid_from": calendar.start.isoformat(), "valid_through": calendar.end.isoformat(),
            "station_root_ids": sorted(roots), "station_stop_ids": sorted(station_ids),
            "station_stops": [stops[stop] for stop in sorted(station_ids)],
            "station_template_count": len(templates), "exact_duplicate_stop_times": sum(duplicates.values()),
        }
    return Feed(key, calendar, templates, metadata, (max_seconds + 3600) // 86400)


def bavarian_holiday(day):
    # Gregorian computus and statewide holidays. August 15 is avoided conservatively.
    year = day.year
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    weekday = (32 + 2 * e + 2 * i - h - k) % 7
    leap = (a + 11 * h + 22 * weekday) // 451
    month, offset = divmod(h + weekday - 7 * leap + 114, 31)
    easter = date(year, month, offset + 1)
    return (day.month, day.day) in {(1, 1), (1, 6), (5, 1), (8, 15), (10, 3), (11, 1),
                                    (12, 25), (12, 26)} or (day - easter).days in {-2, 1, 39, 50, 60}


def select_date(feeds, requested):
    first = max(feed.calendar.start + feed.lookback * DAY for feed in feeds)
    last = min(feed.calendar.end - DAY for feed in feeds)
    if requested is not None:
        if not first <= requested <= last:
            raise ValueError(f"{requested} lacks overlapping GTFS coverage for adjacent service dates "
                             f"(select {first} through {last})")
        if not all(any(not row["_excluded"] for row in feed.extract(requested)) for feed in feeds):
            raise ValueError(f"{requested}: at least one archive has no in-window passenger rail stops")
        return requested, "Explicit --date within the shared GTFS and adjacent service-date coverage."

    for weekdays in ({1, 2, 3}, {0, 4}):
        for offset in range((last - first).days + 1):
            candidate = first + offset * DAY
            if candidate.weekday() in weekdays and not bavarian_holiday(candidate) and all(
                any(not row["_excluded"] for row in feed.extract(candidate)) for feed in feeds
            ):
                return candidate, ("Earliest usable Tuesday–Thursday in shared GTFS coverage, "
                                   "with Monday or Friday as fallback. Bavarian holidays are skipped.")
    raise ValueError("No shared non-holiday weekday with passenger rail calls in both feeds")
