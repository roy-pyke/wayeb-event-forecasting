# Recurrent availability and shared service capacity / 反复可用性与共享服务容量

继 ACN R1 失败后，使用真实 HTTP / PlanetLab 可用性轨迹检验共享重试预算中的机会成本、被动反馈与反复中断。当前阶段是机制验证，不是已确立的新算法或 Flink 生产部署。

- [设计依据与文献排除](docs/DESIGN.md)
- [冻结协议 R2](configs/PROTOCOL_R2.json)
- [本轮完整结果与失败原因](docs/RESULTS.md)
- [结构性反例与容量价格上界](docs/STRUCTURAL_RESULTS.md)
- [数据与Flink源码审计](docs/SOURCE_AUDIT.md)
- [阶段修正记录](docs/RESEARCH_LOG.md)
- [复现步骤](docs/REPRODUCIBILITY.md)

最新独立企业PC实验：489个有效回放组、26时间块、327组真实UP→DOWN→UP；主容量K=2的联合两步调度比冻结的同信息可加对照提高加权完成价值1.408%，比去掉前瞻观测更新的版本提高1.173%，按时间块聚类的区间均为正。网站域的观测贡献没有通过，PlanetLab样本缺乏复发。**标准Bellman前瞻不算新算法，当前仍未满足论文新颖性与现代生产验证要求。**

```bash
./recurrent_research/reproduce.sh
```

验证记录覆盖15个语义测试和24,936条回放的守恒/容量检查。原始轨迹是真实数据，请求工作量/价值/截止时间是明示合成输入；没有部署Flink运行时。

原 ACN 实验与作者代码保持独立。所有阶段按用户要求提交并 push。原始数据、模型和长日志留在忽略的 artifacts/ 下；紧凑统计与复现代码提交到此目录。
