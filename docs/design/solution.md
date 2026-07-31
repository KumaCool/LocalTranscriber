# LocalTranscriber：本地离线语音转写方案

## 1. 目标与边界

本项目面向当前 Linux 主机，总体目标是提供以中文为主的离线音频批量转写。已实现能力与后续目标在 [§1.1](#11-当前实现与目标方案) 中分别标注：

- 区分不同说话人，输出稳定的匿名标签（如 `Speaker 0`、`Speaker 1`）；
- 输出句段级开始、结束时间戳；
- 模型下载并缓存后，不依赖云端 API；
- 支持常见音频/视频输入，并输出 JSON、Markdown/TXT、SRT；
- 支持单文件、显式多文件和指定目录的批量转写；
- 前台运行为默认方式，同时提供显式后台模式；后台模式由本地任务管理器持续执行，终端退出后任务不丢失；
- 目标根据机器资源预算自动限制线程和并发，默认最多使用整机逻辑 CPU 容量的 50%，并允许用户调低性能占用和并发数；
- 优先保证资源可控和任务可恢复，不追求在线实时字幕。

### 1.1 当前实现与目标方案

本文同时记录已实现基线和后续目标，避免把设计误述为现有能力：

| 能力 | 当前实现 | 目标方案 |
|---|---|---|
| 前台单文件转写 | 已实现并验收，当前默认 | 保持默认前台行为，并扩展到多文件和目录批量 |
| Hermes 后台进程调用 | 已实现并验收 | 增加显式、可恢复的统一后台模式 |
| 进程退出后的任务恢复 | 未实现 | 后台管理器持久化队列并恢复未完成任务 |
| 多文件/目录批量提交 | 未实现 | 支持文件列表和目录扫描 |
| 多文件并发推理 | 未实现，当前单 worker | 资源预算内的有界并发 worker 池 |
| CPU 占用配置 | 当前仅支持每任务线程数 | 增加整机 CPU 预算、并发数和每 worker 线程数配置 |
| 实时进度和 ETA | 未实现 | 使用阶段事件与 FunASR 原生回调提供估算进度 |
| 发布版本和更新日志 | 包版本为 `0.1.0`，尚无独立更新日志 | 每次正式发布必须变更版本并更新 `CHANGELOG.md` |

不承诺：

- 自动知道说话人的真实姓名；
- 重叠语音的完美分离；
- 司法鉴定级声纹结论；
- 逐字级精确时间对齐；
- 在资源受限的 CPU 环境上达到实时速度。

## 2. 匿名验收环境约束（2026-07-31 实测）

| 项目 | 当前状态 | 对方案的影响 |
|---|---:|---|
| CPU | 支持 AVX2 的受限 x86_64 CPU | 可运行 CPU 推理，但应限制并发 |
| 内存 | 资源受限 | 并发数必须同时受 CPU 和内存预算约束，不能只按核心数计算 |
| Swap | 仅作应急 | 不能依赖 Swap 提升吞吐 |
| GPU | 无计算 GPU | 全部采用 CPU 路径 |
| 磁盘 | 可容纳模型缓存和中等规模任务 | 仍需源文件/产物清理策略 |
| Python | 3.11 | 适合建立项目独立虚拟环境 |
| FFmpeg | 6.x | 已具备音视频解码和标准化前置条件 |

当前已验收基线仍是一个 worker、一个文件、每 worker 2 个 CPU 推理线程。目标方案在启动时探测逻辑 CPU、可用内存和已有系统负载，再计算安全 worker 数；在当前资源受限主机上，即使用户配置了更高并发，自动计算结果也可能仍为 1。并发能力不等于无条件同时加载多套模型。

## 3. 技术选型

### 3.1 推荐流水线

```text
输入音频/视频
  ↓
FFmpeg 解码与标准化（16 kHz、单声道、PCM）
  ↓
FSMN-VAD：检测有效语音区间
  ↓
SenseVoiceSmall：中文优先的语音识别
  ↓
CAM++：说话人嵌入 + 聚类，得到匿名 speaker ID
  ↓
时间轴整理、短段合并、格式转换
  ↓
JSON + Markdown/TXT + SRT
```

推荐使用：

- `FunASR==1.3.30`（实施时固定并写入锁文件）；
- `iic/SenseVoiceSmall`；
- `fsmn-vad`；
- `cam++`；
- `device="cpu"`。

FunASR 当前官方示例可以通过一个 `AutoModel` 组合上述 ASR、VAD 和说话人模型，并从 `sentence_info` 读取 `start`、`end`、`spk` 和句段文本。CAM++ 是独立说话人模型，区分说话人并非 SenseVoiceSmall 本身的原生输出。

### 3.2 为什么选择它

- SenseVoiceSmall 对中文、粤语及中英混合场景比“只为通用多语种设计”的路径更贴合；
- 非自回归模型适合有限 CPU 资源；
- FunASR 已提供 VAD、ASR、说话人模型的组合接口；
- 完成模型缓存后可以离线处理；
- 相比 WhisperX + pyannote，当前无 GPU、4 核、8 GiB 主机更容易控制资源。

### 3.3 备选方案

| 方案 | 优点 | 当前主机上的问题 | 结论 |
|---|---|---|---|
| faster-whisper | 成熟、Hermes 原生 STT 可直接采用 | 默认不含说话人分离；仍需接 diarization | 适合作为 Hermes 短语音 STT，不作为本项目主线 |
| WhisperX + pyannote | 对齐和说话人生态成熟 | CPU/内存压力较高，部署更复杂 | 保留为准确率对照实验 |
| SenseVoice GGUF | CPU 部署轻，运行时简单 | 不能直接替代完整 CAM++ diarization 流水线 | 可作为无说话人转写的降级路径 |
| 云端 ASR/diarization | 快、维护少 | 有隐私、费用、网络依赖 | 不符合离线优先目标 |

## 4. 说话人和时间戳语义

### 4.1 Speaker 标签

输出的 `Speaker 0`、`Speaker 1` 是一次任务内由声纹嵌入聚类得到的匿名标签：

- 不代表真实姓名；
- 不保证跨文件保持同一编号；
- 若需真实姓名及跨文件身份，需要另行设计声纹注册、阈值匹配和人工确认；
- 已知说话人数时，应允许用户传入人数约束；未知时自动估计。

### 4.2 时间戳

首期提供句段级毫秒时间戳：

```text
[00:03:14.200 --> 00:03:21.650] Speaker 2：示例文本
```

时间戳主要由 VAD/句段结果提供，适合回听定位、会议纪要和常规字幕；它不是逐字强制对齐。SRT 生成不得伪造字级时间。

### 4.3 已知困难场景

- 多人同时讲话；
- 很短的“嗯”“对”“好”；
- 强噪声、音乐、回声和远场录音；
- 电话压缩音频；
- 同一说话人距离/设备发生明显变化；
- VAD 边界刚好跨越说话人切换。

这些场景需要保留原始分段、置信信息（上游可提供时）和可人工修订的结构化结果。

## 5. 输入、处理和输出设计

### 5.1 输入

首期至少支持 FFmpeg 可解码的：WAV、MP3、M4A/AAC、FLAC、OGG/Opus，以及常见 MP4/MKV 中的音轨。

每个任务保留：

- 原始文件路径、大小和哈希；
- FFprobe 媒体信息；
- 标准化音频路径；
- 模型与参数版本；
- 开始/结束时间及错误信息。

### 5.2 标准化

参考命令：

```bash
ffmpeg -i INPUT -vn -ac 1 -ar 16000 -c:a pcm_s16le normalized.wav
```

实现时使用参数数组调用子进程，避免 shell 拼接；遇到多音轨时显式选择音轨并记录。

### 5.3 规范 JSON

JSON 是唯一权威产物，其他格式由 JSON 派生：

```json
{
  "schema_version": 1,
  "source": {"path": "example.m4a", "duration_ms": 120000},
  "engine": {
    "funasr_version": "1.3.30",
    "asr_model": "iic/SenseVoiceSmall",
    "vad_model": "fsmn-vad",
    "speaker_model": "cam++",
    "device": "cpu"
  },
  "segments": [
    {
      "start_ms": 650,
      "end_ms": 4200,
      "speaker": "SPEAKER_00",
      "text": "欢迎使用本地转写工具。"
    }
  ]
}
```

### 5.4 导出格式

- JSON：完整、可恢复、可二次编辑；
- Markdown/TXT：按时间和说话人阅读；
- SRT：每段带时间范围，正文以 `[Speaker 0]` 开头；
- 后续可选 VTT，不在首期强制范围。

## 6. 资源、队列和离线策略

### 6.1 前台与后台运行模型

工具必须同时支持前台和后台两种运行方式，且**默认采用前台运行**：

- **前台模式（默认）：** 命令保持运行，直接输出当前文件/批次的阶段、进度、ETA 和最终摘要；完成后按批次结果返回退出码；用户按 `Ctrl+C` 时执行协作取消并写入持久化终态；适合交互使用、脚本调用和即时观察；
- **后台模式（显式选择）：** 只有用户传入 `--bg` 或使用等价后台提交命令时才启用；命令快速返回批次 ID 和任务 ID，任务由本地后台管理器继续执行；适合长任务、终端可能断开或需要跨会话查询的场景；
- 不允许根据音频时长、文件数量或是否由 Hermes 调用而静默切换运行模式；实际模式必须在命令输出和任务记录中明确显示；
- 前台和后台必须共用同一套输入扫描、批次模型、资源预算、worker 池、进度、取消、产物和错误语义，不能维护两套不同的转写实现；
- 两种模式都支持单文件、多文件和目录批量，也都服从相同的 CPU、内存、并发及单实例调度约束。

统一执行结构：

```text
CLI 接收单文件/文件列表/目录
  ↓
持久化任务清单与队列
  ↓
统一调度器（前台内嵌运行或后台管理器托管）
  ↓
有界 worker 池
  ↓
每个文件独立的规范 JSON 与导出产物
```

- 默认前台命令必须等待批次进入终态；后台模式才快速返回批次 ID 和任务 ID；
- 前台批次也必须先持久化任务状态，以便崩溃诊断和后续重试，但命令退出后不把普通前台任务自动留在后台继续运行；
- 后台管理器采用用户级进程或服务运行，支持 `start/status/stop/restart`，不依赖 shell 的 `&`、`nohup` 或临时终端会话；
- Linux 安装模式优先提供用户级 systemd service；无 systemd 环境提供受跟踪的前台 `worker run`，但不得静默派生无法管理的孤儿进程；
- 后台管理器默认不监听 TCP/HTTP 端口，CLI 通过本地状态文件、锁和受控 IPC 管理；
- 同一运行目录只允许一个管理器持有调度锁，重复启动必须安全拒绝；
- 管理器重启后重新载入 `queued` 任务；中断时仍为 `running` 的任务进入 `interrupted`/可重试状态，不得直接宣称成功；
- 支持按任务或批次查询、取消和重试；取消排队任务立即生效，取消运行中任务应先协作终止，超时后再安全结束子进程；
- 后台退出、系统重启和异常崩溃均不得损坏已完成产物或丢失任务状态。

### 6.2 多文件与目录批量转写

输入形态分为三类，并统一展开为“一个文件一个任务、一次提交一个批次”：

1. **单文件：** 保留现有 `transcribe FILE`；
2. **多文件：** 一次显式传入多个文件，保持用户给定顺序；
3. **目录：** 指定目录后扫描受支持媒体，可选择是否递归。

目录扫描规则：

- 默认只扫描目录当前层；`--recursive` 才递归子目录；
- 只接收 FFmpeg 可探测且包含音轨的文件，扩展名仅用于预筛选，不代替 ffprobe；
- 默认不跟随符号链接，避免目录循环和越界读取；
- 扫描结果按规范化相对路径稳定排序，确保重复提交可复现；
- 排除项目输出、工作、缓存目录，防止把转写产物再次当作输入；
- 同一批次按规范化绝对路径、大小和内容哈希去重；
- 单个文件失败不阻止其他文件继续，批次结果汇总成功、失败、取消和跳过数量；
- 输出保留相对目录结构并增加任务 ID，避免同名文件覆盖；
- 支持 dry-run，只列出将提交的文件、跳过原因和资源估算，不启动转写；
- 大目录采用流式扫描和有界入队，不一次把所有媒体加载进内存。

建议目标 CLI：

```bash
# 默认前台：等待完成并持续显示进度
local-transcriber transcribe recording.m4a --output-dir ./output

# 前台批量：等待整个批次结束
local-transcriber transcribe one.m4a two.wav three.mp4 --output-dir ./output

# 前台目录批量；默认不递归
local-transcriber transcribe-dir ./recordings --output-dir ./output

# 递归扫描，并在提交前预览
local-transcriber transcribe-dir ./recordings --recursive --dry-run

# 显式后台：必要时启动管理器，随后立即返回任务标识
local-transcriber transcribe recording.m4a --bg --output-dir ./output
local-transcriber transcribe-dir ./recordings --recursive --bg --output-dir ./output

# 查询批次和任务
local-transcriber batch status BATCH_ID
local-transcriber job status JOB_ID --json
```

命令名称属于目标接口，实施前可按现有 CLI 兼容性进一步收敛；在代码和端到端测试落地前，不应在 README 中作为当前可用命令展示。

### 6.3 有界并发模型

“支持并发”定义为多个文件可同时处于运行态，但并发必须有上限，并由统一调度器批准：

- `max_workers`：同时执行的文件任务数；默认 `auto`；
- `threads_per_worker`：每个模型 worker 的 PyTorch/OMP/MKL 线程数；默认由预算计算；
- 每个 worker 的模型、临时目录、日志、取消信号和进度相互独立；
- 单文件失败不得终止其他 worker；
- 不允许 CLI 绕过调度器直接启动额外并发模型进程；
- 多 worker 会重复占用模型内存，因此调度上限取 CPU 上限、内存上限和用户并发上限三者的最小值；
- 若实测模型无法安全共享或每个 worker 的峰值内存过高，则保持多文件排队、单 worker 执行，直到真实并发验收通过。

调度公式采用明确的硬上限，而不是只依赖进程优先级：

```text
cpu_thread_budget = max(1, floor(logical_cpu_count × cpu_limit_percent / 100))
cpu_worker_limit  = max(1, floor(cpu_thread_budget / threads_per_worker))
memory_worker_limit = floor(memory_budget_bytes / measured_peak_bytes_per_worker)
effective_workers = min(user_max_workers, cpu_worker_limit, memory_worker_limit)
```

若任一安全条件只能容纳一个 worker，`effective_workers` 必须降为 1；若连一个 worker 的内存安全线都不满足，则拒绝启动并给出资源不足错误。

### 6.4 性能占用配置

默认性能策略为 `balanced`：LocalTranscriber 的**目标 CPU 预算不超过整机逻辑 CPU 容量的 50%**。该值是调度和线程配置的硬上限目标，不承诺操作系统采样值每一秒都精确等于 50%；FFmpeg、线程启动和系统调度可能造成短时波动。

支持以下配置：

| 配置 | 默认值 | 约束与语义 |
|---|---:|---|
| `cpu_limit_percent` | `50` | 范围 `10–50`；用户可以调低，不得在普通配置中突破 50% |
| `max_workers` | `auto` | 可指定正整数，但最终值仍受 CPU/内存预算约束 |
| `threads_per_worker` | `auto` | 可指定正整数，但所有 worker 线程总和不得超过 CPU 线程预算 |
| `memory_limit_percent` | `50` | 用于计算模型 worker 上限；同时保留最低系统空闲内存安全线 |
| `nice` | 平台安全默认值 | 仅作为降低调度优先级的辅助手段，不能代替线程和 worker 上限 |

配置优先级：命令行参数高于项目配置文件，项目配置高于内置默认值。每次任务必须把最终生效的预算、worker 数和线程数写入任务记录，便于复现和诊断。

资源控制要求：

- 设置 PyTorch、OMP、MKL 的每 worker 线程上限；
- Linux/systemd 环境可额外使用 cgroup `CPUQuota` 和 `MemoryHigh/MemoryMax` 形成进程组级保护；
- 没有 cgroup 时使用线程预算、worker 上限、低优先级和周期性资源采样；
- 若持续超出 CPU 目标或可用内存跌破安全线，调度器暂停启动新任务；必要时将并发降级，不能强杀已写出有效产物的任务；
- 资源采样必须统计整个任务进程树，包括 FFmpeg 和模型子进程；
- 自动模式以当前机器的实测峰值 RSS 和吞吐基准为依据，不能仅按 CPU 核心数推断安全并发。

### 6.5 任务、批次与进度状态

- 文件任务状态至少包含 `queued/running/succeeded/failed/cancelled`，并增加后台恢复所需的 `interrupted`；
- 批次状态由其文件任务聚合，不用单个全局布尔值表示；
- 每个文件独立记录来源、哈希、参数、重试次数、进度、错误和产物路径；
- 进度使用阶段事件和 FunASR 原生回调，不能用匀速计时制造假百分比；
- 批次进度按文件工作量聚合，优先按媒体时长加权，未知时长文件在 ffprobe 后再纳入总量；
- 失败、取消和跳过必须进入批次终态计算，不能使批次永久显示“运行中”；
- 原始输入、临时 WAV、任务状态、日志、最终产物和模型缓存分目录管理；
- 成功后临时 WAV 可按策略删除，失败时按隐私策略保留最少诊断材料。

### 6.6 离线与安全边界

- 首次启动显式执行模型预取；只有预取完成后才宣称“可离线”；
- 断网验收必须在阻断网络访问的条件下重新运行已缓存模型的批量任务；
- 后台运行和批量处理不改变隐私边界：不得上传媒体、转写结果、哈希或模型输入；
- 后台管理接口保持本机私有，不增加公网服务；
- 任务日志不得包含转写正文，默认只记录元数据、阶段和脱敏错误。

## 7. 项目形态建议

项目保持“默认前台 CLI + 可选持久化后台队列 + 共享的有界 worker 池”，不先做长期暴露端口的 Web 服务：

```text
LocalTranscriber/
├── docs/
│   ├── solution.md
│   └── skills-and-hermes-integration.md
├── src/
├── tests/
├── var/              # 运行时目录，后续加入 .gitignore
│   ├── input/
│   ├── work/
│   ├── state/          # 队列、批次、任务和调度锁
│   ├── logs/           # 不含转写正文的运行日志
│   └── output/
├── CHANGELOG.md
└── README.md
```

建议 CLI：

```bash
local-transcriber models pull
local-transcriber transcribe recording.m4a --output-dir ./output
local-transcriber transcribe recording.m4a --speakers 2
local-transcriber export result.json --format srt
```

现有前台 `transcribe` 命令保留并继续作为默认入口；多文件、目录和显式后台任务都复用统一调度器，不能各自启动无约束模型进程。将来若确需 UI，应仅监听 localhost 或 WireGuard/Tailscale 私网地址，所有请求只向同一队列提交任务，不能让每个 HTTP 请求直接启动一个模型进程。

## 8. Hermes 集成策略

Hermes 自带 STT 主要用于 Telegram/CLI/Discord 的短语音消息转文字，官方本地 provider 是 `faster-whisper`。它不提供 CAM++ 说话人聚类，也不等价于本项目的会议文件批处理。

推荐分层：

1. **LocalTranscriber 独立 CLI**：负责长音频、时间戳、说话人区分和结构化产物；
2. **Hermes skill（后续创建）**：告诉 Agent 在收到“转写会议/区分说话人”等请求时如何调用 CLI、读取 JSON 并回传文件；
3. **可选 Hermes 原生 tool/plugin**：只有当 CLI 稳定且频繁使用时再封装；
4. **暂不开发 MCP**：工具只服务于本机 Hermes 时，本地 CLI + skill 更简单。若未来多个 Agent 客户端都要共享转写服务，再考虑 stdio MCP，避免开放公网端口。

后台队列落地后，Hermes 对普通短任务仍可使用默认前台模式；对于需要跨会话持续执行或用户明确要求后台运行的长任务，应显式选择后台模式、保存任务 ID，并通过只读状态命令查询进度和终态，而不是自行派生无法恢复的进程。Hermes 仍需在成功后读回并验证 canonical JSON 和所有请求的导出文件。

## 9. 版本、发布与更新日志

### 9.1 版本规则

项目采用 [Semantic Versioning](https://semver.org/) 形式的 `MAJOR.MINOR.PATCH`：

- `MAJOR`：不兼容的 CLI、配置、任务状态或 canonical JSON 变更；
- `MINOR`：向后兼容的新功能，例如后台队列、目录批量或新的导出格式；
- `PATCH`：向后兼容的缺陷、安全或文档修复。

开发中的普通提交不要求每次修改版本；但**每次正式发布必须使用一个高于上一发布的新版本号**。同一版本不得对应两份不同的发布内容，也不得在发布后静默覆盖同名 tag 或构建产物。

版本号必须具有单一来源，并在以下位置保持一致：

- Python 包元数据；
- CLI `--version` 输出；
- Git tag（格式 `vMAJOR.MINOR.PATCH`）；
- GitHub Release 标题与构建产物元数据。

### 9.2 更新日志

仓库根目录新增并长期维护 `CHANGELOG.md`，采用 Keep a Changelog 风格：

```markdown
## [Unreleased]
### Added
### Changed
### Fixed
### Security

## [0.2.0] - YYYY-MM-DD
```

- 所有面向用户的功能、行为变化、兼容性影响、修复和安全变化先写入 `Unreleased`；
- 发布时把相关条目移动到带日期的新版本章节，并重新建立空的 `Unreleased`；
- 更新日志描述用户可感知变化，不复制提交列表，不写“优化若干”等不可验证表述；
- 不兼容变化必须单独标记迁移方式和受影响的 CLI、配置、状态文件或 JSON schema；
- 纯内部重构只有在影响行为、性能或兼容性时才进入更新日志。

### 9.3 发布门禁

每次正式发布必须依序完成：

1. 确认工作树只包含本次发布范围；
2. 全量测试、lint、格式、构建和离线 smoke test 通过；
3. 批量/后台版本还必须分别验证默认前台和显式后台路径、管理器重启恢复、有界并发、50% CPU 默认预算和部分失败聚合；
4. 更新包版本和 `CHANGELOG.md`，检查二者与目标 tag 一致；
5. 构建 sdist/wheel，并在干净临时环境安装后执行 `--version` 与 CLI smoke test；
6. 创建带注释且不可移动的版本 tag，推送提交和 tag；
7. 创建 GitHub Release，附更新日志、升级注意事项和构建产物校验值；
8. 从远端重新读取 tag/Release，确认版本、源码和产物一致。

未完成版本变动或更新日志的构建只能视为开发快照，不得作为正式发布。

## 10. 分阶段实施与验收

本方案的全部实施阶段已合并到一份可跟踪的计划文档：

- [LocalTranscriber 实施计划](../plan/01-localtranscriber-implementation-plan.md)

方案保留目标与验收边界，计划负责阶段顺序、任务和进度状态。同一方案不再拆分为多份计划文档。

## 11. 决策结论

采用 **FunASR + SenseVoiceSmall + FSMN-VAD + CAM++** 作为主线，不以实时字幕服务为目标。前台运行是默认方式，后台运行必须由用户显式选择；两种方式都支持单文件、多文件和目录批量，并共享同一持久化任务模型、统一调度器和资源预算内的有界 worker 池。后台管理器不监听网络端口。默认 CPU 预算上限为整机 50%，用户可调低预算并指定并发/线程上限，但最终并发必须服从 CPU 和内存安全计算。每次正式发布必须变更语义化版本、更新 `CHANGELOG.md` 并通过发布门禁；当前仍无必要为了集成而引入 MCP 或公网 HTTP 服务。