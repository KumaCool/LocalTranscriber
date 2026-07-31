# 相关 Skills、Hermes 音频能力与 MCP 调查

调查日期：2026-07-31。结论以本机实际命令和 Hermes 官方文档为准。

## 1. 本机已安装的相关 Skill

当前 125 个已安装 skill 中，没有专门执行 **FunASR + SenseVoiceSmall + FSMN-VAD + CAM++ 说话人分离** 的 skill。

有一定关联但不能直接完成目标的 skill：

| Skill | 当前状态 | 能力 | 与本项目关系 |
|---|---|---|---|
| `hermes-agent` | 已安装、可用 | Hermes 配置、STT/TTS、MCP、插件说明 | 用于确认 Hermes 原生语音能力和集成方式 |
| `songsee` | skill 已安装；`songsee` 命令未安装 | 频谱图、Mel、MFCC 等音频可视化 | 可辅助检查噪声、静音、音频质量，不负责转写或 diarization |
| `youtube-content` | 已安装 | YouTube 转录与内容整理 | 面向在线视频内容，不是本地 CAM++ 流水线 |
| `teams-meeting-pipeline` | 已安装 | Teams/Graph transcript-first 会议管线 | 依赖 Teams 已有转录，不替代本地 ASR |
| `audiocraft-audio-generation` / `heartmula` | 已安装 | 音频/音乐生成 | 与转写无直接关系 |

本机 Python 环境未发现 `funasr`、`faster-whisper`、`openai-whisper`、`pyannote`、`torch`、`modelscope` 等相关包；系统已有 `ffmpeg` 和 `ffprobe`。

## 2. Hermes Skills Hub 搜索结果

### 2.1 最相关候选

| 标识符 | 来源/信任 | 搜索描述摘要 | 初步判断 |
|---|---|---|---|
| `funasr-asr` | ClawHub / community | 本地中文 FunASR，语音/音视频转录，小内存模式与任务队列 | 值得审查脚本和依赖，但描述未证明支持 CAM++ |
| `funasr-transcribe-skill` | ClawHub / community | 本地音频转写，偏中文/中英混合，不依赖云端 | 可能适合基础 ASR，未证明有说话人分离 |
| `sensevoice-transcribe` | ClawHub / community | SenseVoice-Small + FSMN-VAD，带时间戳和批处理 | 与 ASR/VAD 高度相关，但搜索描述没有 CAM++ |
| `zxkane-audio-transcriber-funasr` | ClawHub / community | 会议/音频转文字 | 需审查实现，描述不足以确认离线及 speaker 标签 |
| `official/mlops/whisper` | official / official | Whisper 安装、99 种语言转写/翻译 | 官方且可信，但不是主线，也不自带 diarization |
| `dlazy-fun-asr` | ClawHub / community | 阿里云百炼 Fun-ASR 录音转写 | 云端路径，不符合离线优先 |
| `assemblyai-transcriber` 等 | ClawHub / community | 云端转写和 speaker diarization | 有说话人能力，但依赖第三方云 API |

说明：Hub 的社区 skill 只是候选工作流，不应直接安装并运行未知脚本。下一步若要采用，应先执行 `hermes skills inspect` 或下载到隔离位置，审查以下内容：

- 是否执行远程脚本或上传音频；
- 模型来源和版本是否锁定；
- 是否真正使用 `spk_model="cam++"`；
- 是否有任意 shell 拼接、凭据读取或不必要网络访问；
- 输出是否保留毫秒起止时间、匿名 speaker ID 和原始 JSON；
- 是否支持 CPU、Python 3.11 和单 worker。

目前**没有安装这些候选 skill**，因为用户本轮要求是搜索和调查，不是安装第三方代码。

### 2.2 skills.sh 开放生态

`npx skills find` 还发现：

- `cat-xierluo/legal-skills@funasr-transcribe`；
- `zxkane/audio-transcriber@audio-transcribe`；
- `agntswrm/agent-media@audio-transcribe`；
- `framersai/agentos-skills@diarization`；
- 多个 Whisper、Deepgram、Azure、AssemblyAI skill。

这些结果大多是通用/云端/Whisper 路线。没有从搜索摘要中发现明确覆盖当前完整本地组合且可信度高于自行实现项目 CLI 的方案。

## 3. Hermes 原生 STT 状态

### 3.1 官方能力

Hermes 官方文档说明，STT provider 支持：

- `local`：本地 `faster-whisper`，无需 API key；
- `groq`：云端 Whisper；
- `openai`：云端 Whisper；
- `mistral`、`xai`：文档当前也列为可选 provider。

原生 STT 服务于：

- Telegram 等消息平台收到的语音消息自动转写；
- CLI/TUI push-to-talk；
- Discord 语音频道中的逐用户语音处理。

官方配置还明确指出：即使把 `stt.enabled` 设为 false，gateway 仍可缓存音频并把文件路径交给 Agent，适合自定义 diarization、alignment、archival 流水线。这与本项目未来集成方向兼容。

### 3.2 匿名验收环境配置与实际可用性

验收环境的 Hermes 配置包含：

```yaml
stt:
  enabled: true
  language: en
  local:
    model: base
```

但实测：

- `hermes tools list` 显示 `stt` toolset 在 CLI 平台为 **disabled**；
- 当前 Python 环境没有安装 `faster-whisper`；
- 没有可用的 Groq/OpenAI 等 STT API key；
- 因而“配置中 enabled”不等于当前本地 STT 已具备完整运行依赖；
- `language: en` 也不适合中文语音，未来若启用 Hermes 原生 STT，应改为空字符串自动检测或按需求设置中文。

Hermes 原生 STT 的目标是把一条语音变成文本，并不提供本项目所需的跨句段 CAM++ 聚类、会议级匿名 speaker 标签及标准化 JSON/SRT。因此它可以和 LocalTranscriber 并存，但不能代替本项目。

## 4. Hermes 插件调查

`hermes plugins list --plain --no-bundled` 没有输出，说明当前没有已启用的第三方/自定义插件；配置也显示：

```yaml
plugins:
  enabled: []
```

Hermes 发行版中发现以下相关 bundled plugin，但均未启用：

| 插件 | 版本 | 作用 | 是否适合当前离线文件转写 |
|---|---:|---|---|
| `google_meet` | 0.2.0 | 加入 Google Meet、读取实时字幕；高级模式可用实时音频 | 否，面向 Meet，且部分模式依赖外部实时服务/浏览器 |
| `teams-platform` | 1.0.0 | Microsoft Teams 消息平台适配 | 否 |
| `teams_pipeline` | 0.1.0 | Graph-backed、transcript-first 的 Teams 会议摘要管线 | 否，依赖 Teams/Graph 转录来源 |

未发现已经安装或启用的 FunASR、SenseVoice、CAM++、WhisperX、pyannote 音频转写插件。

## 5. MCP 调查

### 5.1 本机状态

`hermes mcp list` 的实测结果：

```text
No MCP servers configured.
```

所以当前 Hermes 没有连接任何 MCP，更没有音频/转写 MCP。

### 5.2 Hermes 官方 MCP Catalog

当前 catalog 只有：

- Blender；
- Figma；
- Linear；
- n8n；
- Unreal Engine。

没有官方一键安装的 audio、speech-to-text、Whisper、FunASR、SenseVoice 或 diarization MCP。

Hermes 本身支持本地 stdio 和远程 HTTP MCP，可用：

```bash
hermes mcp add NAME --command COMMAND --args ...
hermes mcp add NAME --url ENDPOINT
hermes mcp test NAME
hermes mcp configure NAME
```

但是当前需求只在这台机器上由 Hermes 调用本地批处理工具时，**CLI + skill 比 MCP 更少一层协议和常驻进程**。只有未来其他 MCP 客户端也要共享同一转写能力时，才建议把稳定 CLI 包成 stdio MCP。

## 6. 集成建议

### 近期

1. 先在 LocalTranscriber 项目中实现并验证独立 CLI；
2. 保留 JSON 为权威结果，Markdown/SRT 从 JSON 导出；
3. 真实样本通过后，为项目创建一个自有 Hermes skill；
4. skill 只封装已审查的本地命令，不复制不明社区脚本；
5. Hermes 收到音频时，可由 Agent 把本地缓存路径交给 CLI。

### 不建议现在做

- 不要为了“看起来集成”先开发 MCP；
- 不要直接启用 Google Meet/Teams 插件来替代本地文件转写；
- 不要让 Hermes 原生 faster-whisper 与 FunASR 同时抢占 CPU；
- 不要直接安装社区 skill 后运行其脚本而不审查；
- 不要把转写 HTTP 服务公开到公网。

### 后续可能的 Hermes 自有 skill

名称可考虑 `local-speaker-transcription`，触发条件包括：

- “转写这个会议录音”；
- “区分说话人并打时间戳”；
- “把这个音频导出 SRT”；
- “离线转写这个中文音频”。

该 skill 应包含：输入检查、单 worker 规则、CLI 命令、超时/后台任务处理、结果验证和媒体文件回传方式。应等 CLI 实测成功后创建，避免把未经验证的命令固化成 skill。

## 7. 调查结论

- 有多个相关社区 skill，但没有已安装且完整覆盖本方案的专用 skill；
- Hermes 有原生本地 `faster-whisper` STT 设计，但本机尚未安装依赖，且它不解决会议级说话人分离；
- Hermes 发行版包含 Google Meet 与 Teams 相关插件，但均未启用，也不适合代替本地离线批处理；
- 当前没有任何 MCP server，官方 MCP catalog 也没有音频转写 MCP；
- 最合理路径仍是：**独立 LocalTranscriber CLI → 真实样本验证 → 自有 Hermes skill → 有跨客户端需求时才考虑 stdio MCP**。

## 8. 2026-07-31 扩展安装决策与结果

### 已安装/登记

- 已将本项目登记为 Hermes Project：`localtranscriber`，主目录由 `${LOCALTRANSCRIBER_ROOT}` 指定；
- 已将工程约束复制并项目化为 `localtranscriber-engineering` Skill，存放于项目内 `.hermes/skills/`；
- 已通过 `skills.external_dirs` 将项目 Skill 目录注册到当前 Hermes profile；
- `hermes config check` 已通过配置结构检查。

该 Skill 提供 CPU/离线 STT、VAD、匿名说话人聚类、时间戳、规范 JSON、资源限制、真实样本和断网验收的工程约束。它是开发指导，不安装模型，也不代表转写能力已可运行。

### 明确不安装

- **第三方 FunASR Skill：暂不安装。** `funasr-asr` 和 `funasr-transcribe-skill` 均为 community 来源；前者的预览未证明 CAM++ 及本项目规范 JSON，后者使用 OpenClaw 固定路径且主模型为 Paraformer，不符合当前项目边界。项目应先实现自己的经测试 CLI。
- **云端 transcribe Skill：不安装。** OpenAI 官方候选依赖云 API，与离线优先目标冲突。
- **Hermes 插件：不启用。** 当前 bundled Meet/Teams 插件处理会议平台字幕或 Graph transcript，不提供本地 FunASR + CAM++ 文件流水线。
- **MCP：不安装。** 当前官方 Catalog 仅有 Blender、Figma、Linear、n8n、Unreal Engine，没有语音转写 MCP；单机阶段引入 MCP 只会增加协议和常驻组件。

后续扩展门槛和执行顺序见 [LocalTranscriber 实施计划的阶段 D](plan/01-localtranscriber-implementation-plan.md#8-阶段-dhermes-调用集成)。

## 9. 阶段 D 最终集成决策（2026-07-31）

- 已新增并验证项目 Skill：`.hermes/skills/local-speaker-transcription/SKILL.md`；
- Hermes 已在 Telegram 会话中以后台进程真实调用 CLI，读回 canonical JSON、Markdown、TXT、SRT 和媒体元数据并完成文件回传；
- 当前不开发原生插件：CLI + Skill 已满足单机调用，没有频繁使用及结构化工具能显著降低误用的证据；
- 当前不安装 MCP：`hermes mcp list` 现场确认没有配置 server，也没有多个 MCP 客户端共享需求；
- 当前不提供 HTTP 服务，保持零新增监听端口和最小暴露面。

详细证据见[阶段 D Hermes 集成验收](acceptance/hermes-integration.md)。
