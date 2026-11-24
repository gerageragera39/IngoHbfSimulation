# Slide content and speaker notes

Target 7:10–8:00. Use the text below as content, not a compulsory visual template.

## 01 — Railway platform assignment simulation (0:20)
Subtitle: A case study of Ingolstadt Hbf
Simulations • Herman Dihtenko / Liliya Radvar / Mohammad Gaber • 27 November 2026
Visual: real wide station photograph, asymmetric editorial title.
Notes: We study whether better use of existing tracks can reduce additional train delays. We compare three dispatching policies using discrete-event simulation.

## 02 — A late train can delay the next one (0:40)
Headline: Can better platform assignment reduce secondary delays without adding capacity?
Short text: An incoming delay disrupts scheduled track occupancy. A following train may need to wait even though another suitable track is free.
Visual: a compact two-track occupancy timeline, not a chain of boxes. Make the distinction between incoming lateness and extra congestion-induced delay.
Notes: We focus on delays generated within the station, not on eliminating delays elsewhere in the network. Reassigning a train might reduce waiting but can also create new conflicts.

## 03 — One station, four platform tracks (0:50)
Ingolstadt Hbf • Gleis 2–5 • RB16, RE1 and ICE, northbound and southbound.
Tracks 2/3: 409 m; tracks 4/5: 419 m; all four platform edges are 76 cm high (DB InfraGO net construction length, not verified usable train length).
Included: arrivals, waiting, compatible track allocation, dwell, departure. Planned extension: simplified entry/exit capacity constraints. Excluded: full network, detailed signalling, passenger movement and freight operations. Include other passenger services on these tracks as background demand if integrating actual timetable.
Visual: cropped DB InfraGO track plan; fallback `assets/station_scope.svg`. Credit source. Do not imply complete station topology in a schematic.
Notes: We selected four long passenger tracks. This is a deliberately restricted station model, not the entire railway network.

## 04 — Not every train can use every track (0:50)
Use `sources/platform_matrix.csv` as an editable table. Label “Simplified platform eligibility”. Distinguish model allowed vs. excluded, not physically impossible. Representative planned track = synthetic baseline value.
Three constraints: one train per modeled track; assignment only to eligible tracks; respect minimum dwell and scheduled departure.
Footnote: “Model assumptions informed by published DB timetables and station data; not a complete set of operational routing permissions.”
Notes: Published departures demonstrate that service groups may use different tracks. ICE 822 appears on tracks 4 and 5 on different days in the 2026 timetable. A departure entry does not establish every approach route or live reassignment feasibility. RE1 southbound on track 5 is supported by an older archived timetable entry, not verified for current operating date.

## 05 — Three strategies, one trade-off (1:30)
Fixed — wait for planned track. Greedy — prefer planned track if free, otherwise another free eligible track; if none, wait. Lookahead (planned) — consider anticipated arrivals and track release times over next 60 minutes, and permit intentional short waiting to avoid future conflicts.
Use `assets/strategy_comparison.svg` or PNG, or recreate its 3 aligned occupancy timelines. Fixed and Lookahead have same outcome in this example; not evidence they are equivalent generally.
Illustrative scenario: RB16 arrives 10:00, planned track 2 busy until 10:01, track 3 free; RB16 needs 6 minutes occupancy; ICE expected 10:02, can only use track 3 in model, needs 2 minutes. Fixed: RB16 waits 1 minute; Greedy: RB16 uses 3 at 10:00, ICE waits 4 minutes; Lookahead: preserves 3, RB16 waits 1 minute. Total waiting 1 / 4 / 1 min. These are hand-worked waiting times, not secondary departure delay or simulation results.
Notes: The first two strategies are implemented in prototype; third is planned. Lookahead uses only information available at decision time, not future random events. Its horizon is a design parameter. The aim is to compare rather than assume a winner.

## 06 — EPC: overall station process (0:45)
Use team IRIS export for EPC 1. Emphasize arrival, allocation, dwell and departure. Caption: “Conceptual target process; simplified infrastructure extensions planned.”
Notes: The train becomes ready after incoming delay, requests a platform, enters when permitted, receives service and departs. Each stage can generate congestion. See EPC spec.

## 07 — EPC: platform assignment (0:45)
Use team IRIS export for EPC 2. Emphasize decision, waiting loop, reservation. Policy determines whether an eligible available track should be reserved now or the train should wait.
Notes: The same process supports all three strategies. An intentional Lookahead wait is possible even if a compatible track is currently free. The model reevaluates on relevant changes.

## 08 — EPC: train departure (0:40)
Use team IRIS export for EPC 3. Emphasize dwell, schedule, exit authorization and release of resources. Caption: “Target process including planned exit-route constraints.”
Notes: A train cannot leave before service completion and scheduled departure. In the extended model, a congested exit route may keep the track occupied until clearance.

## 09 — What we will test (0:50)
Scenarios: normal operation, peak traffic, larger incoming delays, temporary track closure. KPIs: average secondary delay, waiting time, track utilization, reassignments and throughput.
Conclusion: Identify when dynamic allocation helps, when it does not, and how infrastructure limits affect the result.
Notes: Compare policies on identical input schedules and random-delay realizations using repeated simulation runs. Timetable integration, route constraints and Lookahead are planned extensions. No numerical real-world improvement is promised.

## 10 — References (not timed)
DB InfraGO station equipment and track plan; DB published timetable; BEG station data if used; photo author/license/source links; project repository if desired. See sources/evidence.md. Keep references readable; cite sources also on their associated slides.
