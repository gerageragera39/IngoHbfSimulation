
"""Synthetic validation tests and regression checks against checked-in results."""

import csv
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

from analyze_results import PLATFORMS, assignment_category, delay_reduction, transfer_minutes
from dashboard_analytics import (
    assignment_summary, calculate, match_configurations, paired_statistics, passenger_summary,
    platform_summary, sensitivity,
)
from station_dashboard_core import (
    aggregate_groups, csv_bytes, discover_pairs, equivalent_inputs, filter_trains, paired_train,
    queue_events, train_frame, validate_experiment,
)


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fixture(directory, scenario="TIMETABLE_T4_S001", seed=101, *, transfer=None, incoming=0):
    """An independent two-train schedule with same-island and cross-island moves."""
    source, fixed, greedy = [], [], []
    for train, planned, assigned in (("T1", 2, 3), ("T2", 4, 2)):
        shared = dict(
            scenario_id=scenario, scenario_seed=seed, train_id=train, route_group=f"RB_{train}",
            planned_platform=planned, scheduled_arrival=0, scheduled_departure=3,
            incoming_delay=incoming, ready_time=incoming,
        )
        source.append(dict(shared, allowed_platforms="2|3|4|5"))
        for policy, rows, platform, wait in (("FIXED_DB", fixed, planned, 2), ("GREEDY", greedy, assigned, 0)):
            arrival = incoming + wait
            # Passenger fixture values follow the declared movement independently of production helpers.
            mode, cross, same = transfer or ("UNIFORM", 0, None)
            walking = 0 if platform == planned else same if mode == "MATRIX" and train == "T1" else cross
            passengers = arrival + walking
            base_departure = arrival + 3
            departure = max(base_departure, passengers)
            row = dict(shared, policy=policy, assigned_platform=platform, min_dwell=3,
                       platform_arrival=arrival, actual_departure=departure, waiting_min=wait,
                       station_delay_min=departure - (incoming + 3), reassigned=int(planned != platform))
            if transfer is not None:
                row.update(transfer_time_setting=cross, assignment_time=arrival,
                           passenger_transfer_min=walking, passengers_ready_time=passengers,
                           passenger_induced_delay_min=departure - base_departure)
                if mode == "MATRIX":
                    row.update(transfer_mode=mode, same_island_transfer_setting=same)
            rows.append(row)
    files = {"input": directory / f"delay_scenarios_{scenario}_seed{seed}.csv"}
    files.update({policy: directory / f"train_results_{policy}_{scenario}_seed{seed}.csv"
                  for policy in ("FIXED_DB", "GREEDY")})
    for kind, rows in zip(files, (source, fixed, greedy)):
        write_csv(files[kind], rows)
    return files


def edit_csv(path, edit):
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    edit(rows)
    write_csv(path, rows)


def inventory(directory):
    return tuple(validate_experiment(exp) for exp in discover_pairs(directory))


class ValidationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)

    def test_legacy_modern_and_arbitrary_scenario_ids(self):
        names = (
            "S002", "S101", "P1_BASELINE", "P1_T0", "P1_T2", "P1_T5",
            "P1_BATCH_T0_S001", "P1_BATCH_T4_S001", "P1_BATCH_T6_S001",
            "P2_TEST_U6", "P2_TEST_M6", "P2_MATRIX_T2_S001", "P2_MATRIX_T4_S001",
            "P2_MATRIX_T6_S001", "2040-Hbf.winter_seed99_ICE",
        )
        for name in names:
            fixture(self.directory, name)
        entries = discover_pairs(self.directory)
        self.assertEqual(set(names), {item.key[0] for item in entries})
        self.assertEqual({101}, {item.key[1] for item in entries})
        self.assertTrue(all(len(item.files) == 3 for item in entries))

    def test_incomplete_pair_and_input_only_discovery(self):
        files = fixture(self.directory)
        files["GREEDY"].unlink()
        item, = inventory(self.directory)
        self.assertEqual(item.status, "Incomplete")
        self.assertIn("GREEDY", item.detail)
        files["FIXED_DB"].unlink()
        item, = inventory(self.directory)
        self.assertEqual(item.status, "Incomplete")
        self.assertIn("FIXED_DB", item.detail)

    def test_partial_without_original_input_excluded_from_aggregate(self):
        files = fixture(self.directory, transfer=("UNIFORM", 4, None))
        files["input"].unlink()
        entries = inventory(self.directory)
        item, = entries
        self.assertEqual(item.status, "Partial")
        self.assertIsNone(item.pair.inputs)
        self.assertEqual(aggregate_groups(entries)[0], {})

    def test_duplicate_file_same_numeric_seed(self):
        files = fixture(self.directory)
        duplicate = files["GREEDY"].with_name(files["GREEDY"].name.replace("seed101", "seed0101"))
        duplicate.write_bytes(files["GREEDY"].read_bytes())
        item, = inventory(self.directory)
        self.assertEqual(item.status, "Invalid")
        self.assertIn("Duplicate files", item.detail)

    def test_validation_reports_data_errors(self):
        mutations = (
            ("GREEDY", "train_id", "UNKNOWN", "Train IDs do not match"),
            ("GREEDY", "train_id", "T2", "duplicate train_id"),
            ("GREEDY", "scenario_id", "OTHER", "wrong scenario ID"),
            ("GREEDY", "scenario_seed", "102", "wrong seed"),
            ("input", "scenario_id", "OTHER", "scenario CSV ID mismatch"),
            ("input", "scenario_seed", "102", "scenario CSV seed mismatch"),
            ("input", "incoming_delay", "5", "mismatch in incoming_delay"),
            ("GREEDY", "assigned_platform", "7", "illegal assigned platform"),
            ("GREEDY", "planned_platform", "1", "illegal planned platform"),
            ("input", "allowed_platforms", "2", "incompatible assigned platform"),
            ("GREEDY", "actual_departure", "inf", "invalid numerical time"),
            ("GREEDY", "min_dwell", "nan", "invalid numerical time"),
            ("GREEDY", "passenger_induced_delay_min", "3", "incorrect passenger-induced delay"),
            ("GREEDY", "passenger_transfer_min", "2", "incorrect transfer time"),
        )
        for kind, field, value, message in mutations:
            with self.subTest(kind=kind, field=field, value=value):
                files = fixture(self.directory, transfer=("MATRIX", 4, 1))
                edit_csv(files[kind], lambda rows: rows[0].update({field: value}))
                item, = inventory(self.directory)
                self.assertEqual(item.status, "Invalid")
                self.assertIn(message, item.detail)

    def test_overlap(self):
        files = fixture(self.directory)
        edit_csv(files["GREEDY"], lambda rows: rows[1].update(assigned_platform="3"))
        item, = inventory(self.directory)
        self.assertEqual(item.status, "Invalid")
        self.assertIn("overlaps", item.detail)

    def test_passenger_schema_and_settings_must_match(self):
        files = fixture(self.directory, transfer=("MATRIX", 4, 1))
        edit_csv(files["FIXED_DB"], lambda rows: [row.update(transfer_time_setting="5") for row in rows])
        item, = inventory(self.directory)
        self.assertEqual(item.status, "Invalid")
        self.assertIn("Inconsistent passenger model settings", item.detail)
        edit_csv(files["GREEDY"], lambda rows: [row.pop("assignment_time") for row in rows])
        item, = inventory(self.directory)
        self.assertIn("incomplete passenger fields", item.detail)

    def test_train_count_only_required_for_known_batches(self):
        fixture(self.directory, "P1_BATCH_T4_S001", transfer=("UNIFORM", 4, None))
        fixture(self.directory, "NEW_TIMETABLE_T4_S001", transfer=("UNIFORM", 4, None))
        future, phase_one = inventory(self.directory)
        self.assertEqual(future.status, "Validated")
        self.assertEqual(phase_one.status, "Invalid")
        self.assertIn("2 trains, expected 120", phase_one.detail)

    def test_legacy_passenger_metrics_stay_unavailable(self):
        fixture(self.directory, "S002")
        result, = inventory(self.directory)
        self.assertEqual(result.status, "Validated")
        pair = result.pair
        self.assertIsNone(pair.transfer)
        analytics = calculate([pair], pair.last_departure)
        self.assertNotIn("passenger_transfer_min", analytics.trains)
        self.assertTrue(analytics.platforms["passenger_induced_delay_min"].isna().all())
        summary = passenger_summary(analytics.trains, analytics.runs)
        self.assertTrue(summary["Mean direct passenger delay per scenario (min)"].isna().all())
        self.assertEqual(aggregate_groups([result])[0], {})

    def test_repeat_and_smoke_scenarios_stay_outside_batches(self):
        for scenario in ("NEW_SMOKE_S001", "NEW_TEST_S001", "NEW_BASELINE_S001", "NEW_REPEATED_S001"):
            fixture(self.directory, scenario)
        entries = inventory(self.directory)
        self.assertTrue(all(item.status == "Validated" for item in entries))
        self.assertEqual(aggregate_groups(entries)[0], {})


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)

    def test_transfer_modes_use_metadata_and_classify_assignments(self):
        fixture(self.directory, "TIMETABLE_T0_S001", transfer=("MATRIX", 4, 1))
        fixture(self.directory, "OTHER_T9_S001", transfer=("UNIFORM", 3, None))
        uniform, matrix = (item.pair for item in inventory(self.directory))
        self.assertEqual(uniform.transfer, ("UNIFORM", 3, 0))
        self.assertEqual(matrix.transfer, ("MATRIX", 4, 1))
        self.assertEqual([assignment_category(2, p) for p in (2, 3, 4)], ["Unchanged", "Same island", "Cross island"])
        self.assertEqual([transfer_minutes(matrix.transfer, 2, p) for p in (2, 3, 4)], [0, 1, 4])
        self.assertEqual([transfer_minutes(uniform.transfer, 2, p) for p in (2, 3, 4)], [0, 3, 3])
        data = calculate([matrix], matrix.last_departure)
        passenger = passenger_summary(data.trains, data.runs).set_index("Dispatcher")
        self.assertEqual(passenger.at["GREEDY", "Same island"], 1)
        self.assertEqual(passenger.at["GREEDY", "Cross island"], 1)
        self.assertEqual(passenger.at["GREEDY", "Mean walking time when reassigned (min)"], 2.5)
        self.assertEqual(passenger.at["GREEDY", "Mean direct passenger delay per scenario (min)"], 1)

    def test_common_horizon_and_platform_metrics(self):
        fixture(self.directory, "TIMETABLE_T1_S001", transfer=("MATRIX", 1, 1))
        fixture(self.directory, "TIMETABLE_T8_S001", transfer=("MATRIX", 8, 1))
        a, b = (item.pair for item in inventory(self.directory))
        horizon = max(a.last_departure, b.last_departure)
        self.assertEqual(horizon, 8)
        loads = calculate([a], horizon)
        self.assertEqual(set(loads.platforms["horizon_min"]), {horizon})
        fixed = loads.platforms[loads.platforms["policy"] == "FIXED_DB"]
        self.assertEqual(fixed["busy_min"].tolist(), [3, 0, 3, 0])
        self.assertEqual(fixed["utilization_pct"].tolist(), [37.5, 0, 37.5, 0])
        runs = loads.runs.set_index("policy")
        self.assertEqual(runs.at["FIXED_DB", "utilization_range_pp"], 37.5)
        self.assertEqual(runs.at["FIXED_DB", "utilization_sd_pp"], 18.75)
        matrix = assignment_summary(loads.assignments)
        self.assertEqual(len(matrix), 2 * len(PLATFORMS)**2)
        self.assertEqual(matrix["total_train_count"].sum(), 4)
        self.assertEqual((matrix["total_train_count"] == 0).sum(), 28)

    def test_weighted_reduction_and_negative_and_undefined_values(self):
        rows = pd.DataFrame({
            "fixed_total_delay_min": [10, 100], "greedy_total_delay_min": [20, 60],
            "delay_saved_min": [-10, 40],
        })
        stats = paired_statistics(rows)
        self.assertAlmostEqual(stats["reduction_pct"], 100 * 30 / 110)
        self.assertEqual(stats["fixed_wins"], 1)
        self.assertEqual(stats["greedy_wins"], 1)
        stats = paired_statistics(rows.iloc[[0]])
        self.assertEqual(stats["mean_saving_min"], -10)
        self.assertEqual(stats["reduction_pct"], -100)
        self.assertIsNone(stats["ci_low_min"])
        self.assertIsNone(stats["ci_high_min"])
        self.assertIsNone(stats["std_saving_min"])
        self.assertIsNone(delay_reduction(0, 3))

    def test_configurations_separate_repeated_seeds_excluded_within_configuration(self):
        for name, transfer in (("TIMETABLE_T4_S001", 4), ("TIMETABLE_T4_S002", 4), ("TIMETABLE_T6_S001", 6)):
            fixture(self.directory, name, transfer=("MATRIX", transfer, 1))
        fixture(self.directory, "TIMETABLE_T4_S003", seed=103, transfer=("MATRIX", 4, 1))
        groups, excluded = aggregate_groups(inventory(self.directory))
        a = ("TIMETABLE", ("MATRIX", 4, 1))
        b = ("TIMETABLE", ("MATRIX", 6, 1))
        self.assertEqual({a, b}, set(groups))
        self.assertEqual({("TIMETABLE_T4_S001", 101), ("TIMETABLE_T4_S002", 101)}, excluded)
        self.assertEqual([103], [pair.experiment.key[1] for pair in groups[a]])
        self.assertEqual([101], [pair.experiment.key[1] for pair in groups[b]])

    def test_cross_configuration_pairing_checks_original_inputs(self):
        reference = ("TIMETABLE", ("MATRIX", 4, 1))
        candidate = ("TIMETABLE", ("MATRIX", 6, 1))
        for seed, arrival in ((101, 0), (102, 0), (103, 0), (104, 1)):
            fixture(self.directory, f"TIMETABLE_T4_S{seed}", seed, transfer=("MATRIX", 4, 1), incoming=arrival)
        for seed, arrival in ((101, 0), (102, 1), (104, 1), (105, 0)):
            files = fixture(self.directory, f"TIMETABLE_T6_S{seed}", seed, transfer=("MATRIX", 6, 1), incoming=arrival)
            if seed == 104:
                edit_csv(files["input"], lambda rows: rows.reverse())
                edit_csv(files["input"], lambda rows: rows[0].update(allowed_platforms="5|4|3|2"))
        groups, _ = aggregate_groups(inventory(self.directory))
        a, b = groups[reference], groups[candidate]
        self.assertFalse(equivalent_inputs(a[1], b[1]))
        matched, excluded = match_configurations(a, b)
        self.assertEqual([p.experiment.key[1] for p, _ in matched], [101, 104])
        self.assertEqual(excluded, [(102, "Original train inputs differ"), (103, "Missing comparison seed"),
                                    (105, "Missing reference seed")])
        outcomes, issues = sensitivity(groups, reference)
        self.assertEqual(outcomes.at[0, "Matched seeds"], 2)
        self.assertEqual(outcomes.at[0, "Change in paired saving (min)"], -2)
        self.assertEqual(len(issues), 3)

    def test_filter_and_export_uses_exact_records_and_train_pair(self):
        fixture(self.directory, transfer=("MATRIX", 4, 1))
        item, = inventory(self.directory)
        frame = train_frame([item.pair])
        filtered = filter_trains(frame, {"policy": ["GREEDY"], "assignment_category": ["Cross island"]},
                                 {"incoming_delay": (0, 0)}, ["passenger_induced_delay_min"])
        self.assertEqual(filtered["train_id"].tolist(), ["T2"])
        self.assertEqual(list(csv.DictReader(csv_bytes(filtered).decode("utf-8-sig").splitlines()))[0]["train_id"], "T2")
        comparison = paired_train(frame, "T2").set_index("Metric")
        self.assertEqual(comparison.at["Assigned platform", "FIXED_DB − GREEDY"], "Gleis 4 → Gleis 2")
        self.assertEqual(comparison.at["Secondary delay (min)", "FIXED_DB − GREEDY"], 1)
        self.assertEqual(comparison.at["Direct passenger-induced delay (min)", "FIXED_DB − GREEDY"], -1)
        queue = queue_events(frame, item.pair.last_departure)
        self.assertEqual(queue.groupby("Dispatcher")["Waiting trains"].max().to_dict(), {"FIXED_DB": 2, "GREEDY": 0})


class CommittedExperimentRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = inventory(ROOT / "Ingo" / "results")
        cls.groups, cls.excluded = aggregate_groups(cls.inventory)
        cls.matrix = {key: pairs for key, pairs in cls.groups.items() if key[0] == "MATRIX Monte Carlo"}
        cls.horizon = max(pair.last_departure for pairs in cls.matrix.values() for pair in pairs)

    def test_batch_sizes_seed_matches_and_common_horizon(self):
        self.assertEqual(len(self.matrix), 3)
        self.assertEqual([len(group) for group in self.matrix.values()], [10, 10, 10])
        self.assertEqual(self.horizon, 132)
        pairs = [pair for group in self.matrix.values() for pair in group]
        self.assertEqual(len(pairs), 30)
        self.assertEqual(sum(len(pair.runs) for pair in pairs), 60)
        self.assertEqual(len(train_frame(pairs)), 7200)
        reference = ("MATRIX Monte Carlo", ("MATRIX", 4, 1))
        comparisons, excluded = sensitivity(self.groups, reference)
        self.assertTrue(excluded.empty)
        self.assertEqual(set(comparisons["Mode"]), {"UNIFORM", "MATRIX"})
        self.assertEqual(comparisons["Matched seeds"].tolist(), [10] * 5)
        self.assertEqual(Counter(item.status for item in self.inventory)["Invalid"], 1)

    def test_all_six_configurations_match_committed_analysis(self):
        dirs = {
            ("UNIFORM", 0): "P1_BATCH_T0", ("UNIFORM", 4): "P1_BATCH_T4", ("UNIFORM", 6): "P1_BATCH_T6",
            ("MATRIX", 2): "P2_MATRIX_T2", ("MATRIX", 4): "P2_MATRIX_T4", ("MATRIX", 6): "P2_MATRIX_T6",
        }
        for (_, (mode, time, _)), pairs in self.groups.items():
            with self.subTest(mode=mode, time=time):
                stats = paired_statistics(pd.DataFrame([pair.summary for pair in pairs]))
                reference = pd.read_csv(ROOT / "analysis/output" / dirs[mode, time] / "overall_summary.csv")
                value = reference.set_index("metric")["value"]
                for a, b in (
                    ("pairs", "number_of_scenarios"), ("reduction_pct", "total_delay_reduction_pct"),
                    ("mean_saving_min", "mean_paired_scenario_saving_min"),
                    ("ci_low_min", "paired_saving_ci95_lower_min"), ("ci_high_min", "paired_saving_ci95_upper_min"),
                    ("greedy_wins", "scenarios_greedy_better"), ("equal", "scenarios_equal"),
                    ("fixed_wins", "scenarios_greedy_worse"),
                ):
                    self.assertAlmostEqual(stats[a], value[b], places=6)
                self.assertAlmostEqual(stats["fixed_mean_min"], value["sum_fixed_delay_min"] / 10, places=6)
                self.assertAlmostEqual(stats["greedy_mean_min"], value["sum_greedy_delay_min"] / 10, places=6)
                self.assertEqual({pair.summary["trains"] for pair in pairs}, {120})

    def test_matrix_t4_platforms_match_phase_three_outputs(self):
        config = ("MATRIX Monte Carlo", ("MATRIX", 4, 1))
        analytics = calculate(self.matrix[config], self.horizon)
        location = ROOT / "analysis/output/P3_UTILIZATION"
        platform_reference = pd.read_csv(location / "platform_summary.csv").query("configuration == 'MATRIX_T4_S1'")
        actual = platform_summary(analytics.platforms).set_index(["policy", "platform"])
        for row in platform_reference.itertuples():
            self.assertAlmostEqual(actual.at[(row.policy, row.platform), "mean_utilization_pct"],
                                   row.mean_utilization_pct, places=6)
        policy_reference = pd.read_csv(location / "policy_summary.csv").query("configuration == 'MATRIX_T4_S1'")
        averages = analytics.runs.groupby("policy").mean(numeric_only=True)
        for row in policy_reference.itertuples():
            for metric in ("mean_utilization_pct", "utilization_range_pp", "utilization_sd_pp",
                           "same_island_reassignments", "cross_island_reassignments", "passenger_induced_delay_min"):
                self.assertAlmostEqual(averages.at[row.policy, metric], getattr(row, metric), places=6)


if __name__ == "__main__":
    unittest.main()
