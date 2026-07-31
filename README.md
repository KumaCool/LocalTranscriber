# LocalTranscriber

LocalTranscriber 是一个面向 CPU 环境的本地离线语音转写工具，基于 FunASR、SenseVoiceSmall、FSMN-VAD 和 CAM++，可生成带匿名说话人标签与句段时间戳的 JSON、Markdown、TXT 和 SRT 文件。

音频、模型输入和转写结果均可保留在本机。项目不提供 HTTP 服务，也不会主动上传媒体文件。

## 功能特性

- **本地离线转写**：模型下载完成后，可在断网环境运行。
- **匿名说话人聚类**：输出 `SPEAKER_00`、`SPEAKER_01` 等任务内标签。
- **句段时间戳**：提供毫秒级起止时间，不宣称字级强制对齐。
- **多种导出格式**：规范 JSON、Markdown、纯文本和 SRT 字幕。
- **可恢复任务状态**：保存任务记录，并限制为单 worker，适合资源有限的 CPU 主机。
- **媒体预检**：使用 FFmpeg/ffprobe 验证并标准化常见音视频输入。
- **Hermes Agent 集成**：仓库附带可选的本地转写 Skill；CLI 可独立使用。

## 使用限制

- 说话人标签是匿名聚类结果，不能用于识别真实身份。
- 多人、短应答及重叠讲话可能出现说话人合并或分配错误。
- 专业术语、口音、噪声和低质量录音可能降低识别准确率。
- 输出应经过人工复核，不适用于司法鉴定或其他高风险自动决策。
- 当前版本要求 Python 3.11，并以 CPU 单任务运行作为主要支持场景。

## 系统要求

- Linux（主要验证平台；其他平台欢迎测试与贡献）
- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- FFmpeg 与 ffprobe
- 支持 PyTorch CPU 版本的 x86_64 环境
- 足够的磁盘空间用于依赖、模型缓存和转写产物

Ubuntu/Debian 可安装 FFmpeg：

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

## 安装

```bash
git clone https://github.com/KumaCool/LocalTranscriber.git
cd LocalTranscriber
uv sync --locked
```

验证环境：

```bash
uv run local-transcriber environment probe \
  --output var/acceptance/environment.json
```

首次使用时下载模型：

```bash
uv run local-transcriber models pull
```

模型会保存到被 Git 忽略的 `var/cache/models/`。此步骤需要网络连接；完成后可离线转写。

## 快速开始

基本转写：

```bash
uv run local-transcriber transcribe /path/to/input.wav \
  --output-dir var/output
```

不带 `--bg` 时始终前台等待。多文件和目录使用同一持久化调度器，worker/线程数会同时受 CPU、内存和用户上限约束；默认 CPU 预算不超过逻辑 CPU 的 50%。

```bash
uv run local-transcriber transcribe /path/a.wav /path/b.mp3 \
  --output-dir var/output

uv run local-transcriber transcribe-dir /path/to/media-dir \
  --output-dir var/output
```

只有明确需要跨会话或终端断开后继续运行时才传 `--bg`。后台管理器使用本地 Unix IPC，不监听 HTTP/TCP；提交成功会返回 batch/task ID：

```bash
uv run local-transcriber transcribe-dir /path/to/media-dir \
  --output-dir var/output --runtime-dir var/work --bg --json

uv run local-transcriber batch status <batch-id> --runtime-dir var/work --json
uv run local-transcriber batch cancel <batch-id> --runtime-dir var/work --json
uv run local-transcriber batch retry <batch-id> --runtime-dir var/work --json
```

有用户级 systemd 时可用 `worker start/status/stop/restart`；无 systemd 环境应以受跟踪的 `worker run` 前台进程运行管理器，不要使用裸 `&` 或 `nohup`。

指定中文：

```bash
uv run local-transcriber transcribe /path/to/input.wav \
  --output-dir var/output \
  --language zh
```

已知说话人数量时可显式指定，但这不保证聚类质量更高：

```bash
uv run local-transcriber transcribe /path/to/input.wav \
  --output-dir var/output \
  --speakers 2
```

从已有规范 JSON 重新导出 SRT：

```bash
uv run local-transcriber export /path/to/result.json --format srt
```

转写开始后，CLI 会立即在 stderr 输出任务 ID。可从另一个进程只读查询当前状态，不会启动第二个 worker：

```bash
uv run local-transcriber job status <job-id> \
  --runtime-dir var/work \
  --json
```

状态包含当前阶段、单调百分比、实际处理工作量和 ETA 范围。进度由媒体阶段事件、VAD 语音段和 ASR 实际批次驱动；ETA 是动态工程估算，不保证匀速或精确完成时刻。样本不足时 ETA 保持 `null`/`calculating`，负载波动或停滞时置信度可降为 `low`。只有成功写出全部产物后任务才到 `100%`。

查看全部命令：

```bash
uv run local-transcriber --help
uv run local-transcriber transcribe --help
```

## 输出文件

成功任务的输出目录包含：

| 文件 | 说明 |
|---|---|
| `result.json` | 权威结构化结果，包含任务、来源、引擎和句段信息 |
| `transcript.md` | 便于阅读的 Markdown 转写稿 |
| `transcript.txt` | 纯文本转写稿 |
| `transcript.srt` | 字幕文件 |
| `media.json` | 输入媒体的探测信息 |

转写正文会移除 SenseVoice 富文本标签、过滤纯 `nospeech` 句段，并压缩明显的整句连续重复。这些后处理不会自动修正语义误识别。

## 数据与隐私

运行数据保存在 `var/`：

- `var/cache/`：模型缓存
- `var/input/`：本地输入文件（可选）
- `var/work/`：任务状态和临时文件
- `var/output/`：转写结果
- `var/acceptance/`：本地验证产物

这些内容默认被 `.gitignore` 排除。请勿提交录音、转写稿、任务记录或包含机器信息的环境报告。使用者负责确认其有权处理输入媒体，并遵守适用的隐私、版权及数据保护规定。

## 开发

安装开发依赖并运行质量检查：

```bash
uv sync --locked --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

测试默认不下载模型、不访问网络，也不依赖真实私人录音。真实模型运行记录位于 [`docs/acceptance/`](docs/acceptance/)。

贡献前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。安全问题请按 [`SECURITY.md`](SECURITY.md) 私下报告。

## 项目文档

- [技术设计](docs/solution.md)
- [实现计划与工程记录](docs/plan/01-localtranscriber-implementation-plan.md)
- [离线验证](docs/acceptance/offline-verification.md)
- [质量评估矩阵](docs/acceptance/evaluation-matrix.md)
- [真实进度与动态 ETA 验收](docs/acceptance/progress-and-eta.md)
- [批量、后台恢复与资源验收](docs/acceptance/batch-background-resources.md)
- [Hermes Agent 可选集成](docs/skills-and-hermes-integration.md)

`docs/acceptance/` 和 `docs/plan/` 保存开发与验证证据，不代表对所有硬件、语言和音频条件作出质量保证。

## 贡献

欢迎提交问题、文档改进、平台兼容性报告和代码贡献。请确保：

- 不提交无权公开的音频或转写内容；
- 新行为有离线、可重复的测试；
- 不削弱本地处理、单 worker 和隐私边界；
- 提交前通过测试、lint 和格式检查。

## 许可证

Copyright © 2026 Shunnketu Kuma.

本项目基于 [MIT License](LICENSE) 开源。依赖组件和下载模型分别适用其各自的许可证；使用者应自行核对并遵守相关条款。
