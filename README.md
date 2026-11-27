# Ingolstadt Hbf — Railway Platform Assignment Simulation

**University simulation research project · AnyLogic 8.9.10 + Python · Phase 2.1.2 completed (data preparation)**

A discrete-event simulation (DES) of passenger train platform assignment at Ingolstadt Hauptbahnhof, Germany. The research compares exactly two online dispatching policies — **FIXED_DB** and **GREEDY** — on identical train schedules and incoming-delay scenarios, measuring station-induced secondary delay, passenger-transfer effects and platform utilization.

> **Current status:** The executable AnyLogic model still generates 120 synthetic trains. The validated real-timetable bundle contains 116 scheduled through-running trains for 24 November 2026 and is ready for controlled import in Phase 2.2. Real-timetable simulation and calibrated incoming delays are not implemented yet.

## 1. Scope and research question

Can dynamic platform assignment reduce secondary delay relative to fixed planned assignments while accounting for passenger walking and platform compatibility?

- Ingolstadt Hbf (EVA 8000183), Gleis 2–5, exclusive capacity one train per track.
- Real-timetable cohort: through-running ICE, RE and RB trains planned on those tracks during a complete local calendar day. Scheduled cancellations remain included.
- Originating and terminating services are preserved separately for future work; terminal occupation, rolling-stock turns, other tracks, freight, empty stock and shunting are outside the current cohort.
- No detailed signaling, interlocking, conflicting approach routes, headways or individual passenger agents. Compatibility is a research assumption supported by evidence, not official routing authorization.

## 2. Executable model and dispatch policies

[Ingo/Ingo.alp](Ingo/Ingo.alp) uses AnyLogic's Process Modeling Library and Java functions in Main. All time units are minutes.

```text
fromNorth / fromSouth (synthetic Sources)
                 |
             common Wait
                 |
          Main dispatcher
    canUse / choosePlatform / dispatchTrains
                 |
           selectOutput5
        /     /      \      \
    Gleis2 Gleis3 Gleis4 Gleis5
     Delay  Delay  Delay  Delay (capacity 1)
        \     \      /      /
                 |
                sink
       log, release reservation, redispatch
```

**FIXED_DB:** use the planned platform only; wait when occupied or reserved. This is a fixed-assignment simulation baseline, not actual DB dispatching behavior.

**GREEDY:** prefer the planned platform if free; otherwise choose the first free compatible platform in ascending numerical order. Among assignable waiting trains, select earliest ready time, then sequence. Reserve before release and reconsider waiting trains when a request becomes ready or a platform is released. The fifth selector output leads to an auxiliary sink, not a platform. GREEDY does not forecast future availability or optimize passenger costs.

| Synthetic model setting | Saved value |
| --- | --- |
| Train requests | 60 per Source, 120 total |
| Scheduled arrivals | Every 2 minutes per Source |
| Scheduled departure | Scheduled arrival + 5 min |
| Minimum dwell | 3 min |
| Incoming delay | 30% zero; otherwise exponential with mean parameter 4 min, capped at 30 min |
| Randomness | Deterministic per train ID and scenario seed |
| Experiment stop | 500 min |
| Default run parameters | GREEDY, seed 101, P2_TEST_M6, MATRIX, same-island 1 min, cross-island 6 min |

Legacy synthetic compatibility remains hard-coded in the Sources. [route_catalog.csv](route_catalog.csv) is a reference file, not a runtime input.

| Synthetic group | Planned | Allowed |
| --- | ---: | --- |
| RB16_S | 2 | 2, 3 |
| RE1_S | 3 | 2, 3, 5 |
| ICE_S | 3 | 3 |
| RB16_N | 5 | 4, 5 |
| RE1_N | 4 | 4, 5 |
| ICE_N | 4 | 4, 5 |

S/N denotes southbound/northbound. These are not the new empirical compatibility rules.

### Passenger transfer and delay metrics

UNIFORM applies `runTransferTime` to any reassignment. MATRIX uses the symmetric matrix below, with s = `runSameIslandTransferTime`, c = `runTransferTime`. Platform islands are modeled as 2/3 and 4/5. Walking times are assumptions, not measurements.

| Planned → assigned | 2 | 3 | 4 | 5 |
| --- | ---: | ---: | ---: | ---: |
| 2 | 0 | s | c | c |
| 3 | s | 0 | c | c |
| 4 | c | c | 0 | s |
| 5 | c | c | s | 0 |

```text
readyTime = scheduledArrival + incomingDelay
passengersReadyTime = assignmentTime + passengerTransferTime
actualDeparture = max(scheduledDeparture,
                      actualArrival + minDwell,
                      passengersReadyTime)
waiting = actualArrival - readyTime
stationDelay = max(0, actualDeparture
                     - max(scheduledDeparture, readyTime + minDwell))
passengerInducedDelay = max(0, actualDeparture
                             - max(scheduledDeparture, actualArrival + minDwell))
```

Secondary delay excludes unavoidable incoming lateness. Direct passenger-induced delay is a component of secondary delay, not an extra amount to add to it. Walking can be absorbed by available dwell time. Platform utilization is occupied minutes divided by the specified observation horizon.

## 3. Completed synthetic experiments

Each row summarizes 10 paired scenarios (seeds 101–110, 120 trains per policy per scenario). Savings are FIXED_DB minus GREEDY; intervals are paired 95% Student-t confidence intervals on mean per-scenario savings, not on independent individual trains.

| Transfer configuration | Total secondary delay reduction | Mean paired saving, min | 95% CI, min | GREEDY wins |
| --- | ---: | ---: | ---: | ---: |
| UNIFORM 0 min | 74.12% | 223.31 | [174.09, 272.53] | 10/10 |
| UNIFORM 4 min | 46.05% | 138.74 | [85.51, 191.97] | 10/10 |
| UNIFORM 6 min | -183.29% | -552.19 | [-618.18, -486.20] | 0/10 |
| MATRIX same 1 / cross 2 min | 74.12% | 223.31 | [174.09, 272.53] | 10/10 |
| MATRIX same 1 / cross 4 min | 71.58% | 215.63 | [167.06, 264.21] | 10/10 |
| MATRIX same 1 / cross 6 min | 65.36% | 196.89 | [142.91, 250.88] | 10/10 |

Sources: [uniform 0](analysis/output/P1_BATCH_T0/overall_summary.csv), [uniform 4](analysis/output/P1_BATCH_T4/overall_summary.csv), [uniform 6](analysis/output/P1_BATCH_T6/overall_summary.csv), [matrix 2](analysis/output/P2_MATRIX_T2/overall_summary.csv), [matrix 4](analysis/output/P2_MATRIX_T4/overall_summary.csv), [matrix 6](analysis/output/P2_MATRIX_T6/overall_summary.csv).

The same seed set is reused across configurations. Negative reduction means GREEDY produced more delay. Under MATRIX 1/4, platform utilization range decreases from 38.69 to 20.55 percentage points on a common 132-minute batch horizon. See [utilization results](analysis/output/P3_UTILIZATION/policy_summary.csv). These are synthetic sensitivity experiments, not measured DB operational improvements.

## 4. Real timetable and historical evidence (Phase 2.1.2)

DB OpenBoards is the primary source; GTFS.DE and date-specific DB station posters provide supplementary checks.

| Historical archive: 30 Oct–26 Nov 2026 | Result |
| --- | ---: |
| Validated days | 28/28 |
| Request receipts | 2,016 |
| Raw event snapshots / unique event identities | 17,121 / 11,061 |
| Valid scheduled through calls, all tracks | 3,816 |
| Strong reported through-platform observations | 3,686 |
| Eligible observations with changed platform | 403 (10.93%) |
| Changes from other tracks into Gleis 2–5 | 76 |

Events are deduplicated across overlapping day captures using journey ID, event kind, station and scheduled instant. The analysis normalizes RE/RB line IDs before nonstandard source categories, distinguishes incoming/outgoing corridors and preserves uncertain records. Strong observations require uncancelled ordered REAL arrival and departure times and consistent reported platforms. REAL refers to the time type; the platform has no independent verification indicator in the archived schema. A change does not establish its cause.

**Construction-period limitation:** all 28 days fall within the documented Nürnberg–Ingolstadt high-speed railway closure (30 October–12 December 2026). Evidence applies to this closure-period cohort, not normal SFS operations. Station-throat classification may leave upstream routing uncertain. Public infrastructure plans do not establish all authorized routes or operational usable platform lengths.

### Baseline schedule: 24 November 2026

The planned schedule defines the model input, not actual delays or cancellations. Ten cancelled scheduled trains remain included. Three linked ICE pairs are modeled as one occupation per pair based on reciprocal `travelsWith` links and matching movements; both source identities are retained. The RB16 59139/59095 replacement-number discrepancy also retains one planned slot with provenance.

| Baseline metric | Value |
| --- | ---: |
| Day window, Europe/Berlin | 00:00–24:00 (1,440 min) |
| Through trains | 116 |
| ICE / RE1 / RB16 / RB17 / RB15 | 39 / 20 / 34 / 22 / 1 |
| First arrival / last departure | 00:03 / 23:57 |
| Scheduled dwell min / median / mean / max | 1 / 2 / 3.328 / 16 min |
| Provisional minimum dwell | 1 min |
| Known initial through occupations / departures after day / overlapping planned intervals | 0 / 0 / 0 |
| Terminal calls preserved | 132 (37 on Gleis 2–5) |

| Gleis | Planned trains | Known through busy minutes | Share of day |
| --- | ---: | ---: | ---: |
| 2 | 14 | 155 | 10.76% |
| 3 | 34 | 59 | 4.10% |
| 4 | 38 | 93 | 6.46% |
| 5 | 30 | 79 | 5.49% |
| **Total / mean utilization** | **116** | **386** | **6.70%** |

These are scheduled through-service occupations only, not actual station-wide utilization. Terminal occupation is unknown. The synthetic common-horizon utilization cannot be directly compared with this full-day planned value.

### Empirical platform compatibility

Conservative eligibility requires direct scheduled or strong reported evidence on at least two operating days and for at least two distinct train numbers. A valid planned track is retained as a per-train exception. Expanded eligibility adds documented assumptions only. Lack of evidence is not a physical prohibition.

| Baseline route group | Trains | Conservative | Expanded |
| --- | ---: | --- | --- |
| ICE_S | 19 | 2, 3, 4 | 2, 3, 4 |
| ICE_N | 19 | 4, 5 | 4, 5 |
| RE1_S | 10 | 2, 3, 4 | 2, 3, 4, 5 |
| RE1_N | 10 | 4, 5 | 4, 5 |
| RB16_S | 18 | 2, 3 | 2, 3 |
| RB16_N | 16 | 4, 5 | 4, 5 |
| RB15_DONAU_NORD | 1 | 2, 3, 4, 5 | 2, 3, 4, 5 |
| RB17_REG_NORD | 4 | 4, 5 | 4, 5 |
| RB17_NORD_REG | 18 | 4, 5 | 4, 5 |
| ICE 1081 (AMBIGUOUS) | 1 | 3 only | 3 only |

115/116 trains have an alternative under either configuration; the expanded matrix gives 10 an additional choice. The complete historical matrix has 23 route groups and 92 route-track combinations, including groups outside the baseline. Use per-train allowed lists rather than reconstructing eligibility from route names. These are two configurations of GREEDY, not additional dispatchers.

**Project input and evidence:**

- [Simulation timetable — use this for Phase 2.2](data/timetable/historical_analysis/timetable/timetable.csv) · [Metadata and CSV hashes](data/timetable/historical_analysis/timetable/dataset_metadata.json)
- [Conservative matrix](data/timetable/historical_analysis/compatibility/platform_compatibility_conservative.csv) · [Expanded matrix](data/timetable/historical_analysis/compatibility/platform_compatibility_expanded.csv) · [Route-track evidence](data/timetable/historical_analysis/compatibility/platform_compatibility_evidence.csv)
- [Historical report](data/timetable/historical_analysis/reports/historical_platform_report.md) · [Infrastructure research](data/timetable/research/platform_compatibility_research.md) · [Data guide](data/timetable/README.md)
- [Terminal services](data/timetable/historical_analysis/timetable/terminal_services.csv) · [Linked ICE review](data/timetable/historical_analysis/timetable/duplicate_service_review.csv) · [GTFS reconciliation](data/timetable/historical_analysis/timetable/gtfs_baseline_review.csv)

Do **not** use the older provisional GTFS-only `data/timetable/processed/timetable.csv` as the real simulation input.

### Historical arrival delays — not yet calibrated

5,116 signed REAL arrival deviations include terminating services; 3,661 are through arrivals across the eligible archive. The through-only subset has mean 7.86 min, median 3.45 min, 95th percentile 31.48 min, maximum 248.63 min and 494 early arrivals. See [delay summary](data/timetable/historical_analysis/delays/delay_summary.csv) and [signed sample](data/timetable/historical_analysis/delays/historical_arrival_delays.csv).

Reported deviations may already reflect station congestion and upstream processes, not independent approach delays. Future calibration must filter to the target cohort, address early arrivals, extreme delays and correlations, and document construction-period bias. The synthetic 30-minute cap has not changed.

## 5. Quick start

From the repository root, using Python 3.11+ and AnyLogic 8.9.10 with PML. Windows PowerShell:

```powershell
git clone --branch feature/real-timetable https://github.com/gerageragera39/IngoHbfSimulation.git
cd IngoHbfSimulation
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r analysis/requirements_dashboard.txt -r data/timetable/requirements.txt
```

Python analysis and dashboard do not require AnyLogic or live API access when inputs are available.

### Run the current synthetic simulation

1. Open `Ingo/Ingo.alp` in AnyLogic.
2. Select `Simulation`. Set `runPolicy`, `runSeed`, `runScenarioId`, `runTransferMode`, `runTransferTime` and `runSameIslandTransferTime` in Main/experiment parameters. The internal `policy` variable initializes from `runPolicy`.
3. Run both policies with identical scenario ID, seed and input settings. Use a new scenario ID for changed inputs to avoid overwriting reference outputs.
4. Inspect the console and CSVs. Keep model and platform Delay units in minutes.

`BatchMonteCarlo` runs 60 simulations: both policies, 10 paired seeds per configuration (101–110), MATRIX cross-island times 2/4/6 minutes with same-island time 1 minute. Run the experiment in AnyLogic. [run_monte_carlo.py](run_monte_carlo.py) is an optional Windows launcher; adjust its hard-coded installation path locally. It requests launch but does not verify completion. Saved batch IDs can overwrite matching reference CSVs; use a copy or distinct scenario IDs for exploratory runs.

### Validate and analyze simulation CSVs

Exports under [Ingo/results/](Ingo/results/):

- `train_results_<POLICY>_<SCENARIO>_seed<SEED>.csv`: per-train outcomes, assigned track, actual entry/departure, waiting, station delay and passenger fields where available.
- `delay_scenarios_<SCENARIO>_seed<SEED>.csv`: shared input vector, route, schedule, allowed tracks and incoming delays.

Pair results by scenario, seed and train ID. The validator checks identical inputs, compatibility, FIXED_DB assignments, timing, exclusive occupation, expected counts and passenger transfer calculations.

```powershell
python analysis/analyze_results.py --input Ingo/results --output analysis/output/local_matrix_t4 --scenario-glob "P2_MATRIX_T4_S*" --expected-trains 120
python analysis/analyze_platforms.py --input Ingo/results --output analysis/output/local_utilization --scenario-glob "P2_MATRIX_T*" --expected-trains 120
```

The general analyzer defaults to legacy `*_RNG2` scenarios. Select the intended batch explicitly. Platform analytics use a common horizon across selected runs and distinguish same- and cross-island reassignments.

### Launch the dashboard

```powershell
python -m streamlit run analysis/station_dashboard.py
```

The dashboard analyzes completed AnyLogic exports, not live station traffic or real-timetable input files. Five pages: Overview, Platform Utilization, Passenger Transfer, Statistical Analysis and Train Data Explorer. It includes paired statistics, occupancy Gantt views, configuration filtering and CSV export. See the [Russian dashboard guide](analysis/DASHBOARD_README_RU.md).

### Reproduce historical analysis offline

The branch includes the dated OpenBoards archive, processed GTFS extraction and configuration. No API credentials are required. Use a separate output directory to avoid changing reference results:

```powershell
python scripts/analyze_openboards_history.py --output data/timetable/local_replay
python -m unittest discover -s tests -v
```

Optional `--no-charts` skips charts; `--test-log PATH` attaches a saved test result. Exit code 2 indicates acquisition/baseline review is required. The committed [test log](data/timetable/historical_analysis/validation/test_results.txt) records 48 passing tests; run them locally to validate the current checkout.

For acquisition or cached replay only:

```powershell
python scripts/download_ingo_openboards.py --date 2026-11-24 --pause 1
python scripts/download_ingo_openboards.py --date 2026-11-24 --offline
```

The downloader accepts `DB_CLIENT_ID` and `DB_API_KEY` environment variables or securely prompts for credentials. Default spacing is one second (hard minimum 0.2 s, retries included, per process), hourly windows and six hours of boundary padding. Do not run multiple instances without coordinating subscription limits. Historical availability is not guaranteed indefinitely. Use the pinned archive for this study. GTFS ZIPs and source PDFs for the timetable pipeline are local inputs excluded from Git; see the [data guide](data/timetable/README.md) for snapshot details and supplementary GTFS replay.

## 6. Repository map

| Path | Purpose |
| --- | --- |
| [Ingo/](Ingo/) | Executable synthetic model, original backup, result CSVs |
| [analysis/](analysis/) | Paired analysis, platform utilization, Streamlit dashboard, reference outputs |
| [scripts/](scripts/) | OpenBoards and GTFS acquisition, historical validation, route classification, compatibility and baseline preparation |
| [data/timetable/config/](data/timetable/config/) | Route landmarks, evidence thresholds, expanded assumptions, dwell and GTFS crosswalk |
| [data/timetable/openboards/](data/timetable/openboards/) | Pinned 28-day archive, JSON, daily exports and manifests |
| [data/timetable/historical_analysis/](data/timetable/historical_analysis/) | Validated schedule, evidence, historical delays, charts, audit and report |
| [data/timetable/processed/](data/timetable/processed/) | Supplementary GTFS extraction and provisional review |
| [data/timetable/research/](data/timetable/research/) | Infrastructure study |
| [tests/](tests/) | Unit tests, committed-results regression tests and dashboard AppTest |
| [presentation/](presentation/) | Course presentation material and build sources (may reflect earlier phases) |

Historical entry point: `scripts/analyze_openboards_history.py`. Supporting modules: `openboards_history.py` (archive reconciliation), `openboards_services.py` (service classification and linked journeys), `openboards_analysis.py` (statistics and compatibility), `openboards_baseline.py` (baseline), `openboards_report.py` (reports).

## 7. Roadmap and integration contract

| Phase | Status |
| --- | --- |
| Synthetic DES, two dispatchers, paired seeds and CSV logging | Implemented |
| 1.1–1.2 Passenger penalty and transfer matrix | Implemented |
| 1.3 Platform utilization | Implemented |
| 1.4 Streamlit analytics | Implemented for completed simulation exports |
| 2.1 Real schedule and supplementary GTFS | Data preparation complete for controlled through-only cohort |
| 2.1.2 Historical compatibility analysis | Complete; reference data and test log committed |
| 2.2 AnyLogic timetable import | Next; not implemented |
| 2.3 Incoming-delay calibration | Historical sample prepared; calibration pending |
| Final paired Monte Carlo, sensitivity and hourly utilization | Pending for real timetable |
| AnyLogic 3D visualization | Planned separately |

For Phase 2.2, preserve the synthetic mode. Load train ID, route group, scheduled arrival/departure elapsed minutes, planned platform, pipe-delimited `allowed_platforms` and `min_dwell_min` from the historical-analysis timetable. Use `allowed_platforms_expanded` only for sensitivity; preserve fixed-only exceptions and scheduled cancellations. Preserve source identifiers and deterministic event sequencing.

Freeze the main-day cohort and delay vector for both policies. Schedule each request at ready time, including late arrivals after midnight, and finish servicing the cohort even after minute 1440. Handle initial occupation explicitly (none in this baseline). Replace completion counts tied to `2 * trainsPerDirection`, avoid the 500-minute stop in real mode, and adapt validation/export/dashboard metadata for the actual cohort and observation horizon.

Acceptance: test both policies with zero incoming delay; all 116 should complete without reassignment, secondary delay or overlapping occupation. Define deterministic handling of simultaneous release/arrival events. Then test matched seeded scenarios and synthetic regression. Real-timetable import and delay calibration are separate changes; preserve passenger-transfer logic and exactly two dispatchers.

## 8. Limitations, reproducibility and data rights

This is an academic platform-level prototype, not an official DB tool, safety system or operational routing authorization. Evidence describes a construction period. Unobserved alternatives are unknown, not necessarily impossible. Observed use by one train does not establish compatibility of every train in that group. Structural platform dimensions are not operational usable lengths. Terminal occupation and other omitted traffic can materially affect results. One-minute dwell and walking times are provisional assumptions.

Keep original data, scenario inputs, seeds, policy versions and evidence thresholds traceable. Never mix real-timetable results with synthetic reference batches or treat paired train observations as independent replications. Reproduce historical analysis from the pinned archive rather than changing live endpoints.

GTFS.DE / DELFI e.V. attribution and CC BY 4.0 details are in the [data guide](data/timetable/README.md). DB OpenBoards responses and station posters are separate sources subject to their own terms; verify permission for redistribution of raw and derived DB data before public release or sharing beyond authorized use. Do not commit credentials, local secrets or unnecessary build artifacts. No project license file is included; agree on project licensing before external publication.
