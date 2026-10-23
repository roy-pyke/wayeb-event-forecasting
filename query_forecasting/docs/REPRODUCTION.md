# 可复现入口 / Reproduction

仓库根目录运行，Python 3.12。所有原始公开数据、生成特征和大规模随机重复缓存保存在忽略目录；版本库保存协议、代码、紧凑报告。两份模型另有带 SHA256 的快照。完整测试不会读取未开放年份。

```bash
python3.12 -m venv .venv-pattern
.venv-pattern/bin/python -m pip install -r pattern_forecasting/configs/requirements.txt
./query_forecasting/run.sh -m pytest query_forecasting/tests -q
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/prepare.py --datasets air power
./query_forecasting/run.sh query_forecasting/scripts/download_sources.py
```

`prepare.py` 默认仅生成已有训练/校准/开发时期，使用冻结的原始数据校验和及训练时期事件化阈值。这里不运行旧确认数据命令，也不开放剩余年份。已有缓存会校验来源身份。首次作者 CLI 识别核验还需仓库 `setup.sh` 构建固定版本 Wayeb。

从头训练只应在新 clone 或空模型目录进行：

```bash
./query_forecasting/run.sh query_forecasting/scripts/train.py air
./query_forecasting/run.sh query_forecasting/scripts/train.py power
```

在已有冻结模型旁做独立重训并比较，请使用不会覆盖原模型的脚本：

```bash
./query_forecasting/run.sh query_forecasting/scripts/reproduce_sources.py air
./query_forecasting/run.sh query_forecasting/scripts/reproduce_sources.py power
```

本机 PyTorch 2.5.1/CPU 的两次独立重训得到相同文件哈希、相同参数与全部 12 轮损失记录；不承诺跨硬件位级一致。模型归一化只由训练集估计，校准集仅选择训练轮次，没有按新查询重训源模型。

主要开发阶段入口如下；各命令对 `air`、`power` 分别执行。`--limit 2 --repetitions 8` 是实现预检，不能当作完整结果。

```bash
./query_forecasting/run.sh query_forecasting/scripts/balanced_experiment.py air
./query_forecasting/run.sh query_forecasting/scripts/overflow_experiment.py air
./query_forecasting/run.sh query_forecasting/scripts/moment_basis_experiment.py air
./query_forecasting/run.sh query_forecasting/scripts/markov_control_experiment.py air
./query_forecasting/run.sh query_forecasting/scripts/particle_control_experiment.py air
./query_forecasting/run.sh query_forecasting/scripts/summarize_evidence.py
```

实验按起点检查点续跑；输入、模型、源文件或协议哈希改变时，已有目录拒绝继续混用。每个方法都计入真实条件分布调用数；代理模型构造也计入。各方法共享确定的逻辑编译结果，但不跨随机重复缓存神经预测。不同阶段同起点共用精确参考概率；汇总脚本再次检查参考向量一致。

误差衡量的是固定模型内查询积分，不是现实故障预测正确率。原生时钟为空气 1 小时、用电 1 分钟；用电查询起点虽每 5 分钟取样，未来轨迹仍逐分钟演化。无业务事件的原生 tick 记为静默符号，消耗时间但不重复触发 DFA 接受端点。

已完成失败保留在 RESEARCH_LOG；不能通过删除报告或更改冻结源来恢复成功。Air2017/Power2010 在独立确认协议冻结、推送及开发门槛通过前继续禁止访问。
