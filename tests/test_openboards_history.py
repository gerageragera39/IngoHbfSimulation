"""Offline tests for historical OpenBoards validation and simulation input."""

from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from openboards_analysis import analyze, delay_tables, platform_observation
from openboards_baseline import prepare_baseline
from openboards_history import (BOARD_TYPES, EVA, FILES, conflict_rows, dt, file_json,
                                parse_event, read_history, reconcile, track)
from openboards_services import Routes, classify, make_calls, review_linked_calls
from timetable_gtfs import window


DAY = date(2026, 11, 24)
CONFIG = file_json(Path(__file__).resolve().parents[1] / "data/timetable/config/openboards_history.json")
DWELL = {"default_through_minutes": 1, "categories": {}}
NAMES = {"20": "Ingolstadt Nord", "21": "Roth", "22": "München Hbf", "23": "Kinding (Altmühltal)",
         "24": "Weichering", "25": "Ernsgaden", "26": "Berlin Hbf", "27": "Treuchtlingen", EVA: "Ingolstadt Hbf"}


def raw(journey, kind, planned, reported=None, *, category="ag", line="RB16", number="21",
        origin="20", destination="22", track_plan="2 A-C", track_actual="3", via=(),
        time_type="REAL", journey_type="REGULAR", links=(), cancelled=False, journey_cancelled=False,
        additional=False):
    return {
        "journeyId": journey, "evaNumber": EVA, "arrivalId" if kind == "arrivals" else "departureId": "board_1",
        "timeSchedule": planned, "time": reported or planned, "timeType": time_type,
        "platformSchedule": {"name": track_plan}, "platform": {"name": track_actual}, "cancelled": cancelled,
        "additional": additional, "travelsWith": [{"journeyID": link} for link in links],
        "transport": {"category": category, "line": {"name": line}, "journeyNumber": number,
                      "type": "HIGH_SPEED_TRAIN" if category == "ICE" else "REGIONAL_TRAIN",
                      "via": [{"evaNumber": stop} for stop in via]},
        "journeyInfo": {"origin": {"evaNumber": origin}, "destination": {"evaNumber": destination},
                        "type": journey_type, "journeyCancelled": journey_cancelled},
    }


def pair(journey="a", day=DAY, arr="11:02", dep="11:04", **kwargs):
    return [parse_event(raw(journey, kind, f"{day}T{clock}:00+01:00", **kwargs), kind, f"{day}/raw/{kind}#1")
            for kind, clock in zip(BOARD_TYPES, (arr, dep))]


def classified(events):
    grouped = defaultdict(list)
    for event in events:
        grouped[event.key].append(event)
    return make_calls(reconcile(grouped), Routes(CONFIG, NAMES))


def day_fixture(root, day, entries):
    folder = root / str(day)
    (folder / "raw").mkdir(parents=True)
    start, end = (t.isoformat() for t in window(day))
    manifest = dict(date=str(day), eva=EVA, timezone="Europe/Berlin", status="retrieved_for_review",
                    day_start=start, day_end=end, capture_start=start, capture_end=end, finished_utc=end,
                    summary={key: 0 for key in FILES.values()}, requests=[])
    for kind in BOARD_TYPES:
        payload = {kind: entries if kind == "arrivals" else [], "meta": {"consideredStopPlaces": [EVA]}}
        content = json.dumps(payload).encode()
        name = kind + ".json"
        (folder / "raw" / name).write_bytes(content)
        manifest["requests"].append(dict(file=name, endpoint=kind, entries=len(payload[kind]),
                                         sha256=sha256(content).hexdigest(), start=start, end=end,
                                         subdivided=False, truncated_types=[]))
    for filename in FILES:
        (folder / filename).write_text("event_kind,eva,journey_id\n", encoding="utf-8")
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (folder / "summary.json").write_text(json.dumps(manifest["summary"]), encoding="utf-8")
    return folder


class HistoryTests(unittest.TestCase):
    def test_multiday_discovery_missing_days_and_deduplication(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = raw("a", "arrivals", f"{DAY}T00:01:00+01:00")
            day_fixture(root, DAY, [entry, dict(entry, journeyId="b")])
            day_fixture(root, DAY + timedelta(days=1), [entry])
            h = read_history(root, DAY, DAY + timedelta(days=2))
            self.assertEqual([r["status"] for r in h.coverage], ["validated", "validated", "missing"])
            self.assertEqual(h.raw_entries, 3)
            self.assertEqual(len(reconcile(h.snapshots)), 2)
            self.assertEqual(sorted(map(len, h.snapshots.values())), [1, 2])

    def test_corrupt_receipt_and_missing_derived_file(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = day_fixture(root, DAY, [])
            (folder / "raw/arrivals.json").write_text("{}", encoding="utf-8")
            (folder / "summary.json").unlink()
            h = read_history(root, DAY, DAY)
            self.assertEqual(h.coverage[0]["status"], "failed")
            self.assertIn("request_validation_failed", {e["issue"] for e in h.issues})
            self.assertIn("capture_window_gap", {e["issue"] for e in h.issues})

    def test_saturated_request_without_children_does_not_cover_window(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = day_fixture(root, DAY, [raw(str(i), "arrivals", f"{DAY}T10:00:00+01:00")
                                            for i in range(50)])
            path = folder / "manifest.json"
            m = file_json(path)
            m["requests"][0]["subdivided"] = True
            path.write_text(json.dumps(m), encoding="utf-8")
            h = read_history(root, DAY, DAY)
            self.assertIn("unresolved_truncation", {e["issue"] for e in h.issues})

    def test_conflicting_snapshots_keep_planned_and_reject_conflicting_real(self):
        a = pair()[0]
        b = replace(a, reported=a.reported + timedelta(minutes=1), reported_raw="4", source="other")
        snapshots = {a.key: [b, a]}
        result = reconcile(snapshots)[0]
        self.assertEqual(result.event.planned_platform, 2)
        self.assertIsNone(result.event.reported)
        self.assertEqual(result.event.source, a.source)
        self.assertEqual({r["raw_source"] for r in conflict_rows([result])}, {a.source, b.source})
        c = replace(a, planned_raw="5", source="other")
        self.assertIsNone(reconcile({a.key: [a, c]})[0].event.planned_platform)

    def test_preview_cannot_override_real_and_cancellation_vetoes_actual(self):
        a = pair()[0]
        preview = replace(a, time_type="PREVIEW", reported_raw="4")
        result = reconcile({a.key: [preview, a]})[0].event
        self.assertTrue(result.real)
        self.assertEqual(result.reported_platform, 3)
        cancelled = replace(a, cancelled=True)
        self.assertFalse(reconcile({a.key: [a, cancelled]})[0].event.real)

    def test_track_sectors_and_invalid_names(self):
        self.assertEqual(track("Gleis 2 D-G"), 2)
        for name in ("bus", "2A", "8", ""):
            self.assertIsNone(track(name))


class ServiceTests(unittest.TestCase):
    def test_classification_uses_line_ahead_of_unconventional_category(self):
        for category, line, expected in (("ag", "RE18", ("RE", "RE18")), ("BRB", "RB13", ("RB", "RB13")),
                                         ("RB", "RE1", ("RE", "RE1")), ("RE", "RB16", ("RB", "RB16"))):
            event = pair(category=category, line=line)[0]
            self.assertEqual(classify(event)[:2], expected)
        self.assertFalse(classify(pair(category="ag", line="")[0])[0])
        self.assertFalse(classify(pair(category="Bus", line="RB16")[0])[0])

    def test_closure_route_reconciliation_does_not_use_platform_number(self):
        events = pair(line="RE1", origin="26", via=("21",))
        a, d = events
        d = replace(d, via_ids=(), actual_via_ids=())
        south = classified([a, d])[0]
        self.assertEqual((south.route_group, south.actual_group), ("RE1_S", "RE1_S"))
        self.assertIn("TREUCHTLINGEN_5501", south.route_basis)
        sfs = classified([replace(a, via_ids=("23",), actual_via_ids=("23",)), d])[0]
        self.assertIn("N_SFS_5934", sfs.route_group)
        self.assertFalse(sfs.actual_group)
        self.assertIsNone(platform_observation(sfs))
        changed = classified([replace(a, via_ids=("23", "21"), actual_via_ids=("21",)), d])[0]
        self.assertIn("N_SFS_5934", changed.route_group)
        self.assertEqual(changed.actual_group, "RE1_S")

    def test_same_throat_remote_direction_stays_ambiguous(self):
        a, d = pair(category="ICE", line="", origin="26")
        d = replace(d, via_ids=("27",), actual_via_ids=("27",))
        call = classified([a, d])[0]
        self.assertEqual(call.incoming, call.outgoing)
        self.assertFalse(call.route_group)

    def test_same_journey_regional_line_transition(self):
        a, d = pair(origin="25", destination="24", line="RE18")
        call = classified([a, replace(d, line="RB15")])[0]
        self.assertEqual(call.category, "RE")
        self.assertEqual(call.route_group, "RE18_RB15_REG_DONAU")
        self.assertEqual(call.service, "RE18|RB15")

    def test_strong_weak_conflicting_and_cancelled_platforms(self):
        a, d = pair()
        self.assertEqual(platform_observation(classified([a, d])[0]), ("strong", 3))
        self.assertEqual(platform_observation(classified([a, replace(d, time_type="PREVIEW")])[0]), ("weaker", 3))
        self.assertEqual(platform_observation(classified([a])[0]), ("weaker", 3))
        self.assertIsNone(platform_observation(classified([replace(a, time_type="SCHEDULE"),
                                                           replace(d, time_type="PREVIEW")])[0]))
        self.assertIsNone(platform_observation(classified([a, replace(d, reported_raw="2")])[0]))
        self.assertIsNone(platform_observation(classified([a, replace(d, reported=a.reported -
                                                                      timedelta(minutes=1))])[0]))
        for field in ("cancelled", "journey_cancelled", "additional"):
            self.assertIsNone(platform_observation(classified([a, replace(d, **{field: True})])[0]))

    def test_movement_linking_requires_reciprocal_arrival_and_departure_evidence(self):
        regular = pair("regular", category="ICE", number="1507", line="", links=("extra",))
        extra = pair("extra", category="ICE", number="2799", line="", links=("regular",), journey_type="EXTRA")
        calls = classified(regular + extra)
        review, aliases = review_linked_calls(calls, [], DAY)
        self.assertEqual(len(aliases), 1)
        self.assertEqual(review[0]["decision"], "one_platform_occupation_keep_regular")
        for unsafe in ([extra[0], replace(extra[1], links=())],
                       [extra[0], replace(extra[1], reported_raw="4")]):
            review, aliases = review_linked_calls(classified(regular + unsafe), [], DAY)
            self.assertFalse(aliases)
            self.assertEqual(review[0]["decision"], "unconfirmed_keep_source_records")


class AnalysisTests(unittest.TestCase):
    def run_analysis(self, calls, dates=(DAY,)):
        return analyze(calls, dates, Routes(CONFIG, NAMES), set())

    def test_planned_counts_and_reassignment_use_all_platforms(self):
        calls = classified(pair(track_plan="7", track_actual="4") + pair("cancelled", number="22", cancelled=True)
                           + pair("same", number="23", track_plan="5", track_actual="5"))
        result = self.run_analysis(calls)
        scheduled = {(r["route_group"], r["platform"]): r for r in result["scheduled_matrix"]}
        self.assertEqual(scheduled["RB16_S", 2]["cancelled_scheduled_count"], 1)
        self.assertEqual(scheduled["RB16_S", 7]["relative_frequency"], 1 / 3)
        self.assertEqual(scheduled["RB16_S", 1]["scheduled_count"], 0)
        self.assertEqual(result["reassignment_summary"][0]["eligible_count"], 2)
        self.assertEqual(result["reassignment_summary"][0]["reassignment_pct"], 50)
        self.assertEqual(result["reassignment_records"][0]["original_planned_platform"], 7)
        self.assertEqual(result["reassignment_records"][0]["final_reported_platform"], 4)

    def test_evidence_days_and_configurations(self):
        next_day = DAY + timedelta(days=1)
        events = pair("one", line="RE1", track_plan="3", track_actual="2")
        events += pair("two", line="RE1", day=next_day, number="25", track_plan="3", track_actual="2")
        events += pair("three", line="RE1", day=next_day, number="25", track_plan="3", track_actual="2")
        result = self.run_analysis(classified(events), (DAY, next_day))
        evidence = {(r["route_group"], r["platform"]): r for r in result["evidence"]}
        self.assertEqual(evidence["RE1_S", 2]["distinct_observation_days"], 2)
        self.assertEqual(evidence["RE1_S", 2]["distinct_train_numbers"], 2)
        self.assertEqual(result["conservative"]["RE1_S"], {2, 3})
        self.assertEqual(result["expanded"]["RE1_S"], {2, 3, 5})
        self.assertEqual(evidence["RE1_S", 4]["evidence_status"], "UNKNOWN")
        self.assertEqual(evidence["RE1_S", 5]["evidence_status"], "ASSUMED")

    def test_terminal_exclusion_and_planned_platform_exception(self):
        calls = classified(pair(track_plan="2", cancelled=True) + pair("or", origin=EVA)[1:]
                           + pair("te", destination=EVA)[:1])
        routes = Routes(CONFIG, NAMES)
        result = prepare_baseline(calls, DAY, routes, self.run_analysis(calls), set(), [], DWELL)
        self.assertEqual({r["stop_kind"] for r in result["terminal_services"]}, {"originating", "terminating"})
        row, = result["timetable"]
        self.assertEqual(row["allowed_platforms"], "2")
        self.assertEqual(row["allowed_platforms_expanded"], "2")
        self.assertTrue(row["scheduled_cancelled"])
        self.assertTrue(row["planned_platform_exception"])

    def test_midnight_and_dwell_keep_original_times(self):
        before = DAY - timedelta(days=1)
        a = pair("into", before, arr="23:59")[0]
        d = pair("into", DAY, dep="00:00")[1]
        e = pair("out", DAY, arr="23:59")[0]
        f = pair("out", DAY + timedelta(days=1), dep="00:02")[1]
        g, h = pair("zero", DAY, arr="00:00", dep="00:00")
        calls = classified([a, d, e, f, g, h])
        routes = Routes(CONFIG, NAMES)
        result = prepare_baseline(calls, DAY, routes, self.run_analysis(calls), set(), [], DWELL)
        incoming, = result["initial_occupancy"]
        self.assertEqual((incoming["scheduled_arrival_min"], incoming["scheduled_departure_min"]), (-1, 0))
        self.assertEqual(incoming["boundary_status"], "departure_at_midnight")
        self.assertEqual(result["timetable"][1]["scheduled_departure_min"], 1442)
        self.assertEqual(result["timetable"][0]["scheduled_dwell_min"], 0)
        self.assertEqual(result["metadata"]["minimum_dwell_exceeds_schedule"], 1)

    def test_signed_arrival_delays_and_filters(self):
        a, d = pair("early")
        b, e = pair("late", number="22")
        c, f = pair("ontime", number="23")
        calls = classified([replace(a, reported=a.planned - timedelta(seconds=90)), d,
                            replace(b, reported=b.planned + timedelta(minutes=4)), e, c, f]
                           + pair("cancel", journey_cancelled=True)
                           + pair("extra", additional=True) + pair("preview", time_type="PREVIEW"))
        result = self.run_analysis(calls)
        self.assertEqual(sorted(r["arrival_delay_min"] for r in result["delays"]), [-1.5, 0, 4])
        tables = delay_tables(result["delays"], [DAY])
        all_stats = tables["delay_summary"][0]
        self.assertEqual((all_stats["early"], all_stats["on_time"], all_stats["positive"]), (1, 1, 1))
        self.assertEqual(all_stats["max_min"], 4)
        self.assertEqual(tables["delay_by_hour"][11]["count"], 3)


if __name__ == "__main__":
    unittest.main()
