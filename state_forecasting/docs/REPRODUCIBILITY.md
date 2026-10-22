# 复现与使用 / Reproducibility and usage

## 最终 2022 确认实验

```bash
./state_forecasting/reproduce_2022.sh
```

这是最终架构入口。第一次下载 [Zenodo 6854240](https://zenodo.org/records/6854240) 的约 1.6 GB 原始 CSV，检查作者 MD5 `83c713c0f8a6c2f24418cca999b2a8eb`；本次文件 SHA256 为 `3fd0788c1b8fb7753ac0a2047f487c87f59b8b36af2f5553e4990354ed86d168`。原生观测间隔中位数 1 秒，查询仍至少相隔 20 秒。确认区间、预热和全部参数记录在 `CONFIRMATION_2022.json`，源码哈希在 `FROZEN_2022.json`。

已有环境和数据时可以只运行确认或演示：

```bash
./state_forecasting/run.sh state_forecasting/scripts/confirm_2022.py --output runs/my-2022
./state_forecasting/run.sh state_forecasting/scripts/verify_2022.py
./state_forecasting/run.sh state_forecasting/scripts/verify_serving.py --run runs/my-2022
./state_forecasting/run.sh state_forecasting/scripts/stress_fast.py --run runs/my-2022
./state_forecasting/run.sh state_forecasting/scripts/demo_fast.py --run runs/my-2022
```

输出目录包含每日三个模型、原始/校准概率、最终预测、权重轨迹、训练截止时间审计和 `confirmation.json`。最终线上入口 `FastStateSidecar` 在内存中维护快速计数、组合权重和未揭晓查询；没有使用离线的最终周期时长作为在线输入。

## 文件与入口

旧 2020 冻结实验从仓库根目录运行：

```bash
./state_forecasting/reproduce.sh
```

需要 CPython 3.12、JDK 11、Git、curl 和网络。自动创建独立 `.venv-state`，按完整锁文件安装依赖，编译作者 Wayeb 及单独的导出适配器，下载 UCI MetroPT-3，执行因果测试、作者匹配差分测试、合成对照、冻结保留实验和遥测压力测试。原始文件、模型和长日志位于仓库根目录的 `.cache/` 与 `runs/`，不提交到 Git。第一次需要下载约 208 MiB 的数据包以及构建依赖。

指定输出目录（必须尚不存在）：

```bash
./state_forecasting/reproduce.sh runs/my-reproduction
```

分步运行：

```bash
./state_forecasting/setup.sh
./state_forecasting/run.sh -m unittest discover -s state_forecasting/tests -v
./state_forecasting/run.sh -c 'import json; from stateforecast.data import prepare,PACKAGE; prepare(json.loads((PACKAGE/"configs/PROTOCOL.json").read_text()))'
./state_forecasting/run.sh state_forecasting/scripts/verify_wayeb.py
./state_forecasting/run.sh state_forecasting/scripts/controls.py
./state_forecasting/run.sh state_forecasting/scripts/final_holdout.py --output runs/my-final
./state_forecasting/run.sh state_forecasting/scripts/stress.py --run runs/my-final
./state_forecasting/run.sh state_forecasting/scripts/demo.py --run runs/my-final
./state_forecasting/run.sh state_forecasting/scripts/plot_results.py
```

开发失败实验可以独立重现：

```bash
./state_forecasting/run.sh -m stateforecast.experiment --output runs/my-static
./state_forecasting/run.sh -m stateforecast.rolling --output runs/my-rolling
./state_forecasting/run.sh state_forecasting/scripts/evaluate_mixture.py --run runs/my-rolling --output runs/my-mixture
```

`run.sh` 固定 OpenMP 为 2 线程、BLAS 为 1 线程。依赖版本、随机数种子、原始压缩包 SHA256、协议、核心源码与冻结评估脚本哈希均有记录。最终运行检查冻结哈希，不允许悄悄修改模型后仍沿用同一个冻结声明。重现结果会更新 `reports/*.json`，平台与计时差异可以出现在报告里；确定性输入和预测应独立比较。

跨操作系统不声称逐位一致。2020 的 macOS 与 Linux 复现原始 ZIP、样本数、实例数一致，但派生数组哈希不同，平均 Brier 最大差约 0.000565。2022 的原始数据、样本数和识别端点也一致，三个最终方法的平均 Brier 差均小于 0.000005，Linux 相对改善约 34.60%。逐条预测有差异，尚未把差异定位到一个单独原因，不能把相近结果写成哈希完全相同。原始 Linux 推理 p95 为 38.87 ms，超过门槛；其报告的 `quality_pass=false` 原样保留。

2022 同机复跑已完成：从每日模型训练重新执行，原始/校准概率、最终 F0/F1/F2 和组合权重逐元素相同，最大绝对差为 0。两次 p95 分别约 10.88 和 19.23 ms，均满足本机门槛；计时受负载影响。原始发布报告保留首次结果，重复结果与比较保存在 [reproducibility.json](../reports/reproducibility.json)。

最终服务入口使用 `BatchedSurvival` 包装冻结模型，将 9 个危险率区间合成一次树模型调用；其源码单独记录哈希。`verify_serving.py` 检查全部日模型在整个确认集上的原始与校准概率逐元素完全相同，再进行同进程性能比较。本机 p95 从 12.55 ms 降至 1.96 ms。该适配器没有重新训练模型，原冻结代码和原 Linux 超时报告保留。一键入口运行这项检查，若等价性或验收条件失败则以非零状态退出。

## 数据来源与标签

数据：[MetroPT-3](https://archive.ics.uci.edu/dataset/791/metropt+3+dataset)，Davari, Veloso, Ribeiro, Gama，DOI 10.24432/C5VW3R，CC BY 4.0。原始 ZIP SHA256：

```text
aab991a970e58210de853bb8078ce0e63abb4d9412fdc5c79792dae3d8e1721a
```

实际文件包含 1,516,948 行，时间间隔中位数 10 秒，331 个超过 60 秒的缺口。开始和结束事件从 `COMP` 的相邻可观察跃迁派生。缺口中断模式实例，最后可观察时刻之后的标签未知。三个跨时间划分边界的实例被排除。模式语义来自作者编译器生成的 `pattern.sre` 自动机。

数据分段：2 月训练；3 月上半月选择离散粒度；3 月下半月初始校准；4 月开发迭代；5–8 月冻结保留段。新架构每日按已固定的 14 天窗口滚动，最近 2 天仅用于校准。每日更新阶段使用过去已到达的查询和已知结局，对仍运行实例在更新截止时删失。校准段只包含在该段开始的实例，以避免训练/校准实例交叠；若因此为空，跳过校准并记录。

评估单位为真实秒数。每个实例内的查询权重和为 1，再按已知 horizon 标签计算 Brier。报告同时给出逐查询 Brier，避免隐瞒长周期与短周期的权重影响。95% 区间按自然日整块重采样 1,000 次；合成机制对照改按独立生成的实例重采样，因为模拟日历不代表相关结构。

这份数据只记录传感器采样时间，没有网络到达时间。默认假设采样即到达；延迟/丢包是另行注入的压力场景，不是数据中已知的通信故障。`COMP` 波动产生的短周期仍按原观测模式计分，未为了改善结果删除。

## 在线接口

最终入口 `src/stateforecast/online_fast.py` 的 `FastStateSidecar` 接收两类输入；`online.py` 的 `StateSidecar` 是早期实现，也负责被最终入口复用的匹配状态和特征维护。

```python
from stateforecast.online_fast import FastStateSidecar
from stateforecast.serving import BatchedSurvival
from stateforecast.stream import Event

# table 为 configs/dfa.json；两个模型从同一日的 M0/M2.joblib 加载。
sidecar = FastStateSidecar(table, context_model=BatchedSurvival(m2),
                          baseline=BatchedSurvival(m0))
```

事件形式：

```python
Event(instance="apu", kind="LoadStart", event_time=t, arrival_time=t)
Event(instance="apu", kind="Telemetry", event_time=s, arrival_time=t,
      values=(TP2, TP3, H1, DV_pressure, Reservoirs, Oil_temperature, Motor_current))
```

业务事件通过 `accept(event)` 推进作者自动机；遥测只更新上下文。`predict(instance, now)` 输出模式状态、30/60/120 秒完成概率、五个专家的当前权重及 `full_context_pool` / `business_fallback` 来源。收到 `LoadEnd` 或实际经过 horizon 后才更新权重。缺口 `Gap` 使未揭晓标签删失；调用方需要提供可靠的观测覆盖/缺口信息。完整生产系统还需要持久化、流量控制、业务水位线和故障恢复，本原型没有声称具备这些能力。

演示脚本回放保留段前三个完整周期；示例从空业务历史开始，因此示例数值不应当与全历史批量基准逐行等同。

## 源码范围与许可

两个 `upstream/` 子模块均保持原提交。新增内容属于本研究扩展；不把作者论文、作者软件和公开数据合并成一个新许可。使用 Wayeb 仍遵守其原有许可和研究结果公开要求。当前自动机导出仅验证纯事件类型、无窗口 DSFA；不支持通用属性谓词、寄存器或带时间窗模式。
