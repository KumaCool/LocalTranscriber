# 01 LocalTranscriber 实施计划

**进度状态：** `进行中`

**关联方案：** [LocalTranscriber：本地离线语音转写方案](../solution.md)

## 1. 文档约束

1. `docs/plan/` 中的计划文件名必须以两位编号开头，例如 `01-`、`02-`。
2. **一个方案只对应一份计划文档。** 同一方案的阶段和任务必须作为该计划内的章节，不得拆成多个计划文件。
3. 计划必须在标题后记录总体 `进度状态`；各阶段和任务也必须记录状态。
4. 状态仅使用：`待开始`、`进行中`、`受阻`、`已完成`、`已取消`。
5. 计划必须包含“方案关联”，链接到方案及其对应章节。
6. 状态必须由当前验证证据支撑；仅有代码、文件或配置不等于完成。

## 2. 目标与执行顺序

把 [方案](../solution.md) 落地为可验证的 CPU 离线语音转写工具，依次完成：

```text
阶段 A：环境、依赖与模型冒烟
  → 阶段 B：CLI、任务模型与结构化输出
    → 阶段 C：真实样本评估与离线验收
      → 阶段 D：Hermes 调用集成
```

不得绕过上游验收而将下游阶段标为 `已完成`。

## 3. 方案关联

| 计划阶段 | 对应方案 | 落实内容 |
|---|---|---|
| 阶段 A | [§2 主机约束](../solution.md#2-主机约束2026-07-31-实测)、[§3 技术选型](../solution.md#3-技术选型)、[§6 资源与离线策略](../solution.md#6-资源队列和离线策略)、[§9](../solution.md#9-分阶段实施与验收) | 隔离环境、资源探针、模型预取、组合模型冒烟 |
| 阶段 B | [§5 输入处理和输出](../solution.md#5-输入处理和输出设计)、[§6](../solution.md#6-资源队列和离线策略)、[§7 项目形态](../solution.md#7-项目形态建议)、[§9](../solution.md#9-分阶段实施与验收) | 媒体标准化、任务状态、CLI、规范 JSON 和导出器 |
| 阶段 C | [§4 语义](../solution.md#4-说话人和时间戳语义)、[§6](../solution.md#6-资源队列和离线策略)、[§9](../solution.md#9-分阶段实施与验收) | 六类真实样本、质量与资源评估、断网验收 |
| 阶段 D | [§8 Hermes 集成](../solution.md#8-hermes-集成策略)、[§9](../solution.md#9-分阶段实施与验收)、[集成调查](../skills-and-hermes-integration.md) | 项目调用 Skill、端到端调用、插件/MCP 条件决策 |

## 4. 总体进度

| 阶段 | 状态 | 前置条件 | 完成证据 |
|---|---|---|---|
| A 环境、依赖与模型冒烟 | `已完成` | 无 | [阶段 A 验收记录](../acceptance/phase-a.md)：环境可重建、模型已缓存、双人冒烟及资源记录通过 |
| B CLI、任务模型与结构化输出 | `已完成` | 阶段 A 完成 | [阶段 B 验收记录](../acceptance/phase-b.md)：CLI 真实运行、规范 JSON 可读回、导出及错误路径测试通过 |
| C 真实样本评估与离线验收 | `已完成` | 阶段 B 完成 | [评估矩阵](../acceptance/evaluation-matrix.md)及[断网验收](../acceptance/offline-verification.md)：六类样本已运行，限制已记录，缓存模型断网运行成功 |
| D Hermes 调用集成 | `已完成` | 阶段 C 完成 | [阶段 D 验收记录](../acceptance/hermes-integration.md)：Hermes 后台调用、产物验证和 Telegram 回传通过；无需插件/MCP |

---

## 5. 阶段 A：环境、依赖与模型冒烟

**阶段状态：** `已完成`

### 5.1 目标

建立隔离、可复现的 CPU 推理环境，缓存 SenseVoiceSmall、FSMN-VAD 与 CAM++，并用短中文双人音频验证 FunASR 组合结果确实含有文本、句段起止时间和匿名说话人编号。

### 5.2 任务

#### A1. 建立项目骨架和隔离环境

**状态：** `已完成`

- 创建 `pyproject.toml`、锁文件、`src/local_transcriber/`、`tests/`、`var/`；
- 依赖只安装到项目虚拟环境，不修改 Hermes 全局 Python；
- 添加 `.gitignore`，排除模型缓存、虚拟环境、输入、临时文件和产物；
- 固定经实测的 FunASR、Torch、ModelScope 等版本。

**验证：** 新环境可从锁文件重建，包依赖检查通过。

#### A2. 记录运行环境探针

**状态：** `已完成`

- 记录 CPU、线程、内存、Swap、磁盘、Python、FFmpeg/ffprobe；
- 默认 worker 为 1；
- 分别以 2、3 个推理线程运行冒烟基准，不预判最佳值。

**验证：** 探针结果保存为验收证据，且符合方案资源边界。

#### A3. 实现显式模型预取

**状态：** `已完成`

- 增加 `models pull`；
- 预取 `iic/SenseVoiceSmall`、`fsmn-vad`、`cam++`；
- 记录模型版本、缓存路径、来源和许可证；
- 下载失败时不得标记“离线可用”。

**验证：** 三类模型缓存齐全，第二次执行不重复下载完整模型。

#### A4. 运行组合模型冒烟

**状态：** `已完成`

- 使用真实、获得授权的短中文双人音频；
- 在 CPU 上组合 ASR、VAD 和 speaker model；
- 保存未经应用层加工的原始结果样例；
- 验证实际版本的 `sentence_info` 字段，不照搬示例猜测结构。

**验收条件：**

- 至少一个句段有非空文本；
- 有可解析的句段起止毫秒；
- 双人样本出现可用匿名 speaker ID；
- 记录耗时、音频时长、RTF、峰值 RSS 和线程数；
- 记录重叠语音、短应答等限制。

#### A5. 固化回归测试与证据

**状态：** `已完成`

- 测试缺字段、空文本、异常时间范围和无 speaker 输出；
- 只提交脱敏冒烟元数据，不提交未经许可的录音；
- 更新阶段和任务状态。

### 5.3 预计文件

- `pyproject.toml`、锁文件、`.gitignore`
- `src/local_transcriber/models.py`
- `src/local_transcriber/environment.py`
- `tests/test_models.py`
- `tests/test_environment.py`
- `docs/acceptance/` 下的验收记录

### 5.4 阶段完成定义

隔离环境可重建、三类模型已缓存、真实双人冒烟成功、资源数据已记录且测试通过。

**完成证据：** [阶段 A 验收记录](../acceptance/phase-a.md)。

---

## 6. 阶段 B：CLI、任务模型与结构化输出

**阶段状态：** `已完成`

### 6.1 目标

交付可恢复的本地批处理 CLI：安全解析媒体、串行转写、生成权威 JSON，并从 JSON 导出 Markdown/TXT/SRT。

### 6.2 任务

#### B1. 定义并测试规范数据模型

**状态：** `已完成`

- 定义 `schema_version`、source、engine、job、segments；
- 句段至少包含 `start_ms`、`end_ms`、`speaker`、`text`；
- 校验时间非负、结束晚于开始、speaker 为匿名标签；
- 不加入未经真实上游验证的置信度或字级时间字段。

**验证：** 合法和非法文档测试通过，JSON 可写出并等价读回。

#### B2. 实现安全媒体探测与标准化

**状态：** `已完成`

- 使用 ffprobe 参数数组读取元数据并明确选择音轨；
- 使用 FFmpeg 参数数组生成 16 kHz、单声道、PCM WAV；
- 文件路径不得拼入 shell 命令；
- 对不支持、无音轨和损坏媒体给出可诊断错误。

**验证：** WAV、MP3、M4A 和含音轨视频夹具测试通过。

#### B3. 实现单 worker 任务生命周期

**状态：** `已完成`

- 状态限定为 `queued/running/succeeded/failed/cancelled`；
- 输入、工作和输出目录分离；
- 同时只允许一个模型任务；
- 失败保留诊断，成功按策略清理临时 WAV；
- 取消保留结构化状态。

**验证：** 状态迁移、互斥、失败恢复和取消测试通过。

#### B4. 实现转写 CLI

**状态：** `已完成`

```bash
local-transcriber models pull
local-transcriber transcribe INPUT --output-dir OUTPUT
local-transcriber transcribe INPUT --speakers 2
local-transcriber export RESULT.json --format srt
```

- `--speakers` 是聚类约束，不是姓名识别；
- 返回码区分成功、输入错误、模型错误和取消；
- 最终格式全部从规范 JSON 派生。

**验证：** 帮助、参数错误、成功及失败路径集成测试通过。

#### B5. 实现导出器

**状态：** `已完成`

- Markdown/TXT 显示时间范围和匿名说话人；
- SRT 使用句段时间，不伪造字级时间；
- 不跨 speaker 合并句段；
- 重新解析 SRT，验证编号和时间单调递增。

**验证：** JSON、Markdown、TXT、SRT 黄金样例测试通过。

#### B6. 端到端验收

**状态：** `已完成`

- 用真实媒体完成探测、标准化、推理、JSON、Markdown 和 SRT；
- 逐一读回产物；
- 记录退出码、路径、耗时和资源；
- 更新 README 和本计划状态。

### 6.3 预计文件

- `src/local_transcriber/schema.py`
- `src/local_transcriber/media.py`
- `src/local_transcriber/jobs.py`
- `src/local_transcriber/engine.py`
- `src/local_transcriber/exporters.py`
- `src/local_transcriber/cli.py`
- `tests/` 对应测试

### 6.4 阶段完成定义

CLI 真实执行成功，规范 JSON 可读回，Markdown/TXT/SRT 通过验证，失败和取消路径有测试。

**完成证据：** [阶段 B 验收记录](../acceptance/phase-b.md)。

---

## 7. 阶段 C：真实样本评估与离线验收

**阶段状态：** `已完成`

### 7.1 目标

用代表性真实音频评估转写、说话人聚类、时间戳与资源表现，并在断网条件下证明缓存后的离线运行能力。

### 7.2 样本矩阵

| 场景 | 最低要求 | 状态 |
|---|---|---|
| 安静双人 | 两位说话人、清晰近场 | `已完成` |
| 噪声双人 | 稳态或环境噪声 | `已完成` |
| 多人会议 | 三人或以上 | `已完成`（受控短代理样本；聚类质量不达标） |
| 重叠讲话 | 含同时说话片段 | `已完成`（未能分离，记录为限制） |
| 中英混合 | 中文为主、包含英文 | `已完成` |
| 电话音质 | 窄带或强压缩 | `已完成`（G.711 A-law 信道仿真） |

样本必须有合法使用权限，原始录音默认不入库。

### 7.3 任务

#### C1. 建立评估记录格式

**状态：** `已完成`

记录媒体信息、模型和参数、处理时间、RTF、峰值 RSS、人工修订量、speaker 混淆/切换、时间戳偏差和重叠语音表现。

#### C2. 完成六类真实样本运行

**状态：** `已完成`

- 每类至少一个样本；
- 使用统一基线，参数调整单独记录；
- 保存规范 JSON 和评估记录；
- 不以单个干净样本代替完整矩阵。

#### C3. 比较线程和已知人数参数

**状态：** `已完成`

- 比较 2 与 3 个推理线程；
- 比较自动人数估计和 `--speakers N`；
- 根据 RTF、RSS 和质量选择默认值。

#### C4. 完成断网验收

**状态：** `已完成`

- 模型预取完成后禁止网络访问；
- 重新运行一个已知样本；
- 证明没有拉取模型或调用云 API；
- 保存隔离方式、命令、退出码和产物校验结果。

#### C5. 形成结论与限制清单

**状态：** `已完成`

- 给出默认线程和 speaker 参数建议；
- 明确不承诺姓名识别、重叠语音完美分离或字级时间；
- 质量不达标时标记 `受阻` 或记录后续实验，不把冒烟描述为质量验收。

### 7.4 预计文件

- `docs/acceptance/evaluation-matrix.md`
- `docs/acceptance/offline-verification.md`
- 可公开的脱敏 JSON
- 本地、不入库的录音和详细产物

### 7.5 阶段完成定义

六类样本均有结果，资源指标和限制已记录，至少一个断网缓存运行成功。

**完成证据：** [评估矩阵](../acceptance/evaluation-matrix.md)及[断网验收](../acceptance/offline-verification.md)。多人和重叠场景的质量未达标，已按计划明确记录为限制，不将运行成功误述为质量通过。

---

## 8. 阶段 D：Hermes 调用集成

**阶段状态：** `已完成`

### 8.1 目标

CLI 稳定并通过真实验收后，让 Hermes 安全调用 LocalTranscriber、监控长任务、验证并回传 JSON/Markdown/SRT，不提前引入不必要的常驻服务。

### 8.2 当前扩展决策

- 项目已登记为 Hermes Project；
- 项目内已放置并注册 `localtranscriber-engineering` Skill；
- 暂不安装第三方 FunASR 执行 Skill：社区候选未证明完整实现 CAM++、规范 JSON 和项目资源约束；
- 不启用 Meet/Teams 插件：不提供本地文件 diarization；
- 不安装 MCP：官方 Catalog 没有语音转写 MCP，单机阶段 CLI + Skill 边界更小。

这些状态只表示工程指导已就位，不表示转写引擎已经实现。

### 8.3 任务

#### D1. 创建经验证的项目调用 Skill

**状态：** `已完成`

CLI 真实验收后新增 `local-speaker-transcription`，包含输入检查、项目环境调用、单 worker、长任务后台执行、产物读回验证、Telegram 文件回传以及错误/取消/敏感录音规则。

不得把未经执行的命令固化为“可用流程”。

**完成证据：** 已新增并测试 `.hermes/skills/local-speaker-transcription/SKILL.md`，其命令、后台执行、退出码、产物验证、Telegram 回传及隐私规则均来自已执行流程。

#### D2. 验证 Hermes 端到端调用

**状态：** `已完成`

- 从 Hermes 会话提供授权测试音频路径；
- 调用项目 CLI 并等待完成；
- 读取并核验结构化结果；
- 回传用户要求的产物；
- 核对 speaker 标签、时间戳和文件完整性。

**完成证据：** Hermes 使用授权双人样本真实完成后台转写，退出码 `0`、状态 `succeeded`，读回并验证 2 个句段、2 个匿名 speaker 和五个完整产物，并在 Telegram 回传 Markdown、SRT 与 canonical JSON。详见[阶段 D 验收记录](../acceptance/hermes-integration.md)。

#### D3. 决定是否需要原生插件

**状态：** `已完成`

仅当 CLI 已频繁使用且结构化工具接口能显著降低误用时评估。插件必须只包装既有 CLI、验证运行条件、不扩大暴露面，并在网关重启后的新会话中完成真实调用。

**决策：** 当前不开发插件。单机 Hermes 的 Skill + CLI 已覆盖需求，尚无频繁使用及结构化工具显著降低误用的证据；避免增加全局配置、网关重启和维护面。

#### D4. 决定是否需要 stdio MCP

**状态：** `已完成`

仅当多个 MCP 客户端需要共享能力时推进；优先 stdio，复用规范 JSON，保持全局单 worker，不监听公网，并通过 `hermes mcp test` 和真实调用验证。只有本机 Hermes 使用时保持“不安装 MCP”。

**决策：** 当前保持不安装 MCP。现场确认未配置 MCP server，且只有本机 Hermes 使用；同时不提供 HTTP 服务或任何监听端口。

### 8.4 预计文件

- `.hermes/skills/local-speaker-transcription/SKILL.md`（CLI 稳定后）
- 可选插件或 MCP 文件（只有满足决策条件后）
- `docs/acceptance/hermes-integration.md`

### 8.5 阶段完成定义

Hermes 使用项目专用 Skill 真实完成一次授权音频转写，验证并回传产物。插件和 MCP 不是必选项。

---

## 9. 计划整体完成定义

只有以下条件全部满足，整体状态才能改为 `已完成`：

- 隔离环境可重建，模型可显式预取；
- FunASR + SenseVoiceSmall + FSMN-VAD + CAM++ 在 CPU 上真实运行；
- CLI、任务状态、规范 JSON 和导出器通过测试与端到端验收；
- 六类真实样本完成评估；
- 模型缓存后的断网运行成功；
- Hermes 真实调用、验证并回传产物；
- 所有阶段状态及验收记录已同步更新。
