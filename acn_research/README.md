# ACN 恢复取电的预测价值研究

本目录按 2026-10-23 的应用评审及用户授权继续研究。问题是：在车辆仍连接、持续低电流之后，提前知道恢复取电的时间与幅度，能否改进同信息、同动作约束的反馈控制和模型预测控制（model predictive control, MPC）？

本轮依次核查用户请求与可用时间、运行修正后的作者基线、测量未来信息与可实现预测的决策价值。现象存在、预测准确、控制获益和机制新颖性分别报告。

- `reference/`：用户提供评审包的选定原始证据及 SHA256；128 会话已经用于探索，不能改称独立确认集。
- `configs/`：源码固定版本和实验设定。
- `src/acnresearch/`、`scripts/`、`tests/`：新代码、可复现入口和有效性测试。
- `reports/`：可公开的汇总和验证结果。
- `docs/`：设计、来源、失败记录、结论。
- 仓库根目录 `artifacts/acn/`、`.tools/acn/`：忽略的下载、原始用户请求与依赖；不提交认证信息或逐用户请求。

作者 Wayeb/RTCEF 子模块保持原固定版本。ACN/adacharge 采用独立固定源码与显式补丁；各自许可证分别适用。

最新结论入口：[真实预测与独立场站负结果 R1](docs/LEARNED_RESULTS.md)，[设计与新颖性核查](docs/LEARNED_DESIGN.md)。3874个真实录制，Office训练/时间留出加Caltech和JPL外部验证，学习预测未优于每20分钟探测；720个条件性多车世界中略有损失。25项语义测试通过，当前不足以支撑新颖有效机制的论文主张。

旧阶段：[作者基线与完美信息结果 C2/P2](docs/RESULTS.md)。请求全量审计见 [FULL_OFFICE_AUDIT.md](docs/FULL_OFFICE_AUDIT.md)，设计与失败记录见 [RESEARCH_LOG.md](docs/RESEARCH_LOG.md)。`reports/r1/`为最新真实预测结果；`reports/c2/`和`reports/probing_p2/`保留历史阶段，根`reports/value_*`和`reports/probing/`是更早诊断，不能混用。

## 从仓库根目录复现

需要 Python 3.12（本机 3.12.14）、Git 和网络；版本在 requirements-lock.txt 固定。setup 只修改隔离环境中的安装副本，并校验补丁行为。

```bash
python3.12 acn_research/scripts/setup.py
ACN_PY=.tools/acn/venv/bin/python
$ACN_PY acn_research/scripts/fetch_data.py
$ACN_PY acn_research/scripts/audit_linkage.py
$ACN_PY acn_research/scripts/fetch_office_full.py
$ACN_PY acn_research/scripts/audit_office_full.py
PYTHONPATH=acn_research/src $ACN_PY -m pytest -q acn_research/tests
$ACN_PY acn_research/scripts/validate_native.py
$ACN_PY acn_research/scripts/quantization_probe.py
$ACN_PY acn_research/scripts/run_value.py --revision c2 --phase development
$ACN_PY acn_research/scripts/run_value.py --revision c2 --phase evaluation
$ACN_PY acn_research/scripts/analyze_value.py --revision c2
$ACN_PY acn_research/scripts/feedback_sensitivity.py
$ACN_PY acn_research/scripts/probing_value.py --revision p2 --phase development
$ACN_PY acn_research/scripts/probing_value.py --revision p2 --phase evaluation
$ACN_PY acn_research/scripts/plot_final.py
```

最新R1可在完成setup、fetch_data和fetch_office_full后单独复现；不必重新运行C2/P2长实验：

```bash
ACN_PY=.tools/acn/venv/bin/python
$ACN_PY acn_research/scripts/fetch_independent.py
$ACN_PY acn_research/scripts/build_recovery.py --sites office
$ACN_PY acn_research/scripts/learned_recovery.py --phase development
# 原研究在此提交冻结模型/选择，再执行下面的留出评估。
$ACN_PY acn_research/scripts/build_recovery.py --sites caltech jpl
$ACN_PY acn_research/scripts/learned_recovery.py --phase evaluation
$ACN_PY acn_research/scripts/learned_service.py
$ACN_PY acn_research/scripts/diagnose_recovery.py
$ACN_PY acn_research/scripts/plot_learned.py
PYTHONPATH=acn_research/src $ACN_PY -m pytest -q acn_research/tests
```

模型与逐会话预测在`artifacts/acn/r1/`，无需私密API key。代码与原始公开数据下载足以重新训练；GitHub未包含原始请求、逐会话特征或训练模型。重跑会覆盖同名本地派生产物，若要保留原始运行先复制其目录。日期、模型pickle字节和运行时可能跨环境变化；数值比较以公开聚合结果与固定数据/超参数为准。两个站各1200文件固定抽样，不是全站人口。

在已有本机部署直接使用 `.tools/acn/venv/bin/python`；重新运行 setup 也使用该解释器即可。下载有缓存并逐文件校验，不使用私密 token。原始用户请求、逐用户关联和完整轨迹保存在忽略目录；GitHub 包含代码、协议、来源、补丁和汇总，不含这些原始数据。受镜像/API 可用性影响，下载可能失败，脚本会中止，不静默跳过文件。

结果中的整数能量总量应复现；运行时间、浮点尾数和求解器状态可能依赖平台。C1 的严格比较旧环境需查阅历史提交 `5b599d7`，当前 setup 安装的是 C2 修正版。不能用当前补丁环境重跑 C1 后覆盖历史报告。
