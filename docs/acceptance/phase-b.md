# 阶段 B 验收记录：CLI、任务模型与结构化输出

**状态：** `已完成`

**执行环境：** 匿名受限 CPU 验收主机

**执行日期：** 2026-07-31

## 1. 已交付能力

- 规范 JSON 数据模型：`schema_version/source/engine/job/segments`；
- 句段时间、匿名 speaker 标签、文本和顺序校验；
- ffprobe 媒体探测与显式音轨选择；
- FFmpeg 参数数组标准化为 16 kHz、单声道、PCM S16LE；
- 持久化 `queued/running/succeeded/failed/cancelled` 状态；
- 文件锁保证单 worker，失败保留结构化诊断；
- `transcribe`、`export` CLI；
- Markdown、TXT、SRT 全部由规范 JSON 派生；
- 输入错误、模型错误、取消和 worker 冲突使用不同退出码。

## 2. 真实端到端验收

使用阶段 A 的 Apache-2.0 授权双人中文样本：

```bash
uv run local-transcriber transcribe \
  var/input/phase-a/two-speaker-long.wav \
  --output-dir var/output/phase-b-auto \
  --runtime-dir var/work/phase-b-auto \
  --cache-dir var/cache/models \
  --threads 2
```

实际结果：

- 退出码：`0`；
- 音频时长：23.76975 秒；
- 规范 JSON 状态：`succeeded`；
- 句段：2；
- 匿名说话人：`SPEAKER_00`、`SPEAKER_01`；
- 产物：`result.json`、`media.json`、`transcript.md`、`transcript.txt`、`transcript.srt`；
- 全部产物已读回；
- SRT 编号连续，时间范围有效且单调递增。

另以 `--speakers 2` 验证已知人数参数可传递到 FunASR `preset_spk_num`。该短样本在固定两类时聚类为两个句段但同一 speaker，说明人数约束不是“保证每类都出现”；质量与默认参数比较保留到阶段 C。

详细运行产物位于 `.gitignore` 排除的 `var/output/`，不提交录音或转写正文。

## 3. 自动化验证

```text
pytest:              32 passed
ruff check:          PASS
ruff format:         PASS
uv lock --check:     PASS
uv build:            PASS
```

测试覆盖：

- 规范 JSON 合法/非法值和等价读回；
- WAV 媒体探测、标准化、无音轨、损坏媒体；
- 含 shell 元字符的路径不会被当作命令执行；
- 状态迁移、单 worker 互斥、失败诊断和取消；
- CLI 帮助、参数错误、输入错误、模型错误和成功路径；
- Markdown/TXT/SRT 黄金内容及 SRT 重解析。

## 4. 边界

- 本阶段证明 CLI 和产物链路可用，不等于六类真实场景质量评估完成；
- `--speakers N` 是聚类约束，不是姓名识别，也不保证每个标签一定出现；
- 时间戳为句段范围，不声明字级强制对齐；
- 阶段 C 仍需完成六类样本、线程/人数参数比较和断网验收。
