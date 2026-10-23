# 复杂模式预测与有损消息编码研究

这是 `state_forecasting/` 之后的独立研究阶段。旧阶段的冻结实验保持原样。

目标是在复杂模式、同信息强基线和独立领域上检验可证伪的机制。四个候选依次为联合损失证书、精确稀疏刷新、自动机派生的独立概率坐标编码、安全码本阶段选择。均未满足登记的主要优势门槛；完整保留失败和次要发现。**当前未建立新方法论文所需的充分新颖性与强基线优势。**

- [完整结果与证据](docs/RESULTS.md)
- [论文论点审查](docs/PAPER_READINESS.md)
- [英文研究稿：收益边界与负结果](docs/RESEARCH_NOTE.md)
- [设计依据与新颖性核对](docs/DESIGN.md)
- [预先登记的实验协议](configs/PROTOCOL.json)
- [阶段记录与失败诊断](docs/RESEARCH_LOG.md)
- [文献边界](docs/RELATED_WORK.md)
- [概率坐标编译、证明与编码](docs/AFFINE_CODEC.md)
- [闭环反例、经典在线算法与码本失败](docs/CLOSED_LOOP.md)
- [可复现命令与冻结规则](docs/REPRODUCTION.md)
- [配对统计结果](reports/codec-comparisons.json)

业务事件始终完整送达原识别器；实验控制辅助预测上下文或概率消息的传输。通信节省不等于传感器采集或边缘计算节省。

模式族 `nested`、`directional`、`multisignal` 分别包含循环、选择、重叠/反向/联合目标。全部来自作者 Wayeb 的导出自动机，且通过作者 CLI 端点核验。数据是公开空气质量、家庭用电、压缩机传感器流；模式是研究中固定的规则，不是外部标注的故障/事故真值。空气与用电提供不同领域和未来年份；压缩机 2020 数据以前已使用，只作诊断。

三族已完成 36 次作者 CLI 对照、90 份模型、2016 年空气（含六个未见站点）与 2009 年用电确认，以及按周配对置信区间。冻结主坐标编码比较的字节节省仅 0.34%/0.64%，区间包含零。90 模型[公开快照](https://github.com/roy-pyke/wayeb-event-forecasting/releases/tag/pattern-research-20261022)已经下载并在空目录恢复核验。空气 2017 与用电 2010 仍未评估。

只重新生成证据表和图（不训练、不访问新数据）：

```bash
./pattern_forecasting/run.sh pattern_forecasting/scripts/summarize.py
./pattern_forecasting/run.sh pattern_forecasting/scripts/summarize_safe_codebook.py
./pattern_forecasting/run.sh pattern_forecasting/scripts/paper_figures.py
./pattern_forecasting/run.sh pattern_forecasting/scripts/build_evidence_report.py
```
