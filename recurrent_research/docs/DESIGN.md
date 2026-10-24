# 从恢复时间到共享重试容量：设计与证据边界

2026-10-23；R2 协议在下载新轨迹前冻结。此目录独立于旧 ACN 研究，保留其全部失败记录。这里记录可审查的设计依据、备选方案和结论，不把探索过程包装成已证明的新颖性。

## 失败怎样改变问题

R1 的失败不只来自预测器：局部探测 DP 在已无恢复的世界中仍挤占活跃车辆额度，导致少交付0.104 kWh的可复现反例；46次持续恢复中25次在随后至多15分钟内再次中断。于是“预测一次恢复时间，再永久恢复额度”的目标不合适。历史电流又取决于旧 pilot，不能直接提供新控制下反复恢复的反事实能力。

本轮把状态改为反复变化的可达性（recurrent availability），把动作改为竞争同一预算的实际请求（productive attempts），把反馈改为各策略自己的请求响应。每次失败和成功都更新状态信念（belief）；不会免费获得其余目的地的实时状态。

## 真实应用与数据选择

[Apache Flink Async I/O](https://nightlies.apache.org/flink/flink-docs-release-2.3/docs/dev/datastream/operators/asyncio/) 提供事件流异步查询、固定/指数延迟重试、容量上限、背压与检查点。其文档明确指出重试会增加队列容量需求，并讨论有序输出的队首阻塞。这使“等待与重试挤占别的服务机会”成为真实系统问题。R2 只实现可检查的请求调度模型；不冒充 Flink 内核实现、真实吞吐基准或 exactly-once 集成验证。

[Envoy health checking](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/health_checking) 与 [outlier detection](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/outlier) 已把主动健康检查和请求结果提供的被动反馈结合。不能刻意删掉基线能得到的请求响应来制造预测收益。若只读业务请求与纯探测有相同代价、相同健康观测，且成功有非负收益，纯探测可逐步替换为业务请求而不减少可用信息；因此不另建“预测通知”特权通道。该支配关系（dominance）是简单模型事实，不是新理论。

数据采用 [Godfrey Repository of Availability Traces](https://pbg.cs.illinois.edu/availability/)，只选预先指定的 web_sites.avt 与原始 pl-app.avt，不按结果挑节点。前者来自 CMU 对129个网站的HTTP检查，后者来自 PlanetLab 多节点ping。它们提供真实的反复可用/不可用事件，但数据年代久、分辨率低，且网络可达不等于应用吞吐。原始研究与统一格式的测量局限见[数据说明](https://pbg.cs.illinois.edu/availability/readme.pdf)。请求负载、价值和截止时间全部是明示的合成输入，不能宣称真实业务收益。

未选择的新数据也记录理由：

- [Cloud Uptime Archive](https://arxiv.org/abs/2504.09476) 的公开轨迹来自运营方/用户报告，severity 是解释性构造；不是同一客户端每次请求成功的完整标签。可作外部故障描述，不能悄悄当二元请求真值。
- [Google cluster-data](https://github.com/google/cluster-data/blob/master/ClusterData2011_2.md) 是真实 Borg 事件；但机器加入/移除本身是调度器事件，不能为制造探测问题而隐去生产调度器已有的信息。REMOVE 也不自动等于硬件故障。
- ACN 保留为失败与因果可辨识性审计，不拿相同 R1 测试集继续选参数。

## 新颖性排除表

|一手来源|已经做过什么|本轮必须避免的误认|
|---|---|---|
|[Johnston et al. 2017](https://www.mit.edu/~modiano/papers/CV_J_95.pdf)|隐藏ON/OFF状态与自适应信道探测|反复恢复+按历史探测并不新|
|[Karaca et al. 2019](https://arxiv.org/abs/1911.03632)|预测、不确定性、探测反馈开销与调度|加预测器或影子价格不自动新|
|[Yu, Xu, Tong](https://arxiv.org/abs/1610.00399)|随机工作量/截止时间/处理代价/共享容量的 restless bandit|deadline+容量+指数策略已有直接先例|
|[Ryzhov & Powell 2012](https://epubs.siam.org/doi/10.1137/12086279X)|通过一系列LP计算信息的知识梯度，含网络流实验|重解优化问题衡量观测价值不是新概念|
|[Singla 2018](https://arxiv.org/abs/1711.00405)|组合优化中的有价信息、受限/批量探测|非可加探测价值、组合约束本身不能作为首创|
|[Xu et al. 2021](https://arxiv.org/abs/2108.03297)|联合AP探测/选择，contextual bandit与MDP|联合选择与观测的泛化描述不够|
|[Cohen et al. 2014](https://arxiv.org/abs/1302.0792)|探测开销与检测延迟的优化和近似保证|减少探测同时及时检测是既有问题|

检索日期2026-10-23；对摘要与官方文档核实的内容不夸大成全文定理复现。没有搜索到同名方案不是新颖性证明。

## 本轮可证伪的机制问题

唯一值得先检验的区别是：**单目的地收益/信息价值相加，会不会因下一时刻仍共享容量而作出错误选择？**

给定信念向量 b、可见队列 q、容量 K，对选中的目的地集合 A，计算

`Q2(A) = sum(i in A) value(head_i)*b_i + E[ topK_i(value(next_head_i)*b'_i) | A ]`。

期望枚举 A 的可见响应。成功删除已完成队首；失败保留；过期记录删除；仅被尝试的目的地按响应更新信念，再做允许 UP→DOWN 和 DOWN→UP 的时间传播。未来未到达的请求不输入控制器。对照 independent_two_step 对每个目的地独立计算两步动作差再排序，故两者拥有相同数据、预测器与时域，只差共享的第二步分配。

这直接计算被挤占服务的机会成本（opportunity cost），消除R1将失败探测数当统一局部代价的错误。它仍是标准两步POMDP/Bellman前瞻，不命名成新算法。先用它作为**机制可行性上限探针**：若连这个差别在同信息强基线上也没有稳定价值，就不应继续优化其实现或声称论文贡献。若有价值，还须找出相对上述文献可区分的结构、算法或保证。

## 公平性、删失与停止条件

所有控制器共享12个记录的总缓冲上限、相同输入/到期规则、每槽最多K个请求、同一训练模型和自己的历史响应。当前状态 oracle 明确使用额外信息，仅作诊断。固定/指数退避允许未失败目的地照常请求，不故意变弱。

节点首个上线之前和最后可见结束之后不能认定宕机。窗口选择只要求开始前已见到节点；碰到观测终止则共同截断该窗口，保留原窗口与删失计数。真实样本分辨率以内的故障不插值成高精度真值。相同时间窗口构成配对比较单位；置信区间仍只对应这些历史轨迹和合成负载，不能外推成现代生产集群人口结论。

主域按时间60/20/20分割；独立域不用来选模型或策略。先从主域开发集选最强普通因果基线，再冻结测试。性能门槛与新颖性门槛分开记录；即便两者之一通过也不等于论文可发表。
