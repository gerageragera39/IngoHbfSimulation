
"""Streamlit views for the five dispatch analytics sections."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import dashboard_charts as charts
from analyze_results import TOL
from dashboard_analytics import assignment_summary, paired_statistics, passenger_summary, platform_summary
from station_dashboard_core import TRAIN_COLUMNS, csv_bytes, describe_transfer, filter_trains, paired_train, queue_events

RUN_LABELS = {
    "total_station_delay_min": "Secondary delay (min / simulation)",
    "mean_wait_min": "Waiting time (min / train)",
    "affected_trains": "Affected trains / simulation",
    "affected_pct": "Affected trains (%)",
    "reassignments": "Reassignments / simulation",
    "passenger_induced_delay_min": "Direct passenger delay (min / simulation)",
    "mean_utilization_pct": "Mean platform utilization (%)",
    "utilization_range_pp": "Utilization range (pp)",
    "utilization_sd_pp": "Utilization standard deviation (pp)",
}
PLATFORM_LABELS = {
    "policy": "Dispatcher", "platform": "Platform", "scenarios": "Scenarios",
    "horizon_min": "Observation horizon (min)", "mean_utilization_pct": "Mean utilization (%)",
    "total_busy_min": "Total occupied time (min)", "mean_busy_min": "Mean occupied time (min / simulation)",
    "total_train_count": "Total trains served", "mean_train_count": "Trains served / simulation",
    "pooled_mean_occupancy_min": "Mean occupancy per train (min)",
    "mean_passenger_delay_min": "Direct passenger delay (min / simulation)",
}
SCENARIO_LABELS = {
    "scenario_id": "Scenario ID", "scenario_seed": "Seed", "trains": "Trains per simulation",
    "fixed_total_delay_min": "FIXED_DB secondary delay (min)",
    "greedy_total_delay_min": "GREEDY secondary delay (min)",
    "delay_saved_min": "FIXED_DB − GREEDY (min)",
    "delay_reduction_pct": "Secondary delay reduction (%)",
}
STATS_LABELS = {
    "pairs": "Independent paired scenarios",
    "fixed_total_min": "FIXED_DB total delay across scenarios (min)",
    "greedy_total_min": "GREEDY total delay across scenarios (min)",
    "fixed_mean_min": "FIXED_DB mean delay (min / simulation)",
    "greedy_mean_min": "GREEDY mean delay (min / simulation)",
    "mean_saving_min": "Mean paired saving (min)",
    "std_saving_min": "Paired savings sample standard deviation (min)",
    "ci_low_min": "95% CI lower (min)", "ci_high_min": "95% CI upper (min)",
    "reduction_pct": "Aggregate delay reduction (%)",
    "greedy_wins": "GREEDY wins", "equal": "Equal", "fixed_wins": "FIXED_DB wins",
}


def fmt(value, unit=""):
    return "Unavailable" if pd.isna(value) else f"{value:,.2f}{unit}"


def cards(*items):
    for column, (label, value) in zip(st.columns(len(items)), items):
        column.metric(label, value)


def plot(title, fig):
    st.markdown(f"#### {title}")
    st.plotly_chart(fig, theme=None, config={"displaylogo": False, "scrollZoom": False})


def table(frame, filename, *, button="Download CSV"):
    columns = {
        name: st.column_config.NumberColumn(name, format="%.2f")
        for name in frame.select_dtypes(include="floating")
    }
    st.dataframe(frame, hide_index=True, column_config=columns)
    st.download_button(button, csv_bytes(frame), filename, "text/csv", on_click="ignore")


def visible_rows(frame, policies):
    return frame[frame["policy"].isin(policies)]


def scenario_delays(runs):
    return runs.rename(columns={"policy": "Dispatcher", "total_station_delay_min": "Secondary delay (min / simulation)"})


def overview(analytics, policies, tag):
    runs = visible_rows(analytics.runs, policies)
    trains = visible_rows(analytics.trains, policies)
    stats = paired_statistics(analytics.scenarios)
    by_policy = analytics.runs.groupby("policy", sort=False)[list(RUN_LABELS)].mean()
    n_min, n_max = analytics.scenarios["trains"].min(), analytics.scenarios["trains"].max()
    ratio = stats["reduction_pct"]

    st.subheader("Secondary delay")
    delay_cards = [
        (f"{p} mean delay / simulation", fmt(stats[k], " min"))
        for p, k in (("FIXED_DB", "fixed_mean_min"), ("GREEDY", "greedy_mean_min")) if p in policies
    ]
    cards(*delay_cards, ("Aggregate delay reduction", fmt(ratio, "%") if ratio is not None else "Undefined"),
          ("Mean paired saving", fmt(stats["mean_saving_min"], " min")))

    if stats["mean_saving_min"] > TOL:
        finding = f"GREEDY saved {stats['mean_saving_min']:.2f} minutes of secondary delay per simulation on average"
    elif stats["mean_saving_min"] < -TOL:
        finding = f"FIXED_DB saved {-stats['mean_saving_min']:.2f} minutes of secondary delay per simulation on average"
    else:
        finding = "The mean paired difference in secondary delay was zero"
    st.write(f"{finding}. GREEDY had less delay in **{stats['greedy_wins']} of {stats['pairs']}** paired scenarios.")
    st.caption("Aggregate reduction uses total delay across the selected pairs. Affected trains have positive secondary delay.")

    left, right = st.columns(2)
    with left:
        total = by_policy.loc[list(policies), ["total_station_delay_min", "passenger_induced_delay_min"]]
        total = total.rename(columns={"total_station_delay_min": "Secondary delay",
                                      "passenger_induced_delay_min": "Direct passenger delay"})
        total = total.rename_axis("Dispatcher").reset_index().melt(
            "Dispatcher", var_name="Measure", value_name="Minutes / simulation"
        ).dropna()
        plot("Delay by dispatcher", charts.grouped(total, "Measure", "Minutes / simulation", unit="min"))
    with right:
        plot("Secondary delay across scenarios", charts.distribution(scenario_delays(runs), "Secondary delay (min / simulation)"))

    st.subheader("Waiting and reassignments")
    comparison = by_policy.loc[list(policies)].T.rename(index=RUN_LABELS)
    st.caption(f"Dispatcher averages in display order · {' / '.join(policies)}")
    cards(*[(label, " / ".join(fmt(by_policy.loc[p, field], unit) for p in policies))
            for label, field, unit in (
                ("Mean waiting time per train", "mean_wait_min", " min"),
                ("Mean share of affected trains", "affected_pct", "%"),
                ("Mean reassignments per simulation", "reassignments", ""),
            )])
    st.subheader("Passenger delay and platform load")
    cards(*[(label, " / ".join(fmt(by_policy.loc[p, field], unit) for p in policies))
            for label, field, unit in (
                ("Mean direct passenger delay per simulation", "passenger_induced_delay_min", " min"),
                ("Mean platform utilization", "mean_utilization_pct", "%"),
                ("Mean platform utilization range", "utilization_range_pp", " pp"),
            )])
    imbalance = by_policy.loc["FIXED_DB", "utilization_range_pp"] - by_policy.loc["GREEDY", "utilization_range_pp"]
    cards(("Validated paired scenarios", f"{stats['pairs']:,}"),
          ("Trains per simulation", str(n_min) if n_min == n_max else f"{n_min}–{n_max}"),
          ("Reduction in utilization range", fmt(imbalance, " pp")))
    with st.expander("Overview table and CSV export"):
        table(comparison.rename_axis("Average metric").reset_index(), f"{tag}_overview.csv",
              button="Download overview metrics")

    averages = comparison.loc[[RUN_LABELS[k] for k in ("affected_pct", "mean_utilization_pct")]]
    bars = averages.rename_axis("Measure").reset_index().melt("Measure", var_name="Dispatcher", value_name="Percent (%)")
    left, right = st.columns(2)
    with left:
        plot("Affected trains and utilization", charts.grouped(bars, "Measure", "Percent (%)", unit="%"))
    with right:
        waiting = trains.rename(columns={"policy": "Dispatcher", "waiting_min": "Waiting time (min / train)"})
        plot("Waiting time across train records", charts.distribution(waiting, "Waiting time (min / train)", kind="histogram"))
    unit = st.radio("Scenario comparison unit", ["Minutes saved", "Percent reduction"], horizontal=True)
    percentage = unit == "Percent reduction"
    if percentage:
        zero = int((analytics.scenarios["fixed_total_delay_min"] == 0).sum())
        if zero:
            st.caption(f"Percentage reduction is undefined for {zero} paired scenarios with zero FIXED_DB delay.")
    plot("Secondary delay reduction by scenario", charts.paired_bars(analytics.scenarios, percentage=percentage))


def assignments(analytics, policies, tag, prefix):
    st.subheader("Planned-to-assigned platforms")
    st.caption("Diagonal cells show unchanged assignments. Off-diagonal cells show reassignments.")
    a, b = st.columns(2)
    policy = a.selectbox("Matrix dispatcher", policies, index=len(policies) - 1, key=f"{prefix}_matrix_dispatcher")
    measure = b.radio("Assignment counts", ["Mean per scenario", "Total across scenarios"],
                      horizontal=True, key=f"{prefix}_matrix_counts")
    values = assignment_summary(analytics.assignments)
    field = "mean_train_count" if measure == "Mean per scenario" else "total_train_count"
    plot(f"{policy} · {measure}", charts.assignment_matrix(values, field, policy))
    labels = {"policy": "Dispatcher", "planned_platform": "Planned platform", "assigned_platform": "Assigned platform",
              "mean_train_count": "Mean trains per scenario", "total_train_count": "Total trains across scenarios"}
    st.download_button("Download assignment counts", csv_bytes(visible_rows(values, policies).rename(columns=labels)),
                       f"{tag}_assignments.csv", "text/csv", key=f"{prefix}_assignments_download", on_click="ignore")


def platform_utilization(analytics, policies, tag):
    loads = visible_rows(analytics.platforms, policies)
    summary = platform_summary(loads).rename(columns=PLATFORM_LABELS)
    summary["Platform"] = summary["Platform"].map(lambda p: f"Gleis {p}")
    if not loads["horizon_min"].iloc[0]:
        st.info("Utilization is undefined because all actual departures occurred at simulation time zero.")
    st.caption(
        "The common horizon starts at zero and ends at the latest actual departure across all validated batch runs "
        "in this family. Higher utilization can reflect longer occupancy, including direct passenger-induced delay."
    )
    left, right = st.columns(2)
    with left:
        utilization = charts.grouped(summary, "Platform", "Mean utilization (%)", unit="%")
        utilization.update_yaxes(range=[0, 100])
        plot("Platform utilization", utilization)
    with right:
        plot("Trains served by platform", charts.grouped(summary, "Platform", "Trains served / simulation", unit="trains"))
    runs = visible_rows(analytics.runs, policies)
    imbalance = []
    for p, rows in runs.groupby("policy", sort=False):
        for name, field in (("Utilization range", "utilization_range_pp"), ("Utilization standard deviation", "utilization_sd_pp")):
            imbalance.append({"Dispatcher": p, "Spread measure": name, "Mean spread (percentage points)": rows[field].mean()})
    left, right = st.columns(2)
    with left:
        plot("Mean platform occupancy time", charts.grouped(summary, "Platform", "Mean occupancy per train (min)", unit="min"))
    with right:
        plot("Platform load imbalance", charts.grouped(pd.DataFrame(imbalance), "Spread measure",
                                                       "Mean spread (percentage points)", unit="pp"))
    loads = loads.assign(Platform=loads["platform"].map(lambda p: f"Gleis {p}"))
    fig = px.box(loads, x="Platform", y="utilization_pct", color="policy", color_discrete_map=charts.COLORS,
                 labels={"utilization_pct": "Utilization (%)", "policy": "Dispatcher"}, points="outliers")
    plot("Utilization across scenarios", charts.styled(fig))
    with st.expander("Platform statistics and CSV export"):
        table(summary, f"{tag}_platforms.csv", button="Download platform statistics")
        table(pd.DataFrame(imbalance), f"{tag}_load_imbalance.csv", button="Download load imbalance")
    assignments(analytics, policies, tag, "platform")


def individual_platforms(pair, frame, policies):
    policy = st.selectbox("Gantt dispatcher", policies, index=len(policies) - 1)
    plot(f"{policy} platform occupancy", charts.gantt(frame, policy))
    st.caption("Each bar spans actual platform arrival to actual departure for one train. Zoom to inspect simultaneous events.")
    plot("Station queue length", charts.queues(queue_events(frame[frame["policy"].isin(policies)], pair.last_departure)))


def passenger(analytics, transfer, policies, tag):
    trains = visible_rows(analytics.trains, policies)
    summary = passenger_summary(trains, analytics.runs)
    counts = summary.melt("Dispatcher", value_vars=["Same island", "Cross island"], var_name="Movement", value_name="Reassignments")
    st.caption(
        "Gleis 2–3 and Gleis 4–5 form the two modeled islands. Passenger walking can overlap ordinary dwell. "
        "Direct passenger-induced delay is the additional train departure delay after scheduled departure "
        "and minimum dwell allow departure. The simulation uses assumed walking times and has no passenger counts."
    )
    left, right = st.columns(2)
    with left:
        plot("Reassignment categories", charts.grouped(counts, "Movement", "Reassignments", unit="trains"))
    with right:
        if transfer:
            plot("Passenger walking time (min)", charts.walking_matrix(transfer))
        else:
            st.info("Passenger walking parameters are unavailable for this export.")
    table(summary, f"{tag}_passenger_summary.csv", button="Download passenger summary")
    if "passenger_induced_delay_min" in trains and trains["passenger_induced_delay_min"].notna().any():
        delay = "Direct passenger-induced delay (min)"
        data = trains.rename(columns={"policy": "Dispatcher", "passenger_induced_delay_min": delay,
                                      "route_group": "Route group"})
        data = data.assign(Platform=data["assigned_platform"].map(lambda p: f"Gleis {p}"))
        left, right = st.columns(2)
        with left:
            plot("Direct delay across train records", charts.distribution(data, delay, kind="histogram"))
        with right:
            group_by = st.radio("Break down direct delay by", ["Route group", "Platform"], horizontal=True)
            direct = data.groupby(["Dispatcher", group_by], as_index=False)[delay].sum(min_count=1)
            direct = direct.rename(columns={delay: "Total direct delay (min)"})
            plot("Direct delay across selected simulations", charts.grouped(direct, group_by, "Total direct delay (min)", unit="min"))
            st.download_button("Download direct delay breakdown", csv_bytes(direct), f"{tag}_direct_delay.csv",
                               "text/csv", on_click="ignore")
    else:
        st.info("Direct passenger-induced delay is unavailable in these exports.")
    assignments(analytics, policies, tag, "passenger")


def statistical(analytics, policies, tag):
    stats = paired_statistics(analytics.scenarios)
    low, high = stats["ci_low_min"], stats["ci_high_min"]
    st.caption("A positive difference favors GREEDY. The 95% Student-t interval uses one paired difference per independent scenario.")
    st.caption("These results describe synthetic experiments under the selected modeling assumptions. Real DB operations require timetable data and calibration.")
    cards(("Independent pairs", f"{stats['pairs']:,}"), ("Mean paired saving", fmt(stats["mean_saving_min"], " min")),
          ("Paired savings standard deviation", fmt(stats["std_saving_min"], " min")),
          ("95% confidence interval", f"[{low:.2f}, {high:.2f}] min" if low is not None else "Unavailable"))
    left, right = st.columns(2)
    with left:
        plot("Mean saving and 95% confidence interval",
             charts.interval(["Selected configuration"], [stats["mean_saving_min"]], [low], [high],
                             y_title="FIXED_DB − GREEDY (min)"))
    with right:
        labels = ["GREEDY wins", "Equal", "FIXED_DB wins"]
        fig = go.Figure(go.Bar(x=labels, y=[stats["greedy_wins"], stats["equal"], stats["fixed_wins"]],
                              marker_color=[charts.COLORS["GREEDY"], charts.NEUTRAL, charts.COLORS["FIXED_DB"]]))
        fig.update_yaxes(title="Paired scenarios", dtick=1)
        plot("Dispatcher outcomes", charts.styled(fig))
    plot("Paired scenario differences", charts.paired_bars(analytics.scenarios))
    left, right = st.columns(2)
    with left:
        plot("Secondary delay by dispatcher", charts.distribution(scenario_delays(visible_rows(analytics.runs, policies)),
                                                                   "Secondary delay (min / simulation)"))
    with right:
        saved = analytics.scenarios[["delay_saved_min"]].rename(columns={"delay_saved_min": "Paired saving (min)"})
        plot("Distribution of paired savings", charts.distribution(saved, "Paired saving (min)", kind="histogram"))
    with st.expander("Statistical tables and CSV exports"):
        summary = pd.DataFrame({"Metric": list(STATS_LABELS.values()),
                                "Value": [stats[field] for field in STATS_LABELS]})
        table(summary, f"{tag}_paired_statistics.csv", button="Download statistical summary")
        table(analytics.scenarios[list(SCENARIO_LABELS)].rename(columns=SCENARIO_LABELS),
              f"{tag}_paired_scenarios.csv", button="Download paired scenarios")


def comparisons(outcomes, excluded, transfer, tag):
    st.subheader("Transfer sensitivity")
    st.caption(
        f"Reference configuration · {describe_transfer(transfer)}. Each comparison uses only seeds whose original train "
        "inputs match the reference. The estimates apply to the tested transfer settings."
    )
    if outcomes.empty:
        st.info("No other transfer configuration has equivalent inputs for the selected reference.")
    else:
        outcomes = outcomes.sort_values(["Mode", "Same-island time (min)", "Uniform / cross-island time (min)"])
        mode = transfer[0]
        for title, rows in (
            ("Within-model sensitivity", outcomes[outcomes["Mode"] == mode]),
            ("UNIFORM versus MATRIX", outcomes[outcomes["Mode"] != mode]),
        ):
            if rows.empty:
                st.caption(f"{title} is unavailable for this reference.")
                continue
            plot(title, charts.interval(
                rows["Comparison configuration"], rows["Change in paired saving (min)"],
                rows["95% CI lower (min)"], rows["95% CI upper (min)"],
                y_title="Change in paired saving (min)",
                data=[f"{n} matched seeds · reference {ref:.2f} min · comparison {alt:.2f} min"
                      for n, ref, alt in zip(rows["Matched seeds"], rows["Reference mean saving (min)"],
                                             rows["Comparison mean saving (min)"])],
            ))
        st.caption("Positive values mean the comparison setting increased GREEDY’s advantage relative to the matched reference.")
        table(outcomes, f"{tag}_transfer_sensitivity.csv", button="Download matched comparisons")
    if not excluded.empty:
        st.warning(f"{len(excluded)} seed–configuration matches were excluded.")
        with st.expander("Missing and mismatched seeds"):
            table(excluded, f"{tag}_unmatched_seeds.csv", button="Download excluded seeds")


def train_explorer(pair, frame, policies, tag):
    selected = visible_rows(frame, policies)
    choices, ranges, positive = {}, {}, []
    with st.expander("Train filters", expanded=True):
        fields = ("train_id", "route_group", "planned_platform", "assigned_platform")
        for column, field in zip(st.columns(4), fields):
            options = sorted(selected[field].unique())
            choices[field] = column.multiselect(TRAIN_COLUMNS[field], options, key=f"{tag}_{field}")
        left, right = st.columns(2)
        reassigned = left.checkbox("Only reassigned trains", key=f"{tag}_reassigned")
        categories = [c for c in ("Same island", "Cross island", "Unchanged")
                      if c in set(selected["assignment_category"]) and (c != "Unchanged" or not reassigned)]
        choices["assignment_category"] = left.multiselect("Reassignment category", categories, key=f"{tag}_category")
        if reassigned:
            choices["reassigned"] = [1]
        if right.checkbox("Only trains with secondary delay", key=f"{tag}_secondary"):
            positive.append("station_delay_min")
        passenger_field = "passenger_induced_delay_min"
        if passenger_field in selected and right.checkbox("Only trains with positive direct passenger delay", key=f"{tag}_passenger"):
            positive.append(passenger_field)
        for field in ("incoming_delay", "waiting_min", "station_delay_min"):
            lo, hi = float(selected[field].min()), float(selected[field].max())
            if lo == hi:
                st.caption(f"{TRAIN_COLUMNS[field]} · {lo:.2f} for all records")
                continue
            ranges[field] = st.slider(f"{TRAIN_COLUMNS[field]} range", lo, hi, (lo, hi),
                                      step=(hi - lo) / 200, format="%.3f", key=f"{tag}_{field}_range")
    filtered = filter_trains(selected, choices, ranges, positive)
    st.caption(f"{len(filtered):,} of {len(selected):,} train records match the filters.")
    if filtered.empty:
        st.info("No trains match these filters. Clear a filter or widen a range to see records.")
    else:
        columns = [field for field in TRAIN_COLUMNS if field in filtered]
        table(filtered[columns].rename(columns=TRAIN_COLUMNS), f"{tag}_filtered_trains.csv",
              button="Download filtered trains")

    st.subheader("Paired train comparison")
    st.caption("Both dispatchers are shown for the same train, scenario and seed. Positive differences indicate a lower time under GREEDY.")
    train_id = st.selectbox("Train to compare", sorted(frame["train_id"].unique()), key=f"{tag}_compare")
    comparison = paired_train(frame, train_id)
    saving = comparison.loc[comparison["Metric"] == TRAIN_COLUMNS["station_delay_min"], "FIXED_DB − GREEDY"].iloc[0]
    departure = comparison.loc[comparison["Metric"] == TRAIN_COLUMNS["actual_departure"], "FIXED_DB − GREEDY"].iloc[0]
    if abs(saving) <= TOL:
        st.write(f"Both dispatchers produced the same secondary delay for train **{train_id}**.")
    else:
        preferred = "GREEDY" if saving > 0 else "FIXED_DB"
        st.write(f"**{preferred}** produced {abs(saving):.2f} min less secondary delay for train **{train_id}**.")
    if abs(departure) > TOL:
        earlier = "GREEDY" if departure > 0 else "FIXED_DB"
        st.caption(f"{earlier} departed {abs(departure):.2f} min earlier.")
    display = comparison.map(lambda value: f"{value:.2f}" if isinstance(value, float) else value)
    st.dataframe(display, hide_index=True)
    export = comparison.assign(**{"Scenario ID": pair.experiment.key[0], "Seed": pair.experiment.key[1], "Train ID": train_id})
    st.download_button("Download paired train comparison", csv_bytes(export), f"{tag}_train_comparison.csv",
                       "text/csv", on_click="ignore")
