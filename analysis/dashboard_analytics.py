
"""Scenario-level comparisons and descriptive metrics for validated exports."""

from __future__ import annotations

import statistics
from dataclasses import dataclass

import numpy as np
import pandas as pd

from analyze_results import PLATFORMS, POLICIES, TOL, confidence_interval, delay_reduction
from analyze_platforms import metrics, run_metrics
from station_dashboard_core import describe_transfer, equivalent_inputs, train_frame


@dataclass
class Analytics:
    trains: pd.DataFrame
    scenarios: pd.DataFrame
    runs: pd.DataFrame
    platforms: pd.DataFrame
    assignments: pd.DataFrame


def calculate(pairs, horizon):
    """Build tables for one configuration using the family observation horizon."""
    platforms, assignments, runs = [], [], []
    for pair in pairs:
        scenario, seed = pair.experiment.key
        for policy in POLICIES:
            rows = list(pair.runs[policy].values())
            base = {"scenario_id": scenario, "seed": seed, "policy": policy, "horizon_min": horizon}
            loads, matrix = metrics(rows, horizon)
            platforms.extend(dict(base, **row) for row in loads)
            assignments.extend(
                dict(base, planned_platform=p, assigned_platform=q, train_count=matrix[p, q])
                for p in PLATFORMS for q in PLATFORMS
            )
            prefix = "fixed" if policy == "FIXED_DB" else "greedy"
            affected = pair.summary[f"{prefix}_affected_trains"]
            total_wait = pair.summary[f"{prefix}_total_wait_min"]
            runs.append(dict(
                base, **run_metrics(rows, loads, matrix), total_wait_min=total_wait,
                mean_wait_min=total_wait / len(rows), affected_trains=affected,
                affected_pct=100 * affected / len(rows),
                reassignments=sum(int(row["reassigned"]) for row in rows),
            ))
    return Analytics(
        train_frame(pairs),
        pd.DataFrame([pair.summary for pair in pairs]),
        pd.DataFrame(runs),
        pd.DataFrame(platforms),
        pd.DataFrame(assignments),
    )


def platform_summary(platforms):
    by_platform = platforms.groupby(["policy", "platform"], sort=False)
    result = by_platform.agg(
        scenarios=("scenario_id", "size"),
        horizon_min=("horizon_min", "first"),
        mean_utilization_pct=("utilization_pct", "mean"),
        total_busy_min=("busy_min", "sum"),
        mean_busy_min=("busy_min", "mean"),
        total_train_count=("train_count", "sum"),
        mean_train_count=("train_count", "mean"),
        mean_passenger_delay_min=("passenger_induced_delay_min", "mean"),
    )
    result["pooled_mean_occupancy_min"] = (
        result["total_busy_min"] / result["total_train_count"].replace(0, np.nan)
    )
    return result.reset_index()


def assignment_summary(assignments):
    return assignments.groupby(
        ["policy", "planned_platform", "assigned_platform"], sort=False, as_index=False
    ).agg(total_train_count=("train_count", "sum"), mean_train_count=("train_count", "mean"))


def paired_statistics(scenarios):
    fixed = scenarios["fixed_total_delay_min"]
    greedy = scenarios["greedy_total_delay_min"]
    savings = scenarios["delay_saved_min"].tolist()
    mean, low, high = confidence_interval(savings)
    return {
        "pairs": len(savings),
        "fixed_total_min": float(fixed.sum()),
        "greedy_total_min": float(greedy.sum()),
        "fixed_mean_min": float(fixed.mean()),
        "greedy_mean_min": float(greedy.mean()),
        "mean_saving_min": mean,
        "std_saving_min": statistics.stdev(savings) if len(savings) > 1 else None,
        "ci_low_min": low,
        "ci_high_min": high,
        "reduction_pct": delay_reduction(float(fixed.sum()), float(greedy.sum())),
        "greedy_wins": sum(value > TOL for value in savings),
        "equal": sum(abs(value) <= TOL for value in savings),
        "fixed_wins": sum(value < -TOL for value in savings),
    }


def passenger_summary(trains, runs):
    summaries = []
    for policy, rows in trains.groupby("policy", sort=False):
        moved = rows[rows["reassigned"] == 1]
        same = int((moved["assignment_category"] == "Same island").sum())
        cross = len(moved) - same
        available = "passenger_induced_delay_min" in rows and rows["passenger_induced_delay_min"].notna().all()
        summaries.append({
            "Dispatcher": policy,
            "Total reassignments": len(moved),
            "Same island": same,
            "Cross island": cross,
            "Same-island share of reassignments (%)": 100 * same / len(moved) if len(moved) else None,
            "Cross-island share of reassignments (%)": 100 * cross / len(moved) if len(moved) else None,
            "All trains reassigned (%)": 100 * len(moved) / len(rows),
            "Mean walking time when reassigned (min)": (
                moved["passenger_transfer_min"].mean() if available and len(moved) else None
            ),
            "Trains with positive direct delay": (
                int((rows["passenger_induced_delay_min"] > TOL).sum()) if available else None
            ),
            "Mean direct passenger delay per scenario (min)": (
                runs.loc[runs["policy"] == policy, "passenger_induced_delay_min"].mean()
                if available else None
            ),
        })
    return pd.DataFrame(summaries)


def match_configurations(reference, candidate):
    """Match independent seeds only when both original inputs are equivalent."""
    left = {p.experiment.key[1]: p for p in reference}
    right = {p.experiment.key[1]: p for p in candidate}
    if len(left) != len(reference) or len(right) != len(candidate):
        raise ValueError("Cross-configuration comparison requires one pair per seed.")
    matched, excluded = [], []
    for seed in sorted(left.keys() | right.keys()):
        if seed not in left:
            reason = "Missing reference seed"
        elif seed not in right:
            reason = "Missing comparison seed"
        elif left[seed].inputs is None or right[seed].inputs is None:
            reason = "Original inputs unavailable"
        elif not equivalent_inputs(left[seed], right[seed]):
            reason = "Original train inputs differ"
        else:
            matched.append((left[seed], right[seed]))
            continue
        excluded.append((seed, reason))
    return matched, excluded


def sensitivity(groups, reference_key):
    """Compare each configuration with the selected reference on matched seeds."""
    family, reference_transfer = reference_key
    reference = groups[reference_key]
    outcomes, exclusions = [], []
    for (other_family, transfer), candidate in groups.items():
        # Cross-family comparisons use the two controlled Phase 1/2 batches.
        controlled = {"UNIFORM Monte Carlo", "MATRIX Monte Carlo"}
        if transfer is None or reference_transfer is None:
            continue
        if family != other_family and {family, other_family} != controlled:
            continue
        if (other_family, transfer) == reference_key:
            continue
        label = describe_transfer(transfer)
        matched, excluded = match_configurations(reference, candidate)
        exclusions.extend({"Comparison configuration": label, "Seed": seed, "Reason": reason}
                          for seed, reason in excluded)
        if not matched:
            continue
        differences = [b.summary["delay_saved_min"] - a.summary["delay_saved_min"] for a, b in matched]
        change, low, high = confidence_interval(differences)
        control = [a.summary["delay_saved_min"] for a, _ in matched]
        actual = [b.summary["delay_saved_min"] for _, b in matched]
        outcomes.append({
            "Comparison configuration": label,
            "Mode": transfer[0],
            "Uniform / cross-island time (min)": transfer[1],
            "Same-island time (min)": transfer[2] if transfer[0] == "MATRIX" else None,
            "Matched seeds": len(matched),
            "Reference mean saving (min)": statistics.mean(control),
            "Comparison mean saving (min)": statistics.mean(actual),
            "Change in paired saving (min)": change,
            "95% CI lower (min)": low,
            "95% CI upper (min)": high,
        })
    return pd.DataFrame(outcomes), pd.DataFrame(exclusions)
