# Phase 2.1 · Ingolstadt Hbf passenger timetable

## Phase 2.1.2 · OpenBoards history and simulation timetable

The [historical platform report](historical_analysis/reports/historical_platform_report.md) documents the 28-day Ingolstadt Hbf OpenBoards analysis and the 24 November 2026 baseline. Use the [scheduled timetable](historical_analysis/timetable/timetable.csv) for the through-only AnyLogic import. The rest of this guide describes the earlier supplementary GTFS analysis.

Run from the repository root with Python 3.11 or later, matplotlib and tzdata. The analysis reads the 28 local `openboards/YYYY-MM-DD` archives, the earlier GTFS extraction in `processed/normalized_timetable.csv`, and the versioned route and dwell settings. The workflow uses local files and requires no API credentials.

```powershell
python -m unittest discover -s tests -v
python scripts/analyze_openboards_history.py
```

To attach a saved unittest result to the report, pass `--test-log PATH`. Use `--output PATH` to write a separate replay bundle. Use `--no-charts` for a tabular run. The defaults pin the study days, the baseline and the station's inputs. The command exits with status 2 when acquisition coverage or baseline reconciliation requires review. Coverage reports remain available when baseline acquisition cannot be validated.

| Directory | Contents |
| --- | --- |
| [Validation](historical_analysis/validation/) | Acquisition receipts and coverage checks, event conflict snapshots, station-call inventory, historic terminal records and route review |
| [Compatibility](historical_analysis/compatibility/) | All-track and modeled-track matrices, daily usage, reassignment records, evidence, and the two GREEDY configurations |
| [Timetable](historical_analysis/timetable/) | Full-day planned cohort, terminal and excluded services, unresolved cases, linked journeys, GTFS reconciliation, boundary occupation and metadata |
| [Delays](historical_analysis/delays/) | Signed REAL arrival deviations and statistics by route, category, scheduled hour and day |
| [Charts](historical_analysis/charts/) | Platform and reassignment heatmaps, delay distribution and empirical cumulative distribution |

Edit the [historical route configuration](config/openboards_history.json) to review corridor landmarks, line transitions, evidence thresholds and expanded assumptions. The [minimum dwell configuration](config/minimum_dwell.json) supplies the provisional one-minute default. The baseline uses `allowed_platforms` for conservative eligibility and `allowed_platforms_expanded` for sensitivity analysis. Values are pipe-delimited Gleis numbers. The two columns configure the same GREEDY dispatcher. FIXED_DB uses `planned_platform`. Preserve the local ISO 8601 timestamps and use the elapsed-minute fields for simulation events. Rows marked as fixed-only exceptions use their own planned track under both configurations.

The archive reflects the Nürnberg–Ingolstadt high-speed railway closure from 30 October through 12 December 2026. The simulation input covers the observed closure-period through-service cohort. Station-wide experiments need the missing terminal occupation intervals, and normal SFS operation needs separate routing evidence. The historical delay sample retains early arrivals and should be treated as potentially correlated by day and service.

## Supplementary GTFS analysis

This dataset covers Tuesday, **24 November 2026**, from 00:00 inclusive to 24:00 exclusive in Europe/Berlin. It contains **272 passenger train stops**, including 39 from the long-distance feed and 233 from the regional feed. Scheduled platforms were recovered for **194 stops (71.32%)**. Of these, 126 use Gleis 2–5 and 68 use Gleis 1, 6 or 7. The remaining 78 include 66 calls with no platform evidence and 12 with ambiguous or conflicting evidence.

The modeled timetable contains **107 provisional through calls**. Another 19 calls are known to use Gleis 2–5 and have unresolved terminal occupation. There are 143 unresolved records overall, including 134 originating or terminating calls with unknown occupation. These categories overlap. Five example departures in the DB amendment poster also need reconciliation with the GTFS calls. Use the [validation report](processed/validation_report.md) and the [source and dataset metadata](processed/dataset_metadata.json) for the full inventory.

## Sources and licensing

| Raw file | Public source | Archived coverage |
| --- | --- | --- |
| `fernverkehr.zip` | [GTFS.DE long-distance feed](https://www.gtfs.de/de/feeds/de_fv/) · [ZIP](https://download.gtfs.de/germany/fv_free/latest.zip) | 21 Nov–21 Dec 2026 inclusive |
| `regionalverkehr.zip` | [GTFS.DE regional feed](https://www.gtfs.de/de/feeds/de_rv/) · [ZIP](https://download.gtfs.de/germany/rv_free/latest.zip) | 21 Nov–21 Dec 2026 inclusive |
| `regelfahrplan.pdf` | [DB regular departure poster](https://db.info/downloads/schedule/Regeltafel_2993.pdf) | Valid from 14 Dec 2025. Data as of 24 Jun 2026. |
| `aenderungsfahrplan.pdf` | [DB amendment poster](https://db.info/downloads/schedule/Aenderungstafel_2993.pdf) | Valid from 23 Nov 2026. Individual rows have their own operating days. |

GTFS.DE publishes both GTFS feeds using DELFI e.V. NeTEx data under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). This project filters those feeds, converts service times to local timestamps and elapsed minutes, adds audited DB station poster observations, and attaches modeling fields. Credit GTFS.DE and DELFI e.V., retain the license link, and describe these adaptations if sharing the GTFS-derived data. The DB posters are supplementary evidence with separate terms. The source PDFs stay local. The repository crosswalk records individual service identifiers, platform observations and page references. See the [DB station timetable page](https://db.info/ingolstadt-hbf/fahrplan).

All four inputs were fetched on 27 November 2026. The downloaded ZIPs and regular poster matched the three existing local files byte for byte. The [archive receipts](metadata/archive_snapshots.json) pin URLs, timestamps, HTTP modification times and SHA-256 hashes. Feed validity came from the archived calendars because these ZIPs did not provide `feed_start_date` and `feed_end_date`. The GTFS `latest.zip` URLs and DB poster URLs can change. Keep the original files if you need to reproduce this specific snapshot later.

## Reproduce the dataset

Run from the repository root with Python 3.11 or later. The Python dependencies provide charts and an IANA timezone database on Windows. Preparation and validation run offline once the files and Python dependencies are available.

```powershell
python -m pip install -r data/timetable/requirements.txt
python scripts/download_gtfs.py --with-pdfs
python scripts/prepare_timetable.py
python scripts/validate_timetable.py --replay
python -m unittest discover -s tests -p test_timetable.py -v
```

Preparation and validation report exit code **2** for a structurally valid provisional dataset. Exit code **1** indicates an acquisition, processing or validation error. Exit code **0** indicates a bundle that meets the pipeline's readiness checks.

The downloader reuses an existing valid file, including the existing capitalized Windows filenames. For a fresh snapshot, choose another directory with `--raw-dir data/timetable/raw/new-snapshot`. If a download fails, open the four links in the source table and save them under the listed filenames in `data/timetable/raw/`. Compare checksums with the archive receipts before relying on the date-specific DB crosswalk. A new snapshot can require a new date and platform review. The DB posters are optional for GTFS-only extraction.

```powershell
python scripts/prepare_timetable.py --date 2026-11-24 --fv data/timetable/raw/fernverkehr.zip --rv data/timetable/raw/regionalverkehr.zip --station "Ingolstadt Hbf" --modeled-platforms 2,3,4,5 --route-config data/timetable/config/routes.json --dwell-config data/timetable/config/minimum_dwell.json --output-dir data/timetable/processed
python scripts/validate_timetable.py --output-dir data/timetable/processed --replay
```

The GTFS-only form is `python scripts/prepare_timetable.py --no-platform-evidence --output-dir data/timetable/raw/gtfs-only`. Other switches include `--regel`, `--aenderung`, `--platform-evidence` and feed-specific `--fv-station-id` and `--rv-station-id` to disambiguate a station name. Supply the same input options when validating with `--replay`.

## Calendar and station extraction

The default is the first usable Tuesday–Thursday in the shared archive coverage with sufficient adjacent service dates and passenger calls from both feeds. The fallback is the first usable Monday or Friday. The rule skips Bavarian public holidays and conservatively skips 15 August. The selected day is an ordinary non-holiday Tuesday with date-specific timetable amendments, including route truncations. The rule is independent of platform assignments and dispatcher results. See [Bavarian public holidays](https://www.gesetze-bayern.de/Content/Document/BayFTG-1).

Both snapshots identify station `nuf` and child boarding stop `4cbe` at approximately 48.74454° N, 11.43734° E. The parser resolves the exact station name and expands its boarding hierarchy. The rail route type and explicit replacement-service descriptions filter buses and other modes. Ingolstadt Nord and Ingolstadt Audi have their own station IDs. The extraction follows all passenger rail routes in both archives, including RB13, RB14, RB15 and RB17. The archives contain night-service templates for other operating dates. The selected day's after-midnight ICE and regional trains are included.

Two streaming scans of `stop_times.txt` find the station's trips and retain their full stop order. The pipeline joins `agency.txt`, `stops.txt`, `routes.txt`, `trips.txt`, `calendar.txt`, `calendar_dates.txt` and optional `feed_info.txt` and `attributions.txt`. Added and removed services take precedence over the weekly calendar. The preceding and following stops describe the passenger itinerary, which may skip intermediate stations. Identical source stop-time rows are counted and collapsed. Cross-feed duplicates require the same published train number, full itinerary and stop times, with consistent platform evidence. Ambiguous candidates remain visible for review. No duplicate candidates were found in this day.

The selected calendar date is `service_date`. The original GTFS date is `gtfs_service_date`. Each train-stop ID combines the feed, escaped trip ID, original service date and stop sequence. The GTFS clock starts at local noon minus 12 elapsed hours on the original service day, so 24:15 can become 00:15 on the next calendar day. The parser examines preceding service dates according to the largest station time in the feed and also examines the following service date. Output timestamps retain the local UTC offset. Relative minutes count elapsed time from local midnight. An explicitly requested daylight-saving transition day is a complete local calendar day with 23 or 25 elapsed hours. See the [GTFS Schedule reference](https://gtfs.org/documentation/schedule/reference/).

## Recovering scheduled platforms

The feed supplies a single boarding stop, blank `platform_code` fields and no published train number for the selected calls. GTFS route labels such as `ICE 29` identify a line. The extraction accepts explicit GTFS platform codes and names that identify a platform. It retains opaque stop IDs as source identifiers.

The [date-specific crosswalk](config/station_poster_review_2026-11-24.csv) matches the local departure clock, train category or line, destination and, for the regular poster, the next passenger stop. For amendments, the effective destination or changed itinerary must agree, and the operating date must apply. An explicit date-applicable track override takes precedence over the base track. Letters identifying track sectors are omitted from the numeric platform. The crosswalk stores the original GTFS call ID, operator-facing poster label, operating date, document page, result and basis. A published train number is retained only when the matched entry supplies an unambiguous number.

The crosswalk is a reviewed input. To prepare another date, audit both official departure posters, resolve operating-day and track notes, and supply a matching evidence JSON and CSV using the same schema. The importer checks the station, reviewed date, four archived checksums and source call fields. Conflicts are flagged for review. Terminating calls lack evidence in the departure posters. The [poster discrepancy review](processed/validation_report.md#db-poster-and-gtfs-discrepancies) documents examples of departures with no exact GTFS match. Resolve those against dated source evidence before adding or changing any calls.

## Occupancy, boundaries and dwell

The 138 through calls have a median scheduled dwell of **2 minutes**, a mean of **4.058 minutes**, and a range of **1–20 minutes**. Ninety-three are below the synthetic model's three-minute minimum. The [minimum dwell configuration](config/minimum_dwell.json) uses **one minute** as a provisional through-service sensitivity baseline. Per-category overrides are available. The model keeps published dwell separate from the configured operational minimum and flags zero dwell, missing times and a minimum exceeding the schedule.

Through and terminating calls are counted by their arrival time, and originating calls by departure time. Through occupancy uses half-open intervals `[arrival, departure)`. A train arriving before midnight and still present at simulation time zero is written to `initial_occupancy.csv`. Departures exactly at midnight are retained as boundary events with the appropriate cohort status. A through train arriving during the day and leaving after midnight retains a departure above 1440. This snapshot includes eight stops from the preceding GTFS service date, zero known through occupations already active at time zero and zero through departures carrying beyond the end of the window.

The GTFS arrival and departure placeholders are equal for 134 originating or terminating calls in this run. Those endpoints give passenger times but leave the corresponding operational occupation intervals unknown. No applicable stock-turn or through connection was established from the archives. Evaluate pre-midnight terminal occupations and stock moves before treating the station as empty at startup. Freight trains, empty stock, shunting and other operational traffic may also be absent from passenger GTFS.

The [occupancy chart](processed/scheduled_occupancy.png) uses positive scheduled through dwell on known tracks, clipped to the observation window. It found zero overlapping pairs in that subset. Known busy minutes use a union of intervals to avoid double counting. Unresolved calls and unrecorded operations limit the measure. The [timetable overview](processed/timetable_overview.png) shows traffic by hour, platform, category and dwell. The peak hour was 17:00–17:59 with 18 main-day calls.

## Route and platform compatibility

The [route configuration](config/routes.json) defines groups using line or category and neighboring passenger stops. `RB16_S`, `RE1_S`, `ICE_S`, `RB16_N`, `RE1_N` and `ICE_N` carry the legacy AnyLogic compatibility proposals from `route_catalog.csv`. Those alternatives are disabled pending review of applicability to the real train paths. The additional groups describe observed passenger direction. Terminal services and unmatched itineraries can have an unclassified route.

All 126 known modeled-platform calls have a fixed-only allowed list containing their planned platform. The list is a conservative input for the feasibility review and offers GREEDY no alternative for those calls. A reviewed rule can enable alternatives with a documented basis. Any known planned platform outside the proposed list remains fixed-only and flagged for review. A missing platform is tracked as unknown scope.

## Outputs and validation

All CSVs are UTF-8 with comma delimiters, a header, and blank values for unavailable data. Allowed platform values are pipe-delimited. Normalized and model-related exports use the same field names.

| Output | Contents |
| --- | --- |
| `normalized_timetable.csv` | Every passenger call retained from the two feeds, including boundary and unresolved calls |
| `timetable.csv` | Chronological main-day modeled calls with known planned platform and usable through timing, including provisional rows |
| `unresolved_records.csv` | Calls with blocking reasons such as unknown platforms, terminal occupation or possible duplicates |
| `excluded_trains.csv` | Calls on other platforms and any non-passenger records at the station, with reasons |
| `initial_occupancy.csv` | Pre-midnight through intervals with modeled or unresolved platform scope |
| `route_mapping_review.csv` | Modeled calls with fixed-only compatibility pending review |
| `duplicate_review.csv` | Confirmed aliases and ambiguous cross-feed candidates |
| `scheduled_occupancy_conflicts.csv` | Train IDs, platform and overlapping minutes for each conflicting pair |
| `dataset_metadata.json` | Date, sources, checksums, validity, audit counts, quality metrics, output hashes and readiness |
| `validation_report.md` | Human-readable quality tables, validation messages and source discrepancies |

The fields `train_id`, `source_trip_id`, `source_service_id`, `source_stop_id` and `stop_sequence` establish traceability. `train_number`, `train_category`, `line`, `origin`, `destination`, `previous_station`, `next_station` and `route_group` describe the call. `scheduled_arrival_min`, `scheduled_departure_min`, `scheduled_dwell_min` and `min_dwell_min` describe schedule and model timing. `arrival_timestamp` and `departure_timestamp` preserve the original times converted to local ISO 8601. `planned_platform`, `allowed_platforms`, `platform_source`, `platform_evidence` and `compatibility_status` carry platform provenance. `cohort`, `boundary_status`, `occupancy_status`, `model_scope`, `readiness_status`, `blocking_reasons` and `review_flags` support review and integration.

The validator checks required fields, identifiers, time conversions, date and window consistency, arrival/departure ordering, dwell, compatibility, output checksums, cohort exports, station counts and occupancy conflicts. Source replay rebuilds the normalized rows directly from the archived files, exercising station extraction and calendar exception handling. Output checksum changes can also reflect different plotting-library versions. Automated fixtures stay in the test process. A full real-archive replay passes structurally and reports provisional integration readiness.

## Phase 2.2 handoff

Resolve missing or conflicting platforms, the poster discrepancies and terminal occupation intervals that can affect Gleis 2–5. Review minimum dwell and alternate-platform eligibility with an explicit evidence basis. The current data supports a timetable review and does not yet support a representative FIXED_DB versus GREEDY experiment.

The current model defaults to 60 synthetic requests per direction. `TrainRequest` stores `trainId`, `routeGroup`, `sequence`, `plannedPlatform`, `assignedPlatform`, `allowedPlatforms`, `scheduledArrival`, `scheduledDeparture`, `incomingDelay`, `readyTime`, `minDwell`, `actualArrival`, `actualDeparture`, `stationDelay`, `assignmentTime`, `passengerTransferTime`, `passengersReadyTime` and `passengerInducedDelay`. The synthetic sources use minutes, five-minute scheduled dwell and three-minute minimum dwell. The results and dashboard read separate scenario-input and per-policy result CSVs, paired by scenario, seed and train ID. Their occupancy charts measure simulated actual arrival and departure intervals.

For integration, translate timetable fields to the existing `TrainRequest` fields and assign a deterministic `sequence` for ties. Preload the known initial occupations or warm up using verified prior traffic. Keep negative scheduled arrival offsets for measurement, and initialize those trains as already in occupation instead of injecting them into the waiting queue at minute zero. Handle departures exactly at observation start explicitly. Determine whether additional terminal moves or follow-on traffic are needed for the experiment. Freeze the main-day cohort and seeded delays for both policies, stop scheduling main-day requests at the day boundary, and run until every main-day request is processed. Account for the initial cohort in completion and occupancy metrics. Preserve the existing passenger transfer model, the paired export schemas and the synthetic experiment mode.
