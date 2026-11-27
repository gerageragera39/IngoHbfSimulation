"""Generate the station timetable quality report and scheduled occupancy charts."""

from collections import Counter


def table(items, heading="Count"):
    if not items:
        return ["None."]
    return [f"| Measure | {heading} |", "| --- | ---: |",
            *(f"| {key} | {value} |" for key, value in items.items())]


def report(meta):
    counts = meta["counts"]
    lines = [
        f"# {meta['station']} timetable validation",
        "",
        f"**{meta['readiness'].upper()}** · {meta['selected_date']} · Europe/Berlin",
        "",
        meta["date_selection"],
        "",
        meta["platform_evidence"]["status"].replace("_", " ").capitalize() + " for DB poster evidence.",
        "",
        "## Validation findings",
        "",
        *(f"- **Error** — {message}" for message in meta["errors"]),
        *(f"- **Warning** — {message}" for message in meta["warnings"]),
        "",
        "## Station coverage",
        "",
        *table({
            "Unique in-window passenger train stops": counts["station_stops"],
            "Main-day train stops": counts["main_day_stops"],
            "Stops originating on a previous GTFS service date": counts["previous_service_date"],
            "Known platforms": f"{counts['platform_resolved']} ({counts['platform_coverage_pct']}%)",
            "Modeled platform stops": counts["modeled_platforms"],
            "Other platform stops": counts["other_platforms"],
            "Unknown or conflicting platforms": counts["unknown_platforms"],
            "Unknown occupation intervals": counts["unknown_occupancy"],
            "Model-scoped fixed-only compatibility assignments": counts["fixed_only_modeled"],
            "Unclassified or ambiguous routes": counts["unclassified_routes"],
            "Unresolved records": counts["unresolved_records"],
            "Excluded records": counts["excluded_trains"],
            "Main-day modeled rows in timetable.csv": counts["timetable_rows"],
            "Fully ready main-day rows": counts["ready_main_day"],
            "Provisional main-day rows": counts["provisional_main_day"],
            "Initial occupations in the modeled or unknown scope": counts["initial_occupancy"],
            "Scheduled overlapping interval pairs, all known platforms": counts["scheduled_occupancy_conflicts"],
        }),
        "",
        "A stop can appear in multiple review counts. Known other-platform stops can also have unresolved occupation.",
        "",
        "## Scheduled traffic and occupation",
        "",
        f"Peak main-day hours are {', '.join(counts['peak_local_hours']) or 'unavailable'} local time.",
        "The occupancy chart uses known positive passenger dwell intervals clipped to the observation window.",
        "Occupied minutes use the union of intervals. The conflict CSV lists all overlapping interval pairs.",
        "These are published schedule observations. Passenger GTFS omits some operational movements and does not "
        "establish occupation before an originating departure or after a terminating arrival.",
    ]
    for heading, key in (
        ("Hourly main-day calls", "hourly_main_day_stops"), ("Platform", "by_platform"),
        ("Train category", "by_category"), ("Line", "by_line"), ("Route group", "by_route_group"),
        ("Stop kind", "by_stop_kind"), ("Boundary and occupation status", "by_boundary_status"),
        ("Platform evidence status", "by_platform_status"), ("Blocking reasons", "by_blocking_reason"),
        ("Review flags", "by_review_flag"), ("Through scheduled dwell (minutes)", "scheduled_dwell_through_min"),
        ("All published arrival/departure pairs (minutes)", "scheduled_dwell_all_calls_min"),
        ("Scheduled occupied minutes by platform", "scheduled_occupied_minutes"),
    ):
        lines.extend(("", f"### {heading}", "", *table(counts[key], "Value")))
    poster_review = meta["platform_evidence"].get("completeness_review", [])
    if poster_review:
        lines.extend(("", "## DB poster and GTFS discrepancies", "",
                      "The examples below need source reconciliation before the station cohort can be confirmed."))
        for item in poster_review:
            url = meta["station_posters"][item["document"]]["url"]
            lines.append(f"- **{item['departure']} {item['train']}** — {item['finding']} "
                         f"[DB poster, page {item['page']}]({url}#page={item['page']})")
    lines.extend((
        "", "## Review files", "",
        "- `unresolved_records.csv` lists missing, conflicting or incomplete model inputs.",
        "- `excluded_trains.csv` records known other platforms and station calls outside passenger rail scope.",
        "- `route_mapping_review.csv` lists fixed-only compatibility rules.",
        "- `initial_occupancy.csv` lists pre-window occupations with a modeled or unknown platform.",
        "- `scheduled_occupancy_conflicts.csv` preserves all overlapping published intervals and their train IDs.",
        "- `duplicate_review.csv` records confirmed and ambiguous duplicate candidates.",
        "", "## Provenance", "",
        "GTFS data from GTFS.DE, based on DELFI e.V. NeTEx data, is licensed under "
        "[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). This project filtered the data to the station "
        "window and added timetable evidence and modeling fields. Refer to dataset_metadata.json for hashes, "
        "validity dates and acquisition receipts.",
        "",
    ))
    return "\n".join(lines)


def charts(output, meta, intervals, through):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    counts = meta["counts"]
    blue, teal, slate = "#2C5D98", "#207B73", "#49596B"
    title = f"{meta['station']} · {meta['selected_date']}"
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout="constrained")
    fig.suptitle(title + " · Passenger timetable", fontsize=16, fontweight="bold")
    plots = (
        ("Main-day stops by local hour", counts["hourly_main_day_stops"], blue, "Stops"),
        ("Stops by scheduled platform", dict(sorted(counts["by_platform"].items())), teal, "Stops"),
        ("Train category", dict(sorted(counts["by_category"].items())), slate, "Stops"),
        ("Through stop scheduled dwell", dict(sorted(Counter(through).items())), blue, "Stops"),
    )
    for ax, (label, data, color, y_label) in zip(axes.flat, plots):
        ax.set_title(label, loc="left", fontweight="bold")
        ax.set_axisbelow(True)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(axis="y", alpha=0.2)
        ax.set_ylabel(y_label)
        if data:
            captions = [f"{key:g}" if isinstance(key, float) else str(key) for key in data]
            ax.bar(captions, list(data.values()), color=color)
        else:
            ax.text(0.5, 0.5, "No applicable observations", ha="center", va="center", transform=ax.transAxes)
    axes[1, 1].set_xlabel("Scheduled dwell (minutes)")
    fig.savefig(output / "timetable_overview.png", dpi=145)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 4.4), layout="constrained")
    ax.set_title(title + " · Scheduled passenger occupation", loc="left", fontweight="bold")
    labels = sorted(set(intervals) | set(meta["modeled_platforms"]))
    for i, platform in enumerate(labels):
        tracks = intervals.get(platform, [])
        ax.broken_barh([(start, stop - start) for start, stop, _ in tracks], (i - 0.28, 0.56),
                       color=blue if platform in meta["modeled_platforms"] else slate, alpha=0.82)
    ax.set_yticks(range(len(labels)), [f"Gleis {label}" for label in labels])
    ax.set_xlim(0, meta["observation_minutes"])
    ax.set_xlabel("Elapsed hours from local midnight · Known, positive through dwell only")
    ticks = list(range(0, int(meta["observation_minutes"]) + 1, 120))
    ax.set_xticks(ticks, [str(value // 60) for value in ticks])
    ax.grid(axis="x", alpha=0.25)
    fig.savefig(output / "scheduled_occupancy.png", dpi=145)
    plt.close(fig)
