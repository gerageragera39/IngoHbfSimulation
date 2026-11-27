# Ingolstadt Hbf timetable validation

**PROVISIONAL** · 2026-11-24 · Europe/Berlin

Earliest usable Tuesday–Thursday in shared GTFS coverage, with Monday or Friday as fallback. Bavarian holidays are skipped.

Applied for DB poster evidence.

## Validation findings

- **Warning** — 78 calls have unknown or conflicting platforms.
- **Warning** — 19 known modeled-platform calls have blocking issues.
- **Warning** — 126 modeled-platform calls need compatibility review.
- **Warning** — 107 modeled-platform calls use a provisional minimum dwell.
- **Warning** — 5 DB poster entries need a GTFS completeness review.
- **Warning** — Some passenger train numbers are unavailable. Deterministic source IDs are retained.
- **Warning** — 79 calls have an unclassified or ambiguous route group.

## Station coverage

| Measure | Count |
| --- | ---: |
| Unique in-window passenger train stops | 272 |
| Main-day train stops | 272 |
| Stops originating on a previous GTFS service date | 8 |
| Known platforms | 194 (71.32%) |
| Modeled platform stops | 126 |
| Other platform stops | 68 |
| Unknown or conflicting platforms | 78 |
| Unknown occupation intervals | 134 |
| Model-scoped fixed-only compatibility assignments | 126 |
| Unclassified or ambiguous routes | 79 |
| Unresolved records | 143 |
| Excluded records | 68 |
| Main-day modeled rows in timetable.csv | 107 |
| Fully ready main-day rows | 0 |
| Provisional main-day rows | 107 |
| Initial occupations in the modeled or unknown scope | 0 |
| Scheduled overlapping interval pairs, all known platforms | 0 |

A stop can appear in multiple review counts. Known other-platform stops can also have unresolved occupation.

## Scheduled traffic and occupation

Peak main-day hours are 17:00 local time.
The occupancy chart uses known positive passenger dwell intervals clipped to the observation window.
Occupied minutes use the union of intervals. The conflict CSV lists all overlapping interval pairs.
These are published schedule observations. Passenger GTFS omits some operational movements and does not establish occupation before an originating departure or after a terminating arrival.

### Hourly main-day calls

| Measure | Value |
| --- | ---: |
| 00 | 10 |
| 01 | 2 |
| 02 | 0 |
| 03 | 0 |
| 04 | 7 |
| 05 | 12 |
| 06 | 17 |
| 07 | 16 |
| 08 | 14 |
| 09 | 13 |
| 10 | 12 |
| 11 | 12 |
| 12 | 12 |
| 13 | 14 |
| 14 | 13 |
| 15 | 12 |
| 16 | 14 |
| 17 | 18 |
| 18 | 16 |
| 19 | 13 |
| 20 | 13 |
| 21 | 11 |
| 22 | 11 |
| 23 | 10 |

### Platform

| Measure | Value |
| --- | ---: |
| 3 | 34 |
| 4 | 29 |
| 5 | 37 |
| Unknown | 78 |
| 6 | 25 |
| 2 | 26 |
| 1 | 23 |
| 7 | 20 |

### Train category

| Measure | Value |
| --- | ---: |
| ICE | 39 |
| RE | 36 |
| RB | 197 |

### Line

| Measure | Value |
| --- | ---: |
| ICE 41 | 4 |
| RE1 | 36 |
| RB16 | 51 |
| RB17 | 52 |
| RB13 | 40 |
| RB15 | 50 |
| ICE 29 | 32 |
| ICE 25 | 3 |
| RB14 | 4 |

### Route group

| Measure | Value |
| --- | ---: |
| ICE_S | 20 |
| RE1_S | 10 |
| RB16_N | 22 |
| RB17_REGENSBURG | 25 |
| UNCLASSIFIED | 79 |
| RB13_DASING | 20 |
| RB15_WEST | 25 |
| ICE_N | 19 |
| RB16_S | 20 |
| RB17_INGOLSTADT_NORD | 17 |
| RE1_N | 10 |
| RB15_INGOLSTADT_NORD | 3 |
| RB14_EICHSTAETT | 2 |

### Stop kind

| Measure | Value |
| --- | ---: |
| through | 138 |
| terminating | 66 |
| originating | 68 |

### Boundary and occupation status

| Measure | Value |
| --- | ---: |
| within_window | 138 |
| unknown_interval | 134 |

### Platform evidence status

| Measure | Value |
| --- | ---: |
| matched_db_poster | 194 |
| unknown | 66 |
| conflict | 12 |

### Blocking reasons

| Measure | Value |
| --- | ---: |
| terminal_occupation_unknown | 134 |
| platform_missing | 66 |
| platform_conflict | 12 |

### Review flags

| Measure | Value |
| --- | ---: |
| compatibility_review | 126 |
| provisional_minimum_dwell | 138 |
| train_number_unavailable | 117 |
| zero_scheduled_dwell | 134 |
| route_group_unclassified | 79 |

### Through scheduled dwell (minutes)

| Measure | Value |
| --- | ---: |
| count | 138 |
| min | 1.0 |
| mean | 4.058 |
| median | 2.0 |
| max | 20.0 |
| zero | 0 |
| below_legacy_three_minutes | 93 |

### All published arrival/departure pairs (minutes)

| Measure | Value |
| --- | ---: |
| count | 272 |
| min | 0.0 |
| mean | 2.059 |
| median | 1.0 |
| max | 20.0 |
| zero | 134 |
| below_legacy_three_minutes | 227 |

### Scheduled occupied minutes by platform

| Measure | Value |
| --- | ---: |
| 1 | 23.0 |
| 2 | 155.0 |
| 3 | 59.0 |
| 4 | 82.0 |
| 5 | 79.0 |
| 6 | 68.0 |
| 7 | 83.0 |

## DB poster and GTFS discrepancies

The examples below need source reconciliation before the station cohort can be confirmed.
- **06:02 RB 17 84115** — The poster lists the Regensburg service and a 6 December cancellation. GTFS has RB17 at 06:06 with different arrival timing. Shared identity is unverified. [DB poster, page 4](https://db.info/downloads/schedule/Aenderungstafel_2993.pdf#page=4)
- **06:12 RB 15 84256** — This Ulm departure has no exact time-and-line match in GTFS. The 05:56 GTFS service reaches Ulm at the same time. Shared identity is unverified. [DB poster, page 4](https://db.info/downloads/schedule/Aenderungstafel_2993.pdf#page=4)
- **07:05 RE 18 84117** — The same-time GTFS call is labeled RB17 and reaches Regensburg 12 minutes later. RE18 appears elsewhere in the regional archive but has no active Ingolstadt call on 24 November. Shared identity is unverified. [DB poster, page 5](https://db.info/downloads/schedule/Aenderungstafel_2993.pdf#page=5)
- **08:11 RE 1 59401** — The nearby GTFS departure is at 08:12 and reaches München one minute later. The regular-poster 08:12 match identifies a different train number. Shared identity is unverified. [DB poster, page 5](https://db.info/downloads/schedule/Aenderungstafel_2993.pdf#page=5)
- **11:08 RB 13 86679** — GTFS lists an 11:05 Dasing departure with the same destination time. The 11:05 amendment entry is Sunday-only. Shared identity is unverified. [DB poster, page 6](https://db.info/downloads/schedule/Aenderungstafel_2993.pdf#page=6)

## Review files

- `unresolved_records.csv` lists missing, conflicting or incomplete model inputs.
- `excluded_trains.csv` records known other platforms and station calls outside passenger rail scope.
- `route_mapping_review.csv` lists fixed-only compatibility rules.
- `initial_occupancy.csv` lists pre-window occupations with a modeled or unknown platform.
- `scheduled_occupancy_conflicts.csv` preserves all overlapping published intervals and their train IDs.
- `duplicate_review.csv` records confirmed and ambiguous duplicate candidates.

## Provenance

GTFS data from GTFS.DE, based on DELFI e.V. NeTEx data, is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). This project filtered the data to the station window and added timetable evidence and modeling fields. Refer to dataset_metadata.json for hashes, validity dates and acquisition receipts.
