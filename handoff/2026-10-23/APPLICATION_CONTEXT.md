# 修改 prompt 时补充的真实应用背景

日期：2026-10-23（America/Los_Angeles）。以下是实际联网读取到的线索与仍然不知道的事，不是选题排序或后续工作指令。项目代码入口通过 GitHub 连接器读取，应用案例来自基金会、项目社区或开发方。没有安装这些系统、取得客户日志或重启 Wayeb 实验。

## 已知案例与证据范围

| 项目/应用 | 来源中具体做的事 | 现有证据的性质 | 本次未确认的事 |
|---|---|---|---|
| Fledge：UC Davis / Opus One 酒庄 | 温度、湿度、CO2 传感与告警，边缘到云的数据链 | 项目社区具名应用记录 | 开放生产日志、具体提前预测需求 |
| FledgePOWER：RTE / JEA 变电站 | 历史设备数据接入、协议整合、边缘处理 | LF Energy 具名应用报告 | 可公开的运行日志、未来故障标签 |
| EVerest：电动车充电 | 充电会话、授权、事务、协议处理 | 基金会采用报告与可读取的接口代码 | 可训练的生产会话日志、预测需求及收益 |
| ThingsBoard：süc//dacor 机床监测 | 从机床控制程序采集电机电源状态，显示产线状态 | 厂商客户案例；终端汽车供应商未具名 | 案例版本、原始日志、预测用途 |
| Apache StreamPipes：包装机 | 活动布尔信号产生包装事件，累计计数、存储和维护通知 | 官方具体流程教程，未具名生产客户 | 完整实测数据、故障标签、独立部署证据 |
| EdgeX / Technotects：process skid | 泵与传感器监测、接入和动作 | 明确为客户 PoC，含商业组件 | 完整客户应用代码和原始数据开放性 |
| eKuiper + EdgeX / Neuron | 事件流采集、清洗、规则计算、设备反控 | 有代码的官方工程教程；部分使用模拟器 | 该示例的生产部署和预测效果 |

这些来源分别支持代码存在、工程流程或采用背景。它们没有共同证明某个新预测算法必要，也没有证明“有开源软件”就有可训练的公开日志。案例方的效果描述没有在本次独立复验。

## Fledge：酒庄的传感与告警

LF Edge 的[社区用例](https://lf-edge.atlassian.net/wiki/spaces/FLEDGE/pages/15040959/Use%2BCases) 列出 UC Davis 和 Opus One，描述 CO2、温湿度测量和传感器到云的数据处理。[项目页](https://lfedge.org/projects/fledge/) 和 [README.rst](https://github.com/fledge-iot/fledge/blob/develop/README.rst) 提供采集、缓存、处理、转发及插件架构的信息。

本次读到了平台的 [Apache-2.0 LICENSE](https://github.com/fledge-iot/fledge/blob/develop/LICENSE)。酒庄全部软硬件、数据和具体告警配置是否开放，不能由平台许可推断。现有来源说明的是监测与告警；“提前预测未来越界能否帮助行动”目前是研究问题，还不是已证实的用户需求。

## FledgePOWER：电网设备的数据链

LF Energy 的[2024 峰会回顾](https://lfenergy.org/lf-energy-summit-recap-and-video-an-intelligent-edge-for-energy-automation-fledgepower-in-rte-substations-jeas-iiot-61850/) 给出 RTE 和 JEA 的变电站应用，涉及历史设备接入、数据整合和边缘处理。另有 [RTU/SCADA 协议转换设计](https://lf-energy.atlassian.net/wiki/spaces/FLED/pages/13673845/Plugins%2Bconfiguration%2Bdesign)，说明消息和数据模型转换。

[部署仓库](https://github.com/fledge-power/fledgepower-deployment) 提供容器构建与 YAML 配置入口，本次读取的该仓库 LICENSE 为 Apache-2.0。各插件及外部依赖的许可不能一概而论。没有从已读页面取得公开运行日志、故障标签，也没有证据表明这些应用已经提出了我们目前的多模式概率查询问题。

## EVerest：实际充电会话与协议接口

旧地址 `EVerest/everest-core` 现重定向到 [EVerest/EVerest](https://github.com/EVerest/EVerest)。[当前 README](https://github.com/EVerest/EVerest/blob/main/README.md) 说明模块间 MQTT 通信、充电协议和 Apache-2.0。LF Energy 的[审计公告](https://lfenergy.org/lf-energy-advances-ev-charging-security-with-independent-everest-audit/) 报告其行业采用；本次没有独立复核规模。

读到的 [EVSE manager 接口](https://github.com/EVerest/EVerest/blob/main/interfaces/evse_manager.yaml) 涉及授权、暂停/恢复和事务停止等命令，并引用相关类型。[config 目录](https://github.com/EVerest/EVerest/tree/main/config) 有 `config-sil.yaml`、`config-sil-dc.yaml`、`config-sil-ocpp201.yaml` 等软件在环（software-in-the-loop, SIL）配置，未执行。它说明存在明确的流程对象和仿真入口，不等于已获取真实充电会话日志或已证明预测价值。

## ThingsBoard：机床生产监测与版本变化

[süc//dacor 案例](https://thingsboard.io/case-studies/dacor/) 描述在机床控制程序中采集铣削电机电源状态，经 IoT 模块接入产线监测。已知用途是设备状态与停机可视化；没有据此确认未来停机预测、终端客户代码开放或日志下载入口。

本次读取[当前 LICENSE](https://github.com/thingsboard/thingsboard/blob/master/LICENSE) 发现 4.4+ 为 BUSL-1.1。官方 [2026-09-29 公告](https://thingsboard.io/blog/one-thingsboard-source-available/) 区分了 4.4+ 的 source-available 与之前 Community Edition 的 Apache-2.0。当前默认分支、旧 CE、专业分析产品和案例版本是不同对象；目前没有选定用于复现的旧 CE tag。

## StreamPipes：从活动信号到维护计数

官方[使用量维护教程](https://streampipes.apache.org/blog/2025/04/30/usage-based-maintanence/) 给出 `timestamp`、`active` 字段，以 `false→true` 生成包装操作事件，累计计数、存储并触发维护通知。来源没有给出具名工厂、完整原始数据或真实故障标签，因此目前是具体工程教程的证据。

[开源仓库](https://github.com/apache/streampipes) 与 [Compose README](https://github.com/apache/streampipes/blob/dev/installer/compose/README.md) 给出实现和安装入口；本次代码文件头确认为 Apache-2.0，开发分支的安装文件属于快照版本。使用量达到阈值与预测未来故障是不同目标；单纯计数、更新率或现有维护规则是否已足够，是尚未回答的问题。

## EdgeX / eKuiper：现实集成需求与模拟教程

[Technotects 案例](https://www.edgexfoundry.org/use-cases/case-study-3/) 明确是 process skid 的客户 PoC，使用 Edge Central 和商业驱动等组件。它支持现实工业集成的需求背景，不能作为全栈开源生产验证。

[eKuiper 的 EdgeX 教程源码](https://github.com/lf-edge/ekuiper/blob/master/docs/en_US/edgex/edgex_rule_engine_tutorial.md) 展示 source、SQL、sink 和消息总线接入；[Neuron+eKuiper 教程](https://www.emqx.com/zh/blog/industrial-iot-data-collection-cleaning-and-control) 包含模拟器、清洗和反控。本次 eKuiper LICENSE 确认为 Apache-2.0；Neuron、EMQX、Edge Central 和各驱动的版本/许可另有边界。这些教程支持接入流程存在，没有提供可直接借用的生产预测收益。

## 与现有研究的关系

目前这些线索让“真实应用是否需要预测”“现有简单方法哪里不够”“数据与结果标签能否取得”成为更具体的问题。它们没有把 Q5/Q6 自动变成工业需求，也没有指定新的算法路线。原 Wayeb 实验的结果与失败保持原状。

具体代码文件的读取身份记录在 `APPLICATION_SOURCES.json`。其中 Git blob SHA 用于标识读到了哪份文件，不能当作已经固定并执行过整套系统的 commit。
