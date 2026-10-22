# 复现说明 / Reproducibility

## 1. Get the exact sources and run

```bash
git clone --recurse-submodules https://github.com/roy-pyke/wayeb-event-forecasting.git
cd wayeb-event-forecasting
./reproduce.sh
```

The complete command builds both author engines, runs three author tests, runs the FMM/PST demo, installs RTCEF's isolated Python environment and runs the bounded Kafka integration. Use `./reproduce.sh --core` for just the original forecasting line. No Docker daemon is needed.

Prerequisites are Git, curl, a **JDK 11** and **CPython 3.12** (the core-only runner can use another Python 3 version). macOS automatically selects JDK 11 with `java_home`; on other systems use `WAYEB_JAVA_HOME=/path/to/jdk-11`. Set `WAYEB_PYTHON=/path/to/python3.12` if Python 3.12 is not the default. The recorded local RTCEF run uses CPython 3.12.7 on Apple Silicon; runtime versions are retained in its report.

Run scripts from any directory; they locate this repository themselves. The `wayeb` CLI preserves the caller's working directory so user-supplied relative input/output paths work normally.

## 2. What is fixed

| Item | Record |
| --- | --- |
| Author source revisions（作者源码版本） | Git submodule gitlinks and `SOURCE.json`; `scripts/check_sources.py` rejects changed commits or tracked source edits |
| Compiler and packaging（编译与打包） | Original Scala 2.12.10; sbt 1.9.9; assembly 2.2.0; JDK 11; `toolchain.json` |
| Dependencies（依赖） | Original author Java/Scala library versions in `build/build.sbt`; exact direct and transitive Python versions in `configs/requirements-rtcef.lock.txt` |
| Download integrity（下载完整性） | SHA-256 of sbt launcher; SHA-512 of Kafka archive, both verified before use |
| Data generation（数据生成） | Fixed seeds and an explicit generator; parameters and input SHA-256 hashes saved per run |
| Model settings（模型设置） | Core `configs/demo.json`; generated HOCON/pattern/configuration files; RTCEF generated `rtcef.ini` |
| Outputs（输出） | Per-run logs, commands, models and JSON report under ignored `runs/`; compact public evidence under `reports/` |

Full model files and timestamps need not have identical bytes across platforms/JVMs. Core validation compares input hashes and numerical forecast metrics, excluding runtime and serialization details. The recorded repeated core runs agreed within absolute tolerance `1e-12`.

## 3. Core data and checks

The core demo uses two independent streams sampled from an explicit second-order categorical source over `A/B/C`. It uses different seeds for the 6,000-event training stream and 2,000-event test stream. The pattern is `A · (B | C)` with order 2, a future horizon of 20 event steps, and confidence threshold 0.6. The binary forecast window has 2 steps; interval maximum spread is 10.

The runner checks an independent literal-pattern match count, nonempty learned models, finite numeric statistics and nonempty forecasts. Its JSON report retains input hashes, actual commands and both full-order Markov（全阶马尔可夫）and variable-order PST（变阶预测后缀树）statistics. The three selected author tests also exercise interval search, PST operations and register-automaton language equivalence.

Forecast statistics are produced by the author's implementation. FMM and PST have different warm-up behaviour, so this demonstration does not establish comparative model superiority. A future event step is not an elapsed-time unit. Precision guarantees in the theory are conditional on modelling assumptions; they are not a universal empirical accuracy guarantee.

## 4. RTCEF service check

```bash
./setup_rtcef.sh
./run_rtcef.sh
```

The bounded run starts its own single-node Kafka broker and the authors' five services: engine（预测引擎）, observer（性能观察器）, collector（数据收集器）, optimiser/controller（优化控制器）, and model factory（模型工厂）. Two Py4J gateways connect the Python services to RTCEF's embedded Wayeb engine. It uses loopback ports 9092, 9093, 25333–25336, and refuses to start if any is already occupied.

It first trains on 1,000 synthetic maritime-shaped records and evaluates on a separate 400-record stream. Another seeded stream exercises the distributed service path. A separate `controlled_scores` topic injects an explicit high-to-low score sequence to trigger retraining and Bayesian optimisation, without presenting those injected values as measured forecasting accuracy. The run checks new model publications and engine score reports carrying the new model versions. This tests control flow, model exchange and forward progress.

The replay advances in fixed chunks and waits for specific completed collector dataset versions (3 before retraining, 8 before optimisation). The selected data windows are copied and hashed before the next chunk. This prevents service scheduling from silently changing the adaptation training dataset.

All started processes are owned by the run and stopped in a `finally` block on completion or error. `Ctrl-C` also enters this cleanup path. Kafka data, topic messages, logs, models and the complete generated configuration stay in that run's directory for inspection.

## 5. Compatibility changes and limits

- **Build overlay（构建适配）:** the authors' old sbt plugins and repository endpoints are replaced by a small pinned build outside both submodules. Forecasting source and Scala version remain unchanged. The RTCEF engine is a distinct embedded version; its serialized models must not be mixed with the standalone Wayeb 0.6 models.
- **PST CLI（命令行参数）:** the standalone author's CLI parses `pMin`, `alpha`, `gammaMin` and `r` as integers, although their model values are fractional. The demo supplies these values through the author's HOCON configuration mechanism via `WAYEB_CONFIG_FILE`.
- **Python environment（Python 环境）:** the author requests Python 3.9/NumPy 1.19.5, which does not provide the needed modern CPython/Apple Silicon wheels. This deployment uses an isolated, pinned CPython 3.12 compatibility environment with NumPy 1.26.4. Validation is evidence for this environment, not a claim of exact historic environment reproduction.
- **Kafka polling（消息轮询）:** `scripts/rtcef_service.py` changes the default consumer poll wait to 50 ms before executing the original service entry point. This transport adapter avoids the legacy busy-poll behaviour; service decisions and message payloads remain the authors' code. Both submodules remain unchanged.
- **Kafka client（Kafka 客户端）:** version 2.1.5 is pinned, matching the release period of RTCEF v1.0.0. In the inspected 2.2.15 client, `position()` could spin while its assigned consumer's fetch position was uninitialised, stalling the collector. The final pinned environment passed the complete integration check.
- **Evaluation boundary（评估边界）:** the author's factory currently trains and evaluates optimisation candidates on the same assembled dataset; its separate train/test assembly is commented out. This is retained and explicitly recorded. The separate 400-record held-out check does not repair or validate that optimisation methodology.
- **Scientific scope（科学结论范围）:** these are synthetic deployment checks. They do not reproduce the published maritime/fraud datasets, paper throughput, optimisation gains or the lossless-adaptation theorem. The 2026 Altair AI Studio integration is catalogued as a systems extension, not installed by this project.

