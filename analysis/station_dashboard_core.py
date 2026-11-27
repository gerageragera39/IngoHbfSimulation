
"""Discover and validate completed AnyLogic exports independently of Streamlit."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from analyze_platforms import observation_horizon
from analyze_results import (
    FILENAME_RE, POLICIES, analyse_records, assignment_category, close,
    indexed, load_csv, require, transfer_configuration,
)

INPUT_RE = re.compile(r"delay_scenarios_(.+)_seed(\d+)\.csv")
REPLICATE_RE = re.compile(r"(.+)_S\d+$")
KNOWN_BATCH_RE = re.compile(r"(P1_BATCH|P2_MATRIX)_T\d+_S\d+$")
BATCH_NAMES = {"P1_BATCH": "UNIFORM Monte Carlo", "P2_MATRIX": "MATRIX Monte Carlo"}
INPUT_TIMES = ("scheduled_arrival", "scheduled_departure", "incoming_delay", "ready_time")
INPUT_COLUMNS = {"scenario_id", "scenario_seed", "train_id", "route_group",
                 "planned_platform", "allowed_platforms", *INPUT_TIMES}
TRAIN_COLUMNS = {
    "train_id": "Train ID",
    "route_group": "Route group",
    "planned_platform": "Planned platform",
    "assigned_platform": "Assigned platform",
    "scheduled_arrival": "Scheduled arrival (min)",
    "scheduled_departure": "Scheduled departure (min)",
    "incoming_delay": "Incoming delay (min)",
    "ready_time": "Ready time (min)",
    "platform_arrival": "Actual platform arrival (min)",
    "actual_departure": "Actual departure (min)",
    "min_dwell": "Minimum dwell time (min)",
    "waiting_min": "Waiting time (min)",
    "station_delay_min": "Secondary delay (min)",
    "reassigned": "Reassigned",
    "assignment_time": "Assignment time (min)",
    "passenger_transfer_min": "Passenger walking time (min)",
    "passengers_ready_time": "Passenger ready time (min)",
    "passenger_induced_delay_min": "Direct passenger-induced delay (min)",
    "assignment_category": "Assignment category",
    "scenario_id": "Scenario ID",
    "scenario_seed": "Seed",
    "policy": "Dispatcher",
}
INTEGER_COLUMNS = {"planned_platform", "assigned_platform", "scenario_seed", "reassigned"}
TIME_COLUMNS = set(INPUT_TIMES) | {
    "platform_arrival", "actual_departure", "min_dwell", "waiting_min", "station_delay_min",
    "assignment_time", "passenger_transfer_min", "passengers_ready_time",
    "passenger_induced_delay_min", "transfer_time_setting", "same_island_transfer_setting",
}

Key = tuple[str, int]
FileStamp = tuple[str, int, int, int]  # Absolute path, modified time, size, creation/change time.
Transfer = tuple[str, float, float] | None


@dataclass(frozen=True)
class Experiment:
    key: Key
    files: tuple[tuple[str, FileStamp], ...]

    @property
    def family(self):
        scenario, _ = self.key
        known = KNOWN_BATCH_RE.fullmatch(scenario)
        if known:
            return BATCH_NAMES[known[1]], True
        if re.fullmatch(r"S\d+", scenario):
            return "Historical scenarios", False
        if re.search(r"(?:^|_)(?:TEST|BASELINE|SMOKE|REPEAT(?:ED)?)(?:_|[A-Z]*\d|$)",
                     scenario, re.IGNORECASE):
            return "Standalone experiments", False
        replicate = REPLICATE_RE.fullmatch(scenario)
        if replicate:
            return re.sub(r"_T\d+(?:\.\d+)?$", "", replicate[1]), True
        return "Standalone experiments", False


@dataclass
class Pair:
    experiment: Experiment
    runs: dict
    inputs: dict | None
    transfer: Transfer
    summary: dict
    last_departure: float


@dataclass
class Validation:
    experiment: Experiment
    status: str
    detail: str
    pair: Pair | None = None


def discover_pairs(directory: Path) -> tuple[Experiment, ...]:
    """Include input-only and one-sided experiments in the validation inventory."""
    groups = defaultdict(list)
    for path in directory.iterdir():
        result = FILENAME_RE.fullmatch(path.name)
        original = INPUT_RE.fullmatch(path.name)
        if not (result or original) or not path.is_file():
            continue
        kind, scenario, seed = result.groups() if result else ("input", *original.groups())
        stat = path.stat()
        stamp = (str(path.resolve()), stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns)
        groups[scenario, int(seed)].append((kind, stamp))
    return tuple(Experiment(key, tuple(sorted(files))) for key, files in sorted(groups.items()))


def validate_experiment(experiment: Experiment) -> Validation:
    """Classify a pair and reuse the CLI's validation on the same loaded rows."""
    scenario, seed = experiment.key
    counts = Counter(kind for kind, _ in experiment.files)
    duplicates = [kind for kind, count in counts.items() if count > 1]
    missing = [policy for policy in POLICIES if not counts[policy]]
    if duplicates:
        return Validation(experiment, "Invalid", f"Duplicate files for {', '.join(duplicates)}.")
    if missing:
        return Validation(experiment, "Incomplete", f"Missing result files for {', '.join(missing)}.")
    paths = {kind: Path(stamp[0]) for kind, stamp in experiment.files}
    try:
        runs = {policy: indexed(load_csv(paths[policy]), paths[policy].name) for policy in POLICIES}
        inputs = indexed(load_csv(paths["input"]), paths["input"].name) if "input" in paths else None
        expected = 120 if KNOWN_BATCH_RE.fullmatch(scenario) else None
        summary, _, _ = analyse_records((scenario, seed), runs, inputs, expected)
        first = next(iter(runs["FIXED_DB"].values()))
        transfer = transfer_configuration(first) if "transfer_time_setting" in first else None
        # Phase 1 export has no mode column and encodes UNIFORM through its schema.
        if transfer and transfer[0] == "UNIFORM":
            transfer = (transfer[0], transfer[1], 0.0)
        horizon = observation_horizon(run.values() for run in runs.values())
        pair = Pair(experiment, runs, inputs, transfer, summary, horizon)
    except KeyError as exc:
        return Validation(experiment, "Invalid", f"Missing CSV column {exc.args[0]}.")
    except (OSError, ValueError, TypeError, csv.Error) as exc:
        return Validation(experiment, "Invalid", str(exc))
    if inputs is None:
        return Validation(experiment, "Partial",
                          "Original input CSV is missing. Result-pair checks passed, but input compatibility is unverified.",
                          pair)
    return Validation(experiment, "Validated", "All three CSV files passed validation.", pair)


def configuration_key(pair: Pair):
    return pair.experiment.family[0], pair.transfer


def describe_transfer(transfer: Transfer):
    if transfer is None:
        return "Legacy · passenger data unavailable"
    mode, cross, same = transfer
    return f"MATRIX · {cross:g} min cross-island · {same:g} min same-island" if mode == "MATRIX" else f"UNIFORM · {cross:g} min"


def aggregate_groups(inventory: tuple[Validation, ...]):
    """Keep only independent, fully validated batch pairs."""
    candidates = defaultdict(list)
    for entry in inventory:
        if entry.status == "Validated" and entry.experiment.family[1]:
            candidates[configuration_key(entry.pair)].append(entry.pair)
    groups, repeated = {}, set()
    for config, pairs in candidates.items():
        counts = Counter(pair.experiment.key[1] for pair in pairs)
        keep = []
        for pair in pairs:
            if counts[pair.experiment.key[1]] == 1:
                keep.append(pair)
            else:
                repeated.add(pair.experiment.key)
        if keep:
            groups[config] = tuple(keep)
    return groups, repeated


def equivalent_inputs(left: Pair, right: Pair) -> bool:
    """Compare source train records, ignoring experiment labels and row order."""
    if left.inputs is None or right.inputs is None or left.inputs.keys() != right.inputs.keys():
        return False
    for tid, a in left.inputs.items():
        b = right.inputs[tid]
        if a["route_group"] != b["route_group"] or int(a["planned_platform"]) != int(b["planned_platform"]):
            return False
        if set(map(int, a["allowed_platforms"].split("|"))) != set(map(int, b["allowed_platforms"].split("|"))):
            return False
        if any(not close(a[col], b[col]) for col in INPUT_TIMES):
            return False
        if not close(left.runs["FIXED_DB"][tid]["min_dwell"], right.runs["FIXED_DB"][tid]["min_dwell"]):
            return False
        if {k: a[k] for k in a.keys() - INPUT_COLUMNS} != {k: b[k] for k in b.keys() - INPUT_COLUMNS}:
            return False
    return True


def train_frame(pairs, policies=POLICIES):
    records = [row for pair in pairs for policy in policies for row in pair.runs[policy].values()]
    frame = pd.DataFrame(records)
    if frame.empty:
        return frame
    for column in INTEGER_COLUMNS & set(frame):
        frame[column] = frame[column].astype(int)
    for column in TIME_COLUMNS & set(frame):
        frame[column] = frame[column].astype(float)
    frame["assignment_category"] = [
        assignment_category(p, q) for p, q in zip(frame["planned_platform"], frame["assigned_platform"])
    ]
    return frame.sort_values(["scenario_id", "scenario_seed", "policy", "scheduled_arrival", "train_id"])


def filter_trains(frame, choices, ranges, positive=()):
    """Apply categorical, inclusive numeric-range and positive-value filters."""
    mask = pd.Series(True, index=frame.index)
    for field, values in choices.items():
        if values:
            mask &= frame[field].isin(values)
    for field, (low, high) in ranges.items():
        mask &= frame[field].between(low, high)
    for field in positive:
        mask &= frame[field] > 1e-7
    return frame.loc[mask]


def paired_train(frame, train_id):
    a = frame.loc[frame["train_id"] == train_id].set_index("policy")
    require(len(a) == 2 and set(a.index) == set(POLICIES)
            and len(a[["scenario_id", "scenario_seed"]].drop_duplicates()) == 1,
            "Train comparison requires both dispatchers for a single scenario and seed.")
    fields = ("assigned_platform", "waiting_min", "actual_departure", "station_delay_min",
              "passenger_transfer_min", "passenger_induced_delay_min")
    rows = []
    for field in fields:
        if field not in a:
            continue
        fixed, greedy = (a.at[policy, field] for policy in POLICIES)
        if field == "assigned_platform":
            fixed, greedy = f"Gleis {fixed}", f"Gleis {greedy}"
            difference = "Unchanged" if fixed == greedy else f"{fixed} → {greedy}"
        else:
            difference = fixed - greedy
        rows.append({"Metric": TRAIN_COLUMNS[field], "FIXED_DB": fixed,
                     "GREEDY": greedy, "FIXED_DB − GREEDY": difference})
    return pd.DataFrame(rows)


def queue_events(frame, horizon):
    """Step-function queue from exact ready and platform-arrival events."""
    records = []
    for policy, trains in frame.groupby("policy", sort=False):
        changes = Counter({0.0: 0, horizon: 0})
        for ready, arrival in zip(trains["ready_time"], trains["platform_arrival"]):
            changes[ready] += 1
            changes[arrival] -= 1
        length = 0
        for time, change in sorted(changes.items()):
            length += change
            records.append({"Dispatcher": policy, "Simulation time (min)": time,
                            "Waiting trains": length})
    return pd.DataFrame(records)


def csv_bytes(frame):
    return frame.to_csv(index=False).encode("utf-8-sig")
