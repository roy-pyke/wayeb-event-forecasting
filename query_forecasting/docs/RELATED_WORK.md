# 新方向的文献排查 / Literature screening

检索日期：2026-10-22（America/Los_Angeles）。下面是决定是否实施的依据，而不是穷尽性的新颖性证明。检索使用原始论文、作者网页与会议出版页；检索不到相同措辞不构成首创证据。

| 已有工作 | 已有机制与本轮决定 |
|---|---|
| [Boyd et al., NeurIPS 2022, Predictive Querying for Autoregressive Neural Sequence Models](https://ics.uci.edu/~smyth/papers/prob_seq_queries_NeurIPS_2022.pdf) | 受限路径的重要性采样、搜索及二者混合已有直接方法；§4.3 也讨论多个查询共享计算。排除“把神经事件模型接到正则查询”作为独立创新。 |
| [Boyd et al., AISTATS 2023](https://proceedings.mlr.press/v206/boyd23a.html) | 连续时间事件查询、命中时间及 A-before-B 的重要性采样；不能把换成真实时间作为创新。 |
| [Liang et al., ICML 2020, Variable Skipping](https://proceedings.mlr.press/v119/liang20b.html) | 自回归范围查询中的变量跳过，并明确包括正则文本匹配。排除单纯跳过无关符号。 |
| [Re et al., 2026, Estimating Great Expectations with Potentials](https://arxiv.org/abs/2610.11399) | 2026-10-08 初稿、10-21 修订；前缀势函数、无偏加性修正、零方差理想势及与重要性采样组合均已有。排除将马尔可夫代理的 Bellman 残差直接称为新控制变量。 |
| [Randhawa & Juneja, ACM TOMACS 2004](https://randhawa.us/files/tomacs.pdf) | 时序差分控制变量与重要性采样的组合更早已有基础。 |
| [Pettersson & Krumscheid, 2021](https://arxiv.org/abs/2107.01355) | 非光滑问题的自适应分层、分配与贪心细化已有研究。本轮不能宣称发明分层 Monte Carlo 或 Neyman 分配。 |
| [Chopin, Wang & Gerber, 2025](https://arxiv.org/abs/2501.04842) | 用先导样本训练决策树进行自适应分层。新候选必须面对数据驱动分层，不能仅胜过朴素采样。 |
| [Cairoli et al., QPM 2025](https://doi.org/10.1016/j.nahs.2025.101606) | 时序逻辑预测监测与共形保证、布尔组合已有系统方案；排除简单加共形层。 |
| [Innes & Ramamoorthy, IROS 2024](https://www.pure.ed.ac.uk/ws/portalfiles/portal/459482770/InnesRamamoorthyIROS2024AdaptiveSplittingOfReusable.pdf) | 复用时序监控器与稀有事件分裂采样已有先例；监控器辅助采样本身不是新颖性。 |

待检验的差别很窄：由作者自动机的剩余可行输出语言（residual output language）编译**联合查询的确定分支、方差上界与预算分配**，用精确前缀概率构成一个正权、总质量为一的路径分布。它同时给出无偏估计和逐次逻辑一致性。基本分层恒等式和凸性均为经典数学；潜在贡献是这套针对事件模式查询的编译和计算分配机制及其必要性证据。若普通分层或已有查询方法取得同样效果，本候选失败。

未完成的排查：大规模多查询统计模型检查、语义重要性采样与概率程序的 cutset 条件化。即使开发结果为正，在这些最接近方向完成全文对照前，也不能宣布首创。
