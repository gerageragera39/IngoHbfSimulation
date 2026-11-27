"""Compute station platform evidence and historical arrival delay statistics."""

from collections import defaultdict
from itertools import product
from statistics import mean, median, quantiles, stdev

from openboards_history import local
from openboards_services import call_row, event_delay
from timetable_gtfs import BERLIN


TRACKS = tuple(range(1, 8))
LIMITATION = ("Nürnberg–Ingolstadt SFS closure, 2026-10-30 through 2026-12-12. "
              "Evidence applies to the recorded closure-period station movements. "
              "Published itinerary and reported platform carry no official routing authorization.")


def platform_observation(call):
    if not call.operational:
        return None
    real = [e for e in call.events if e.real]
    platforms = [e for e in real if e.reported_platform]
    if len(real) == 2 and real[0].reported > real[1].reported:
        return None
    if len(platforms) == 2 and platforms[0].reported_platform == platforms[1].reported_platform:
        return "strong", platforms[0].reported_platform
    if len(platforms) == 1:
        return "weaker", platforms[0].reported_platform
    return None


def delay_summary(values):
    if not values:
        return dict(count=0, early=0, on_time=0, positive=0, mean_min=None, median_min=None,
                    sample_stddev_min=None, min_min=None, p05_min=None, p25_min=None,
                    p75_min=None, p90_min=None, p95_min=None, p99_min=None, max_min=None)
    q = quantiles(values, n=100, method="inclusive") if len(values) > 1 else values * 99
    return dict(
        count=len(values), early=sum(v < 0 for v in values), on_time=values.count(0),
        positive=sum(v > 0 for v in values), mean_min=mean(values), median_min=median(values),
        sample_stddev_min=stdev(values) if len(values) > 1 else None,
        min_min=min(values), p05_min=q[4], p25_min=q[24], p75_min=q[74],
        p90_min=q[89], p95_min=q[94], p99_min=q[98], max_min=max(values),
    )


def distinct(calls):
    return len({c.day for c in calls}), len({c.ref.number for c in calls if c.ref.number})


def record_examples(calls, max_examples=3):
    ordered = sorted(calls, key=lambda c: (c.start, c.id))
    examples = []
    for call in ordered:
        if all(prior.ref.number != call.ref.number for prior in examples):
            examples.append(call)
        if len(examples) == max_examples:
            break
    return "|".join(f"{c.day}/{c.ref.number or '?'}/{c.id}" for c in examples)


def route_catalog(calls, config):
    catalog = {}
    for rule, group in config["groups"].items():
        _, incoming, outgoing = rule.rsplit("|", 2)
        catalog[group] = (incoming, outgoing)
    for call in calls:
        for key, incoming, outgoing in ((call.route_group, call.incoming, call.outgoing),
                                         (call.actual_group, call.actual_incoming, call.actual_outgoing)):
            if key:
                catalog[key] = incoming, outgoing
    return dict(sorted(catalog.items()))


def compare_compatibility(catalog, scheduled, strong, weaker, changes, config):
    conservative, expanded = defaultdict(set), defaultdict(set)
    rows = []
    for group, (incoming, outgoing) in catalog.items():
        for platform in config["modeled_platforms"]:
            key = (group, platform)
            planned, observed = scheduled[key], strong[key]
            c_days, c_numbers = distinct({c.id: c for c in planned + observed}.values())
            s_days, s_numbers = distinct(planned)
            a_days, a_numbers = distinct(observed)
            repeat = (c_days >= config["min_repeat_days"]
                      and c_numbers >= config["min_repeat_train_numbers"])
            assumption = config["expanded_assumptions"].get(group, {}).get(str(platform), "")
            closure_sfs = "N_SFS_5934" in (incoming, outgoing)
            if closure_sfs:
                repeat = False
                assumption = ""
                status = "CLOSURE_SFS_ITINERARY_ONLY" if planned else "UNKNOWN"
                justification = "The closure-period archive cannot qualify normal SFS platform alternatives."
            elif repeat:
                status = "REPEATED_SCHEDULED_AND_OBSERVED" if planned and observed else (
                    "REPEATED_OBSERVED" if observed else "REPEATED_SCHEDULED")
                justification = "Evidence meets the configured operating-day and train-number thresholds."
            elif planned or observed:
                status = "LIMITED_DIRECT_EVIDENCE"
                justification = ("Direct evidence falls below the configured repeat threshold. "
                                 "A qualifying planned assignment may use a documented train-specific exception.")
            elif weaker[key]:
                status = "WEAK_OBSERVATION_ONLY"
                justification = "Single-event REAL reports are insufficient to authorize a through alternative."
            else:
                status = "UNKNOWN"
                justification = "No qualifying station evidence and no explicit incompatibility finding."
            if repeat:
                conservative[group].add(platform)
            if repeat or assumption:
                expanded[group].add(platform)
            if assumption and not repeat:
                if status == "UNKNOWN":
                    status = "ASSUMED"
                justification += " Expanded only. " + assumption
            rows.append(dict(
                route_group=group, incoming_corridor=incoming, outgoing_corridor=outgoing, platform=platform,
                scheduled_count=len(planned), actual_count=len(observed), weaker_count=len(weaker[key]),
                reassignment_count=len(changes[key]), distinct_observation_days=a_days,
                distinct_train_numbers=a_numbers, distinct_scheduled_days=s_days,
                distinct_scheduled_train_numbers=s_numbers, distinct_direct_evidence_days=c_days,
                distinct_direct_evidence_train_numbers=c_numbers, evidence_status=status,
                conservative_allowed=repeat, expanded_allowed=bool(repeat or assumption),
                expanded_basis="legacy_model_assumption" if assumption and not repeat else "",
                scheduled_examples=record_examples(planned), actual_examples=record_examples(observed),
                justification=justification, limitations=LIMITATION,
            ))
    return rows, conservative, expanded


def analyze(calls, dates, routes, duplicate_aliases):
    catalog = route_catalog(calls, routes.config)
    scheduled, strong, weaker, changes, reassignment, eligible = (defaultdict(list) for _ in range(6))
    platform_records, reassignment_records, delays, route_review = [], [], [], []
    within_history = set(dates)
    for call in calls:
        if call.day not in within_history or call.id in duplicate_aliases:
            continue
        if call.identity_issue or call.pair_issue or (call.category and call.stop_kind == "through"
                                                       and (not call.route_group or not call.actual_group)):
            if call.identity_issue != "outside_ice_re_rb":
                route_review.append(call_row(call, routes))
        if call.is_planned_through and call.route_group:
            scheduled[call.route_group, call.planned_platform].append(call)
        observation = platform_observation(call)
        if observation:
            quality, platform = observation
            group = call.actual_group
            (strong if quality == "strong" else weaker)[group, platform].append(call)
            a = call.arrival.event if call.arrival else None
            d = call.departure.event if call.departure else None
            observation_time = next(e.reported for e in call.events if e.real and e.reported_platform)
            record = dict(call_row(call, routes), observation_quality=quality,
                          observed_platform=platform, observation_timestamp=local(observation_time),
                          arrival_delay_min=event_delay(a) if a else None,
                          departure_delay_min=event_delay(d) if d else None)
            platform_records.append(record)
            if (quality == "strong" and a.planned_platform and a.planned_platform == d.planned_platform
                    and call.planned_platform == a.planned_platform):
                planned = a.planned_platform
                eligible[group].append(call)
                reassignment[group, planned, platform].append(call)
                if planned != platform:
                    changes[group, platform].append(call)
                    reassignment_records.append(dict(record, reassignment_route_group=group,
                                                     original_planned_platform=planned,
                                                     final_reported_platform=platform))
        if (call.category and not call.identity_issue and not call.pair_issue and not call.cancelled
                and not call.additional and not any(e.no_passenger_change for e in call.events)
                and call.arrival and call.stop_kind in {"through", "terminating"}):
            event = call.arrival.event
            delay = event_delay(event)
            if delay is not None and (call.dwell is None or call.dwell >= 0):
                delays.append(dict(
                    train_id=call.id, source_journey_id=event.journey, train_number=event.number,
                    train_category=call.category, line=event.line, normalized_service=call.service,
                    stop_kind=call.stop_kind, route_group=(call.actual_group or "AMBIGUOUS_ROUTE")
                    if call.stop_kind == "through" else "TERMINATING",
                    planned_route_group=call.route_group, service_date=call.day,
                    scheduled_hour=event.planned.astimezone(BERLIN).hour,
                    scheduled_arrival=local(event.planned), reported_arrival=local(event.reported),
                    arrival_delay_min=delay, raw_source=call.arrival.reported_source,
                ))

    scheduled_totals = {g: sum(len(scheduled[g, p]) for p in TRACKS) for g in catalog}
    scheduled_matrix, observed_matrix, reassignment_matrix = [], [], []
    scheduled_route_summary = []
    for group in catalog:
        records = [c for p in TRACKS for c in scheduled[group, p]]
        days, numbers = distinct(records)
        scheduled_route_summary.append(dict(
            route_group=group, unique_scheduled_through_services=len(records),
            cancelled_scheduled_count=sum(c.cancelled for c in records),
            distinct_operating_days=days, distinct_train_numbers=numbers,
        ))
    scheduled_by_day, observed_by_day = [], []
    for group, platform in product(catalog, TRACKS):
        s, a, w = scheduled[group, platform], strong[group, platform], weaker[group, platform]
        s_days, s_numbers = distinct(s)
        a_days, a_numbers = distinct(a)
        w_days, w_numbers = distinct(w)
        times = [next(e.reported for e in c.events if e.real and e.reported_platform) for c in a + w]
        scheduled_matrix.append(dict(
            route_group=group, platform=platform, scheduled_count=len(s),
            route_scheduled_total=scheduled_totals[group], distinct_operating_days=s_days,
            distinct_train_numbers=s_numbers, cancelled_scheduled_count=sum(c.cancelled for c in s),
            relative_frequency=len(s) / scheduled_totals[group] if scheduled_totals[group] else 0,
        ))
        observed_matrix.append(dict(
            route_group=group, platform=platform, strong_count=len(a), weaker_count=len(w),
            distinct_operating_days=a_days, distinct_train_numbers=a_numbers,
            weaker_distinct_operating_days=w_days, weaker_distinct_train_numbers=w_numbers,
            earliest_observation=local(min(times)) if times else "",
            latest_observation=local(max(times)) if times else "",
            representative_strong=record_examples(a), representative_weaker=record_examples(w),
        ))
        day_counts = [defaultdict(int) for _ in range(3)]
        for counts, observations in zip(day_counts, (s, a, w)):
            for call in observations:
                counts[call.day] += 1
        for day in dates:
            scheduled_by_day.append(dict(service_date=day, route_group=group, platform=platform,
                                         scheduled_count=day_counts[0][day]))
            observed_by_day.append(dict(service_date=day, route_group=group, platform=platform,
                                        strong_count=day_counts[1][day], weaker_count=day_counts[2][day]))

    for group, planned, final in product(catalog, TRACKS, TRACKS):
        records = reassignment[group, planned, final]
        days, numbers = distinct(records)
        reassignment_matrix.append(dict(
            route_group=group, original_planned_platform=planned, final_reported_platform=final,
            eligible_count=len(records), reassignment_count=len(records) if planned != final else 0,
            distinct_operating_days=days, distinct_train_numbers=numbers,
        ))

    def reassignment_summary(group, possible, changed):
        c_days, c_numbers = distinct(changed)
        p_days, p_numbers = distinct(possible)
        return dict(route_group=group, eligible_count=len(possible), reassignment_count=len(changed),
                    reassignment_pct=100 * len(changed) / len(possible) if possible else None,
                    distinct_eligible_days=p_days, distinct_eligible_train_numbers=p_numbers,
                    distinct_reassignment_days=c_days, distinct_reassignment_train_numbers=c_numbers)

    all_eligible = [c for group in catalog for c in eligible[group]]
    all_changed = [c for group in catalog for p in TRACKS for c in changes[group, p]]
    summary = [reassignment_summary("ALL", all_eligible, all_changed)]
    summary.extend(reassignment_summary(group, eligible[group], [c for p in TRACKS for c in changes[group, p]])
                   for group in catalog)
    evidence, conservative, expanded = compare_compatibility(catalog, scheduled, strong, weaker,
                                                               changes, routes.config)
    return dict(
        catalog=catalog, scheduled_matrix=scheduled_matrix, scheduled_by_day=scheduled_by_day,
        scheduled_route_summary=scheduled_route_summary,
        observed_matrix=observed_matrix, observed_by_day=observed_by_day, platform_records=platform_records,
        reassignment_matrix=reassignment_matrix, reassignment_records=reassignment_records,
        reassignment_summary=summary, evidence=evidence, conservative=conservative, expanded=expanded,
        delays=delays, route_review=route_review,
    )


def delay_tables(delays, dates):
    def breakdown(field, domain=()):
        groups = defaultdict(list)
        for row in delays:
            groups[row[field]].append(row["arrival_delay_min"])
        return [{field: key, **delay_summary(groups[key])} for key in sorted(set(groups) | set(domain))]

    return {
        "delay_summary": [dict(scope="ALL", **delay_summary([r["arrival_delay_min"] for r in delays])),
                          dict(scope="THROUGH", **delay_summary([r["arrival_delay_min"] for r in delays
                                                               if r["stop_kind"] == "through"]))],
        "delay_by_route_group": breakdown("route_group"),
        "delay_by_category": breakdown("train_category"),
        "delay_by_hour": breakdown("scheduled_hour", range(24)),
        "delay_by_day": breakdown("service_date", dates),
    }
