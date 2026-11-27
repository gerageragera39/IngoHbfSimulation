# Phase 2.1.2 historical platform analysis

## Coverage and data quality

The archive covers **28 of 28** calendar days from 2026-10-30 through 2026-11-26 in Europe/Berlin. The audit read **17,121** event rows in usable raw board responses and reconciled them to **11,061** unique event identities, including the capture padding. **10,904** unique events have scheduled times inside the study dates. The manifest contains **2,016** receipts and **0** subdivided request windows. A validated day has readable required files, verifiable successful receipts and continuous arrival and departure coverage over its declared capture.

The event key uses DB journey ID, event kind, station EVA and scheduled instant. The board event IDs can repeat across services. Overlap produced 6,060 repeated event rows and 0 materially conflicting event keys. Message references and raw response hashes can differ without changing the fields used here. The scheduled day's source is preferred for traceability. Planned platform must agree across all supplied track values, a REAL time or track conflict removes the conflicting value from operational evidence, and any cancellation flag vetoes actual evidence. The conflict CSV preserves all material variants and raw pointers. Acquisition or event validation issues by type were none. Missing platform fields are tallied per day in the [coverage table](../validation/dataset_coverage.csv).

## Service classification and setting

**3,816** unique planned ICE, RE or RB through calls have ordered scheduled times and a known planned track across all platforms, including 146 cancelled planned calls. 2 of the valid calls have an unresolved route and are counted outside the route matrices. Exact RE and RB line IDs take precedence over nonstandard labels such as `ag`, `BRB` and RB carrying an RE1 line ID. A same-journey line transition retains both lines and uses the arrival-side category for category summaries. The [route and service review](../validation/route_service_review.csv) and station-call inventory preserve the original labels and itinerary evidence.

The [infrastructure research](../../research/platform_compatibility_research.md) identifies the München and Ingolstadt Nord faces of VzG 5501, the 5934 connection at Ingolstadt Nord, and the separate Regensburg 5851, Donauwörth/Ulm 5382 and Augsburg 5381 approaches. Configured local itinerary landmarks establish the station approach. A remote northern itinerary supplies a directional inference when local evidence is missing. Explicit Treuchtlingen markers are preserved in route provenance. The `NORD_5501` group describes the station throat and allows for unresolved upstream paths. A same-throat inference needs evidence on both legs. Explicit SFS itineraries are retained in the planned classification. The closure keeps those itinerary labels out of confirmed actual SFS evidence.

Nürnberg–Ingolstadt SFS closure, 2026-10-30 through 2026-12-12. Evidence applies to the recorded closure-period station movements. Published itinerary and reported platform carry no official routing authorization. The supplied research records structural lengths of 409 m on Gleise 2–3 and 419 m on Gleise 4–5. Operational usable length, rolling-stock restrictions and authorized interlocking routes require separate evidence.

## Scheduled and reported platform counts

Each cell contains scheduled assignments followed by strong through-platform observations. Planned counts retain cancellations with usable schedules. The archive yields **3,686 strong observations** with ordered, uncancelled REAL arrival and departure times and matching reported tracks. 5 single-event observations are recorded separately. Raw platform object fields observed were **ifopt, name**. REAL describes event times. The platform values are reports accompanying those times, with no independent platform-verification indicator established in the archived schema.

| Route group | Gleis 1 planned / strong | Gleis 2 planned / strong | Gleis 3 planned / strong | Gleis 4 planned / strong | Gleis 5 planned / strong | Gleis 6 planned / strong | Gleis 7 planned / strong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ICE_MUC_5501_TO_MUC_5501 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| ICE_N | 0 / 0 | 0 / 0 | 0 / 0 | 526 / 504 | 1 / 11 | 0 / 0 | 0 / 0 |
| ICE_NORD_5501_TO_AUG_5381 | 0 / 0 | 0 / 0 | 1 / 1 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| ICE_S | 0 / 0 | 0 / 4 | 544 / 518 | 0 / 4 | 0 / 1 | 0 / 0 | 0 / 0 |
| RB15_DONAU_NORD | 20 / 14 | 0 / 3 | 0 / 2 | 19 / 17 | 1 / 2 | 0 / 1 | 20 / 15 |
| RB15_NORD_DONAU | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| RB15_RB17_DONAU_REG | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 5 / 5 | 63 / 59 | 8 / 8 |
| RB15_RE18_DONAU_REG | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 24 / 24 | 40 / 38 |
| RB16_AUG_5381_TO_MUC_5501 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| RB16_AUG_5381_TO_NORD_5501 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| RB16_MUC_5501_TO_MUC_5501 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| RB16_N | 0 / 0 | 0 / 1 | 0 / 0 | 199 / 295 | 229 / 164 | 83 / 62 | 79 / 60 |
| RB16_S | 47 / 36 | 396 / 255 | 96 / 239 | 0 / 1 | 8 / 8 | 0 / 0 | 0 / 0 |
| RB17_NORD_REG | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 12 | 367 / 341 | 20 / 22 | 0 / 5 |
| RB17_RB15_REG_DONAU | 0 / 0 | 4 / 4 | 0 / 0 | 0 / 0 | 56 / 54 | 0 / 1 | 36 / 35 |
| RB17_REG_5851_TO_REG_5851 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| RB17_REG_NORD | 0 / 1 | 0 / 1 | 0 / 0 | 0 / 5 | 105 / 99 | 96 / 93 | 114 / 110 |
| RE18_RB15_REG_DONAU | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 64 / 63 | 0 / 0 | 0 / 0 |
| RE1_MUC_5501_TO_MUC_5501 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| RE1_MUC_5501_TO_N_SFS_5934 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 7 / 0 |
| RE1_N | 0 / 0 | 0 / 0 | 0 / 0 | 268 / 242 | 0 / 5 | 0 / 2 | 0 / 1 |
| RE1_N_SFS_5934_TO_MUC_5501 | 0 / 0 | 8 / 0 | 1 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| RE1_S | 1 / 0 | 0 / 7 | 258 / 228 | 0 / 3 | 0 / 0 | 0 / 0 | 0 / 0 |

See the [scheduled matrix](../compatibility/scheduled_platform_matrix.csv), [scheduled route totals](../compatibility/scheduled_route_summary.csv), [Gleis 2–5 planned matrix](../compatibility/scheduled_platform_matrix_gleis_2_5.csv), [observed matrix](../compatibility/observed_platform_matrix.csv), [Gleis 2–5 observed matrix](../compatibility/observed_platform_matrix_gleis_2_5.csv) and [supporting records](../compatibility/platform_evidence_records.csv) for totals, frequencies, zero-count combinations, dates and raw evidence.

## Actual reassignment

**403 of 3,686** eligible observations changed tracks (10.933%). Eligibility requires both scheduled tracks to agree and a strong reported track. The route key describes the reported station movement, with the scheduled route retained separately. The full [planned-to-reported matrix](../compatibility/reassignment_matrix.csv) includes unchanged diagonal cells and all seven platforms. 76 changes came from other tracks into Gleis 2–5. Arrival and departure delay values in the [reassignment records](../compatibility/platform_reassignments.csv) describe associations without causal interpretation.

| Planned / reported | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 47 | 1 | 15 | 0 | 2 | 1 | 0 |
| 2 | 3 | 255 | 135 | 0 | 0 | 0 | 0 |
| 3 | 0 | 15 | 836 | 8 | 1 | 0 | 0 |
| 4 | 0 | 0 | 1 | 937 | 30 | 2 | 7 |
| 5 | 0 | 1 | 0 | 100 | 704 | 6 | 8 |
| 6 | 0 | 1 | 0 | 16 | 10 | 250 | 3 |
| 7 | 1 | 2 | 1 | 22 | 6 | 5 | 254 |

| Route group | Eligible | Changed | Percent | Change days | Train numbers |
| --- | --- | --- | --- | --- | --- |
| ALL | 3686 | 403 | 10.93% | 28 | 112 |
| ICE_MUC_5501_TO_MUC_5501 | 0 | 0 | — | 0 | 0 |
| ICE_N | 515 | 12 | 2.33% | 10 | 10 |
| ICE_NORD_5501_TO_AUG_5381 | 1 | 0 | 0.00% | 0 | 0 |
| ICE_S | 527 | 9 | 1.71% | 8 | 8 |
| RB15_DONAU_NORD | 54 | 13 | 24.07% | 11 | 3 |
| RB15_NORD_DONAU | 0 | 0 | — | 0 | 0 |
| RB15_RB17_DONAU_REG | 72 | 1 | 1.39% | 1 | 1 |
| RB15_RE18_DONAU_REG | 62 | 1 | 1.61% | 1 | 1 |
| RB16_AUG_5381_TO_MUC_5501 | 0 | 0 | — | 0 | 0 |
| RB16_AUG_5381_TO_NORD_5501 | 0 | 0 | — | 0 | 0 |
| RB16_MUC_5501_TO_MUC_5501 | 0 | 0 | — | 0 | 0 |
| RB16_N | 582 | 147 | 25.26% | 28 | 28 |
| RB16_S | 539 | 157 | 29.13% | 28 | 22 |
| RB17_NORD_REG | 380 | 20 | 5.26% | 15 | 11 |
| RB17_RB15_REG_DONAU | 94 | 3 | 3.19% | 3 | 3 |
| RB17_REG_5851_TO_REG_5851 | 0 | 0 | — | 0 | 0 |
| RB17_REG_NORD | 309 | 21 | 6.80% | 14 | 10 |
| RE18_RB15_REG_DONAU | 63 | 0 | 0.00% | 0 | 0 |
| RE1_MUC_5501_TO_MUC_5501 | 0 | 0 | — | 0 | 0 |
| RE1_MUC_5501_TO_N_SFS_5934 | 0 | 0 | — | 0 | 0 |
| RE1_N | 250 | 8 | 3.20% | 7 | 7 |
| RE1_N_SFS_5934_TO_MUC_5501 | 0 | 0 | — | 0 | 0 |
| RE1_S | 238 | 11 | 4.62% | 8 | 9 |

## Simulation compatibility

The conservative configuration requires direct evidence across at least 2 operating days and 2 distinct train numbers. Scheduled and strong observations for the same call count once for that threshold. A single valid planned assignment can still justify retaining its train as fixed to that track. Weak observations and absence of direct evidence remain distinguishable from an explicit infrastructure prohibition. None of the archived evidence establishes a prohibition or official authorization.

Expanded eligibility adds documented sensitivity assumptions only. The legacy column refers to the synthetic AnyLogic rules in `Ingo.alp` and `route_catalog.csv`. In particular, the legacy ICE/RE1 northward corridor labels presumed SFS access. They cannot validate unrestricted SFS use in this dataset.

| Route group | Original AnyLogic | Supplied research | Conservative | Expanded |
| --- | --- | --- | --- | --- |
| ICE_MUC_5501_TO_MUC_5501 | — | — | — | — |
| ICE_N | 4\|5 | 4 | 4\|5 | 4\|5 |
| ICE_NORD_5501_TO_AUG_5381 | — | — | — | — |
| ICE_S | 3 | 2\|3 | 2\|3\|4 | 2\|3\|4 |
| RB15_DONAU_NORD | — | 3\|4 | 2\|3\|4\|5 | 2\|3\|4\|5 |
| RB15_NORD_DONAU | — | — | — | — |
| RB15_RB17_DONAU_REG | — | — | 5 | 5 |
| RB15_RE18_DONAU_REG | — | — | — | — |
| RB16_AUG_5381_TO_MUC_5501 | — | — | — | — |
| RB16_AUG_5381_TO_NORD_5501 | — | — | — | — |
| RB16_MUC_5501_TO_MUC_5501 | — | — | — | — |
| RB16_N | 4\|5 | 4\|5 | 4\|5 | 4\|5 |
| RB16_S | 2\|3 | 2\|3 | 2\|3 | 2\|3 |
| RB17_NORD_REG | — | 5 | 4\|5 | 4\|5 |
| RB17_RB15_REG_DONAU | — | — | 5 | 5 |
| RB17_REG_5851_TO_REG_5851 | — | — | — | — |
| RB17_REG_NORD | — | 2\|5 | 4\|5 | 4\|5 |
| RE18_RB15_REG_DONAU | — | — | 5 | 5 |
| RE1_MUC_5501_TO_MUC_5501 | — | — | — | — |
| RE1_MUC_5501_TO_N_SFS_5934 | — | — | — | — |
| RE1_N | 4\|5 | 4 | 4\|5 | 4\|5 |
| RE1_N_SFS_5934_TO_MUC_5501 | — | — | — | — |
| RE1_S | 2\|3\|5 | 3 | 2\|3\|4 | 2\|3\|4\|5 |

- The supplied report proposed RB17_REG_NORD on Gleis 2. The full archive gives 0 planned and 1 strong reports over 1 distinct evidence days. Direct evidence falls below the configured repeat threshold. A qualifying planned assignment may use a documented train-specific exception.

### Newly supported or assumed alternatives

| Route group | Platform | Scheduled / strong / changes | Strong days / trains | Basis | Example |
| --- | --- | --- | --- | --- | --- |
| ICE_S | 2 | 0 / 4 / 4 | 4 / 3 | REPEATED_OBSERVED | 2026-11-05/1601/765ed1619e0c87b3acd3 |
| ICE_S | 4 | 0 / 4 / 4 | 3 / 4 | REPEATED_OBSERVED | 2026-11-01/1003/67b3369c48ab27be7783 |
| RB15_DONAU_NORD | 2 | 0 / 3 / 3 | 3 / 2 | REPEATED_OBSERVED | 2026-11-03/84271/fcc120c6a22b4967eb9f |
| RB15_DONAU_NORD | 3 | 0 / 2 / 2 | 2 / 2 | REPEATED_OBSERVED | 2026-11-04/84267/cf76bce7e672d4380762 |
| RB15_DONAU_NORD | 4 | 19 / 17 / 3 | 15 / 3 | REPEATED_SCHEDULED_AND_OBSERVED | 2026-11-02/84275/f358e97c2f8d9d26c265 |
| RB15_DONAU_NORD | 5 | 1 / 2 / 2 | 2 / 1 | REPEATED_SCHEDULED_AND_OBSERVED | 2026-11-04/84271/dd337c3f2a2ef7a4f620 |
| RB15_RB17_DONAU_REG | 5 | 5 / 5 / 1 | 5 / 2 | REPEATED_SCHEDULED_AND_OBSERVED | 2026-10-31/84115/2656f7e64572b91b0d58 |
| RB17_NORD_REG | 4 | 0 / 12 / 12 | 10 / 8 | REPEATED_OBSERVED | 2026-11-03/84323/a90acb23a123aad78265 |
| RB17_NORD_REG | 5 | 367 / 341 / 0 | 25 / 19 | REPEATED_SCHEDULED_AND_OBSERVED | 2026-10-30/84351/a2ca8c23c4a6f16afa1f |
| RB17_RB15_REG_DONAU | 5 | 56 / 54 / 1 | 8 / 10 | REPEATED_SCHEDULED_AND_OBSERVED | 2026-10-31/84122/2eba5e794e53e929d810 |
| RB17_REG_NORD | 4 | 0 / 5 / 5 | 3 / 4 | REPEATED_OBSERVED | 2026-10-30/84330/ed4eab3de474aa4f6b84 |
| RB17_REG_NORD | 5 | 105 / 99 / 5 | 27 / 16 | REPEATED_SCHEDULED_AND_OBSERVED | 2026-10-30/84320/424fcb6b4d922cc85337 |
| RE18_RB15_REG_DONAU | 5 | 64 / 63 / 0 | 8 / 11 | REPEATED_SCHEDULED_AND_OBSERVED | 2026-10-31/84120/d51094f35dd16abd0901 |
| RE1_S | 4 | 0 / 3 / 3 | 3 / 2 | REPEATED_OBSERVED | 2026-11-03/4001/126d67573990c6f356b1 |
| RE1_S | 5 | 0 / 0 / 0 | 0 / 0 | ASSUMED |  |

The [compatibility evidence](../compatibility/platform_compatibility_evidence.csv) records the status and justification of each route–platform pair. The same GREEDY dispatcher can use either configuration. In the baseline, **115 / 116 (99.138%)** of trains have an alternative under conservative eligibility. **115 / 116 (99.138%)** have one under expanded eligibility. The expanded configuration gives 10 trains more options.

## Full-day timetable

The baseline is **2026-11-24**, selected in advance and checked against the local GTFS extraction and station-poster crosswalk. The [GTFS comparison](../timetable/gtfs_baseline_review.csv) shows 0 modeled-track GTFS through calls with an unresolved time, track or service match. The [timetable](../timetable/timetable.csv) contains **116** scheduled through trains on Gleise 2, 3, 4, 5, including 10 cancelled planned calls. The [terminal data](../timetable/terminal_services.csv) preserve 132 originating or terminating/endpoint calls, 37 on the modeled tracks. Terminal occupation intervals are unknown. There are 0 known modeled through occupations at midnight, 0 modeled departures beyond the day window, and 0 overlapping planned through-occupation pairs.

The date-specific DB amendment poster (page 6) lists RB16 59095 as the replacement for 59139. OpenBoards has only 59139, with two uncancelled REAL reports. The GTFS schedule and the board agree on the planned times, platform and itinerary direction. The baseline keeps the OpenBoards identity and one planned slot, with the poster number preserved separately. Which train number actually ran remains uncertain.

The 1 fixed-only per-train exceptions are ICE 1081 on Gleis 3. These retain the scheduled platform for both configurations. The [unresolved services](../timetable/unresolved_services.csv) and [excluded services](../timetable/excluded_services.csv) preserve individual decisions. The dwell median is 2.0 minutes, the mean is 3.328 and the range is 1.0 to 16.0. The cohort contains 0 zero-duration stops, 0 stops below their configured minimum, and 0 reversed-time cases in the baseline review. The configurable one-minute default is a modeling assumption. The input keeps the original scheduled times and publishes elapsed minutes relative to local midnight.

### Linked ICE records

| ICE records | Raw relation | Matching scheduled record | Baseline decision |
| --- | --- | --- | --- |
| 1507 / 2799 | Reciprocal links and matching full movement | fv:q9h6:2026-11-24:6 | one_platform_occupation_keep_regular |
| 1502 / 29004 | Reciprocal links and matching full movement | fv:p1rk:2026-11-24:1 | one_platform_occupation_keep_regular |
| 1080 / 2852 | Reciprocal links and matching full movement | fv:15ilf:2026-11-24:1 | one_platform_occupation_keep_regular |

The extra journeys are retained with source links in the review and exclusions. Reciprocal OpenBoards `travelsWith` records and agreeing times, platforms and routes support one modeled platform occupation per pair. The source does not establish the exact consist or a confirmed replacement relationship. The regular journey is the planned representation, corroborated on this day by the locally archived schedule.

## Historical incoming delay

The [delay sample](../delays/historical_arrival_delays.csv) includes 5,116 deduplicated REAL arrivals of eligible services, including terminating arrivals for future calibration review. Separate route and through-only summaries are available. The sample retains **604 early**, **11 on-time** and **4,501 late** arrivals. Mean / median / sample standard deviation were 7.392 / 3.600 / 13.384 minutes. The 5th, 25th, 75th, 90th, 95th and 99th percentiles were -1.550, 1.113, 8.404, 18.892, 28.613, 58.511 minutes. The observed range was -27.300 to 248.633 minutes. Day and scheduled-hour groupings use Europe/Berlin. Correlation within trains, groups and days is possible, and the construction period limits generalization.

## Verification and AnyLogic readiness

The repository unittest suite ran **48 tests**. Result **OK**. [Test log](../validation/test_results.txt)

**Ready for a controlled AnyLogic timetable import**. Use the conservative timetable and its fixed-only exceptions for the through-only closure-period cohort. Carry scheduled conflicts into the dispatch queue and account for the day boundary. A station-wide or normal-SFS experiment needs terminal occupation and routing evidence. The dwell and expanded platform assumptions remain subject to sensitivity analysis.

Reproduce the bundle with `python scripts/analyze_openboards_history.py` and the tests with `python -m unittest discover -s tests -v`. See the [Phase 2.1.2 guide](../../README.md#phase-212--openboards-history-and-simulation-timetable) for the offline inputs and options.
