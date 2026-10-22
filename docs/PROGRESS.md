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

## 2026-10-22 — 3. RTCEF deployment and live service integration

- Installed CPython 3.12 compatibility dependencies and pinned all direct/transitive Python packages; selected kafka-python 2.1.5 after diagnosing collector startup with a newer client.
- Built the authors' embedded RTCEF Wayeb engine separately from standalone Wayeb 0.6; preserved both submodules without source edits.
- Installed and verified a local Kafka 3.4.0 distribution; no Docker daemon required.
- Ran real Kafka, two Py4J gateways, and all five author services on seeded synthetic data.
- Observed the collector/factory assemble stream data, observer-triggered retraining, three Bayesian optimisation trials, and engine score reports after model swaps to versions 0 and 4.
- Evaluated the initial model on a separate 400-record test stream; labelled injected adaptation scores and the author's in-sample optimisation scoring explicitly.
- Verified cleanup stopped all owned child processes; recorded compact evidence in `reports/rtcef-validation.json`.

## 2026-10-22 — 4. Reproduction entry point, documentation and CI

- Added `./reproduce.sh` for the complete build/test/forecast/service sequence and `--core` for the standalone engine.
- Fixed RTCEF replay/data-window barriers and verified a second complete run, including identical adaptation-window hashes and all candidate parameters/metrics within `1e-10`.
- Added the literature map, bilingual reproduction guide, validation index and compatibility/evaluation boundaries.
- Added GitHub Actions to run the full sequence on Ubuntu/JDK 11/Python 3.12, with report/log artifacts and actions pinned to commit SHAs.
- Added the project to the surrounding research workspace's local navigation README.

