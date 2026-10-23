# 文献边界与待证实的新颖性

本表记录当前检索发现的直接相关工作。没有检索到完全相同实现不能证明全球首创；方法贡献必须同时通过强基线实验。

| 来源 | 已经解决或提出的部分 | 本项目不能据此声称的新颖性 | 尚可验证的具体差别 |
|---|---|---|---|
| [Wayeb / RTCEF，2025](https://cer.iit.demokritos.gr/publications/papers/2025/debs2025.pdf) | 复杂事件概率预测，运行时模型更新与不中断预测 | 自动机预测、在线更新不是新概念 | 多模式未来结果约束是否可用于有损预测消息的确定性损失界 |
| [Dynamic-DeepHit，2020](https://pubmed.ncbi.nlm.nih.gov/30951460/) 与[作者代码](https://github.com/chl8856/Dynamic-DeepHit) | 时间更新、注意力、删失事件似然与排序 | 注意力 GRU、动态剩余时间分布不是新概念 | 本项目只是共享输入、独立模式头的任务适配基线；不是原论文复现 |
| [Deshpande 等，VLDB 2004](https://web.stanford.edu/class/cs240e/papers/vldb04.pdf) | 利用统计关联选择传感器读数，优化置信质量与通信成本 | 按信息价值选传感器、考虑联合关系都不是新概念 | 当前候选发送已计算的预测分量；使用相对完整预测器的逐结果损失上界，依赖形式可达性而非高斯模型置信度 |
| [Solowjow 与 Trimpe，2020](https://doi.org/10.1016/j.automatica.2020.109009) | 事件触发通信及学习 | 预测误差大时触发不是新概念 | 触发与消息内容由可行未来结果上的 proper-score 增量约束决定 |
| [Predd 等，2009](https://arxiv.org/abs/0710.3183) | 概率一致性与 proper scoring rule 下的不被支配 | 逻辑概率约束、欧氏一致性修正不是新理论 | 本项目统一给所有策略这项能力，再检查损失证书有无独立价值 |
| [Ari 等，2024/2026](https://arxiv.org/abs/2410.08706) | 有双向延迟、信息年龄、包长度的目标导向更新 | 联合优化何时发送与发送多少，不是空白方向 | 当前机制的保证是即时可靠交付条件下逐查询相对损失界；不声称该论文的长期平均最优性或延迟鲁棒性 |
| [Lindemann 等，CDC 2018](https://arxiv.org/abs/2011.12772) | 时间逻辑任务的事件触发反馈控制 | 形式规范结合事件触发不是新概念 | 本项目不控制物理系统，目标是未来模式概率消息的评分损失 |
| [Fani Sani 等，2023](https://link.springer.com/article/10.1007/s10844-022-00775-9) | 预测监测的性能保持事件日志抽样 | 少用数据还能保性能不是独立贡献 | 训练轨迹抽样与运行时概率消息选择需要分开 |
| [Kumar 等，2026](https://onlinelibrary.wiley.com/doi/10.1155/jece/2164804) | 频谱感知中联合交叉熵、Brier 与通信稀疏正则 | 将 Brier 和通信成本放在同一目标中不是新概念 | 经验加权训练正则与无需结果标签的确定性增量证书不同；该差别仍需有实际收益 |
| [AutoMon，SIGMOD 2022，作者项目](https://github.com/hsivan/automon) | 从函数代码自动派生分布式安全监控约束，按精度要求减少通信 | 自动构造确定性通信触发约束不是新概念 | 多节点平均向量的函数监控，与单实体多个未来事件概率的联合损失及消息编码问题不同；不能据此声称通用系统更优 |
| [Poupart 与 Boutilier，NIPS 2004](https://papers.neurips.cc/paper_files/paper/2004/file/81c2f886f91e18fe16d6f4e865877cb6-Paper.pdf)，§4 | 用不变子空间压缩 POMDP 信念状态，保留预测奖励和后续压缩状态所需信息 | 用基、秩和概率结构进行线性无损压缩不是新理论 | 当前候选从有限期限、无拟合概率的事件语言产生预测输出空间；不承担 POMDP 控制或保持转移不变性的任务 |
| [Predictive Representations of State，NIPS 14](https://proceedings.neurips.cc/paper/2001/file/1e4d36177d71bbb3558e43af9577d70e-Paper.pdf) 与 [IJCAI 2021 的明确公式](https://www.ijcai.org/proceedings/2021/0299.pdf) | 用核心未来测试的预测概率表示状态，线性恢复其他测试概率 | “只保留一组独立预测概率”这个抽象思想已有直接先例 | 当前编译针对给定事件语言、状态和有限期限，对所有允许的未来流成立；不学习整个生成过程的 PSR。这个限定差别仍不自动构成足够的论文贡献 |
| [Liu 等，Optimizing Error-Bounded Lossy Compression for Scientific Data with Diverse Constraints](https://www.yuanjianliu.net/files/2022TPDS-preprint.pdf) | 科学数据压缩中保留用户指定的范围、区域与精度约束 | 带约束且带误差界的压缩不是空白方向 | 事件语言派生的概率等式、逐可行结果评分增量、在线选择消息是否发送需要具体区分 |
| [KRAKEN，DEBS 2026，作者机构摘要](https://www.bifold.berlin/impact-transfer/publications/view/publication-detail/kraken-joint-optimization-of-operator-placement-and-communication-for-distributed-stream-processing) | 对分布式流算子位置和 all-push/push-pull 通信联合规划，权衡元组量与延迟 | 联合考虑执行位置与通信不是本工作的独创概念 | 本项目固定执行位置、预测模型和业务流，研究辅助概率消息内容；不能把它当作完成同一预测任务的直接数值基线 |
| [Bansal 等，Competitive Algorithms for Generalized k-Server in Uniform Metrics](https://doi.org/10.1145/3568677) | §3 讨论对阶段仍可行状态均匀抽样，归于标准 uniform MTS 分析 | 阶段交集、随机剩余状态、调和竞争界不是新机制 | 固定码字索引的安全集合是该经典问题的一个实例；必须检查实际评分、退路和字节成本 |
| [Bubeck 与 Rabani，Parametrized Metrical Task Systems](https://arxiv.org/abs/1904.03874) | MSS/subset chasing 及按请求结构分析的竞争结果 | 用在线选择避免当前贪心不是新概念 | 本项目没有建立优于其一般理论的新结构定理 |
| [Bubeck 等，Metrical Service Systems with Transformations](https://arxiv.org/abs/2009.08266) | 允许可行空间上的免费环境变换，更一般的追逐问题 | 免费公共状态变化的在线形式化也有先例 | 当前实现保留固定索引，可化成普通 MSS；不声称解决其广义变换问题 |
| [Seidel 等，Window-based Periodic Event-triggered Consensus](https://people.kth.se/~dimos/pdfs/TCNS_Seidel_23.pdf) | 历史窗口余量触发；PDF 第 7 页明确提醒较不保守的规则不必减少闭环触发次数 | “利用历史”及“点态放松不能保证闭环节省”的一般警示已有直接来源 | 这里给出 Brier/互斥概率的精确有理数反例与任意大比值；尚未确立其单独可发表的新颖性 |

还找到预测式几何监测（prediction-based geometric monitoring）线索：[作者站点 PDF](https://minosng.github.io/Papers/sigmod12.pdf)、[分布式最小二乘模型监测](https://www.cs.utoronto.ca/~mgabel/papers/DILSQ%20-%20KDD%202015%20Camera%20Draft.pdf)、[异构流几何监测](https://www.weizmann.ac.il/math/AmirAbboud/sites/math.AmirAbboud/files/uploads/Geometric%20Monitoring.pdf)。其安全区域与通信阈值思想很相关，不能把“在确定性界内不通信”作为全球首创声明。第一篇全文访问存在工具错误，当前仅作为待深入核对的来源，不能冒称完成逐条理论对照。

候选差别应表述为**把复杂事件的可行未来标签编译为预测消息更新的损失约束，并研究精确/贪心内容选择与成本边界**。目前多个开发实验发现动态自动机相对强静态参照的收益很小；这会削弱贡献，必须写进论文可行性判断，不能用好看的全量上传对照覆盖。

后续坐标编码候选的原创性风险同样明确：线性概率压缩已有直接先例，新的组合必须体现自动机和时间期限派生关系的必要性。`AFFINE_CODEC.md` 给出可核验的命题、算法和反证。即使实验成功，也只能称有证据的候选贡献；本次检索不构成“没有任何类似论文”的证明。

后续码本开发门槛也失败：经典随机阶段策略被同码本历史 minimax 在通信指标上超过。见 `CLOSED_LOOP.md` 和 `RESULTS.md`。因此当前没有把某个已有算法改名后宣布为新机制，也没有把普通码本的压缩收益归因于阶段记忆。
