# Wayeb event forecasting research deployment

[![Reproduce author deployment](https://github.com/roy-pyke/wayeb-event-forecasting/actions/workflows/reproduce.yml/badge.svg)](https://github.com/roy-pyke/wayeb-event-forecasting/actions/workflows/reproduce.yml)

部署作者代码，研究从 **Pattern Markov Chains（模式马尔可夫链）** 到 **Prediction Suffix Trees（预测后缀树，PST）** 和 **RTCEF（运行时自适应复杂事件预测）** 的方法演进。

This repository deploys the authors' implementations. It does not replace them with a new forecasting algorithm. Author repositories are Git submodules pinned to exact commits; deployment tooling, configurations, and validation evidence live here.

## Sources

| Implementation | Fixed revision | Purpose |
| --- | --- | --- |
| [ElAlev/Wayeb](https://github.com/ElAlev/Wayeb) | `b58a0cbe8c2c174d19394153c03504031ac57465` | Full-order Markov forecasting, variable-order PST forecasting, symbolic automata and register transducers |
| [manospits/rtcef](https://github.com/manospits/rtcef) | `9bf8796b223a1a657bc51f49475d6d4fbf616172` (`v1.0.0`) | Run-time adaptation with Kafka, model retraining and Bayesian hyperparameter optimisation |

See [the literature map](docs/LITERATURE.md) for papers, their relationship, and the distinction between deployment validation and paper experiment reproduction.

## Deployment milestones

1. Source audit, pinned author code and public GitHub repository.
2. Isolated build, recognition, full-order and PST forecasting with separate training and test streams.
3. RTCEF environment and a bounded adaptation integration check.
4. Reproduction guide, recorded results and final verification.

Completed milestones are committed and pushed directly, as requested. Validation status will be recorded alongside each completed stage.

## Run Wayeb

Requirements: **JDK 11**, Python 3 for the standard-library runner, Git and curl. On macOS the scripts select an installed JDK 11; elsewhere set `WAYEB_JAVA_HOME` or `JAVA_HOME`.

```bash
git clone --recurse-submodules https://github.com/roy-pyke/wayeb-event-forecasting.git
cd wayeb-event-forecasting
./setup.sh
./run_demo.sh
./wayeb --help
```

`setup.sh` downloads a checksum-verified sbt launcher and compiles the pinned author sources using [an isolated build overlay](build/build.sbt). Algorithms and upstream sources remain unchanged. Both the original Scala version (2.12.10) and author library versions are retained; obsolete build plugins are replaced by the pinned packaging tools in [toolchain.json](toolchain.json).

The demo generates 6,000 training events and 2,000 independent test events with fixed seeds, compiles the pattern `A · (B | C)`, learns a full-order Markov chain and a PST, then runs both interval and binary-window forecasting. Parameters are in [configs/demo.json](configs/demo.json). Each `runs/demo-*/` directory contains data, a literal-pattern match oracle, configuration, commands/logs, trained models and `report.json`.

[The recorded validation](reports/core-validation.json) found 631 matches, exactly agreeing with the independent oracle. All forecasting metrics agreed within `1e-12` across two runs. Three author tests passed: waiting-time forecast interval construction, PST behaviour and register-automaton/regular-expression equivalence. These are deployment checks on a small synthetic process, not reproductions of the papers' real-world experiments or a fair benchmark between model families (their warm-up lengths differ).

```bash
./scripts/sbt.sh 'core/testOnly Specs.model.waitingTime.WaitingTimeSpec Specs.vmm.PST Specs.srem.NSRAeqSREM'
```

## Run the later RTCEF implementation

```bash
./setup_rtcef.sh
./run_rtcef.sh
```

This uses CPython 3.12 in `.venv-rtcef/`, the authors' separate embedded Wayeb engine and a checksum-verified local Kafka 3.4.0 broker. The bounded run starts all five author services, trains and evaluates an initial model, then injects explicitly labelled control scores to exercise retraining, three Bayesian optimisation trials and two engine model swaps. All started processes are stopped afterwards. It requires loopback ports 9092, 9093 and 25333–25336 to be free.

The service integration passed, including observed engine scores for retrained model 0 and optimised model 4; see [RTCEF validation](reports/rtcef-validation.json). This proves the exercised service flow works locally. It does not establish real concept-drift performance. The author's optimisation factory currently scores candidates on its training data; the separate held-out check does not change that upstream behaviour.

For all build/validation steps in sequence, run `./reproduce.sh` (`--core` for only standalone Wayeb). See [复现说明 / Reproducibility](docs/REPRODUCIBILITY.md) for environment choices, compatibility fixes and the limits of the validation.

The full RTCEF check also passed twice: input/adaptation-window hashes, held-out counts and model versions agreed, and all optimisation candidate parameters and metrics agreed within `1e-10`. [Validation index](reports/VALIDATION.md) links the compact evidence. The GitHub Actions workflow runs the full reproduction command on Ubuntu with JDK 11 and Python 3.12 after pushes and pull requests, and retains run reports/logs as downloadable artifacts.

## Licensing

Wayeb has an author-specific dual licence: individual noncommercial research uses CC BY-NC-SA 4.0 with the additional conditions in [the author's licence](upstream/Wayeb/LICENSE.md), including public research results. RTCEF's top-level licence is LGPL-3.0; its embedded Wayeb code retains its own notices. Upstream code and publications keep their existing licences. This repository is public to share deployment and validation results. No private research data or local credentials belong here.

