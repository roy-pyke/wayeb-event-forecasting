# 部署验证 / Deployment validation

Local checks completed on **2026-10-22**, macOS arm64. These are controlled synthetic checks of the authors' software, not reproductions of their real-world benchmark tables.

| Check | Result | Evidence |
| --- | --- | --- |
| Author source integrity（作者源码完整性） | Two pinned commits; no tracked upstream edits | [SOURCE.json](../SOURCE.json) |
| Pattern recognition（模式识别） | 631 detections, exactly matching an independent literal-pattern oracle | [Core report](core-validation.json) |
| Full-order Markov forecasting（全阶马尔可夫预测） | Learned model, interval and binary-window forecasting passed | [Core report](core-validation.json) |
| Prediction suffix tree（预测后缀树） | Training and both forecasting modes passed | [Core report](core-validation.json) |
| Core repeatability（核心流程复现） | Two runs; identical input hashes and metrics within `1e-12` | [Core report](core-validation.json) |
| Author semantic tests（作者语义测试） | 3 passed: waiting-time intervals, PST, register automata/SREM equivalence | [Core report](core-validation.json) |
| RTCEF live services（实时服务集成） | Kafka, two gateways and all five author services exercised | [RTCEF report](rtcef-validation.json) |
| Model adaptation（模型适应） | Observer-triggered retraining, 3 Bayesian optimisation candidates, score reports from model versions 0 and 4 | [RTCEF report](rtcef-validation.json) |
| RTCEF repeatability（自适应流程复现） | Two runs; fixed input/window hashes, matching held-out counts/model versions; candidate parameters and metrics within `1e-10` | [RTCEF report](rtcef-validation.json) |
| Process cleanup（进程清理） | All owned Kafka/Java/Python child processes stopped | [RTCEF report](rtcef-validation.json) |

The RTCEF adaptation scores are injected on a dedicated control topic; they are not observed concept drift. Its factory retains the author's current in-sample optimisation scoring. A separate initial-model check uses 1,000 training and 400 held-out records. Read [the reproduction guide](../docs/REPRODUCIBILITY.md) before interpreting the numeric statistics.

Full local evidence is under the project's ignored `runs/core-final*` and `runs/rtcef-stable*` directories. Fresh runs use timestamped directories. GitHub Actions provides a separate Linux run with reports and logs attached to the [workflow run](https://github.com/roy-pyke/wayeb-event-forecasting/actions/workflows/reproduce.yml).

