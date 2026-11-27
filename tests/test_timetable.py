"""Offline tests for the static timetable pipeline using temporary synthetic archives."""

import argparse
import csv
from datetime import date, timedelta
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from download_gtfs import acquire
from prepare_timetable import build, exit_code, input_arguments, prepare
from timetable_gtfs import Calendar, gtfs_anchor, read_feed, select_date, window
from timetable_model import apply_evidence, classify_route, csv_rows, load_evidence
from timetable_quality import read_bundle, scheduled_occupancy
from validate_timetable import replay


DAY = date(2026, 5, 6)
WEEK = "monday tuesday wednesday thursday friday saturday sunday"


def csv_text(columns, rows):
    stream = StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(columns.split())
    writer.writerows(rows)
    return stream.getvalue()


def fixture(path, key):
    stops = [
        ("hbf", "Ingolstadt Hbf", "1", "", ""),
        ("p2", "Ingolstadt Hbf", "0", "hbf", "2"),
        ("plain7", "Ingolstadt Hbf", "0", "hbf", ""),
        ("p3", "Ingolstadt Hbf (Gleis 3)", "0", "hbf", ""),
        ("boarding", "Boarding Area", "4", "p2", ""),
        ("bus", "Ingolstadt Hbf Bus", "0", "hbf", ""),
        ("north", "Ingolstadt Nord", "0", "", ""),
        ("audi", "Ingolstadt Audi", "0", "", ""),
        ("south", "Baar-Ebenhausen", "0", "", ""),
    ]
    trips = []
    times = []

    def trip(code, route, service, arr, dep, platform="p2", kind="through", number=""):
        trips.append((code, route, service, number))
        if kind != "originating":
            times.append((code, "north", 10, "00:00:00", "00:00:00", "", ""))
        times.append((code, platform, 31, arr, dep, "1" if kind == "terminating" else "",
                      "1" if kind == "originating" else ""))
        if kind != "terminating":
            times.append((code, "south", 40, "28:59:00", "28:59:00", "", ""))

    trip("shared", "regional", "current", "08:00:00", "08:03:00", number="101")
    if key == "fv":
        trip("into/day", "ice", "previous", "23:59:00", "24:02:00", "p3")
        trip("after24", "ice", "previous", "24:11:00", "24:13:00", "boarding")
        trip("past_end", "ice", "current", "23:59:00", "24:03:00", "p3")
        trip("end_edge", "ice", "current", "24:00:00", "24:03:00")
        trip("start_edge", "ice", "previous", "23:58:00", "24:00:00", "p3")
        trip("outside", "ice", "previous", "20:00:00", "20:01:00")
        trip("removed", "ice", "removed", "10:00:00", "10:03:00")
        trip("baseline", "ice", "baseline", "15:00:00", "15:01:00", "p3")
        trip("missing_time", "ice", "current", "", "13:00:00", "p3")
        trip("same_time_distinct", "ice", "current", "08:00:00", "08:04:00", number="203")
        trip("uncertain_copy", "ice", "current", "18:00:00", "18:04:00")
    else:
        trip("unknown", "regional", "current", "09:00:00", "09:02:00", "plain7")
        trip("origin", "regional", "current", "11:00:00", "11:00:00", kind="originating")
        trip("terminal", "regional", "current", "12:00:00", "12:00:00", kind="terminating")
        trip("bus_trip", "bus", "current", "12:30:00", "12:31:00", "bus")
        trip("replacement", "replacement", "current", "12:40:00", "12:41:00")
        trip("other_station", "regional", "current", "01:00:00", "01:01:00", "audi")
        trip("uncertain_copy_rv", "ice", "current", "18:00:00", "18:04:00")
        times.append(next(item for item in times if item[:2] == ("shared", "p2")))
    tables = {
        "agency": ("agency_id agency_name agency_timezone", [("a", "Example Rail", "Europe/Berlin")]),
        "stops": ("stop_id stop_name location_type parent_station platform_code", stops),
        "routes": ("route_id agency_id route_type route_short_name route_long_name", [
            ("regional", "a", 2, "RB16", ""), ("ice", "a", 101, "ICE 41", ""),
            ("bus", "a", 3, "42", ""), ("replacement", "a", 2, "RB16", "Ersatzverkehr"),
        ]),
        "trips": ("trip_id route_id service_id trip_short_name", trips),
        "stop_times": ("trip_id stop_id stop_sequence arrival_time departure_time pickup_type drop_off_type", times),
        "calendar": (f"service_id start_date end_date {WEEK}", [
            ("baseline", "20260504", "20260510", 1, 1, 1, 1, 1, 0, 0),
            ("removed", "20260504", "20260510", 1, 1, 1, 1, 1, 0, 0),
        ]),
        "calendar_dates": ("service_id date exception_type", [
            ("previous", "20260505", 1), ("current", "20260506", 1), ("removed", "20260506", 2),
        ]),
        "feed_info": ("feed_version feed_start_date feed_end_date", [("fixture", "20260504", "20260510")]),
    }
    with ZipFile(path, "w") as archive:
        for name, (columns, values) in tables.items():
            archive.writestr(name + ".txt", csv_text(columns, values))


class TimetableTest(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.fv = self.directory / "fernverkehr.zip"
        self.rv = self.directory / "Regionalverkehr.zip"
        fixture(self.fv, "fv")
        fixture(self.rv, "rv")
        self.output = self.directory / "processed"
        parser = argparse.ArgumentParser()
        input_arguments(parser)
        self.args = parser.parse_args([
            "--date", str(DAY), "--raw-dir", str(self.directory), "--output-dir", str(self.output),
            "--no-platform-evidence",
        ])

    def test_calendar_filter_and_day_selection(self):
        fv = read_feed("fv", self.fv, "Ingolstadt Hbf")
        rv = read_feed("rv", self.rv, "Ingolstadt Hbf")
        self.assertEqual(select_date([fv, rv], None)[0], DAY)
        self.assertEqual(fv.calendar.rule("current", DAY), "calendar_dates:add")
        self.assertEqual(fv.calendar.rule("removed", DAY), "")
        self.assertEqual(fv.calendar.rule("baseline", DAY), "calendar:wednesday")
        calendar = Calendar([], [{"service_id": "all", "date": "20260506", "exception_type": "1"}], {})
        self.assertEqual(calendar.rule("all", DAY), "calendar_dates:add")
        with self.assertRaisesRegex(ValueError, "adjacent service dates"):
            select_date([fv, rv], date(2026, 5, 4))

    def test_station_extraction_platforms_and_full_day_boundaries(self):
        feed = read_feed("fv", self.fv, "Ingolstadt Hbf")
        self.assertEqual(feed.metadata["station_root_ids"], ["hbf"])
        self.assertEqual(set(feed.metadata["station_stop_ids"]), {"hbf", "p2", "p3", "plain7", "boarding", "bus"})
        calls = {row["source_trip_id"]: row for row in feed.extract(DAY)}
        self.assertTrue({"removed", "outside", "end_edge"}.isdisjoint(calls))
        initial = calls["into/day"]
        self.assertEqual(initial["train_id"], "fv:into%2Fday:2026-05-05:31")
        self.assertEqual((initial["scheduled_arrival_min"], initial["scheduled_departure_min"]), (-1, 2))
        self.assertEqual((initial["cohort"], initial["boundary_status"], initial["planned_platform"]),
                         ("initial", "initial", "3"))
        self.assertEqual((calls["after24"]["scheduled_arrival_min"], calls["after24"]["planned_platform"]), (11, "2"))
        self.assertEqual(calls["past_end"]["scheduled_departure_min"], 1443)
        self.assertEqual(calls["past_end"]["boundary_status"], "after_window")
        self.assertEqual(calls["start_edge"]["boundary_status"], "departure_at_start")
        self.assertEqual(calls["shared"]["previous_station"], "Ingolstadt Nord")
        self.assertEqual(calls["shared"]["next_station"], "Baar-Ebenhausen")

    def test_europe_berlin_dst_uses_elapsed_time(self):
        spring = date(2026, 3, 29)
        fall = date(2026, 10, 25)
        self.assertEqual(window(spring)[1] - window(spring)[0], timedelta(hours=23))
        self.assertEqual(window(fall)[1] - window(fall)[0], timedelta(hours=25))
        self.assertEqual(gtfs_anchor(spring) - window(spring)[0], timedelta(hours=-1))
        self.assertEqual(gtfs_anchor(fall) - window(fall)[0], timedelta(hours=1))

    def test_merge_duplicate_assessment_and_model_rules(self):
        _, _, rows, excluded, _, feeds, _, _, found = build(self.args)
        calls = {row["source_trip_id"]: row for row in rows}
        self.assertEqual(feeds["rv"]["exact_duplicate_stop_times"], 1)
        self.assertEqual(calls["shared"]["source_aliases"], "rv:shared:2026-05-06:31")
        self.assertIn("same_time_distinct", calls)
        self.assertEqual(len(found), 2)
        for trip_id in ("uncertain_copy", "uncertain_copy_rv"):
            self.assertIn("possible_duplicate", calls[trip_id]["blocking_reasons"])
        self.assertEqual(calls["shared"]["route_group"], "RB16_S")
        self.assertEqual(calls["shared"]["allowed_platforms"], "2")
        self.assertEqual(calls["shared"]["compatibility_status"], "fixed_only_unverified_model_rule")
        self.assertEqual(calls["unknown"]["planned_platform"], "")
        self.assertEqual(calls["unknown"]["model_scope"], "unknown")
        self.assertIn("missing_arrival_or_departure", calls["missing_time"]["blocking_reasons"])
        for trip_id, kind in (("origin", "originating"), ("terminal", "terminating")):
            row = calls[trip_id]
            self.assertEqual(row["stop_kind"], kind)
            self.assertEqual(row["occupancy_status"], "unknown")
            self.assertIsNone(row["min_dwell_min"])
        self.assertEqual({row["source_trip_id"] for row in excluded}, {"bus_trip", "replacement"})
        self.assertNotIn("other_station", calls)

    def test_compatibility_preserves_planned_platform(self):
        row = {"line": "RB17", "planned_platform": "5"}
        rules = [{"match": {"line": ["RB17"]}, "group": "RB17", "allowed_platforms": ["2", "3"],
                  "enable_alternatives": True, "basis": "verified_infrastructure"}]
        self.assertEqual(classify_route(row, rules, {"2", "3", "5"}),
                         ("RB17", ["5"], "fixed_only_planned_outside_rule"))
        self.assertEqual(classify_route({**row, "planned_platform": "2"}, rules, {"2", "3", "5"}),
                         ("RB17", ["2", "3"], "verified_infrastructure"))

    def test_invalid_dwell_config_and_minimum_exceeds_schedule(self):
        config = self.directory / "dwell.json"
        self.args.dwell_config = config
        config.write_text(json.dumps({"default_through_minutes": -1, "reviewed": False, "categories": {}}))
        with self.assertRaisesRegex(ValueError, "Minimum dwell parameters"):
            build(self.args)
        config.write_text(json.dumps({"default_through_minutes": 3, "reviewed": False, "categories": {}}))
        _, _, rows, *_ = build(self.args)
        row = next(row for row in rows if row["source_trip_id"] == "baseline")
        self.assertEqual(row["min_dwell_min"], 3)
        self.assertEqual(row["scheduled_dwell_min"], 1)
        self.assertIn("minimum_dwell_exceeds_schedule", row["blocking_reasons"])

    def test_occupancy_detects_all_overlaps_and_uses_interval_union(self):
        def interval(key, start, end):
            return {"train_id": key, "planned_platform": "2", "occupancy_status": "scheduled_passenger_dwell",
                    "scheduled_arrival_min": start, "scheduled_departure_min": end}
        _, busy, conflicts = scheduled_occupancy([
            interval("a", -1, 10), interval("b", 3, 7), interval("c", 4, 12), interval("d", 12, 16),
        ], 15)
        self.assertEqual(busy, {"2": 15})
        self.assertEqual({(row["first_train_id"], row["second_train_id"]) for row in conflicts},
                         {("a", "b"), ("a", "c"), ("b", "c")})

    def test_outputs_validation_and_reproducibility(self):
        meta = prepare(self.args)
        self.assertEqual(exit_code(meta), 2)
        self.assertEqual(meta["counts"]["initial_occupancy"], 1)
        self.assertEqual(meta["counts"]["nonpassenger_exclusions"], 2)
        self.assertFalse(meta["integration_ready"])
        self.assertEqual(read_bundle(self.output)[1], [])
        self.assertEqual(replay(self.args, meta), [])
        self.assertEqual(prepare(self.args), meta)
        timetable = self.output / "timetable.csv"
        records = list(csv_rows(timetable))
        self.assertNotIn("into/day", {row["source_trip_id"] for row in records})
        self.assertIn("past_end", {row["source_trip_id"] for row in records})
        timetable.write_text("train_id\nwrong\n", encoding="utf-8")
        self.assertIn("Missing or changed output timetable.csv", read_bundle(self.output)[1])

    def test_evidence_date_hash_and_matching_checks(self):
        config = self.directory / "poster.json"
        _, _, rows, *_ = build(self.args)
        row = next(row for row in rows if row["source_trip_id"] == "unknown")
        values = {
            "train_id": row["train_id"], "operating_date": str(DAY), "gtfs_departure_local": "09:02",
            "gtfs_line": "RB16", "gtfs_next_station": row["next_station"], "gtfs_destination": row["destination"],
            "status": "matched", "document": "regel", "page": "1", "platform": "5", "train_number": "72",
            "basis": "Synthetic evidence",
        }
        evidence = self.directory / "poster.csv"
        evidence.write_text(csv_text(" ".join(values), [list(values.values())]), encoding="utf-8")
        config.write_text(json.dumps({"date": str(DAY), "station": "Ingolstadt Hbf", "review": "fixture",
                                      "matches_file": evidence.name, "source_sha256": {"regel": "hash"}}))
        sources = {"regel": {"sha256": "hash", "url": "https://example.invalid/poster.pdf"}}
        self.assertFalse(load_evidence(config, "Ingolstadt Hbf", DAY + timedelta(days=1), {}, sources)[0])
        self.assertFalse(load_evidence(config, "Ingolstadt Hbf", DAY, {}, {})[0])
        matches, meta = load_evidence(config, "Ingolstadt Hbf", DAY, {}, sources)
        self.assertEqual(meta["status"], "applied")
        apply_evidence(row, matches[row["train_id"]], sources)
        self.assertEqual((row["planned_platform"], row["train_number"]), ("5", "72"))
        self.assertIn("#page=1", row["platform_evidence"])
        with self.assertRaisesRegex(ValueError, "Stale station poster evidence"):
            apply_evidence(row, [{**values, "gtfs_departure_local": "09:01"}], sources)
        apply_evidence(row, [{**values, "platform": "2"}], sources)
        self.assertEqual((row["platform_status"], row["planned_platform"]), ("conflict", ""))

    def test_existing_archive_is_reused_without_network(self):
        existing = self.rv.read_bytes()
        with patch("download_gtfs.urlopen", side_effect=AssertionError("Unexpected download")):
            acquire("rv", self.directory)
        self.assertEqual(self.rv.read_bytes(), existing)


if __name__ == "__main__":
    unittest.main()
