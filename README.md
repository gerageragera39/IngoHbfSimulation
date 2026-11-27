# Ingolstadt Hbf — Railway Platform Assignment Optimization

**University Simulations course project · Work in progress**

A discrete-event simulation of platform occupancy and dispatching at **Ingolstadt Hauptbahnhof (Germany)**. The research question is whether dynamically assigning trains to compatible platforms can reduce **station-induced secondary delays**, compared with keeping planned platform assignments.

The prototype uses **AnyLogic 8.9.10**, the **Process Modeling Library (PML)**, and Java functions within AnyLogic. Python validates completed runs and analyzes paired Monte Carlo experiments. Real timetable integration and the OR-Tools optimizer are planned.

## 1. Research question and objectives

> How much can dynamic platform assignment reduce secondary delay under the same timetable and incoming-delay scenarios, relative to fixed planned platforms?

The project aims to:

- Simulate arrivals, station waiting, exclusive platform occupation, dwell and departure.
- Honor train-to-platform compatibility constraints.
- Evaluate **FIXED_DB**, **GREEDY**, and eventually **OPTIMIZED (OR-Tools)** strategies on identical scenarios.
- Distinguish delays caused inside the modeled station from pre-existing incoming delays.
- Produce reproducible experiments and per-train results for statistical comparison.

## 2. Scope

We model **Gleis 2, 3, 4 and 5**, not the entire railway network. The north/south directions identify the train groups entering the station; their subsequent routes are outside the model.

**Included:** two incoming train streams, central waiting area, platform eligibility and assignment, platform occupation with capacity one, dwell, release, and basic delay metrics.

The current passenger model represents walking time through transfer parameters. Track geometry, switches, signals, approach conflicts, individual passenger agents, trains moving beyond the station, and real-time DB dispatch decisions are outside the modeled scope.

**Important:** the compatibility matrix is a **model assumption**, not a verified complete map of physically feasible station routes. For future real-timetable experiments, all trains occupying Gleis 2–5 must be accounted for, including trains not eligible for reassignment.

## 3. Model architecture

```text
fromNorth (Source) ──┐
                    ├──> wait (Wait: common holding area)
fromSouth (Source) ──┘                 |
                                      v
                     Java dispatcher on Main
                     canUse() / choosePlatform()
                           dispatchTrains()
                                      |
                                      v
                           selectOutput5
                          /    |    |    \
                       Gleis2 Gleis3 Gleis4 Gleis5
                       Delay  Delay  Delay  Delay
                          \    |    |    /
                                   v
                               sink (Sink)
```

- **`fromNorth`** creates southbound trains (`RB16_S`, `RE1_S`, `ICE_S`).
- **`fromSouth`** creates northbound trains (`RB16_N`, `RE1_N`, `ICE_N`).
- **`wait`** holds trains until the dispatcher releases a selected train using `free(agent)`.
- **`selectOutput5`** routes each released train based on `assignedPlatform`.
- **`Gleis2`–`Gleis5`** are `Delay` blocks with **capacity 1**, representing platform occupation.
- **`sink`** logs departure, releases the dispatcher's platform reservation, and triggers a fresh dispatch decision.
- The selector's fifth exit goes to an auxiliary `sink1` in the model; it should eventually be used as an explicitly monitored error path, not as a platform.

There is one **central waiting area**, rather than separate queues tied to specific platforms. A waiting train can be assigned to an alternative compatible platform before being released.

The dispatcher is implemented through **Agent → Function** elements on `Main`, not by Java methods declared inside PML event fields.

## 4. Platform compatibility matrix (model version 0.2)

`S` means southbound; `N` means northbound. Check marks indicate platforms **allowed in the current simulation**, not universally validated infrastructure permissions.

| Train group | Gleis 2 | Gleis 3 | Gleis 4 | Gleis 5 | Representative planned platform |
| --- | :---: | :---: | :---: | :---: | :---: |
| RB16_S | ✓ | ✓ | — | — | 2 |
| RE1_S | ✓ | ✓ | — | ✓ | 3 |
| ICE_S | — | ✓ | — | — | 3 |
| RB16_N | — | — | ✓ | ✓ | 5 |
| RE1_N | — | — | ✓ | ✓ | 4 |
| ICE_N | — | — | ✓ | ✓ | 4 |

The checked-in **`route_catalog.csv`** lists these six groups and their allowed platforms separated by `|`. It is currently a **reference file only**; the test Sources still assign group properties in Java code rather than loading this CSV. The checked-in catalog also contains legacy `entry_corridor` and `exit_corridor` columns, which the simulation **does not use**. They should be removed when the input format is standardized.

## 5. Dispatch strategies

### FIXED_DB — baseline (implemented)

Each train may use only its **planned platform**. If the platform is occupied or reserved, it waits even when a compatible alternative is free. `FIXED_DB` is a fixed-assignment **simulation baseline**, **not** a reproduction of real DB dispatching behavior.

### GREEDY — availability-based assignment (implemented)

When a train appears or a platform becomes free, the dispatcher:

1. Inspects waiting trains in the common `Wait` block.
2. Filters platforms to those allowed for each train and currently not occupied/reserved.
3. Prefers the train's planned platform if free; otherwise searches alternatives by ascending platform number.
4. Chooses among eligible waiting trains by earliest ready time, with arrival sequence as a tie-breaker.
5. Reserves the platform, assigns the train, and releases it from `Wait`.

This is a **simple online Greedy policy**. It does not yet forecast platform release times or solve a global scheduling problem.

### OPTIMIZED — OR-Tools (planned)

A planned optimizer will choose both platform assignments and train service order, respecting compatibility, exclusive capacity, minimum dwell and departure constraints. The intended method is **rolling horizon**: optimize using information currently available, rather than knowing future random disturbances in advance. A platform-change penalty may be included as a secondary objective. Start with file-based exchange between AnyLogic and Python; more interactive integration depends on AnyLogic license constraints.

## 6. Train data and delay calculation

Every `TrainRequest` agent has the following fields:

| Field | Meaning |
| --- | --- |
| `trainId`, `routeGroup`, `sequence` | Identity, route category, deterministic arrival order |
| `plannedPlatform`, `assignedPlatform`, `allowedPlatforms` | Planned, assigned and eligible platforms |
| `scheduledArrival`, `scheduledDeparture` | Scheduled event times |
| `incomingDelay`, `readyTime` | Initial delay and earliest time available for station processing |
| `minDwell` | Minimum required platform dwell |
| `actualArrival`, `actualDeparture` | Actual platform entry and departure times |
| `stationDelay` | Station-induced secondary delay |

All model time calculations should use **minutes**.

For train *i*, the earliest possible departure without further station congestion is:

```text
earliestDeparture_i = max(scheduledDeparture_i,
                          readyTime_i + minDwell_i)
```

Its secondary delay is:

```text
stationDelay_i = max(0, actualDeparture_i - earliestDeparture_i)
```

This avoids counting unavoidable incoming lateness as delay caused by the station itself.

Completed experiments provide per-train CSV exports with platform, timing, secondary delay, and passenger transfer fields where supported by the export schema.

**Planned metrics:** number/share of affected trains, maximum delay, late-departure share, utilization, platform reassignment count, throughput, recovery time, variability and confidence intervals across scenarios.

## 7. Current development status

| Component | Status | Notes |
| --- | --- | --- |
| AnyLogic PML flow | **Working** | Two Sources, shared Wait, selector, four Delays, Sink |
| `TrainRequest` agent | **Implemented** | Train-specific state |
| `canUse()` | **Implemented** | Compatibility check |
| `choosePlatform()` and `dispatchTrains()` | **Implemented** | Central dispatching |
| FIXED_DB | **Implemented** | Planned platform only |
| GREEDY | **Implemented** | Online assignment to free eligible platforms |
| Console logging / basic delay KPIs | **Implemented** | Per-train events and aggregate summary |
| Verified real DB timetable / `trains.csv` | **Not implemented** | Synthetic arrivals used now |
| Random incoming delays with reproducible seeds | **Implemented** | Synthetic input scenarios |
| Per-train CSV output | **Implemented** | AnyLogic exports in `Ingo/results/` |
| Python + OR-Tools optimizer | **Not implemented** | Planned |
| Monte Carlo statistical experiments | **Implemented** | Paired FIXED_DB and GREEDY batches |
| Simulation analytics dashboard | **Implemented** | Local Streamlit app backed by validated CSVs |
| Dashboard tests | **Implemented** | Synthetic fixtures, committed-data regressions, and Streamlit AppTest |

### First manual comparison: 10 synthetic trains

Two manual runs were performed using the same ten artificial train requests (five from each Source). The console outputs were:

| Metric | FIXED_DB | GREEDY |
| --- | ---: | ---: |
| Completed trains | 10 | 10 |
| Total secondary delay | **2.0 minutes** | **1.0 minute** |
| Mean secondary delay per train | 0.2 minutes | 0.1 minutes |
| Trains with secondary delay | 2 | 1 |
| Platform reassignments | 0 | 3 |

In this particular scenario, GREEDY reduced total secondary delay by **50%**. For example, train `S3` was reassigned from Gleis 4 to compatible Gleis 5, allowing an earlier departure.

**This is a smoke-test result, not a measured improvement in real DB operations.** Ten artificial arrivals with zero incoming delays provide no reliable estimate of operational benefits. The real study requires validated timetable data and many paired stochastic scenarios.

## 8. Running the current model

**Requirement:** AnyLogic **8.9.10**, with the Process Modeling Library.

1. Clone the repository or download its files.
2. Open **`Ingo/Ingo.alp`** in AnyLogic.
3. On `Main`, find the `policy` variable. Set its initial value to **`"GREEDY"`** or **`"FIXED_DB"`**.
4. Check **Model time units = minutes** and **Delay time units = minutes** for **all four** Gleis Delays.
5. Run the `Simulation` experiment and inspect the AnyLogic console.
6. Run the other policy on the same synthetic settings and compare the final summary.

The current test setup creates **5 trains per Source**, with a **2-minute interarrival time** for each stream, **3-minute minimum dwell**, and planned departure **5 minutes after the synthetic ready/arrival time**. Incoming delay is zero. The saved `Simulation` experiment uses a **500-minute stop time**; the ten-train test finishes much earlier.

**Known pitfall:** if `Delay time` is configured in *seconds* while its Java expression computes minutes, five minutes will be treated as five seconds (shown as `0.0833333` model minutes). The current committed `Ingo.alp` has the Delay units set to **minutes**.

**Manual acceptance checklist:** all ten trains depart; no two trains occupy the same platform simultaneously; assigned platforms are compatible; trains waiting for occupied platforms are reconsidered upon departure; FIXED_DB does not reassign platforms; and the final console summary prints the aggregate delays.

The relative order of simultaneous events may depend on AnyLogic's event ordering; future experiments must freeze each train's complete input record and scenario identifier across policies.

### Launch the analytics dashboard

Run these commands from the repository root.

```bash
python -m pip install -r analysis/requirements_dashboard.txt
python -m streamlit run analysis/station_dashboard.py
```

**Ingolstadt Hbf — Dispatching Analytics** analyzes completed AnyLogic CSVs across five sections. Overview, Platform Utilization, Passenger Transfer, and Statistical Analysis compare the selected Monte Carlo configuration. Train Data Explorer filters individual results and compares the same train under both dispatchers. The dashboard includes CSV exports, paired confidence intervals, and an occupancy Gantt chart built from actual arrival and departure times.

Run the automated tests with `python -m unittest discover -s tests -v`. See the [Russian dashboard guide](analysis/DASHBOARD_README_RU.md) for validation, filtering, and interpretation.

## 9. Repository layout

```text
IngoHbfSimulation/
├── Ingo/
│   ├── Ingo.alp             # Current AnyLogic model
│   ├── Ingo.original.alp    # Earlier project backup
│   └── results/             # Completed simulation CSV exports
├── analysis/                # CLI analysis, Streamlit dashboard, reference outputs
├── tests/                   # Dashboard tests
├── route_catalog.csv        # Route groups and permitted platforms
└── README.md                # This documentation
```

## 10. Roadmap

1. **Validate real timetable inputs.** Choose one operating date and time window; gather all trains using Gleis 2–5; verify arrivals, departures, planned platforms and alternate eligibility; distinguish facts from assumptions.
2. **Integrate `trains.csv`.** Replace hard-coded synthetic arrivals with scheduled train requests, preserving the existing PML architecture.
3. **Add reproducible incoming delays.** Record the random seed and complete delay vector for each scenario.
4. **Improve validation and logging.** Assert capacity/compatibility invariants, save per-train CSV records, and evaluate FIXED_DB and GREEDY on identical scenarios.
5. **Integrate Python + OR-Tools.** Start with a hand-verifiable optimization example and file-based exchange, then rolling-horizon dispatch decisions.
6. **Run paired Monte Carlo experiments.** Start with 10–20 debugging scenarios, then 100 and potentially 500–1,000 subject to performance and license constraints.
7. **Perform sensitivity analysis.** Vary mean incoming lateness, zero-delay probability, large disturbances, correlated delays, alternative-platform eligibility and traffic intensity.
8. **Deliver reproducible results.** Document assumptions, configurations, seeds, input data, statistics, and how a teammate can reproduce each experiment.

A separate 3D station visualization is planned in AnyLogic.

## 11. Team conventions

- Keep the same PML topology when comparing policies; only dispatch logic should vary.
- Use minutes consistently across source inputs, timetable fields, dwell times and KPIs.
- Do not use future random-delay information in online dispatch decisions.
- Keep published DB information distinct from assumptions, synthetic data and experimental compatibility restrictions.
- Never allow two trains to occupy one platform or a train to enter an incompatible platform.
- Pair policy evaluations by identical train inputs and random seeds.
- Make every code/data change reviewable and test it with a small known scenario.
- Avoid presenting results from a single artificial run as operational conclusions.

## Disclaimer

This is an **academic research prototype**, not an official Deutsche Bahn tool or a control system for real trains. Physical infrastructure and operational rules have been simplified. The compatibility assumptions and synthetic comparison results must not be interpreted as verified real-world railway capabilities or performance.

**License:** No project license file is currently included. The team should agree on licensing and external redistribution before publication beyond the course.
