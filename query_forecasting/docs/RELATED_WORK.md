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

## Q2 后的近邻全文审计

| 工作与可核查位置 | 对本项目的约束 |
|---|---|
| [Boyd 作者实现 `sample.py`](https://github.com/ajboyd2/prob_seq_queries/blob/main/seq_queries/sample.py)，`beam_search_is_hybrid`、`beam_search_lower_bound`、`tree_is_estimate_rnn`；论文 §4.2–4.3 | 搜索已知质量加残余重要性采样、缓存前缀及多查询复用都不是本项目独创。本项目新增同前沿、多查询平衡混合适配器；它没有复现作者 tail-splitting 搜索策略，不能冒称作者软件完整复现。 |
| [STMC，CAV 2020，§2 Algorithm 1](https://lagrange.mechse.illinois.edu/pubs/RoWaWeDuVi2020/RoWaWeDuVi2020.pdf) | 在随机种子空间跨转移步分层，支持一般可模拟系统。当前 LHS 是其思想的特例适配，不代表整个 PRISM 工具的性能。 |
| [Hansen 等，TACAS 2015，作者全文](https://chaki.bitbucket.io/publications/TACAS-2015.pdf) | 用 SMT 构造事件输入区域的抽象指示函数，再进行重要性采样。已核对全文；“语义指导采样”这一宽泛表述不成立为新贡献。 |
| [Borges 等，PLDI 2014](https://ntrs.nasa.gov/api/citations/20150004088/downloads/20150004088.pdf)；[FSE 2015](https://cs.unibg.it/esecfse_proceedings/fse15/p866-borges.pdf) | 程序路径条件分解、约束区域分层、按误差影响重分配计算都有早期先例。 |
| [Vilnis 等，ICML 2023，Arithmetic Sampling](https://arxiv.org/abs/2210.15458)；[Sato，2026，DAST](https://arxiv.org/abs/2609.33038) | 算术编码低差异序列及语义重排都已有，不能把前缀排序本身称为创新。 |
| [Liu 等，2026-10-13，Weighted Ensemble Sampling for Rare-Event Estimation in Language Models](https://arxiv.org/abs/2610.19202) | 动态复制、合并神经前缀且始终用原始模型采样已有直接近邻。否决单纯“将静态分组改成动态粒子分组”的新颖性主张。 |
| [Deville & Tillé，2004，Cube method](https://libra.unine.ch/entities/publication/f0a9a172-55e3-4763-b37c-f004ad27891b)；[Fast Compression of MCMC Output，2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8393937/) | 保持辅助变量矩的随机抽样/压缩已有成熟基础。任何后续正权控制量方案必须明确承认这一来源。 |

Q2 判断：完整联合输出集合的必要性已被更近的监控状态和边际支持集消融否定。文献差别加泛用采样优势不够支撑当前论文主张。


## Q3–Q5 的范围收缩

[Poupart 与 Boutilier，NeurIPS 2002，§2.3、§3.1–3.2](https://proceedings.neurips.cc/paper_files/paper/2002/file/14ea0d5b0cf49525d1866cb1e95ada5d-Paper.pdf) 已给出保持奖励的转移不变子空间、Krylov 构造和 self-sufficient marginal families。故“保持边缘量便能精确预测未来”“最小转移闭合空间”不能作为本项目新定理。当前占用量闭合证明是其有限事件查询场景下的直接应用。该文研究信念压缩；本候选另外要求对任意非马尔可夫神经源保留完整历史、正质量、无偏和逐次联合路径一致性，这一具体组合是否有足够新颖性尚待审查。

[Poupart、Ortiz 与 Boutilier，UAI 2001](https://arxiv.org/pdf/1301.2305) 已有价值导向粒子采样及根据决策误差自适应样本量。再次排除“针对下游任务分配采样预算”的宽泛创新措辞。

[MPCR，JCP 2020，§2.2](https://arxiv.org/html/1702.05198v3) 先分箱、再以约束优化保存物理矩。[Factored Particles，UAI 2002](https://arxiv.org/pdf/1301.0590) 将投影粒子重新组合并明确承认该近似的偏差。这些都是必要对照，而非因为应用领域不同就可以忽略。

Q5 同时加入时间变化的一阶马尔可夫代理：在确定的贪心代表前缀上查询所有可能末符号，每个 8 步查询预先用 36 个真实源调用，全部计入预算。它支持已有加性控制变量/LHS 和正权调和矩传播。它们是更强的常规对照，不将该代理构造另包装为新贡献。
