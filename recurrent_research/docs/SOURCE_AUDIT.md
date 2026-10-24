# 数据与开源实现审计

R2 数据获取在协议提交 d195cc7 之后。压缩包4,632,954字节，SHA-256 `043a7d81c0b98de1a093d7aa9fbe57527924eb4bb013d7d39cbd313683ce46e0`；单文件校验和见 reports/r2/sources.json。fetch.py 只按固定文件名读取归档成员，检查散列，不执行其中代码，不自动替换输入。

## 数据资格

网站129节点、47,843段可用区间；PlanetLab669节点、28,705段。原始提供方分别为 Bakkaloglu, Wylie, Wang, Ganger (CMU-CS-02-129, 2002) 与 Stribling PlanetLab All Pairs Ping (2004–2005)，统一格式由 Brighten Godfrey 整理。来源自带 availability.bib 保存在 artifacts/recurrent/r2/。不把集合作者当原始测量作者，也不替原始数据加自定许可。代码只分发获取方式、哈希与聚合统计。

统一格式损失了探测延迟与每批失败比例。网站是单观测点的HTTP可达性，PlanetLab是多观测点多数ping成功；因此二者是不同测量机制，不等同现代API服务质量。PL原始日志含系统升级/观测异常，不使用经未来总体统计清洗的版本。

首个上线之前、最后记录结束之后均作为未知。保守规则造成明显样本损失：网站测试预选188窗口中132完整可用，PlanetLab测试316中仅28完整可用；其余分别56/288窗口包含初始未知。未换样本来凑显著性。独立域的有效样本量很小，应把置信区间、覆盖率和条件性选择一起看，不能宣称覆盖全部669节点。

## 模型资格

仅网站前60%时间的UP/DOWN区间曝光量（exposure）拟合连续时间二态马尔可夫模型（CTMC），半事件平滑。UP→DOWN约2.1785e-5/秒，DOWN→UP约2.0717e-4/秒；转换到600秒得到 p01=0.11614、p11=0.98779，900秒为0.16850、0.98228。模型明确允许多次反转，不把上线设成吸收态。参数与分割点保存在 model.json。该简单模型是同信息控制对照的共同输入，不先假定其充分表达可用期长度或共因故障。

## Flink源码对应

读取 Apache Flink release-2.2.0，tag对象 `0cc95fcc145eddcfc87fc1b4ddf96ddd0f2ee15f` 指向 commit `5a336892424a9458653ead89610bf60d771ab8d7`。

固定源码：[AsyncWaitOperator.java](https://github.com/apache/flink/blob/5a336892424a9458653ead89610bf60d771ab8d7/flink-streaming-java/src/main/java/org/apache/flink/streaming/api/operators/async/AsyncWaitOperator.java)。第100–101行 capacity 是 stream element queue 的容量；191/194行创建有序/无序队列；256行先将输入加入队列；541行附近 processRetry 满足条件时注册延迟定时器，只有最终成功/失败路径才完成结果。

**关键区别**：Flink capacity 是未完成逻辑操作/记录的上限，不是简单的每秒网络请求配额。R2 分别限制总缓冲记录与每槽尝试，不能把模拟的K直接称作Flink capacity，不能据此声称修改Flink就会得到相同收益。源码阅读验证了应用动机，不构成对生产系统的性能实验。
