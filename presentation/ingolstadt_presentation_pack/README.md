# Ingolstadt Hbf — presentation handoff for Codex

Prepared 2026-11-24 for the Simulations course presentation on Friday, 27 November 2026.

**Start with `CODEX_TASK.md`.** This is a research and design handoff, not a finished slide deck. English presentation, target 7–8 minutes; 9 main slides plus references. Three IRIS EPC exports will be supplied by the team separately.

Contents:
- `brief/slides.md`: slide copy, design direction and speaker notes.
- `epc/IRIS_build_specs.md`: three conceptual EPCs, including correct strategy-dependent waiting logic.
- `sources/evidence.md`: official sources, limitations, evidence for compatibility.
- `sources/platform_matrix.csv`, `sources/timetable_examples.csv`, `sources/platform_dimensions.csv`: structured slide data.
- `sources/asset_manifest.json`: original media URLs and credits.
- `assets/strategy_comparison.svg` and `.png`: original editorial-style timeline graphic, not a real simulation output.
- `assets/station_scope.svg` and `.png`: original schematic, explicitly not track topology.
- `fetch_assets.py`: fetches the external originals into `assets/external/` on a machine with internet access.

## Download limitation
The external PDF and photograph files were inspected or located through web research, but could not be transferred into the file-generation environment (network/DNS and download service failure). They are **not** bundled as binaries. The manifest and script are provided so Codex can fetch them, or a human can download them in a browser. Do not invent missing photos or substitute a different station. The SVG/PNG assets in this package are generated originals, not photographs or official plans.

The DB timetable endpoint serves changing documents, and the cached text and rendered PDF exposed different timetable revisions. Evidence records explicitly distinguish the visually checked 2026 timetable (valid from 14 Dec 2025) from an older text-indexed version (valid from 15 Jun 2025). Recheck downloaded originals before putting exact times in a slide. No operational routing permissions were verified. 
