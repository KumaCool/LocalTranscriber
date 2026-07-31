# 阶段 A 验收记录：环境、模型与组合冒烟

**状态：** `已完成`

**执行环境：** 匿名受限 CPU 验收主机

**执行日期：** 2026-07-31

## 1. 环境边界

环境探针原始 JSON 位于本地不入库路径 `var/acceptance/environment.json`。

| 项目 | 实测结果 |
|---|---|
| CPU | x86_64，支持 AVX2 的受限 CPU 环境 |
| 内存 | 资源受限，按单任务策略验收 |
| Swap | 仅作应急，不纳入吞吐能力 |
| 项目磁盘 | 足以容纳模型缓存与验收产物 |
| Python | CPython 3.11，项目 `.venv` |
| FFmpeg / ffprobe | 6.x |
| GPU | 不可用，固定 `device=cpu` |
| worker | 1 |
| 比较线程数 | 2、3 |

## 2. 固定依赖和模型

依赖由 `uv.lock` 固定，实际环境使用：

- FunASR `1.3.30`
- ModelScope `1.39.0`
- PyTorch / torchaudio `2.10.0+cpu`
- Python `3.11.15`

模型均从 ModelScope 下载到 `var/cache/models/`，许可证均为 Apache-2.0：

| 角色 | 模型 | 固定 revision | 本地大小 |
|---|---|---|---:|
| ASR | `iic/SenseVoiceSmall` | `7bf452403abd7353a300cd760f7adae7701c92c1` | 897 MiB |
| VAD | `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch` | `f9a8b8274674755d925277e27063869038d41515` | 3.9 MiB |
| Speaker | `iic/speech_campplus_sv_zh-cn_16k-common` | `a045b2afcaa9c3049c98a9215a2bc274407ab237` | 28 MiB |

第二次执行模型预取成功，耗时 14.91 秒、峰值 RSS 671836 KiB，没有重复传输完整模型权重。

## 3. 授权样本

冒烟样本来自 CAM++ 官方模型仓库的 Apache-2.0 示例：

- `examples/speaker1_a_cn_16k.wav`
- `examples/speaker2_a_cn_16k.wav`

为避免太短的说话片段导致聚类退化，分别重复至约 11.15 秒和 10.62 秒，中间加入 2 秒静音，生成 23.76975 秒、16 kHz、单声道、PCM S16LE 的双人样本。原始样本和派生产物仅保存在被 `.gitignore` 排除的 `var/input/phase-a/`。

## 4. 组合模型冒烟结果

实际调用：SenseVoiceSmall + FSMN-VAD + CAM++，`device=cpu`，模型参数均使用本地绝对路径。

| 线程 | 音频时长 | 推理耗时 | 推理 RTF | 峰值 RSS | 句段 | speaker |
|---:|---:|---:|---:|---:|---:|---|
| 2 | 23.76975 s | 4.05490 s | 0.17059 | 3263952 KiB | 2 | 0、1 |
| 3 | 23.76975 s | 3.17121 s | 0.13341 | 3269964 KiB | 2 | 0、1 |

两个线程配置都返回了实际版本的 `sentence_info`，字段为：

```text
start, end, sentence, timestamp, spk
```

两个句段均有非空中文文本、有效毫秒范围，并分别给出匿名 `spk=0` 和 `spk=1`。两次输出一致。3 线程在该样本上快约 21.8%，内存增加约 5.9 MiB；阶段 C 的代表性样本矩阵完成前不据此最终确定默认线程数。

## 5. 已确认限制

- CAM++ 给出的是任务内匿名 speaker 编号，不是姓名识别。
- 未配置标点模型时，FunASR 明确回退为 `vad_segment` diarization；句段边界依赖 VAD，不是句法句子边界。
- 9.83 秒短双人拼接样本只产生一个 VAD 句段并被标为单 speaker；延长每位说话人的有效语音且加入静音后才稳定得到两个 speaker。这证明短应答和短片段可能聚类失败。
- 重叠语音尚未在阶段 A 质量验收；CAM++ 聚类也不等于源分离。
- `sentence_info.timestamp` 存在，但阶段 A 只承诺句段 `start/end`；不会把它未经进一步验证地声明为可交付字级强制对齐。
- 首次依赖配置误装了 CUDA PyTorch 且缺少 torchaudio；已改为 PyTorch 官方 CPU wheel 索引并固定 `torch/torchaudio 2.10.0+cpu`。

## 6. 自动测试

`tests/test_environment.py` 和 `tests/test_models.py` 覆盖：

- 环境报告必填项、单 worker 和 2/3 线程策略；
- 三个固定模型；
- 实际 `sentence_info` 正常结构；
- 缺字段、空文本、非法时间范围和无 speaker；
- 模型 manifest 写出和读回。

阶段完成依据：隔离环境可由锁文件重建、三类模型缓存完整、真实授权双人组合冒烟成功、资源指标已记录、自动测试通过。
