# LocalTranscriber：本地离线语音转写方案

## 1. 目标与边界

本项目面向当前 Linux 主机，提供以中文为主的离线音频批量转写：

- 区分不同说话人，输出稳定的匿名标签（如 `Speaker 0`、`Speaker 1`）；
- 输出句段级开始、结束时间戳；
- 模型下载并缓存后，不依赖云端 API；
- 支持常见音频/视频输入，并输出 JSON、Markdown/TXT、SRT；
- 优先保证资源可控和任务可恢复，不追求在线实时字幕。

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
| 内存 | 资源受限 | 单任务运行；避免多个模型进程并行 |
| Swap | 仅作应急 | 不能依赖 Swap 提升吞吐 |
| GPU | 无计算 GPU | 全部采用 CPU 路径 |
| 磁盘 | 可容纳模型缓存和中等规模任务 | 仍需源文件/产物清理策略 |
| Python | 3.11 | 适合建立项目独立虚拟环境 |
| FFmpeg | 6.x | 已具备音视频解码和标准化前置条件 |

运行策略：默认一个 worker、一个文件；CPU 线程建议 2～3，模型常驻与否后续通过基准测试决定。

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

- 默认 worker 数为 1；
- 同一时间只加载一套模型；
- 设置 PyTorch/OMP/MKL 线程上限，基准后默认取 2 或 3；
- 任务状态至少包含 `queued/running/succeeded/failed/cancelled`；
- 原始输入、临时 WAV、最终产物和模型缓存分目录管理；
- 成功后临时 WAV 可按策略删除，失败时保留诊断材料；
- 首次启动显式执行模型预取；只有预取完成后才宣称“可离线”；
- 断网验收必须在清空网络访问条件下重新跑一段已缓存模型的测试音频。

## 7. 项目形态建议

首期做本地 CLI 和批处理队列，不先做长期暴露端口的 Web 服务：

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
│   └── output/
└── README.md
```

建议 CLI：

```bash
local-transcriber models pull
local-transcriber transcribe recording.m4a --output-dir ./output
local-transcriber transcribe recording.m4a --speakers 2
local-transcriber export result.json --format srt
```

将来若确需 UI，应仅监听 localhost 或 WireGuard/Tailscale 私网地址，并通过队列串行提交任务，不能让每个 HTTP 请求直接启动一个模型进程。

## 8. Hermes 集成策略

Hermes 自带 STT 主要用于 Telegram/CLI/Discord 的短语音消息转文字，官方本地 provider 是 `faster-whisper`。它不提供 CAM++ 说话人聚类，也不等价于本项目的会议文件批处理。

推荐分层：

1. **LocalTranscriber 独立 CLI**：负责长音频、时间戳、说话人区分和结构化产物；
2. **Hermes skill（后续创建）**：告诉 Agent 在收到“转写会议/区分说话人”等请求时如何调用 CLI、读取 JSON 并回传文件；
3. **可选 Hermes 原生 tool/plugin**：只有当 CLI 稳定且频繁使用时再封装；
4. **暂不开发 MCP**：工具只服务于本机 Hermes 时，本地 CLI + skill 更简单。若未来多个 Agent 客户端都要共享转写服务，再考虑 stdio MCP，避免开放公网端口。

## 9. 分阶段实施与验收

本方案的全部实施阶段已合并到一份可跟踪的计划文档：

- [LocalTranscriber 实施计划](plan/01-localtranscriber-implementation-plan.md)

方案保留目标与验收边界，计划负责阶段顺序、任务和进度状态。同一方案不再拆分为多份计划文档。

## 10. 决策结论

采用 **FunASR + SenseVoiceSmall + FSMN-VAD + CAM++** 作为主线；采用单任务 CPU 批处理，不以实时服务为目标。先交付可验证的 CLI 和规范 JSON，再做 Hermes skill；当前没有必要为了集成而引入 MCP。