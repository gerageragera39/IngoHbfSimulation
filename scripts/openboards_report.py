"""Render the reproducible history report and make static research figures."""

from collections import Counter
from math import ceil, log1p

from openboards_analysis import LIMITATION, TRACKS
from timetable_model import csv_rows


def md_table(headers, rows):
    def cell(value):
        return str(value if value is not None else "—").replace("|", "\\|")

    lines = ["| " + " | ".join(map(cell, headers)) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(map(cell, row)) + " |" for row in rows)
    return "\n".join(lines)


def report(meta, analysis, baseline, compatibility_rows, validation, duplicates, test_summary):
    modeled = meta["modeled_platforms"]
    catalog = analysis["catalog"]
    stats = meta["historical_delay_summary"]
    changed = analysis["reassignment_summary"][0]
    dwell = meta["dwell"]
    scopes = meta["dynamic_reassignment"]
    baseline_date = meta["baseline_date"]
    checks = meta["coverage"]
    baseline_pairs = [r for r in duplicates if str(r["service_date"]) == baseline_date]
    observed = { (r["route_group"], r["platform"]): r["strong_count"] for r in analysis["observed_matrix"]}
    scheduled = { (r["route_group"], r["platform"]): r["scheduled_count"]
                 for r in analysis["scheduled_matrix"]}
    totals = md_table(
        ["Route group", *[f"Gleis {p} planned / strong" for p in TRACKS]],
        [(g, *(f"{scheduled[g, p]} / {observed[g, p]}" for p in TRACKS)) for g in catalog],
    )
    changes = md_table(
        ["Route group", "Eligible", "Changed", "Percent", "Change days", "Train numbers"],
        [(r["route_group"], r["eligible_count"], r["reassignment_count"],
          f'{r["reassignment_pct"]:.2f}%' if r["reassignment_pct"] is not None else "—",
          r["distinct_reassignment_days"], r["distinct_reassignment_train_numbers"])
         for r in analysis["reassignment_summary"]],
    )
    all_changes = Counter()
    for r in analysis["reassignment_matrix"]:
        all_changes[r["original_planned_platform"], r["final_reported_platform"]] += r["eligible_count"]
    movement_matrix = md_table(
        ["Planned / reported", *TRACKS],
        [(planned, *(all_changes[planned, final] for final in TRACKS)) for planned in TRACKS],
    )
    configs = md_table(
        ["Route group", "Original AnyLogic", "Supplied research", "Conservative", "Expanded"],
        [(r["route_group"], r["legacy_platforms"] or "—", r["research_platforms"] or "—",
          r["conservative"] or "—", r["expanded"] or "—")
         for r in compatibility_rows],
    )
    additions = md_table(
        ["Route group", "Platform", "Scheduled / strong / changes", "Strong days / trains", "Basis", "Example"],
        [(r["route_group"], r["platform"], f'{r["scheduled_count"]} / {r["actual_count"]} / {r["reassignment_count"]}',
          f'{r["distinct_observation_days"]} / {r["distinct_train_numbers"]}', r["evidence_status"],
          (r["actual_examples"] or r["scheduled_examples"]).split("|")[0])
         for r in analysis["evidence"] if r["expanded_allowed"]
         and (not r["conservative_allowed"] or r["platform"] not in meta["legacy_platforms"].get(r["route_group"], []))],
    )
    pairs = md_table(
        ["ICE records", "Raw relation", "Matching scheduled record", "Baseline decision"],
        [(f'{r["regular_train_number"]} / {r["other_train_number"]}',
          "Reciprocal links and matching full movement" if r["identical_full_movement"] and
          r["reciprocal_arrival_and_departure_links"] else "Review required",
          r["regular_gtfs_exact_train_number_and_times"], r["decision"]) for r in baseline_pairs],
    )
    issue_types = Counter(row["issue"] for row in validation)
    issues = ", ".join(f"{k} ({n})" for k, n in sorted(issue_types.items())) or "none"
    fmt = lambda value: f"{value:.3f}" if value is not None else "—"
    modeled_gtfs = meta["gtfs_unmatched_or_disagree_known_modeled_platform"]
    number_crosswalks = [r for r in baseline["gtfs_review"] if r["crosswalk_basis"]]
    number_review = "\n\n".join(r["crosswalk_basis"] for r in number_crosswalks)
    unresolved = [r for r in baseline["unresolved_services"] if r.get("planned_platform_exception")]
    exceptions = ", ".join(f'{r["train_category"]} {r["train_number"]} on Gleis {r["planned_platform"]}'
                           for r in unresolved) or "none"
    restricted_research = [r for r in analysis["evidence"] if not r["conservative_allowed"]
                           and r["platform"] in meta["research_reference_platforms"].get(r["route_group"], [])]
    research_review = "\n".join(
        f"- The supplied report proposed {r['route_group']} on Gleis {r['platform']}. The full archive gives "
        f"{r['scheduled_count']} planned and {r['actual_count']} strong reports over "
        f"{r['distinct_direct_evidence_days']} distinct evidence days. {r['justification']}"
        for r in restricted_research
    )
    return f"""# Phase 2.1.2 historical platform analysis

## Coverage and data quality

The archive covers **{checks['validated_days']} of {checks['expected_days']}** calendar days from {meta['first_day']} through {meta['last_day']} in Europe/Berlin. The audit read **{checks['raw_event_snapshots']:,}** event rows in usable raw board responses and reconciled them to **{checks['deduplicated_events']:,}** unique event identities, including the capture padding. **{checks['deduplicated_events_in_days']:,}** unique events have scheduled times inside the study dates. The manifest contains **{checks['request_receipts']:,}** receipts and **{checks['split_windows']}** subdivided request windows. A validated day has readable required files, verifiable successful receipts and continuous arrival and departure coverage over its declared capture.

The event key uses DB journey ID, event kind, station EVA and scheduled instant. The board event IDs can repeat across services. Overlap produced {checks['duplicate_snapshots']:,} repeated event rows and {checks['material_conflict_keys']:,} materially conflicting event keys. Message references and raw response hashes can differ without changing the fields used here. The scheduled day's source is preferred for traceability. Planned platform must agree across all supplied track values, a REAL time or track conflict removes the conflicting value from operational evidence, and any cancellation flag vetoes actual evidence. The conflict CSV preserves all material variants and raw pointers. Acquisition or event validation issues by type were {issues}. Missing platform fields are tallied per day in the [coverage table](../validation/dataset_coverage.csv).

## Service classification and setting

**{meta['valid_scheduled_through_calls']:,}** unique planned ICE, RE or RB through calls have ordered scheduled times and a known planned track across all platforms, including {meta['cancelled_valid_scheduled_through_calls']:,} cancelled planned calls. {meta['unmapped_valid_scheduled_through_calls']:,} of the valid calls have an unresolved route and are counted outside the route matrices. Exact RE and RB line IDs take precedence over nonstandard labels such as `ag`, `BRB` and RB carrying an RE1 line ID. A same-journey line transition retains both lines and uses the arrival-side category for category summaries. The [route and service review](../validation/route_service_review.csv) and station-call inventory preserve the original labels and itinerary evidence.

The [infrastructure research](../../research/platform_compatibility_research.md) identifies the München and Ingolstadt Nord faces of VzG 5501, the 5934 connection at Ingolstadt Nord, and the separate Regensburg 5851, Donauwörth/Ulm 5382 and Augsburg 5381 approaches. Configured local itinerary landmarks establish the station approach. A remote northern itinerary supplies a directional inference when local evidence is missing. Explicit Treuchtlingen markers are preserved in route provenance. The `NORD_5501` group describes the station throat and allows for unresolved upstream paths. A same-throat inference needs evidence on both legs. Explicit SFS itineraries are retained in the planned classification. The closure keeps those itinerary labels out of confirmed actual SFS evidence.

{LIMITATION} The supplied research records structural lengths of 409 m on Gleise 2–3 and 419 m on Gleise 4–5. Operational usable length, rolling-stock restrictions and authorized interlocking routes require separate evidence.

## Scheduled and reported platform counts

Each cell contains scheduled assignments followed by strong through-platform observations. Planned counts retain cancellations with usable schedules. The archive yields **{meta['strong_actual_platform_observations']:,} strong observations** with ordered, uncancelled REAL arrival and departure times and matching reported tracks. {meta['weaker_actual_platform_observations']:,} single-event observations are recorded separately. Raw platform object fields observed were **{', '.join(meta['raw_platform_fields']) or 'none'}**. REAL describes event times. The platform values are reports accompanying those times, with no independent platform-verification indicator established in the archived schema.

{totals}

See the [scheduled matrix](../compatibility/scheduled_platform_matrix.csv), [scheduled route totals](../compatibility/scheduled_route_summary.csv), [Gleis 2–5 planned matrix](../compatibility/scheduled_platform_matrix_gleis_2_5.csv), [observed matrix](../compatibility/observed_platform_matrix.csv), [Gleis 2–5 observed matrix](../compatibility/observed_platform_matrix_gleis_2_5.csv) and [supporting records](../compatibility/platform_evidence_records.csv) for totals, frequencies, zero-count combinations, dates and raw evidence.

## Actual reassignment

**{changed['reassignment_count']:,} of {changed['eligible_count']:,}** eligible observations changed tracks ({fmt(changed['reassignment_pct'])}%). Eligibility requires both scheduled tracks to agree and a strong reported track. The route key describes the reported station movement, with the scheduled route retained separately. The full [planned-to-reported matrix](../compatibility/reassignment_matrix.csv) includes unchanged diagonal cells and all seven platforms. {meta['reassignments_into_scope_from_other_platforms']:,} changes came from other tracks into Gleis 2–5. Arrival and departure delay values in the [reassignment records](../compatibility/platform_reassignments.csv) describe associations without causal interpretation.

{movement_matrix}

{changes}

## Simulation compatibility

The conservative configuration requires direct evidence across at least {meta['min_repeat_days']} operating days and {meta['min_repeat_train_numbers']} distinct train numbers. Scheduled and strong observations for the same call count once for that threshold. A single valid planned assignment can still justify retaining its train as fixed to that track. Weak observations and absence of direct evidence remain distinguishable from an explicit infrastructure prohibition. None of the archived evidence establishes a prohibition or official authorization.

Expanded eligibility adds documented sensitivity assumptions only. The legacy column refers to the synthetic AnyLogic rules in `Ingo.alp` and `route_catalog.csv`. In particular, the legacy ICE/RE1 northward corridor labels presumed SFS access. They cannot validate unrestricted SFS use in this dataset.

{configs}

{research_review}

### Newly supported or assumed alternatives

{additions}

The [compatibility evidence](../compatibility/platform_compatibility_evidence.csv) records the status and justification of each route–platform pair. The same GREEDY dispatcher can use either configuration. In the baseline, **{scopes['conservative_eligible']} / {meta['modeled_trains']} ({fmt(scopes['conservative_pct'])}%)** of trains have an alternative under conservative eligibility. **{scopes['expanded_eligible']} / {meta['modeled_trains']} ({fmt(scopes['expanded_pct'])}%)** have one under expanded eligibility. The expanded configuration gives {scopes['expanded_increases_options']} trains more options.

## Full-day timetable

The baseline is **{baseline_date}**, selected in advance and checked against the local GTFS extraction and station-poster crosswalk. The [GTFS comparison](../timetable/gtfs_baseline_review.csv) shows {modeled_gtfs} modeled-track GTFS through calls with an unresolved time, track or service match. The [timetable](../timetable/timetable.csv) contains **{meta['modeled_trains']}** scheduled through trains on Gleise {', '.join(map(str, modeled))}, including {meta['modeled_cancelled_scheduled']} cancelled planned calls. The [terminal data](../timetable/terminal_services.csv) preserve {meta['terminal_services']} originating or terminating/endpoint calls, {meta['terminal_services_on_modeled_platforms']} on the modeled tracks. Terminal occupation intervals are unknown. There are {meta['initial_trains_in_occupation']} known modeled through occupations at midnight, {meta['departures_after_end']} modeled departures beyond the day window, and {meta['scheduled_through_overlap_pairs']} overlapping planned through-occupation pairs.

{number_review}

The {meta['planned_platform_exceptions']} fixed-only per-train exceptions are {exceptions}. These retain the scheduled platform for both configurations. The [unresolved services](../timetable/unresolved_services.csv) and [excluded services](../timetable/excluded_services.csv) preserve individual decisions. The dwell median is {dwell.get('median', '—')} minutes, the mean is {dwell.get('mean', '—')} and the range is {dwell.get('min', '—')} to {dwell.get('max', '—')}. The cohort contains {dwell.get('zero', 0)} zero-duration stops, {meta['minimum_dwell_exceeds_schedule']} stops below their configured minimum, and {meta['negative_dwell_review_count']} reversed-time cases in the baseline review. The configurable one-minute default is a modeling assumption. The input keeps the original scheduled times and publishes elapsed minutes relative to local midnight.

### Linked ICE records

{pairs}

The extra journeys are retained with source links in the review and exclusions. Reciprocal OpenBoards `travelsWith` records and agreeing times, platforms and routes support one modeled platform occupation per pair. The source does not establish the exact consist or a confirmed replacement relationship. The regular journey is the planned representation, corroborated on this day by the locally archived schedule.

## Historical incoming delay

The [delay sample](../delays/historical_arrival_delays.csv) includes {stats['count']:,} deduplicated REAL arrivals of eligible services, including terminating arrivals for future calibration review. Separate route and through-only summaries are available. The sample retains **{stats['early']:,} early**, **{stats['on_time']:,} on-time** and **{stats['positive']:,} late** arrivals. Mean / median / sample standard deviation were {fmt(stats['mean_min'])} / {fmt(stats['median_min'])} / {fmt(stats['sample_stddev_min'])} minutes. The 5th, 25th, 75th, 90th, 95th and 99th percentiles were {', '.join(fmt(stats[k]) for k in ('p05_min', 'p25_min', 'p75_min', 'p90_min', 'p95_min', 'p99_min'))} minutes. The observed range was {fmt(stats['min_min'])} to {fmt(stats['max_min'])} minutes. Day and scheduled-hour groupings use Europe/Berlin. Correlation within trains, groups and days is possible, and the construction period limits generalization.

## Verification and AnyLogic readiness

{test_summary}

**{meta['readiness']}**. {meta['readiness_detail']}

Reproduce the bundle with `python scripts/analyze_openboards_history.py` and the tests with `python -m unittest discover -s tests -v`. See the [Phase 2.1.2 guide](../../README.md#phase-212--openboards-history-and-simulation-timetable) for the offline inputs and options.
"""


def make_charts(directory, analysis):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def save(fig, name):
        fig.text(0.015, 0.015, f"Ingolstadt Hbf · {analysis['date_label']} · Nürnberg–Ingolstadt SFS closure",
                 fontsize=8, color="#41536a")
        fig.savefig(directory / f"{name}.png", dpi=140, bbox_inches="tight", pad_inches=0.18)
        plt.close(fig)

    def heatmap(matrix, field, platforms, title, name):
        lookup = {(r["route_group"], r["platform"]): r[field] for r in matrix}
        groups = list(analysis["catalog"])
        values = [[lookup[g, p] for p in platforms] for g in groups]
        fig, ax = plt.subplots(figsize=(9.6, max(4, len(groups) * .35 + 1.8)))
        image = ax.imshow([[log1p(v) for v in row] for row in values], cmap="Blues", aspect="auto")
        ax.set_xticks(range(len(platforms)), platforms)
        ax.set_yticks(range(len(groups)), groups, fontsize=8)
        ax.set(xlabel="Gleis", title=title)
        for i, row in enumerate(values):
            for j, value in enumerate(row):
                ax.text(j, i, str(value), ha="center", va="center", fontsize=8,
                        color="white" if log1p(value) > image.norm.vmax * .60 else "#102840")
        fig.tight_layout(rect=(0, .04, 1, 1))
        save(fig, name)

    for key, field, title, name in (
        ("scheduled_matrix", "scheduled_count", "Planned through assignments", "scheduled_platform"),
        ("observed_matrix", "strong_count", "Strong reported through-platform observations", "observed_platform"),
    ):
        heatmap(analysis[key], field, TRACKS, title, name)
        heatmap(analysis[key], field, analysis["modeled_platforms"], title + " · Gleise 2–5", name + "_modeled")
    heatmap(analysis["observed_matrix"], "weaker_count", TRACKS,
            "Single-event reported platform observations", "observed_platform_weaker")

    lookup = {(r["route_group"], r["original_planned_platform"], r["final_reported_platform"]):
              r["reassignment_count"] for r in analysis["reassignment_matrix"]}
    groups = list(analysis["catalog"])
    for offset in range(0, len(groups), 12):
        selected = groups[offset:offset + 12]
        fig, axes = plt.subplots(ceil(len(selected) / 3), 3, figsize=(12, ceil(len(selected) / 3) * 3.1),
                                 squeeze=False, layout="constrained")
        max_value = max(lookup.values(), default=0)
        for ax, group in zip(axes.flat, selected):
            values = [[lookup[group, p, q] for q in TRACKS] for p in TRACKS]
            ax.imshow([[log1p(v) for v in row] for row in values], cmap="YlGnBu", vmin=0,
                      vmax=max(1, log1p(max_value)))
            for i, row in enumerate(values):
                for j, value in enumerate(row):
                    ax.text(j, i, str(value) if i != j else "·", ha="center", va="center", fontsize=7,
                            color="white" if log1p(value) > .60 * log1p(max_value) else "#102840")
            ax.set_xticks(range(7), TRACKS)
            ax.set_yticks(range(7), TRACKS)
            ax.set_title(group, fontsize=8)
            ax.tick_params(labelsize=7, length=0)
        for ax in list(axes.flat)[len(selected):]:
            ax.set_visible(False)
        fig.suptitle("Observed platform changes by route group · planned rows / reported columns", fontsize=12)
        fig.supxlabel("Reported Gleis", y=0.045, fontsize=9)
        fig.supylabel("Planned Gleis", fontsize=9)
        fig.get_layout_engine().set(rect=(.025, .06, .96, .92))
        save(fig, f"reassignments_by_route_{offset // 12 + 1}")

    delays = sorted(r["arrival_delay_min"] for r in analysis["delays"])
    if delays:
        for file, title in (("arrival_delay_distribution", "Signed arrival delay distribution"),
                            ("arrival_delay_ecdf", "Empirical cumulative distribution of signed arrival delay")):
            fig, ax = plt.subplots(figsize=(8.4, 4.4))
            if file.endswith("ecdf"):
                ax.step([delays[0], *delays], [0, *(n / len(delays) for n in range(1, len(delays) + 1))],
                        where="post", color="#13689b")
                ax.set(ylabel="Cumulative fraction", ylim=(0, 1.02))
            else:
                ax.hist(delays, bins=80, color="#13689b", edgecolor="white", linewidth=.5)
                ax.set(ylabel="Arrivals", yscale="log")
            ax.axvline(0, linestyle="--", color="#a2472b", linewidth=1)
            ax.set(xlabel="Reported minus scheduled arrival (minutes)", title=title)
            ax.grid(axis="y", alpha=.18)
            fig.tight_layout(rect=(0, .04, 1, 1))
            save(fig, file)


def legacy_platforms(path):
    return {r["route_group"]: [int(p) for p in r["model_allowed_platforms"].split("|")]
            for r in csv_rows(path)}
