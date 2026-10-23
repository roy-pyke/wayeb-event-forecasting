# 复杂事件概率查询 / Complex-event probability queries

本目录研究一个新问题：给定同一个包含遥测信息的自回归事件模型，怎样以较少模型调用同时估计多个模式、多个期限的完成概率，并保持概率的逻辑一致性（coherence）。旧目录的四轮通信假设及负结果保持不变。

当前为候选机制的开发检验，尚未建立论文新颖性或实证优势。设计、相关工作和反证门槛先于实验登记在 [DESIGN](docs/DESIGN.md)、[RELATED_WORK](docs/RELATED_WORK.md) 和 [PROTOCOL](configs/PROTOCOL.json)。研究记录见 [RESEARCH_LOG](docs/RESEARCH_LOG.md)。

不把模型内的积分精度称为现实预测准确率；不使用旧确认年份充当新留出测试。空气 2017、用电 2010 仍关闭。
