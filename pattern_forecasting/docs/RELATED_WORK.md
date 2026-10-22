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

还找到预测式几何监测（prediction-based geometric monitoring）线索：[作者站点 PDF](https://minosng.github.io/Papers/sigmod12.pdf)、[分布式最小二乘模型监测](https://www.cs.utoronto.ca/~mgabel/papers/DILSQ%20-%20KDD%202015%20Camera%20Draft.pdf)、[异构流几何监测](https://www.weizmann.ac.il/math/AmirAbboud/sites/math.AmirAbboud/files/uploads/Geometric%20Monitoring.pdf)。其安全区域与通信阈值思想很相关，不能把“在确定性界内不通信”作为全球首创声明。第一篇全文访问存在工具错误，当前仅作为待深入核对的来源，不能冒称完成逐条理论对照。

候选差别应表述为**把复杂事件的可行未来标签编译为预测消息更新的损失约束，并研究精确/贪心内容选择与成本边界**。目前多个开发实验发现动态自动机相对强静态参照的收益很小；这会削弱贡献，必须写进论文可行性判断，不能用好看的全量上传对照覆盖。
