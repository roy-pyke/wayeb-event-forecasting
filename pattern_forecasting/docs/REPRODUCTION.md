# 复现入口与实验隔离

工作目录为仓库根目录。Python 3.12；作者 Wayeb 的 Java/sbt 部署沿用仓库既有脚本。首次运行：

```bash
./pattern_forecasting/setup.sh
./pattern_forecasting/run.sh -m pytest pattern_forecasting/tests -q
./pattern_forecasting/run.sh pattern_forecasting/scripts/prepare.py
./pattern_forecasting/run.sh pattern_forecasting/scripts/verify_wayeb.py
./pattern_forecasting/run.sh pattern_forecasting/scripts/audit_data.py
./pattern_forecasting/run.sh pattern_forecasting/scripts/train.py
```

三个模式族分别为 `nested`（默认）、`directional`、`multisignal`。后两族设置环境变量后使用相同代码、独立配置、数据缓存、模型与报告目录，禁止交叉加载模型。例如：

```bash
PATTERN_FAMILY=multisignal ./pattern_forecasting/setup.sh
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/prepare.py
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/train.py --profile short
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/refresh.py --dataset air --backbone short-hgb-31-180-s20261022 --epsilon 0.0005 0.002 --full-coherence --strategies whole sparse greedy_delta greedy_loss
```

`--profile short` 的窗口为各数据集的 1、2、3 个原生时间单位；查询频率不变。数据准备文件包含下一次匹配时间与观测覆盖，因而多个窗口共用同一因果特征和事件流，但它们不是独立数据实验。

确认集只有在相应配置目录存在 `FROZEN.json` 时才允许生成。该文件应记录最终代码、模型、数据源、超参数、主要比较与失败解释的冻结；当前开发迭代中尚未创建。不得把旧 2020 MetroPT 数据称为独立确认，也不得在看见确认结果后改主要声明。

原始 UCI 文件只保存于忽略的缓存目录，首次下载及每次复用都核对固定 SHA-256。大模型和中间预测保存在忽略的 `runs/`，仓库保存完整脚本、协议与可审核的数值报告。报告中的按周簇统计保留多站点共享天气的相关性；时间采用数据记录的钟表时间，未擅自推定原始时区。

Python 路径可通过 `WAYEB_PYTHON` 指定。所有主预测器使用同一 20,000 个训练查询及相同缓存年龄增强，共 40,000 个视图；树模型展开风险区间后的训练行数因此更多。Isotonic 校准只使用校准时期，超参数只使用开发时期。注意力 GRU 是公开结构的 PyTorch 任务适配，不是原作者 TensorFlow 实验的精确复现。
