# Wayeb event forecasting research deployment

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

## Licensing

Wayeb has an author-specific dual licence: individual noncommercial research uses CC BY-NC-SA 4.0 with the additional conditions in [the author's licence](upstream/Wayeb/LICENSE.md), including public research results. RTCEF's top-level licence is LGPL-3.0; its embedded Wayeb code retains its own notices. Upstream code and publications keep their existing licences. This repository is public to share deployment and validation results. No private research data or local credentials belong here.

