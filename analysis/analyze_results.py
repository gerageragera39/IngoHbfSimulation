#!/usr/bin/env python3
"""Paired Monte Carlo analysis for Ingolstadt Hbf AnyLogic simulation.

Run from the repository root:
    python analysis/analyze_results.py --input Ingo/results --output analysis/output \
        --scenario-glob '*_RNG2' --expected-trains 120

Requires Python 3.9+; matplotlib is needed only to make the PNG charts.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path

POLICIES = ("FIXED_DB", "GREEDY")
FILENAME_RE = re.compile(r"^train_results_(FIXED_DB|GREEDY)_(.+)_seed(\d+)\.csv$")
TOL = 1e-7

# Two-sided 95% Student-t quantiles, df = 1..30.
T_975 = (
    None, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365,
    2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145, 2.131,
    2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069,
    2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042,
)


def close(a, b, tol=TOL):
    return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=tol)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    require(bool(rows), f"Empty CSV: {path}")
    return rows


def indexed(rows, label):
    result = {}
    for r in rows:
        tid = r["train_id"]
        require(tid and tid not in result, f"Missing/duplicate train_id={tid!r} in {label}")
        result[tid] = r
    return result


def save_csv(path, rows, headers):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def validate_passenger_transfer(t, prefix):
    # Backward compatibility with old CSV files
    if "passenger_transfer_min" not in t:
        require(
            not t["scenario_id"].startswith("P2_"),
            f"{prefix}: missing transfer data",
        )
        return

    planned = int(t["planned_platform"])
    assigned = int(t["assigned_platform"])

    mode = t.get("transfer_mode", "UNIFORM")

    require(
        mode in ("UNIFORM", "MATRIX"),
        f"{prefix}: invalid transfer mode",
    )

    cross = float(t["transfer_time_setting"])
    same = float(
        t.get("same_island_transfer_setting", 0.0)
    )

    require(
        math.isfinite(cross) and cross >= 0
        and math.isfinite(same) and same >= 0,
        f"{prefix}: invalid transfer setting",
    )

    if planned == assigned:
        expected_transfer = 0.0

    elif mode == "UNIFORM":
        expected_transfer = cross

    elif (planned - 2) // 2 == (assigned - 2) // 2:
        expected_transfer = same

    else:
        expected_transfer = cross

    actual_transfer = float(t["passenger_transfer_min"])
    assignment = float(t["assignment_time"])
    passengers_ready = float(t["passengers_ready_time"])

    arrival = float(t["platform_arrival"])
    departure = float(t["actual_departure"])
    scheduled_departure = float(t["scheduled_departure"])
    min_dwell = float(t["min_dwell"])

    require(
        close(actual_transfer, expected_transfer),
        f"{prefix}: incorrect transfer time",
    )

    require(
        float(t["ready_time"]) - TOL
        <= assignment <= arrival + TOL,
        f"{prefix}: incorrect assignment time",
    )

    require(
        close(
            passengers_ready,
            assignment + expected_transfer,
        ),
        f"{prefix}: incorrect passenger ready time",
    )

    departure_without_transfer = max(
        scheduled_departure,
        arrival + min_dwell,
    )

    expected_departure = max(
        departure_without_transfer,
        passengers_ready,
    )

    require(
        close(departure, expected_departure),
        f"{prefix}: incorrect departure time",
    )

    expected_passenger_delay = max(
        0.0,
        passengers_ready - departure_without_transfer,
    )

    require(
        close(
            t["passenger_induced_delay_min"],
            expected_passenger_delay,
        ),
        f"{prefix}: incorrect passenger-induced delay",
    )

def validate_one(policy, rows_by_train, scenario_by_train, scenario_id, seed):
    occupancy = defaultdict(list)
    for tid, t in rows_by_train.items():
        prefix = f"{scenario_id} seed{seed} {policy} train {tid}"
        require(t["policy"] == policy, f"{prefix}: wrong policy")
        require(t["scenario_id"] == scenario_id, f"{prefix}: wrong scenario ID")
        require(int(t["scenario_seed"]) == seed, f"{prefix}: wrong seed")
        s = scenario_by_train[tid]
        require(s["scenario_id"] == scenario_id, f"{prefix}: scenario CSV ID mismatch")
        require(int(s["scenario_seed"]) == seed, f"{prefix}: scenario CSV seed mismatch")
        for col in ("route_group", "planned_platform"):
            require(t[col] == s[col], f"{prefix}: mismatch in {col}")
        for col in ("scheduled_arrival", "scheduled_departure", "incoming_delay", "ready_time"):
            require(close(t[col], s[col]), f"{prefix}: mismatch in {col}")

        planned, assigned = int(t["planned_platform"]), int(t["assigned_platform"])
        allowed = {int(n) for n in s["allowed_platforms"].split("|") if n}
        require(assigned in (2, 3, 4, 5) and assigned in allowed,
                f"{prefix}: illegal assigned platform {assigned}")
        if policy == "FIXED_DB":
            require(assigned == planned, f"{prefix}: FIXED_DB has reassignment")
        reassign = int(t["reassigned"])
        require(reassign == int(assigned != planned), f"{prefix}: reassignment flag wrong")

        scheduled_arrival = float(t["scheduled_arrival"])
        ready = float(t["ready_time"])
        incoming = float(t["incoming_delay"])
        platform_arrival = float(t["platform_arrival"])
        departure = float(t["actual_departure"])
        min_dwell = float(t["min_dwell"])
        waiting = float(t["waiting_min"])
        secondary = float(t["station_delay_min"])
        scheduled_departure = float(t["scheduled_departure"])
        require(incoming >= -TOL and min_dwell >= -TOL, f"{prefix}: negative input time")
        require(close(ready, scheduled_arrival + incoming), f"{prefix}: wrong ready_time")
        require(platform_arrival >= ready - TOL, f"{prefix}: on platform before ready")
        require(departure + TOL >= platform_arrival + min_dwell,
                f"{prefix}: minimum dwell violation")
        require(close(waiting, max(0.0, platform_arrival - ready)),
                f"{prefix}: waiting time mismatch")
        expected_secondary = max(0.0, departure - max(scheduled_departure, ready + min_dwell))
        require(close(secondary, expected_secondary), f"{prefix}: secondary delay mismatch")
        validate_passenger_transfer(t, prefix)
        occupancy[assigned].append((platform_arrival, departure, tid))

    for platform, windows in occupancy.items():
        windows.sort()
        for prev, cur in zip(windows, windows[1:]):
            require(cur[0] >= prev[1] - TOL,
                    f"{scenario_id} seed{seed} {policy}: Gleis {platform} overlaps "
                    f"{prev[2]} and {cur[2]}")


def confidence_interval(values):
    """Paired scenario-level mean and 95% Student-t interval."""
    n = len(values)
    mean = statistics.mean(values)
    if n < 2:
        return mean, None, None
    std = statistics.stdev(values)
    df = n - 1
    # For df > 30 use the first-order expansion of the t critical value.
    critical = T_975[df] if df <= 30 else 1.959964 + 2.372 / df
    halfwidth = critical * std / math.sqrt(n)
    return mean, mean - halfwidth, mean + halfwidth


def analyse_scenario(key, paths, scenario_dir, expected_trains):
    scenario_id, seed = key
    require(set(paths) == set(POLICIES),
            f"Missing one policy for {scenario_id} seed{seed}: have {list(paths)}")
    source_path = scenario_dir / f"delay_scenarios_{scenario_id}_seed{seed}.csv"
    require(source_path.exists(), f"Missing input scenario CSV: {source_path}")
    inputs = indexed(load_csv(source_path), str(source_path))
    fixed = indexed(load_csv(paths["FIXED_DB"]), str(paths["FIXED_DB"]))
    greedy = indexed(load_csv(paths["GREEDY"]), str(paths["GREEDY"]))
    require(set(fixed) == set(greedy) == set(inputs),
            f"Train IDs do not match across 3 CSV files for {scenario_id} seed{seed}")
    if expected_trains is not None:
        require(len(inputs) == expected_trains,
                f"{scenario_id} seed{seed}: {len(inputs)} trains, expected {expected_trains}")
    validate_one("FIXED_DB", fixed, inputs, scenario_id, seed)
    validate_one("GREEDY", greedy, inputs, scenario_id, seed)
    # Verify identical passenger model settings
    if scenario_id.startswith("P2_"):
        configurations = set()

        for row in list(fixed.values()) + list(greedy.values()):
            configurations.add((
                row["transfer_mode"],
                float(row["transfer_time_setting"]),
                float(row["same_island_transfer_setting"]),
            ))

        require(
            len(configurations) == 1,
            f"{scenario_id}: inconsistent transfer settings",
        )
    for tid in fixed:
        for col in ("route_group", "planned_platform", "scheduled_arrival",
                    "scheduled_departure", "incoming_delay", "ready_time", "min_dwell"):
            if col in ("route_group", "planned_platform"):
                require(fixed[tid][col] == greedy[tid][col],
                        f"{scenario_id}: Fixed/Greedy differ for {tid}, {col}")
            else:
                require(close(fixed[tid][col], greedy[tid][col]),
                        f"{scenario_id}: Fixed/Greedy differ for {tid}, {col}")

    pair_rows = []
    for tid in sorted(inputs, key=lambda t: (t[0], int(t[1:]) if t[1:].isdigit() else t)):
        a, b = fixed[tid], greedy[tid]
        delay_a, delay_b = float(a["station_delay_min"]), float(b["station_delay_min"])
        waiting_a, waiting_b = float(a["waiting_min"]), float(b["waiting_min"])
        pair_rows.append({
            "scenario_id": scenario_id, "scenario_seed": seed, "train_id": tid,
            "route_group": a["route_group"], "incoming_delay_min": float(a["incoming_delay"]),
            "planned_platform": a["planned_platform"],
            "fixed_platform": a["assigned_platform"], "greedy_platform": b["assigned_platform"],
            "fixed_delay_min": delay_a, "greedy_delay_min": delay_b,
            "delay_saved_min": delay_a - delay_b,
            "fixed_wait_min": waiting_a, "greedy_wait_min": waiting_b,
            "wait_saved_min": waiting_a - waiting_b,
            "greedy_reassigned": int(b["reassigned"]),
        })

    total_a = sum(float(r["station_delay_min"]) for r in fixed.values())
    total_b = sum(float(r["station_delay_min"]) for r in greedy.values())
    wait_a = sum(float(r["waiting_min"]) for r in fixed.values())
    wait_b = sum(float(r["waiting_min"]) for r in greedy.values())
    n = len(inputs)
    delays_in = [float(x["incoming_delay"]) for x in inputs.values()]
    summary = {
        "scenario_id": scenario_id, "scenario_seed": seed, "trains": n,
        "fixed_total_delay_min": total_a, "greedy_total_delay_min": total_b,
        "delay_saved_min": total_a - total_b,
        "delay_reduction_pct": 100 * (total_a - total_b) / total_a if total_a else "",
        "fixed_mean_delay_min": total_a / n, "greedy_mean_delay_min": total_b / n,
        "fixed_total_wait_min": wait_a, "greedy_total_wait_min": wait_b,
        "fixed_affected_trains": sum(float(x["station_delay_min"]) > TOL for x in fixed.values()),
        "greedy_affected_trains": sum(float(x["station_delay_min"]) > TOL for x in greedy.values()),
        "fixed_max_delay_min": max(float(x["station_delay_min"]) for x in fixed.values()),
        "greedy_max_delay_min": max(float(x["station_delay_min"]) for x in greedy.values()),
        "greedy_reassignments": sum(int(x["reassigned"]) for x in greedy.values()),
        "greedy_better_trains": sum(r["delay_saved_min"] > TOL for r in pair_rows),
        "equal_trains": sum(abs(r["delay_saved_min"]) <= TOL for r in pair_rows),
        "greedy_worse_trains": sum(r["delay_saved_min"] < -TOL for r in pair_rows),
        "zero_incoming_trains": sum(d <= TOL for d in delays_in),
        "positive_incoming_trains": sum(d > TOL for d in delays_in),
        "mean_incoming_delay_min": statistics.mean(delays_in),
    }
    return summary, pair_rows, delays_in


def create_charts(summaries, incoming_delays, output):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("Charts skipped: matplotlib is not installed. Run 'python -m pip install matplotlib'.")
        return

    labels = [x["scenario_id"] for x in summaries]
    x = list(range(len(summaries)))
    width = 0.38
    fig, ax = plt.subplots(figsize=(max(8, len(x) * 1.2), 5))
    ax.bar([i - width / 2 for i in x], [r["fixed_total_delay_min"] for r in summaries],
           width, label="FIXED_DB")
    ax.bar([i + width / 2 for i in x], [r["greedy_total_delay_min"] for r in summaries],
           width, label="GREEDY")
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.set_ylabel("Total secondary delay (min)")
    ax.set_title("Ingolstadt Hbf: paired scenarios")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "delay_by_scenario.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(max(8, len(x) * 1.2), 5))
    ax.bar(labels, [r["delay_saved_min"] for r in summaries])
    ax.axhline(0, linewidth=1)
    ax.set_ylabel("FIXED_DB minus GREEDY (min)")
    ax.set_title("Paired savings in total secondary delay")
    ax.tick_params(axis="x", labelrotation=35)
    fig.tight_layout()
    fig.savefig(output / "paired_savings.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(incoming_delays, bins=25)
    ax.set_xlabel("Incoming delay (min)")
    ax.set_ylabel("Train observations")
    ax.set_title("Synthetic incoming delays across all scenarios")
    fig.tight_layout()
    fig.savefig(output / "incoming_delay_histogram.png", dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("Ingo/results"),
                        help="Directory containing AnyLogic result and scenario CSV files")
    parser.add_argument("--output", type=Path, default=Path("analysis/output"),
                        help="Directory for summary CSV files and charts")
    parser.add_argument("--scenario-glob", default="*_RNG2",
                        help="Only analyse scenario IDs matching this pattern (default: *_RNG2)")
    parser.add_argument("--expected-trains", type=int, default=120,
                        help="Require this many trains per policy/scenario; 0 disables check")
    args = parser.parse_args()
    require(args.input.is_dir(), f"Input directory does not exist: {args.input}")
    groups = defaultdict(dict)
    for path in args.input.glob("train_results_*.csv"):
        match = FILENAME_RE.fullmatch(path.name)
        if not match:
            continue   # Ignore old files without scenario/seed suffixes.
        policy, scenario_id, seed_str = match.groups()
        if not fnmatch.fnmatchcase(scenario_id, args.scenario_glob):
            continue   # Ignore S001 from the old, biased RNG.
        key = (scenario_id, int(seed_str))
        require(policy not in groups[key], f"Duplicate policy file: {path}")
        groups[key][policy] = path
    require(groups, f"No matching paired scenarios in {args.input}; pattern={args.scenario_glob}")
    summaries, pairs, incoming = [], [], []
    for key, paths in sorted(groups.items(), key=lambda pair: pair[0]):
        summary, current_pairs, delays_in = analyse_scenario(
            key, paths, args.input, None if args.expected_trains == 0 else args.expected_trains
        )
        summaries.append(summary)
        pairs.extend(current_pairs)
        incoming.extend(delays_in)

    args.output.mkdir(parents=True, exist_ok=True)
    save_csv(args.output / "scenario_summary.csv", summaries, list(summaries[0]))
    save_csv(args.output / "train_pair_comparison.csv", pairs, list(pairs[0]))

    paired = [s["delay_saved_min"] for s in summaries]
    mean, lower, upper = confidence_interval(paired)
    fixed_sum = sum(s["fixed_total_delay_min"] for s in summaries)
    greedy_sum = sum(s["greedy_total_delay_min"] for s in summaries)
    ratio = 100 * (fixed_sum - greedy_sum) / fixed_sum if fixed_sum else float('nan')
    info = [
        ("number_of_scenarios", len(summaries)),
        ("number_of_paired_train_observations", len(pairs)),
        ("sum_fixed_delay_min", fixed_sum),
        ("sum_greedy_delay_min", greedy_sum),
        ("total_delay_reduction_pct", ratio),
        ("mean_paired_scenario_saving_min", mean),
        ("paired_saving_ci95_lower_min", lower if lower is not None else ""),
        ("paired_saving_ci95_upper_min", upper if upper is not None else ""),
        ("scenarios_greedy_better", sum(x > TOL for x in paired)),
        ("scenarios_equal", sum(abs(x) <= TOL for x in paired)),
        ("scenarios_greedy_worse", sum(x < -TOL for x in paired)),
    ]
    save_csv(args.output / "overall_summary.csv",
             [{"metric": k, "value": v} for k, v in info], ["metric", "value"])
    create_charts(summaries, incoming, args.output)
    print("\nValidated and analyzed paired scenarios:")
    for row in summaries:
        print(f"  {row['scenario_id']} seed={row['scenario_seed']}: "
              f"FIXED_DB={row['fixed_total_delay_min']:.2f} min; "
              f"GREEDY={row['greedy_total_delay_min']:.2f} min; "
              f"saved={row['delay_saved_min']:.2f} min")
    print(f"\nScenarios: {len(summaries)}; paired trains: {len(pairs)}")
    print(f"Aggregate secondary delay reduction: {ratio:.1f}%")
    print(f"Mean paired saving per scenario: {mean:.2f} minutes")
    if lower is not None:
        print(f"95% Student-t CI for mean scenario saving: [{lower:.2f}, {upper:.2f}] min")
    else:
        print("95% CI unavailable with only one scenario; run at least two paired scenarios.")
    print(f"Results saved to: {args.output.resolve()}")
    print("Note: these are synthetic scenarios; CI describes variability under the chosen simulator inputs, not DB reality.")


if __name__ == "__main__":
    main()
