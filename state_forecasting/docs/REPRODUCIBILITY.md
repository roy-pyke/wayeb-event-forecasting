# 复现与使用 / Reproducibility and usage

## 文件与入口

从仓库根目录运行：

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

`src/stateforecast/online.py` 的 `StateSidecar` 接收两类输入：

```python
Event(instance="apu", kind="LoadStart", event_time=t, arrival_time=t)
Event(instance="apu", kind="Telemetry", event_time=s, arrival_time=t,
      values=(TP2, TP3, H1, DV_pressure, Reservoirs, Oil_temperature, Motor_current))
```

业务事件推进作者自动机；遥测只更新上下文。`predict(instance, now)` 输出模式状态、30/60/120 秒完成概率、遥测年龄和状态专家权重。收到 `LoadEnd` 或实际经过 horizon 后才更新权重。缺口 `Gap` 使未揭晓标签删失；调用方需要提供可靠的观测覆盖/缺口信息。完整生产系统还需要持久化、流量控制、业务水位线和故障恢复，本原型没有声称具备这些能力。

演示脚本回放保留段前三个完整周期；示例从空业务历史开始，因此示例数值不应当与全历史批量基准逐行等同。

## 源码范围与许可

两个 `upstream/` 子模块均保持原提交。新增内容属于本研究扩展；不把作者论文、作者软件和公开数据合并成一个新许可。使用 Wayeb 仍遵守其原有许可和研究结果公开要求。当前自动机导出仅验证纯事件类型、无窗口 DSFA；不支持通用属性谓词、寄存器或带时间窗模式。
