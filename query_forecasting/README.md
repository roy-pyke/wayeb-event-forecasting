# 复杂事件概率查询 / Complex-event probability queries

本目录研究一个新问题：给定同一个包含遥测信息的自回归事件模型，怎样以较少模型调用同时估计多个模式、多个期限的完成概率，并保持概率的逻辑一致性（coherence）。旧目录的四轮通信假设及负结果保持不变。

当前仍为候选机制的开发检验，尚未完成论文级独立确认。Q1 优先级、Q2 输出支持分组、Q3 调和矩传播和 Q4 超预算分组均未通过全部机制/成本门槛，负结果完整保留。现在检验[转移闭合占用量](docs/Q5_OCCUPANCY.md)及[有限期限商](docs/Q6_FINITE_CLOSURE.md)，并加入同源一阶控制变量和普通离散粒子滤波等强对照。

设计、[文献边界](docs/RELATED_WORK.md)、[逐阶段失败记录](docs/RESEARCH_LOG.md)和各项 `configs/` 协议分别保存，不把泛用平衡抽样、控制变量或转移不变空间称为新数学。原始设计见 [DESIGN](docs/DESIGN.md)，数值汇总见 [evidence-summary.json](reports/evidence-summary.json)，其中明确标出尚未结束的比较。

[可复现入口](docs/REPRODUCTION.md)包含训练、测试、完整实验和断点续跑。两个冻结神经源已独立重训到逐字节相同，并发布了[校验和模型快照](https://github.com/roy-pyke/wayeb-event-forecasting/releases/tag/query-sources-20261022)；空目录下载恢复也已验证。

不把模型内的积分精度称为现实预测准确率；不使用旧确认年份充当新留出测试。空气 2017、用电 2010 仍关闭。
