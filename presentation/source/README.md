# Ingolstadt Hbf presentation source

The 16:9 deck has nine presentation slides and one untimed references slide. Speaker notes divide 7 minutes 30 seconds among Herman Dihtenko, Liliya Radvar and Mohammad Gaber. The three conceptual EPCs follow the supplied IRIS build brief and use editable PowerPoint shapes and text.

## Build

Run `build_deck.mjs` with Node.js and the Codex-bundled `@oai/artifact-tool`. If the package is outside Node's module search path, set `ARTIFACT_TOOL_ENTRY` to the bundle's absolute `@oai/artifact-tool/dist/artifact_tool.mjs` path. In the Codex desktop app, the workspace-dependency tool returns the Node executable and package directory.

```powershell
$env:ARTIFACT_TOOL_ENTRY = '<absolute path to artifact_tool.mjs>'
node .\build_deck.mjs .\Ingolstadt_Hbf_revised.pptx
.\export_pdf.ps1 -Presentation .\Ingolstadt_Hbf_revised.pptx -Pdf .\Ingolstadt_Hbf_revised.pdf
```

The PowerShell export uses Microsoft PowerPoint for Windows. PowerPoint can also export the deck through its PDF export menu.

## Included inputs and credits

- `assets/platform_matrix.csv` contains the unchanged eligibility matrix and synthetic planned tracks. `assets/platform_dimensions.csv` records the published platform dimensions. [Project repository](https://github.com/gerageragera39/IngoHbfSimulation/tree/226917c), [DB InfraGO station equipment](https://www.dbinfrago.com/web/bahnhoefe/leistungen/stationsnutzung/stationshalt/stationsausstattung/Ingolstadt-Hbf-12671312).
- `assets/db-passenger-plan.png` is a passenger-area crop of DB InfraGO AG's Ingolstadt Hbf (MIH) service facilities plan dated 19 October 2026. It was rendered with Poppler at 168 dpi using `-x 2020 -y 1418 -W 890 -H 465`. Editable teal highlights and labels identify modeled tracks 2–5. [Original track plan](https://trassenfinder.de/apn/MIH).
- `assets/station_platforms.jpg` is a Wikimedia Commons preview of Thesenbauer's 15 June 2013 photograph. Slide 1 crops the image. [Photograph](https://commons.wikimedia.org/wiki/File:Neue_Bahnsteige_Ingolstadt_Hauptbahnhof.JPG), [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
- `assets/station_exterior.jpeg` is a Wikimedia Commons preview of Renardo la vulpo's 29 May 2022 photograph. [Photograph](https://commons.wikimedia.org/wiki/File:Ingolstadt,_Hauptbahnhof_v_W,_3.jpeg), [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
- The ICE 822 example was checked on PDF page 3 of the downloaded Deutsche Bahn departure timetable, valid from 14 December 2025. [Departure timetable](https://www.bahnhof.de/downloads/schedule/Regeltafel_2993.pdf).
- Slide 5 uses a hand-worked comparison. The illustrated southbound RE1 plans to use track 2. The model matrix retains track 3 as the representative baseline for that service group.
