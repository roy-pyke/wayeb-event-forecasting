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

坐标编译与编码入口：

```bash
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/compile_codec.py
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/affine_codec.py --dataset air --backbone short-gru-32-0.01-s20261022 --representations all zero basis
./pattern_forecasting/run.sh pattern_forecasting/scripts/summarize.py
```

只有在完成开发和种子复验、提交当前源代码之后，才运行 `freeze_confirmation.py`。多通道族使用 `--replicate-seeds`，其余诊断族不加该参数。冻结记录源代码、训练模型、阈值及开发清单的 SHA；`prepare.py --confirmation`、`confirmation.py` 和确认编码实验都会核对冻结身份。生成 `FROZEN.json` 后先提交并 push，再运行确认准备和评分；不得覆盖已有冻结文件。

```bash
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/train.py --datasets air power --profile short --replicates
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/freeze_confirmation.py --replicate-seeds
# Commit and push the freeze before the following confirmation commands.
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/prepare.py --datasets air power --confirmation
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/confirmation.py
```

模型训练采用固定种子和确定性 CPU 算法；归档对象包含耗时元数据，因此重训文件的 SHA 不承诺逐字节相同。冻结 SHA 用于确认正在评估的确实是选定的那份模型，科学复现应比较预测与统计结果，同时记录运行时版本和硬件差异。GitHub CI 的三个模式族矩阵测试不下载研究数据；正式数据、训练和作者 CLI 核验须按这里的独立入口运行。
