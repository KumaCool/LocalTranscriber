# LocalTranscriber 使用说明

[English](user-guide.md) | **简体中文**

本文面向直接使用 LocalTranscriber 的用户，汇总安装、模型准备、单文件与批量转写、后台任务、结果导出及常见问题。命令均在项目根目录执行。

## 1. 工具用途与边界

LocalTranscriber 在本机使用 CPU 完成音视频转写，输出：

- 带毫秒级句段时间戳的文字；
- `SPEAKER_00`、`SPEAKER_01` 等匿名说话人标签；
- JSON、Markdown、TXT 和 SRT 文件。

需要注意：

- 说话人标签只区分任务中的声音簇，不能识别真实身份；
- 时间戳是句段级，不是字词级强制对齐；
- 重叠讲话、短应答、噪声、口音和专业术语可能降低准确率；
- 重要内容应人工复核，不应用于司法鉴定或高风险自动决策。

## 2. 运行要求

- Linux；
- Python 3.11；
- [uv](https://docs.astral.sh/uv/)；
- FFmpeg 和 ffprobe；
- 支持 PyTorch CPU 版本的 x86_64 主机；
- 足够空间存放 Python 依赖、模型缓存和转写结果。

Ubuntu/Debian 安装 FFmpeg：

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

## 3. 安装与首次准备

```bash
git clone https://github.com/KumaCool/LocalTranscriber.git
cd LocalTranscriber
uv sync --locked
```

确认版本：

```bash
uv run local-transcriber --version
```

检查本机环境并保存报告：

```bash
uv run local-transcriber environment probe \
  --output var/acceptance/environment.json
```

首次运行前下载固定版本的模型：

```bash
uv run local-transcriber models pull
```

模型默认保存在 `var/cache/models/`。模型预取需要联网；缓存完整后，实际转写可以离线运行。

## 4. 最常用操作

### 4.1 转写一个文件

```bash
uv run local-transcriber transcribe /path/to/input.wav \
  --output-dir var/output
```

命令默认在前台运行并等待完成。启动后 stderr 会显示任务 ID，成功后 stdout 会显示结果 JSON 路径。

### 4.2 转写多个文件

```bash
uv run local-transcriber transcribe \
  /path/to/a.wav /path/to/b.mp3 \
  --output-dir var/output
```

多个任务使用同一个有界调度器；程序会根据 CPU 和可用内存降低实际并发度。不要把 `--max-workers` 视为保证并发数。

### 4.3 转写目录

仅扫描目录当前层：

```bash
uv run local-transcriber transcribe-dir /path/to/media \
  --output-dir var/output
```

递归扫描子目录：

```bash
uv run local-transcriber transcribe-dir /path/to/media \
  --recursive \
  --output-dir var/output
```

正式处理前预览将接受和跳过的文件：

```bash
uv run local-transcriber transcribe-dir /path/to/media \
  --recursive --dry-run --json \
  --output-dir var/output
```

支持的扩展名：`.aac`、`.flac`、`.m4a`、`.mkv`、`.mov`、`.mp3`、`.mp4`、`.ogg`、`.opus`、`.wav`、`.webm`、`.wma`。

扫描时会跳过符号链接、重复路径、内容重复文件、不支持的扩展名和无法解析的媒体。递归扫描还会排除名为 `runtime`、`output`、`cache`、`work`、`state` 的目录，以及本次指定的运行、输出和缓存目录。

## 5. 常用转写参数

| 参数 | 默认值 | 用途 |
|---|---:|---|
| `--output-dir PATH` | 必填 | 保存最终结果的根目录 |
| `--runtime-dir PATH` | `var/work` | 保存任务、批次状态和本地 IPC 数据 |
| `--cache-dir PATH` | `var/cache/models` | 模型缓存目录 |
| `--language VALUE` | `auto` | 语言提示：`auto`、`zh`、`en`、`yue`、`ja`、`ko` |
| `--speakers N` | 自动 | 提示已知说话人数；不保证聚类一定更准 |
| `--threads N` | `2` | 请求每个 worker 使用的线程数，最终值受资源预算约束 |
| `--max-workers N` | `1` | 请求最大 worker 数，最终值受 CPU 和内存预算约束 |
| `--cpu-limit-percent N` | `50` | CPU 预算百分比 `1–100`；设为 `0` 关闭 CPU 预算 |
| `--memory-limit-percent N` | `70` | 内存预算百分比 `1–100`；设为 `0` 关闭百分比预算 |
| `--config PATH` | 无 | 从 TOML 文件读取 `[resources]` 配置 |
| `--nice N` | `10` | 进程 nice 值，范围 `0–19` |
| `--keep-normalized` | 关闭 | 保留 FFmpeg 标准化后的临时 WAV |
| `--bg` | 关闭 | 提交给本地后台管理器 |
| `--json` | 关闭 | 对支持的命令输出机器可读 JSON |

指定中文：

```bash
uv run local-transcriber transcribe /path/to/input.wav \
  --output-dir var/output \
  --language zh
```

提示有两位说话人：

```bash
uv run local-transcriber transcribe /path/to/input.wav \
  --output-dir var/output \
  --speakers 2
```

资源配置优先级为：命令行参数 > TOML 配置文件 > 内置默认值。例如：

```toml
[resources]
cpu_limit_percent = 50
memory_limit_percent = 70
max_workers = 1
threads_per_worker = 2
nice = 10
```

通过 `--config /path/to/local-transcriber.toml` 使用。任一百分比设为 `0` 即关闭对应预算。关闭内存百分比预算并不绕过物理可用内存检查：当前可用内存无法容纳一个 worker 时，调度器仍会拒绝启动。

## 6. 前台进度、状态和取消

不传 `--bg` 时，命令始终使用前台模式。前台会显示当前阶段、完成比例和 ETA 估算；ETA 可能暂时显示为计算中，也会随负载变化。

从另一个终端查询单个任务：

```bash
uv run local-transcriber job status <job-id> \
  --runtime-dir var/work
```

获取 JSON：

```bash
uv run local-transcriber job status <job-id> \
  --runtime-dir var/work --json
```

前台运行时按 `Ctrl+C` 会请求取消当前批次，并以退出码 `130` 结束。只有全部产物成功写出后，任务才会到达 `100%` 和 `succeeded`。

## 7. 后台运行与恢复

后台管理器只使用本机 Unix IPC，不监听 HTTP 或 TCP 端口。

### 7.1 有用户级 systemd 的环境

```bash
uv run local-transcriber worker start --runtime-dir var/work
uv run local-transcriber worker status --runtime-dir var/work
```

提交后台批次：

```bash
uv run local-transcriber transcribe-dir /path/to/media \
  --recursive \
  --output-dir var/output \
  --runtime-dir var/work \
  --bg --json
```

命令成功后会立即返回 batch ID 和 task ID。

### 7.2 没有用户级 systemd 的环境

在一个受终端复用器或服务管理器跟踪的终端中运行：

```bash
uv run local-transcriber worker run --runtime-dir var/work
```

再从另一个终端提交带 `--bg` 的任务。不要用裸 `&` 或 `nohup` 启动无人管理的 worker。

### 7.3 查询、取消和重试

```bash
uv run local-transcriber batch status <batch-id> \
  --runtime-dir var/work

uv run local-transcriber batch cancel <batch-id> \
  --runtime-dir var/work --json

uv run local-transcriber batch retry <batch-id> \
  --runtime-dir var/work --json
```

也可将 `batch` 换成 `job`，对单个任务执行 `status`、`cancel` 或 `retry`。

管理器重启后：

- `queued` 任务可以继续处理；
- 原先正在运行的任务会如实标记为中断，不会假装成功；
- 中断或失败任务需要显式执行 `retry`；
- 重试会创建新 ID，并保留旧任务记录及已有成功产物。

停止或重启 systemd worker：

```bash
uv run local-transcriber worker stop --runtime-dir var/work
uv run local-transcriber worker restart --runtime-dir var/work
```

`job cancel/retry` 和 `batch cancel/retry` 需要后台管理器正在运行；纯状态查询直接读取持久化记录。

## 8. 输出目录与文件

每个成功任务都有独立结果目录。目录批量处理会保留输入的相对目录结构，并在目录名中加入任务 ID，避免同名覆盖。

| 文件 | 说明 |
|---|---|
| `result.json` | 权威结构化结果，包含来源、引擎、任务和句段信息 |
| `transcript.md` | 适合阅读的 Markdown 转写稿 |
| `transcript.txt` | 纯文本转写稿 |
| `transcript.srt` | SRT 字幕 |
| `media.json` | ffprobe 得到的输入媒体信息 |

`result.json` 是其他导出格式的唯一权威来源。每个句段包含：

```json
{
  "start_ms": 650,
  "end_ms": 4200,
  "speaker": "SPEAKER_00",
  "text": "……"
}
```

程序会移除 SenseVoice 富文本标签、过滤纯 `nospeech` 句段，并压缩明显的整句连续重复；不会自动修正语义误识别。

## 9. 从 JSON 重新导出

```bash
uv run local-transcriber export /path/to/result.json --format srt
uv run local-transcriber export /path/to/result.json --format md
uv run local-transcriber export /path/to/result.json --format txt
```

默认输出到 JSON 同目录并使用对应扩展名。也可指定路径：

```bash
uv run local-transcriber export /path/to/result.json \
  --format srt \
  --output /path/to/meeting.srt
```

## 10. 数据、隐私与离线使用

默认运行数据位于：

- `var/cache/`：模型缓存；
- `var/input/`：可选的本地输入副本；
- `var/work/`：任务状态、IPC 数据和临时文件；
- `var/output/`：最终转写结果；
- `var/acceptance/`：本机验证产物。

这些目录默认不提交到 Git。请勿公开录音、转写稿、任务记录或环境报告。使用者应确保有权处理输入媒体，并遵守隐私、版权和数据保护要求。

如需严格离线使用：

1. 联网执行一次 `models pull`；
2. 确认后续命令始终使用同一个 `--cache-dir`；
3. 在断网条件下先用一份非敏感样本完成验证；
4. 不要删除或移动已缓存模型。

LocalTranscriber 本身不提供 HTTP 服务，也不会主动上传媒体，但首次安装依赖和预取模型需要网络。

## 11. 常见问题

### 找不到 FFmpeg 或 ffprobe

安装 FFmpeg 后重新执行环境探测：

```bash
uv run local-transcriber environment probe \
  --output var/acceptance/environment.json
```

### 后台提交失败并提示无法连接 systemd bus

当前环境没有可用的用户级 systemd。按“没有用户级 systemd 的环境”一节，使用受跟踪的 `worker run`，再重新提交。

### 请求多个 worker，实际仍只有一个

这是资源保护行为。实际 worker 数同时受逻辑 CPU、默认 50% CPU 预算、可用内存和用户参数约束。资源不足时会自动降低，而不是强行并发加载多个模型。

### 说话人标签错乱

匿名聚类对重叠讲话、短句、多人和低质量录音较敏感。`--speakers N` 只是提示，不是准确性保证；应人工校正重要结果。

### 目录里有文件没有处理

先运行 `transcribe-dir --dry-run --json` 查看跳过原因。常见原因包括扩展名不支持、媒体损坏、符号链接、内容重复或位于排除目录。

### 如何查看完整命令帮助

```bash
uv run local-transcriber --help
uv run local-transcriber transcribe --help
uv run local-transcriber transcribe-dir --help
uv run local-transcriber worker --help
```

## 12. 升级与回滚

升级前停止后台 worker，然后切换到目标版本并按锁文件同步：

```bash
uv run local-transcriber worker stop --runtime-dir var/work
git fetch --tags origin
git checkout v0.2.1
uv sync --locked
uv run local-transcriber --version
```

回滚时切换回旧 tag，并再次执行 `uv sync --locked`。版本变化和兼容性说明见 [`../CHANGELOG.md`](../CHANGELOG.md)。不要覆盖或移动已有版本 tag。
