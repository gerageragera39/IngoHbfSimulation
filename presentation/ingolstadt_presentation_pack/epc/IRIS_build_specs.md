# IRIS EPC build specifications

Use the course's exact EPC notation. E = event (state), F = function (action), XOR = exclusive connector. Events and functions alternate; connectors as needed. Use a separate start/end event on each diagram. These are conceptual target processes, not a claim that route constraints are already implemented. Keep diagrams landscape where possible, or split into two columns only if readable; export SVG or PDF from IRIS, or high-resolution PNG. Avoid screenshots with toolbars.

## EPC 1 — Overall station process
E Train arrival scheduled
F Model incoming delay / advance to actual readiness
E Train ready for station entry
F Allocate platform (subprocess EPC 2)
E Platform reserved
F Obtain entry authorization and enter station [planned route constraints]
E Train at platform
F Perform passenger service / minimum dwell
E Service completed
F Manage departure (subprocess EPC 3)
E Train departed and station resources released

## EPC 2 — Platform assignment
E Train ready for allocation
XOR join (initial arrival or reevaluation)
F Evaluate assignment policy and eligible track availability
XOR split after function
  E Suitable track selected now
  F Reserve selected track
  E Platform reserved (end)
  OR exclusive alternate:
  E Allocation deferred (no eligible available track OR intentional Lookahead wait)
  F Wait for relevant resource change or planned reevaluation time
  E Allocation can be reevaluated
  -> loop back to XOR join before Evaluate function.

Do not label the negative branch only “No free platform” because Lookahead may deliberately defer assignment. Resource changes include releases, reopened tracks and updated expected arrivals. Ensure policy never reserves an ineligible or occupied track. If IRIS requires a different valid connector arrangement, preserve semantics and use course rules.

## EPC 3 — Train departure
E Passenger service completed
F Wait until scheduled departure time (if necessary)
E Train eligible for departure
F Request and wait for exit route [planned]
E Exit route reserved
F Depart from platform and clear platform track
E Platform track clear
F Release platform reservation and finish exit movement
E Exit route clear
F Release exit route and record completion
E Train departed and station resources released

Note: In final implementation distinguish departure from platform, track clearance and exit-route clearance; release resources only when clear. EPC expresses target conceptual process, not verified signalling rules.
