# Recurrent availability and shared service capacity / 反复可用性与共享服务容量

继 ACN R1 失败后，使用真实 HTTP / PlanetLab 可用性轨迹检验共享重试预算中的机会成本、被动反馈与反复中断。当前阶段是机制验证，不是已确立的新算法或 Flink 生产部署。

- [设计依据与文献排除](docs/DESIGN.md)
- [冻结协议 R2](configs/PROTOCOL_R2.json)

原 ACN 实验与作者代码保持独立。所有阶段按用户要求提交并 push。原始数据、模型和长日志留在忽略的 artifacts/ 下；紧凑统计与复现代码提交到此目录。
