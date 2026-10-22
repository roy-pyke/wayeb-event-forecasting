# Milestones

## 2026-10-22 — 1. Source and project foundation

- Verified the local 2017 paper's authors and DOI.
- Located the authors' current Wayeb code and the later RTCEF v1.0.0 release.
- Pinned both author repositories as submodules; recorded paper lineage and licence boundaries.
- Created a separate deployment project under the research workspace's existing `projects/` directory.
- Planned independent training/test data and bounded integration validation.

Build and runtime claims are deferred to the subsequent validation reports.

## 2026-10-22 — 2. Author engine build and reproducible forecasting

- Built the author Wayeb 0.6 source into `artifacts/wayeb.jar` with JDK 11, original Scala 2.12.10 and a separate sbt 1.9.9 / assembly 2.2.0 overlay.
- Ran independent seeded 6,000-event training and 2,000-event evaluation streams through recognition, FMM estimation, PST learning and both interval/classification forecasting methods.
- Verified all 631 recognition matches with an independent literal-pattern check.
- Repeated the complete run and verified identical input hashes and all forecast metrics to absolute tolerance `1e-12`.
- Passed three author tests covering waiting-time intervals, PST and register-automaton semantics.
- Saved compact evidence in `reports/core-validation.json`; full run artifacts remain in ignored `runs/` directories.
- Also built RTCEF's separate embedded Wayeb engine and installed the isolated Python compatibility environment. Its service integration is the next milestone.

