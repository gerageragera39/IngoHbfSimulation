
"""Offline Streamlit dashboard for completed Ingolstadt Hbf experiments."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st

import dashboard_pages as pages
from analyze_results import POLICIES
from dashboard_analytics import calculate, sensitivity
from station_dashboard_core import (
    aggregate_groups, configuration_key, describe_transfer, discover_pairs, train_frame,
    validate_experiment,
)

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("Overview", "Platform Utilization", "Passenger Transfer", "Statistical Analysis", "Train Data Explorer")

st.set_page_config(page_title="Ingolstadt Hbf — Dispatching Analytics", layout="wide",
                   initial_sidebar_state="auto")
st.markdown("""
<style>
    .block-container { max-width: 1480px; padding: 3.4rem 3rem 3rem; }
    .block-container h1 { font-size: 2.25rem; letter-spacing: -.035em; }
    .block-container :is(h2, h3, h4) { letter-spacing: -.02em; }
    [data-testid="stMetric"] {
        min-height: 94px; padding: .85rem 1rem; border-radius: 12px;
        background: #121D2B; border: 1px solid #2A3A4F;
        font-variant-numeric: tabular-nums;
    }
    [data-testid="stMetricLabel"] p { color: #ABBBD0; white-space: normal; }
    [data-testid="stMetricValue"] { font-size: 1.43rem; white-space: normal; }
    [data-testid="stMetricValue"] > div { white-space: normal; }
    [data-testid="stPlotlyChart"] { border: 1px solid #2A3A4F; border-radius: 12px; overflow: hidden; }
    [data-testid="stCaptionContainer"] { opacity: 1; }
    [data-testid="stCaptionContainer"] p { color: #ABBBD0; }
    ::selection { background: #1F6259; color: #F5FAFF; }
    @media (max-width: 720px) {
        .block-container { padding: 3rem 1rem 2rem; }
        .block-container h1 { font-size: 1.75rem; }
        [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
        [data-testid="stMainBlockContainer"] [data-testid="stColumn"] { min-width: min(100%, 290px); }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:has([data-testid="stMetric"]) {
            flex: 1 1 calc(50% - .5rem); min-width: 145px; }
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource(max_entries=1200, show_spinner=False)
def cached_pair(experiment):
    return validate_experiment(experiment)


@st.cache_resource(max_entries=2, show_spinner="Validating experiment CSVs…")
def cached_inventory(directory, experiments):
    return tuple(cached_pair(experiment) for experiment in experiments)


@st.cache_data(max_entries=20, show_spinner=False)
def cached_analytics(configuration, files, horizon, _pairs):
    return calculate(_pairs, horizon)


@st.cache_data(max_entries=12, show_spinner=False)
def cached_sensitivity(configuration, files, _groups):
    return sensitivity(_groups, configuration)


@st.cache_data(max_entries=15, show_spinner=False)
def cached_trains(experiment, _pair):
    return train_frame([_pair])


def choose(widget, label, options, key, preferred=None, format_func=str):
    """Keep a dependent selection only while it is available."""
    current = st.session_state.get(key)
    if current is not None and current not in options:
        del st.session_state[key]
    index = options.index(preferred) if preferred in options else 0
    return widget.selectbox(label, options, index=index, key=key, format_func=format_func)


def filename(*parts):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", "_".join(map(str, parts))).strip("._")


def select_aggregate(groups):
    families = sorted({key[0] for key in groups})
    st.sidebar.subheader("Aggregate scope")
    family = choose(st.sidebar, "Experiment family", families, "family", "MATRIX Monte Carlo")
    transfers = [config for batch, config in groups if batch == family]
    modes = sorted({config[0] if config else "Legacy" for config in transfers})
    mode = choose(st.sidebar, "Passenger transfer mode", modes, "mode", "MATRIX")
    cross, same = None, None
    if mode != "Legacy":
        times = sorted({config[1] for config in transfers if config and config[0] == mode})
        label = "Cross-island transfer time" if mode == "MATRIX" else "Uniform transfer time"
        cross = choose(st.sidebar, label, times, "cross", 4.0, lambda n: f"{n:g} min")
        same = 0.0
        if mode == "MATRIX":
            same_times = sorted({config[2] for config in transfers if config and config[:2] == (mode, cross)})
            same = choose(st.sidebar, "Same-island transfer time", same_times, "same", 1.0, lambda n: f"{n:g} min")
    selection = (family, (mode, cross, same) if mode != "Legacy" else None)
    policies = st.sidebar.multiselect("Aggregate dispatcher display", POLICIES, default=POLICIES)
    return selection, policies


def select_individual(inventory, preferred):
    candidates = [entry for entry in inventory if entry.pair is not None]
    if not candidates:
        st.info("No paired train results are available for individual inspection.")
        return None
    configurations = sorted({configuration_key(entry.pair) for entry in candidates},
                            key=lambda key: (key[0], key[1] or ("", 0, 0)))
    st.sidebar.subheader("Individual scenario")
    config = choose(st.sidebar, "Individual configuration", configurations, "individual_config", preferred,
                    lambda key: f"{key[0]} · {describe_transfer(key[1])}")
    items = {entry.experiment.key: entry for entry in candidates if configuration_key(entry.pair) == config}
    scenarios = sorted({sid for sid, _ in items})
    scenario = choose(st.sidebar, "Scenario ID", scenarios, "individual_scenario")
    seeds = sorted(seed for sid, seed in items if sid == scenario)
    seed = choose(st.sidebar, "Random seed", seeds, "individual_seed")
    policies = st.sidebar.multiselect("Individual dispatcher display", POLICIES, default=POLICIES)
    entry = items[scenario, seed]
    st.caption(f"{scenario} · seed {seed} · {describe_transfer(config[1])} · {entry.pair.summary['trains']} trains per simulation")
    if entry.status == "Partial":
        st.warning(entry.detail)
    if not policies:
        st.info("Select at least one dispatcher for this individual scenario.")
        return None
    return entry.pair, cached_trains(entry.experiment, entry.pair), policies


def inventory_panel(inventory, groups, repeated):
    aggregate = {pair.experiment.key for group in groups.values() for pair in group}
    complete = sum(entry.status == "Validated" for entry in inventory)
    excluded = len(inventory) - len(aggregate)
    st.caption(
        f"{len(inventory):,} discovered · {complete:,} fully validated pairs · "
        f"{len(aggregate):,} eligible batch pairs · {excluded:,} excluded from aggregate analysis"
    )
    with st.expander("CSV validation and exclusions"):
        if not inventory:
            st.info("No experiment CSVs with scenario and seed suffixes were found in this directory.")
            return
        detail = []
        for entry in inventory:
            key = entry.experiment.key
            message = entry.detail
            if key in repeated:
                message = "Repeated seed within this configuration. All pairs with this seed are excluded."
            elif entry.status == "Validated" and key not in aggregate:
                message = "Available for individual inspection. This scenario is outside a Monte Carlo batch."
            detail.append({
                "Scenario ID": key[0], "Seed": key[1], "Experiment family": entry.experiment.family[0],
                "Validation": entry.status, "Aggregate eligible": key in aggregate, "Detail": message,
            })
        scope = st.radio("Validation rows", ["Excluded only", "All discovered"], horizontal=True)
        records = pd.DataFrame(detail)
        if scope == "Excluded only":
            records = records[~records["Aggregate eligible"]]
        if records.empty:
            st.success("All discovered pairs are eligible for aggregate analysis.")
        else:
            pages.table(records, "experiment_validation.csv", button="Download validation report")


def main():
    st.title("Ingolstadt Hbf — Dispatching Analytics")
    st.caption("Discrete-event simulation and dispatcher performance analysis")
    page = st.sidebar.radio("Analysis section", PAGES)
    st.sidebar.divider()
    results = st.sidebar.text_input("Results directory", "Ingo/results",
                                    key="results_directory",
                                    help="Enter a local directory containing train results and original input CSVs.")
    if st.sidebar.button("Refresh CSVs"):
        for cache in (cached_pair, cached_inventory, cached_analytics, cached_sensitivity, cached_trains):
            cache.clear()
    try:
        if not results.strip():
            raise ValueError("Enter a results directory to load experiment CSVs.")
        directory = Path(results.strip()).expanduser()
        if not directory.is_absolute():
            directory = ROOT / directory
        if not directory.is_dir():
            raise ValueError(f"Results directory does not exist or is not a directory: {directory}")
        experiments = discover_pairs(directory)
    except (OSError, ValueError, RuntimeError) as exc:
        st.error(str(exc))
        return

    inventory = cached_inventory(directory.resolve(), experiments)
    groups, repeated = aggregate_groups(inventory)
    selection, policies = select_aggregate(groups) if groups else (None, ())
    inventory_panel(inventory, groups, repeated)
    st.header(page)

    if page == "Train Data Explorer":
        individual = select_individual(inventory, selection)
        if individual:
            pair, frame, dispatchers = individual
            pages.train_explorer(pair, frame, dispatchers, filename(*pair.experiment.key))
        return

    if selection is None:
        st.info("No fully validated Monte Carlo pairs are available. Inspect the validation report or select a results directory with batch exports.")
    elif not policies:
        st.info("Select at least one dispatcher to display the aggregate charts.")
    else:
        family, transfer = selection
        pairs = groups[selection]
        horizon = max(pair.last_departure for key, group in groups.items() if key[0] == family for pair in group)
        available_counts = [p.summary["trains"] for p in pairs]
        counts = str(min(available_counts))
        if min(available_counts) != max(available_counts):
            counts += f"–{max(available_counts)}"
        st.caption(
            f"{family} · {describe_transfer(transfer)} · {len(pairs)} paired scenarios · "
            f"{counts} trains per simulation · 0–{horizon:g} min family observation horizon"
        )
        if len(policies) == 1:
            st.caption("Paired comparisons use both dispatcher results.")
        tag = filename(family, describe_transfer(transfer))
        analytics = cached_analytics(selection, tuple(p.experiment for p in pairs), horizon, pairs)
        if page == "Overview":
            pages.overview(analytics, policies, tag)
        elif page == "Platform Utilization":
            pages.platform_utilization(analytics, policies, tag)
        elif page == "Passenger Transfer":
            pages.passenger(analytics, transfer, policies, tag)
        else:
            pages.statistical(analytics, policies, tag)
        if page in ("Passenger Transfer", "Statistical Analysis"):
            outcomes, excluded = cached_sensitivity(selection, experiments, groups)
            pages.comparisons(outcomes, excluded, transfer, tag)

    if page == "Platform Utilization":
        st.divider()
        st.subheader("Individual scenario occupancy")
        individual = select_individual(inventory, selection)
        if individual:
            pages.individual_platforms(*individual)


if __name__ == "__main__":
    main()
