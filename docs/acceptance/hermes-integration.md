# 阶段 D 验收记录：Hermes 调用集成

**状态：** `已完成`

**执行环境：** 匿名受限 CPU 验收主机

**执行日期：** 2026-07-31

## 1. 已交付能力

- 新增项目专用 Hermes Skill：`.hermes/skills/local-speaker-transcription/SKILL.md`；
- 固化授权输入检查、项目路径、模型缓存、单 worker、2 线程及后台任务规则；
- 固化退出码、取消、worker 冲突、隐私和敏感产物处理规则；
- 固化规范 JSON、Markdown、TXT、SRT、媒体元数据的读回校验；
- 固化 Telegram `MEDIA:` 文件回传规则；
- 新增 Skill frontmatter、运行契约及语义/隐私边界测试。

Skill 明确区分匿名 speaker 聚类与身份识别、句段时间戳与字级对齐，并要求多人及重叠讲话结果人工复核。

## 2. Hermes 真实端到端验收

Hermes 在当前 Telegram 会话中选择阶段 C 已授权的双人中文样本，先用 `ffprobe` 验证音轨，再以受跟踪的后台进程运行：

```bash
uv run local-transcriber transcribe \
  "${LOCALTRANSCRIBER_ROOT}/var/input/phase-c/quiet-two-speaker.wav" \
  --output-dir var/output/hermes \
  --runtime-dir var/work/hermes \
  --cache-dir var/cache/models \
  --threads 2
```

实际结果：

```text
后台会话：       proc_ec2d61da683c
退出码：         0
Job ID：         20260731T050406-f83508f5
任务状态：       succeeded
引擎：           FunASR 1.3.30 / CPU / 2 threads
音频：           WAV / PCM S16LE / 16 kHz / mono
音频时长：       23.770 s
句段：           2
匿名 speaker：   SPEAKER_00、SPEAKER_01
```

Hermes 独立解析并核验：

- `schema_version == 1`；
- `job.status == succeeded` 且 `job.error == null`；
- source 路径、大小、SHA-256 和时长齐全，SHA-256 与原文件重算一致；
- 每个句段起止时间为合法整数范围；
- speaker 标签均以 `SPEAKER_` 开头；
- 引擎记录为 CPU、2 线程及三个固定模型；
- `media.json` 可解析且时长与规范 JSON 一致；
- 五个产物均非空并已读回。

产物位于 Git 忽略路径：

```text
var/output/hermes/20260731T050406-f83508f5/result.json
var/output/hermes/20260731T050406-f83508f5/media.json
var/output/hermes/20260731T050406-f83508f5/transcript.md
var/output/hermes/20260731T050406-f83508f5/transcript.txt
var/output/hermes/20260731T050406-f83508f5/transcript.srt
```

本阶段最终通过 Telegram 原生媒体附件回传 Markdown、SRT 和 canonical JSON，完成“授权音频 → Hermes 调用 CLI → 后台等待 → 产物验证 → Telegram 回传”的计划闭环。

## 3. 原生插件决策

**结论：当前不开发、不启用 LocalTranscriber 原生插件。**

理由：

- 当前只有本机 Hermes 使用，CLI + Skill 已覆盖结构化调用、错误处理及回传；
- 还没有足够的频繁使用证据证明专用工具 schema 能显著减少误用；
- 插件会增加全局配置、网关重启、新会话回归及长期维护面；
- 当前 bundled Google Meet/Teams 插件处理会议平台字幕或 Graph transcript，不是本地 FunASR + CAM++ 文件流水线；
- `hermes plugins list` 现场检查未发现已启用的本项目转写插件。

只有在频繁使用后确认自然语言 Skill 调用仍易误用，并且结构化工具接口能显著改善输入验证、状态查询或产物选择时，才重新评估。插件仍应只包装既有 CLI，不复制模型逻辑，也不得开放网络监听。

## 4. MCP 与网络服务决策

**结论：当前不安装 MCP，也不提供 HTTP 服务。**

现场 `hermes mcp list` 返回 `No MCP servers configured`。当前不存在多个 MCP 客户端共享能力的需求；stdio MCP 会额外增加协议和配置，但不改善单机 Hermes 的核心流程。HTTP 服务更会引入常驻进程和监听面，与离线批处理及最小暴露原则不符。

若未来多个 MCP 客户端确需共享能力，才考虑只提供 stdio MCP，并复用 canonical JSON、全局单 worker 锁及相同隐私规则；不得默认监听公网或私网端口。

## 5. 已知限制

- speaker 是匿名标签，不代表人物身份，且跨运行不保证稳定；
- 时间戳是句段级，不是字级强制对齐；
- 当前样本正文仍包含 SenseVoice 富文本标签和重复内容；
- 多人和重叠讲话聚类质量不可靠，必须人工复核；
- 峰值内存历史验收约 3.2 GiB，因此维持单 worker 和 2 线程；
- Skill 文件在当前长会话中不会重新注入系统提示；本次验收直接按刚写入并读回的同一运行契约执行。新会话会通过已注册的项目 Skill 目录发现该 Skill。

## 6. 验收结论

阶段 D 已完成。Hermes 已真实调用 LocalTranscriber 处理授权音频，等待后台任务完成，校验 canonical JSON 和全部派生产物，并通过当前 Telegram 会话回传文件。当前最小且充分的集成边界是：

```text
Hermes Agent → 项目 Skill → 本地 CLI → canonical JSON → 派生导出
```

无需插件、MCP 或 HTTP 服务。
