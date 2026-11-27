"""Classify OpenBoards station calls and resolve explicitly linked movements."""

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date
from hashlib import sha256
import re

from openboards_history import EVA, consensus, dt, local
from timetable_gtfs import BERLIN, normalized


LINE = re.compile(r"(?:RE|RB)\d+[A-Z]?")
NOT_RAIL = {"BUS", "SEV", "ERSATZBUS", "SCHIENENERSATZVERKEHR"}


def classify(event):
    category, line = (re.sub(r"\s+", "", s.upper()) for s in (event.category, event.line))
    if category in NOT_RAIL or event.replacement:
        return "", "", "replacement_or_nonrail"
    if category == "ICE" and event.transport != "REGIONAL_TRAIN":
        return "ICE", "ICE", ""
    if event.transport != "REGIONAL_TRAIN":
        return "", "", "outside_ice_re_rb"
    if LINE.fullmatch(line):
        return line[:2], line, ""
    if not line and LINE.fullmatch(category):
        return category[:2], category, ""
    if category in {"RE", "RB"} and (not line or re.fullmatch(r"\d+[A-Z]?", line)):
        return category, category + line, "" if line else "regional_line_unresolved"
    return "", "", "regional_identity_unresolved"


class Routes:
    def __init__(self, config, names):
        self.config = config
        self.names = names
        self.station = config["station_eva"]
        self.markers = {normalized(n): c for c, values in config["stations"].items() for n in values}
        self.north = {normalized(n) for n in config["north_direction_markers"]}

    def name(self, eva):
        return self.names.get(eva, eva)

    def side(self, event, endpoint):
        """Use the first local corridor landmark, with a qualified directional fallback."""
        markers = [normalized(self.name(eva)) for eva in (*event.via_ids, endpoint)
                   if eva and eva != self.station]
        hits = [self.markers[m] for m in markers if m in self.markers]
        if hits:
            first = hits[0]
            if first == "NORD_5501":
                first = next((c for c in hits if c != "NORD_5501"), first)
                # A local Ingolstadt Nord call pins the 5501 throat even when
                # more distant through destinations lie on another corridor.
                if first not in {"TREUCHTLINGEN_5501", "N_SFS_5934"}:
                    first = "NORD_5501"
            corridor = "NORD_5501" if first == "TREUCHTLINGEN_5501" else first
            return corridor, first
        if any(marker in self.north for marker in markers):
            return "NORD_5501", "north_itinerary_inferred_upstream_unknown"
        return "", ""

    def resolve_side(self, own, other, endpoint, kind, reported=False):
        snapshots = own.snapshots if own else []
        if not snapshots and other:
            # The other board's via describes the opposite leg.
            snapshots = [replace(other.event, via_ids=(), actual_via_ids=())]
        elif reported and any(e.real for e in snapshots):
            snapshots = [e for e in snapshots if e.real]
        if reported:
            snapshots = [replace(e, via_ids=e.actual_via_ids) for e in snapshots]
        candidates = [self.side(e, endpoint) for e in snapshots]
        landmarks = {basis for _, basis in candidates if basis}
        corridors = {corridor for corridor, _ in candidates if corridor}
        explicit = landmarks - {"north_itinerary_inferred_upstream_unknown"}
        if explicit:
            corridors = {c for c, b in candidates if b in explicit}
        if len(corridors) > 1:
            return "", "conflicting_" + kind + "_corridors:" + "|".join(sorted(corridors))
        if corridors:
            return next(iter(corridors)), "|".join(sorted(explicit or landmarks))
        return "", "unresolved_" + kind + "_corridor"

    def group(self, service, incoming, outgoing):
        key = "|".join((service, incoming, outgoing))
        if key in self.config["groups"]:
            return self.config["groups"][key]
        return f"{service.replace('|', '_')}_{incoming}_TO_{outgoing}" if service and incoming and outgoing else ""

    @staticmethod
    def qualified_pair(incoming, outgoing, a_basis, d_basis):
        if incoming and incoming == outgoing:
            # Same-throat itineraries need explicit evidence on both legs.
            # A remote directional marker alone cannot establish a reversal.
            return not any("inferred" in basis for basis in (a_basis, d_basis))
        return bool(incoming and outgoing)


@dataclass
class Call:
    arrival: object
    departure: object
    stop_kind: str
    category: str
    service: str
    identity_issue: str
    route_group: str
    incoming: str
    outgoing: str
    route_basis: str
    pair_issue: str
    actual_group: str = ""
    actual_incoming: str = ""
    actual_outgoing: str = ""
    actual_route_basis: str = ""

    @property
    def events(self):
        return [v.event for v in (self.arrival, self.departure) if v]

    @property
    def ref(self):
        return self.events[0]

    @property
    def id(self):
        return sha256("|".join((self.ref.journey, *(f"{e.kind}:{e.planned.isoformat()}"
                                                    for e in self.events))).encode()).hexdigest()[:20]

    @property
    def start(self):
        return self.ref.planned

    @property
    def day(self):
        return self.start.astimezone(BERLIN).date()

    @property
    def end(self):
        return self.departure.event.planned if self.departure else None

    @property
    def dwell(self):
        return (self.end - self.start).total_seconds() / 60 if self.arrival and self.departure else None

    @property
    def cancelled(self):
        return any(e.cancelled or e.journey_cancelled for e in self.events)

    @property
    def additional(self):
        return any(e.additional or e.journey_type in {"EXTRA", "REPLACEMENT"} for e in self.events)

    @property
    def planned_platform(self):
        for record in (self.arrival, self.departure):
            if record and (any(s.planned_raw and not s.planned_platform for s in record.snapshots)
                           or len({s.planned_platform for s in record.snapshots if s.planned_platform}) > 1):
                return None
        return consensus(e.planned_platform for e in self.events)

    @property
    def is_planned_through(self):
        return (self.stop_kind == "through" and not self.pair_issue and self.dwell is not None
                and self.dwell >= 0 and bool(self.planned_platform) and not self.additional)

    @property
    def operational(self):
        return (self.stop_kind == "through" and bool(self.actual_group) and not self.identity_issue
                and not self.pair_issue and not self.cancelled
                and not any(e.additional or e.journey_type == "EXTRA" for e in self.events)
                and not any(e.no_passenger_change for e in self.events)
                and (self.dwell is None or self.dwell >= 0))


def make_call(arrival, departure, routes, multiple=False):
    events = [record.event for record in (arrival, departure) if record]
    snapshots = [snapshot for record in (arrival, departure) if record for snapshot in record.snapshots]
    origin = consensus(e.origin_id for e in snapshots)
    destination = consensus(e.destination_id for e in snapshots)
    if origin == destination == routes.station:
        kind = "station_only"
    elif origin == routes.station:
        kind = "originating"
    elif destination == routes.station:
        kind = "terminating"
    elif origin and destination:
        kind = "through"
    else:
        kind = "unknown_endpoints"
    types = {classify(e) for e in snapshots}
    known = {(category, service) for category, service, _ in types if category}
    category, service = next(iter(known)) if len(known) == 1 else ("", "")
    issue = next(iter(types))[2] if len(types) == 1 else ""
    if len(known) > 1 or (known and any(not category for category, _, _ in types)):
        issue = "conflicting_service_identity"
        if arrival and departure:
            a_types = {classify(e) for e in arrival.snapshots}
            d_types = {classify(e) for e in departure.snapshots}
            a_category, a_service, a_issue = classify(arrival.event)
            _, d_service, d_issue = classify(departure.event)
            transition = f"{a_service}|{d_service}"
            if (len(a_types) == len(d_types) == 1 and not (a_issue or d_issue)
                    and transition in routes.config.get("line_transitions", ())):
                category, service, issue = a_category, transition, ""
    elif not known and len(types) > 1:
        issue = "unidentified_conflicting_labels"
    pair_issue = ""
    if multiple:
        pair_issue = "multiple_events_for_journey"
    elif any(len({getattr(e, key) for e in snapshots if getattr(e, key)}) > 1
             for key in ("origin_id", "destination_id", "number")):
        pair_issue = "conflicting_journey_identity"
    actual_group = actual_in = actual_out = actual_basis = ""
    if kind == "through" and category and not issue and not pair_issue:
        incoming, a_basis = routes.resolve_side(arrival, departure, origin, "incoming")
        outgoing, d_basis = routes.resolve_side(departure, arrival, destination, "outgoing")
        group = ""
        if routes.qualified_pair(incoming, outgoing, a_basis, d_basis):
            group = routes.group(service, incoming, outgoing)
        elif incoming and incoming == outgoing:
            d_basis += " (same-throat path unresolved)"
        operating = [e for e in snapshots if e.real] or snapshots
        actual_origin = consensus(e.actual_origin_id or e.origin_id for e in operating)
        actual_dest = consensus(e.actual_destination_id or e.destination_id for e in operating)
        if actual_origin and actual_dest and routes.station not in (actual_origin, actual_dest):
            actual_in, ai_basis = routes.resolve_side(arrival, departure, actual_origin, "incoming", reported=True)
            actual_out, ao_basis = routes.resolve_side(departure, arrival, actual_dest, "outgoing", reported=True)
            actual_basis = f"{ai_basis} -> {ao_basis}"
            day = events[0].planned.astimezone(BERLIN).date()
            if ("N_SFS_5934" in (actual_in, actual_out) and
                    date.fromisoformat(routes.config["closure_start"]) <= day <=
                    date.fromisoformat(routes.config["closure_end"])):
                actual_basis += " (SFS itinerary during closure, path unverified)"
            elif routes.qualified_pair(actual_in, actual_out, ai_basis, ao_basis):
                actual_group = routes.group(service, actual_in, actual_out)
    else:
        incoming = outgoing = a_basis = d_basis = group = ""
    return Call(arrival, departure, kind, category, service, issue, group, incoming, outgoing,
                f"{a_basis} -> {d_basis}" if a_basis or d_basis else "", pair_issue,
                actual_group, actual_in, actual_out, actual_basis)


def make_calls(events, routes):
    journeys = defaultdict(lambda: defaultdict(list))
    for record in events:
        journeys[record.event.journey][record.event.kind].append(record)
    calls = []
    for kinds in journeys.values():
        arrivals = kinds["arrivals"]
        departures = kinds["departures"]
        if len(arrivals) > 1 or len(departures) > 1:
            calls.extend(make_call(a, None, routes, multiple=True) for a in arrivals)
            calls.extend(make_call(None, d, routes, multiple=True) for d in departures)
        else:
            calls.append(make_call(next(iter(arrivals), None), next(iter(departures), None), routes))
    return sorted(calls, key=lambda c: (c.start, c.id))


def event_delay(event):
    return (event.reported - event.planned).total_seconds() / 60 if event.real else None


def call_row(call, routes):
    a = call.arrival.event if call.arrival else None
    d = call.departure.event if call.departure else None
    return dict(
        train_id=call.id, source_journey_id=call.ref.journey, train_number=call.ref.number,
        train_category=call.category, line="|".join(dict.fromkeys(e.line for e in call.events if e.line)),
        normalized_service=call.service,
        original_arrival_category=a.category if a else "", original_departure_category=d.category if d else "",
        original_arrival_line=a.line if a else "", original_departure_line=d.line if d else "",
        original_arrival_train_number=a.number if a else "", original_departure_train_number=d.number if d else "",
        origin=routes.name(call.ref.origin_id), destination=routes.name(call.ref.destination_id),
        arrival_via=" | ".join(map(routes.name, a.via_ids)) if a else "",
        departure_via=" | ".join(map(routes.name, d.via_ids)) if d else "",
        route_group=call.route_group, incoming_corridor=call.incoming, outgoing_corridor=call.outgoing,
        route_basis=call.route_basis, stop_kind=call.stop_kind, service_date=call.day,
        actual_route_group=call.actual_group, actual_incoming_corridor=call.actual_incoming,
        actual_outgoing_corridor=call.actual_outgoing, actual_route_basis=call.actual_route_basis,
        planned_platform=call.planned_platform, scheduled_arrival=local(a.planned) if a else "",
        scheduled_departure=local(d.planned) if d else "", scheduled_dwell_min=call.dwell,
        scheduled_arrival_platform=a.planned_platform if a else "",
        scheduled_departure_platform=d.planned_platform if d else "",
        arrival_platform_source=a.planned_raw if a else "", departure_platform_source=d.planned_raw if d else "",
        arrival_reported_time=local(a.reported) if a else "", departure_reported_time=local(d.reported) if d else "",
        arrival_time_type=a.time_type if a else "", departure_time_type=d.time_type if d else "",
        arrival_reported_platform=a.reported_platform if a else "",
        departure_reported_platform=d.reported_platform if d else "",
        arrival_cancelled=a.cancelled if a else "", departure_cancelled=d.cancelled if d else "",
        journey_cancelled=any(e.journey_cancelled for e in call.events),
        scheduled_cancelled=call.cancelled, additional_or_extra=call.additional,
        journey_type=call.ref.journey_type, administration=call.ref.administration,
        replacement_transport=any(e.replacement for e in call.events),
        linked_journey_ids="|".join(sorted({link for e in call.events for link in e.links})),
        identity_issue=call.identity_issue, pair_issue=call.pair_issue,
        arrival_source=a.source if a else "", departure_source=d.source if d else "",
        arrival_scheduled_platform_source=call.arrival.planned_platform_source if a else "",
        departure_scheduled_platform_source=call.departure.planned_platform_source if d else "",
        arrival_reported_source=call.arrival.reported_source if a else "",
        departure_reported_source=call.departure.reported_source if d else "",
    )


def exact_movement(a, b):
    if len(a.events) != 2 or len(b.events) != 2 or a.cancelled or b.cancelled:
        return False
    return all(x.real and y.real and x.reported_platform and x.planned_platform
               and (x.planned, x.reported, x.planned_platform, x.reported_platform, x.origin_id,
                    x.destination_id, x.via_ids) ==
               (y.planned, y.reported, y.planned_platform, y.reported_platform, y.origin_id,
                y.destination_id, y.via_ids)
               for x, y in zip(a.events, b.events))


def review_linked_calls(calls, gtfs, focus_day):
    """Treat reciprocal regular/extra links with identical full movements as one occupancy."""
    by_journey = defaultdict(list)
    for call in calls:
        by_journey[call.ref.journey].append(call)
    focus_numbers = [("1507", "2799"), ("1502", "29004"), ("1080", "2852")]
    reviewed, omitted = [], set()
    for extra in calls:
        if extra.category != "ICE" or extra.ref.journey_type != "EXTRA":
            continue
        for link in sorted({link for e in extra.events for link in e.links}):
            for regular in by_journey[link]:
                if regular.ref.journey_type != "REGULAR" or regular.category != "ICE":
                    continue
                reciprocal = (len(extra.events) == len(regular.events) == 2
                              and all(regular.ref.journey in e.links for e in extra.events)
                              and all(extra.ref.journey in e.links for e in regular.events))
                same_movement = exact_movement(regular, extra)
                accepted = reciprocal and same_movement
                if accepted:
                    omitted.add(extra.id)
                reviewed.append(link_review(regular, extra, gtfs, reciprocal, same_movement, accepted))
    for original, possible_extra in focus_numbers:
        if any(r["service_date"] == focus_day and r["regular_train_number"] == original
               and r["other_train_number"] == possible_extra for r in reviewed):
            continue
        a = next((c for c in calls if c.day == focus_day and c.ref.number == original), None)
        b = next((c for c in calls if c.day == focus_day and c.ref.number == possible_extra), None)
        row = link_review(a, b, gtfs, False, bool(a and b and exact_movement(a, b)), False)
        row.update(service_date=focus_day, regular_train_number=original, other_train_number=possible_extra)
        reviewed.append(row)
    return reviewed, omitted


def link_review(regular, other, gtfs, reciprocal, same_movement, accepted):
    def matches(call):
        if not call:
            return ""
        return "|".join(r["train_id"] for r in gtfs if r["train_category"] == "ICE"
                        and r["train_number"] == call.ref.number and call.arrival and call.departure
                        and dt(r["arrival_timestamp"]) == call.start and dt(r["departure_timestamp"]) == call.end)

    result = dict(
        service_date=(regular or other).day if regular or other else "",
        reciprocal_arrival_and_departure_links=reciprocal, identical_full_movement=same_movement,
        decision="one_platform_occupation_keep_regular" if accepted else "unconfirmed_keep_source_records",
        rationale=("REGULAR and EXTRA are linked on both boards with identical itinerary, scheduled and REAL "
                   "times, and scheduled and reported platforms. One modeled occupation. Physical consist "
                   "and replacement status remain unspecified by the source." if accepted else
                   "Insufficient linked-movement evidence to collapse distinct journey IDs."),
        regular_gtfs_exact_train_number_and_times=matches(regular),
        other_gtfs_exact_train_number_and_times=matches(other),
    )
    for label, call in (("regular", regular), ("other", other)):
        result.update({
            label + "_train_number": call.ref.number if call else "",
            label + "_journey_id": call.ref.journey if call else "",
            label + "_journey_type": call.ref.journey_type if call else "",
            label + "_administration": call.ref.administration if call else "",
            label + "_scheduled_arrival": local(call.start) if call and call.arrival else "",
            label + "_scheduled_departure": local(call.end) if call else "",
            label + "_cancelled": call.cancelled if call else "",
            label + "_additional_flag": any(e.additional for e in call.events) if call else "",
            label + "_replacement_transport_flag": any(e.replacement for e in call.events) if call else "",
            label + "_sources": "|".join(e.source for e in call.events) if call else "",
        })
    return result
