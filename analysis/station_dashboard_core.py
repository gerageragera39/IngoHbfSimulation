"""Pure data/model utilities for the Ingolstadt Hbf simulation dashboard.

Reads existing AnyLogic train_results_*.csv; requires no event logger or AnyLogic API.
All times in the input CSV and here are simulation minutes.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Dict, Tuple

import numpy as np
import pandas as pd

POLICIES = ("FIXED_DB", "GREEDY")
PLATFORMS = (2, 3, 4, 5)
ROUTE_COLORS = {
    "RB16_S": "#36C9A6",
    "RE1_S": "#58A6FF",
    "ICE_S": "#FFB45E",
    "RB16_N": "#9D8CFF",
    "RE1_N": "#F472B6",
    "ICE_N": "#F87171",
}
REQUIRED = {
    "policy", "train_id", "route_group", "planned_platform", "assigned_platform",
    "scheduled_arrival", "scheduled_departure", "incoming_delay", "ready_time",
    "platform_arrival", "actual_departure", "min_dwell", "waiting_min",
    "station_delay_min", "reassigned", "scenario_id", "scenario_seed",
}
NUMERIC = (
    "planned_platform", "assigned_platform", "scheduled_arrival", "scheduled_departure",
    "incoming_delay", "ready_time", "platform_arrival", "actual_departure",
    "min_dwell", "waiting_min", "station_delay_min", "reassigned", "scenario_seed",
)
FILE_RE = re.compile(r"train_results_(FIXED_DB|GREEDY)_(S\d+)_seed(\d+)\.csv$")


def discover_pairs(results_dir: Path) -> Dict[Tuple[str, int], Dict[str, Path]]:
    """Return only scenarios having both strategy results, sorted by seed."""
    results_dir = Path(results_dir)
    all_files: Dict[Tuple[str, int], Dict[str, Path]] = {}
    if not results_dir.is_dir():
        return {}
    for path in results_dir.glob("train_results_*.csv"):
        match = FILE_RE.fullmatch(path.name)
        if not match:
            continue
        policy, scenario_id, seed_str = match.groups()
        all_files.setdefault((scenario_id, int(seed_str)), {})[policy] = path
    pairs = {key: paths for key, paths in all_files.items() if set(paths) == set(POLICIES)}
    return dict(sorted(pairs.items(), key=lambda item: (item[0][1], item[0][0])))


def read_results(path: Path, *, scenario_id: str, seed: int, policy: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: отсутствуют колонки: {', '.join(sorted(missing))}")
    if len(df) == 0:
        raise ValueError(f"{path.name}: пустой файл")
    if df["train_id"].isna().any() or df["train_id"].duplicated().any():
        raise ValueError(f"{path.name}: отсутствующие или повторяющиеся train_id")
    for col in NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="raise")
    if not df["policy"].eq(policy).all():
        raise ValueError(f"{path.name}: неверное значение policy")
    if not df["scenario_id"].eq(scenario_id).all():
        raise ValueError(f"{path.name}: неверное значение scenario_id")
    if not df["scenario_seed"].eq(seed).all():
        raise ValueError(f"{path.name}: неверный scenario_seed")
    if not df["assigned_platform"].isin(PLATFORMS).all():
        raise ValueError(f"{path.name}: обнаружена неизвестная платформа")
    if (df["platform_arrival"] + 1e-7 < df["ready_time"]).any():
        raise ValueError(f"{path.name}: поезд занимает платформу раньше ready_time")
    if (df["actual_departure"] + 1e-7 < df["platform_arrival"] + df["min_dwell"]).any():
        raise ValueError(f"{path.name}: нарушено минимальное время стоянки")
    expected_wait = np.maximum(0.0, df["platform_arrival"] - df["ready_time"])
    expected_delay = np.maximum(
        0.0,
        df["actual_departure"] - np.maximum(
            df["scheduled_departure"], df["ready_time"] + df["min_dwell"]
        ),
    )
    if not np.allclose(df["waiting_min"], expected_wait, atol=1e-7, rtol=1e-9):
        raise ValueError(f"{path.name}: waiting_min не совпадает с расчётом")
    if not np.allclose(df["station_delay_min"], expected_delay, atol=1e-7, rtol=1e-9):
        raise ValueError(f"{path.name}: station_delay_min не совпадает с расчётом")
    if not ((df["assigned_platform"] != df["planned_platform"]).astype(int) == df["reassigned"]).all():
        raise ValueError(f"{path.name}: неверный флаг reassigned")
    return df.sort_values(["scheduled_arrival", "train_id"]).reset_index(drop=True)


def load_pair(results_dir: Path, scenario_id: str, seed: int):
    """Read and cross-check an existing scenario, returning (fixed, greedy)."""
    paths = discover_pairs(results_dir).get((scenario_id, seed))
    if not paths:
        raise FileNotFoundError(f"Сценарий {scenario_id}, seed {seed}: нет двух файлов стратегий")
    fixed = read_results(paths["FIXED_DB"], scenario_id=scenario_id, seed=seed, policy="FIXED_DB")
    greedy = read_results(paths["GREEDY"], scenario_id=scenario_id, seed=seed, policy="GREEDY")
    a, b = fixed.set_index("train_id"), greedy.set_index("train_id")
    if set(a.index) != set(b.index):
        raise ValueError("Fixed DB / Greedy: наборы train_id не совпадают")
    for col in ("route_group", "planned_platform", "scheduled_arrival", "scheduled_departure", "incoming_delay", "ready_time", "min_dwell"):
        left, right = a[col].sort_index(), b[col].sort_index()
        if col == "route_group":
            good = left.equals(right)
        else:
            good = np.allclose(left.to_numpy(dtype=float), right.to_numpy(dtype=float), atol=1e-7, rtol=1e-9)
        if not good:
            raise ValueError(f"Fixed DB / Greedy: разные исходные данные, колонка {col}")
    return fixed, greedy


def classify(df: pd.DataFrame, t: float):
    """Reconstruct states from completed-journey records at minute t.

    Boundaries: ready <= t < platform_arrival => queue;
    platform_arrival <= t < actual_departure => platform;
    scheduled_arrival <= t < ready => approach.
    """
    future = df["scheduled_arrival"] > t
    approaching = (df["scheduled_arrival"] <= t) & (t < df["ready_time"])
    queued = (df["ready_time"] <= t) & (t < df["platform_arrival"])
    on_platform = (df["platform_arrival"] <= t) & (t < df["actual_departure"])
    departed = df["actual_departure"] <= t
    states = {
        "future": df[future].copy(),
        "approaching": df[approaching].copy(),
        "queued": df[queued].copy(),
        "platform": df[on_platform].copy(),
        "departed": df[departed].copy(),
    }
    for key, table in states.items():
        if key == "queued":
            table["waiting_now"] = np.maximum(0.0, t - table["ready_time"])
            table.sort_values(["ready_time", "train_id"], inplace=True)
        elif key == "platform":
            table.sort_values(["assigned_platform", "platform_arrival"], inplace=True)
    return states


def timeline_counts(df: pd.DataFrame, times: np.ndarray):
    """Count waiting and occupied trains over time without simulating again."""
    ready = df["ready_time"].to_numpy(dtype=float)[:, None]
    arrival = df["platform_arrival"].to_numpy(dtype=float)[:, None]
    departure = df["actual_departure"].to_numpy(dtype=float)[:, None]
    grid = np.asarray(times, dtype=float)[None, :]
    queue = ((ready <= grid) & (grid < arrival)).sum(axis=0)
    occupied = ((arrival <= grid) & (grid < departure)).sum(axis=0)
    return queue, occupied


def final_metrics(df: pd.DataFrame):
    return {
        "total_delay": float(df["station_delay_min"].sum()),
        "total_wait": float(df["waiting_min"].sum()),
        "reassigned": int(df["reassigned"].sum()),
        "count": len(df),
        "affected": int((df["station_delay_min"] > 1e-7).sum()),
    }


def metrics_now(df: pd.DataFrame, states: dict):
    departed = states["departed"]
    assigned = pd.concat([states["platform"], departed], ignore_index=True)
    return {
        "queue": len(states["queued"]),
        "approaching": len(states["approaching"]),
        "on_platform": len(states["platform"]),
        "departed": len(departed),
        "delay_so_far": float(departed["station_delay_min"].sum()),
        "reassign_so_far": int(assigned["reassigned"].sum()),
    }
