# Task: create a polished academic presentation (PPTX)

You are working in the existing IngoHbfSimulation repository. Read this package first. Build the final editable 16:9 PowerPoint and a PDF preview, without changing simulation code. Use the existing repo to cross-check project status, not to turn the deck into a code demo. If the user provides IRIS EPC exports, use them. If not, keep the EPC positions as clearly labeled placeholders or build draft vector EPCs from the specification; do not represent them as exported IRIS files.

Professor Voigt approved the challenging project and said programming is acceptable; for Friday's presentation he explicitly requested problem setting and process description using EPCs, no implementation details necessary. The project compares Fixed, Greedy and planned Lookahead. No promise that Lookahead wins or that savings are validated in the real world.

## Deliverable
- English, 9 main slides + 1 references slide; 7–8 minutes, three team members: Herman Dihtenko, Liliya Radvar, Mohammad Gaber. Date 27 November 2026.
- Editable PPTX, rendered PDF, and preferably source script. Put outputs in a dedicated presentation directory; retain credits and sources. Include speaker notes with timing. If images/EPCs unavailable, flag in final handoff.
- Fetch source assets via `python fetch_assets.py`; inspect downloaded track plan and crop passenger section around tracks 2–5. Do not distort or mislabel the plan. Attribution: DB InfraGO AG, document date as shown on actual download. Photos: use Wikimedia license credits and indicate crops. If downloads are blocked, use the supplied original conceptual schematic, not a fake official plan or stock photo of another station.
- Read `sources/evidence.md` before writing claims. Use a simplified matrix, not verified rail interlocking compatibility; published departures show examples only. Real schedule vs. simulation assumptions clearly separate. Current matrix entries unchanged from the repo unless user explicitly requests changes.

## Art direction: editorial / transport research, not a generic AI deck
Use a confident Swiss railway-inspired editorial grid, off-white paper #F5F3EF, near-black ink #18252B, deep teal #0C6265 and restrained signal orange #C65C36. Use a modern sans (Aptos, Inter if installed, or Arial) with high contrast. Large title type 40–54 pt, slide titles 30–40 pt, body 20–24 pt, sources 10–12 pt. Use generous margins and consistent alignment. No gradients, rounded dashboard cards, random pictograms, arrow chains, shadowed boxes, clip art, or generic corporate template. EPCs are the exception: preserve the actual required notation rather than redesigning semantics for decoration. Use actual photos on title and context slide, a carefully cropped genuine station plan, a typographic matrix and a horizontal rail occupancy timeline; use whitespace and thin rules. A single dominant visual per slide. Keep narrative text short and put details in notes. Do not place captions over unreadable portions of photos. Prefer editable native tables/text and vector graphics.

## Workflow
1. Read `brief/slides.md`, `epc/IRIS_build_specs.md`, `sources/evidence.md` and data CSVs. Check for provided EPCs in the project.
2. Download assets and verify actual file format and relevant content. Verify dates and timetable examples from originals if using exact times. Prefer open-licensed photos. If unavailable, use generated scope graphic and source links.
3. Build deck and add speaker notes. Use `assets/strategy_comparison.svg` or rebuild natively at equivalent scale; do not replace it with a process-arrow diagram.
4. Render every slide and inspect for overlap, overflow, cropped text, illegible EPC labels, inconsistent fonts. Ensure no slide is a wall of text. Reference slide after conclusion, not timed.
5. Final response: link outputs, state any missing sources/IRIS exports or assumptions; no claims of new simulation results unless actually run and verified.
