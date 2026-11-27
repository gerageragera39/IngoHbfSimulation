
"""Exercise the Streamlit entry point and its widgets using the shipped datasets."""

import json
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from test_dashboard_analytics import ROOT, edit_csv, fixture

APP = ROOT / "analysis" / "station_dashboard.py"


class DashboardAppTests(unittest.TestCase):
    def assert_rendered(self, app, page, charts=0):
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertEqual(app.header[0].value, page)
        self.assertGreaterEqual(len(app.get("plotly_chart")), charts)

    def test_navigation_defaults_individual_filters_and_csv_controls(self):
        app = AppTest.from_file(str(APP), default_timeout=45).run()
        self.assert_rendered(app, "Overview", 5)
        self.assertEqual(app.title[0].value, "Ingolstadt Hbf — Dispatching Analytics")
        self.assertEqual(app.sidebar.selectbox(key="family").value, "MATRIX Monte Carlo")
        self.assertEqual(app.sidebar.selectbox(key="cross").value, 4.0)
        self.assertEqual(app.sidebar.selectbox(key="same").value, 1.0)
        self.assertIn("71.58%", [m.value for m in app.metric])
        next(r for r in app.radio if r.label == "Scenario comparison unit").set_value("Percent reduction").run()
        self.assert_rendered(app, "Overview", 5)
        self.assertIn("Secondary delay reduction (%)", app.get("plotly_chart")[-1].proto.spec)

        nav = app.sidebar.radio[0]
        nav.set_value("Platform Utilization").run()
        self.assert_rendered(app, "Platform Utilization", 8)
        gantt = next(json.loads(e.proto.spec) for e in app.get("plotly_chart")
                     if "Actual departure %{" in e.proto.spec)
        self.assertTrue(gantt["data"][0]["base"])
        self.assertNotIn("frames", gantt)
        self.assertIn("Download platform statistics", [b.proto.label for b in app.get("download_button")])
        app.sidebar.selectbox(key="individual_scenario").set_value("P2_MATRIX_T4_S002").run()
        self.assert_rendered(app, "Platform Utilization", 8)
        self.assertIn("10 paired scenarios", " ".join(c.value for c in app.caption))
        self.assertIn("P2_MATRIX_T4_S002 · seed 102", " ".join(c.value for c in app.caption))

        app.sidebar.radio[0].set_value("Passenger Transfer").run()
        self.assert_rendered(app, "Passenger Transfer", 7)
        walking = next(json.loads(e.proto.spec) for e in app.get("plotly_chart")
                       if "min walking time" in e.proto.spec)
        self.assertEqual(walking["data"][0]["text"][0], ["0.00", "1.00", "4.00", "4.00"])

        app.sidebar.radio[0].set_value("Statistical Analysis").run()
        self.assert_rendered(app, "Statistical Analysis", 7)
        self.assertIn("[167.06, 264.21] min", [m.value for m in app.metric])
        app.sidebar.selectbox(key="family").set_value("UNIFORM Monte Carlo").run()
        self.assert_rendered(app, "Statistical Analysis", 7)
        app.sidebar.selectbox(key="cross").set_value(6.0).run()
        self.assert_rendered(app, "Statistical Analysis", 7)
        self.assertIn("-552.19 min", [m.value for m in app.metric])

        app.sidebar.radio[0].set_value("Train Data Explorer").run()
        self.assert_rendered(app, "Train Data Explorer")
        app.sidebar.selectbox(key="individual_config").set_value(("Historical scenarios", None)).run()
        self.assert_rendered(app, "Train Data Explorer")
        self.assertFalse(any(c.label == "Only trains with positive direct passenger delay" for c in app.checkbox))
        app.sidebar.multiselect[1].set_value(["FIXED_DB"]).run()
        next(c for c in app.checkbox if c.label == "Only reassigned trains").check().run()
        self.assert_rendered(app, "Train Data Explorer")
        self.assertTrue(any("No trains match" in item.value for item in app.info))
        self.assertIn("Download paired train comparison", [b.proto.label for b in app.get("download_button")])

    def test_empty_directory_partial_input_and_fingerprint_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            app = AppTest.from_file(str(APP), default_timeout=45)
            app.session_state["results_directory"] = str(directory)
            app.run()
            self.assert_rendered(app, "Overview")
            self.assertTrue(any("No fully validated Monte Carlo" in item.value for item in app.info))
            self.assertFalse(app.get("plotly_chart"))

            paths = fixture(directory, transfer=("MATRIX", 4, 1))
            app.run()
            self.assert_rendered(app, "Overview", 5)
            self.assertIn("1", [m.value for m in app.metric if "Validated" in m.label])

            edit_csv(paths["input"], lambda rows: rows[0].update(incoming_delay="120"))
            app.run()
            self.assertTrue(any("No fully validated Monte Carlo" in item.value for item in app.info))
            paths["input"].unlink()
            app.sidebar.radio[0].set_value("Train Data Explorer").run()
            self.assert_rendered(app, "Train Data Explorer")
            self.assertTrue(any("Original input CSV is missing" in warning.value for warning in app.warning))


if __name__ == "__main__":
    unittest.main()
