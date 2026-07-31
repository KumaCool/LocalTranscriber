# 01 LocalTranscriber 实施计划

**进度状态：** `已完成`

**关联方案：** [LocalTranscriber：本地离线语音转写方案](../design/solution.md)

## 1. 文档约束

1. `docs/plan/` 中的计划文件名必须以两位编号开头，例如 `01-`、`02-`。
2. **一个方案只对应一份计划文档。** 同一方案的阶段和任务必须作为该计划内的章节，不得拆成多个计划文件。
3. 计划必须在标题后记录总体 `进度状态`；各阶段和任务也必须记录状态。
4. 状态仅使用：`待开始`、`进行中`、`受阻`、`已完成`、`已取消`。
5. 计划必须包含“方案关联”，链接到方案及其对应章节。
6. 状态必须由当前验证证据支撑；仅有代码、文件或配置不等于完成。

## 2. 目标与执行顺序

把 [方案](../design/solution.md) 落地为可验证的 CPU 离线语音转写工具，依次完成：

```text
阶段 A：环境、依赖与模型冒烟
  → 阶段 B：CLI、任务模型与结构化输出
    → 阶段 C：真实样本评估与离线验收
      → 阶段 D：Hermes 调用集成
        → 阶段 E：真实转写进度与动态 ETA
          → 阶段 F：前后台双模式、批量队列与资源控制
            → 阶段 G：版本化发布与更新日志
```

不得绕过上游验收而将下游阶段标为 `已完成`。

## 3. 方案关联

| 计划阶段 | 对应方案 | 落实内容 |
|---|---|---|
| 阶段 A | [§2 主机约束](../design/solution.md#2-主机约束2026-07-31-实测)、[§3 技术选型](../design/solution.md#3-技术选型)、[§6 资源与离线策略](../design/solution.md#6-资源队列和离线策略)、[§10](../design/solution.md#10-分阶段实施与验收) | 隔离环境、资源探针、模型预取、组合模型冒烟 |
| 阶段 B | [§5 输入处理和输出](../design/solution.md#5-输入处理和输出设计)、[§6](../design/solution.md#6-资源队列和离线策略)、[§7 项目形态](../design/solution.md#7-项目形态建议)、[§10](../design/solution.md#10-分阶段实施与验收) | 媒体标准化、任务状态、CLI、规范 JSON 和导出器 |
| 阶段 C | [§4 语义](../design/solution.md#4-说话人和时间戳语义)、[§6](../design/solution.md#6-资源队列和离线策略)、[§10](../design/solution.md#10-分阶段实施与验收) | 六类真实样本、质量与资源评估、断网验收 |
| 阶段 D | [§8 Hermes 集成](../design/solution.md#8-hermes-集成策略)、[§10](../design/solution.md#10-分阶段实施与验收)、[集成调查](../design/skills-and-hermes-integration.md) | 项目调用 Skill、端到端调用、插件/MCP 条件决策 |
| 阶段 E | [§6 资源、队列和离线策略](../design/solution.md#6-资源队列和离线策略)、[§7 项目形态](../design/solution.md#7-项目形态建议)、[§8 Hermes 集成](../design/solution.md#8-hermes-集成策略) | 阶段化进度、FunASR 原生回调、动态 ETA、持久化状态与 Hermes 进度通知 |
| 阶段 F | [§6.1 前后台运行](../design/solution.md#61-前台与后台运行模型)、[§6.2 批量转写](../design/solution.md#62-多文件与目录批量转写)、[§6.3 并发](../design/solution.md#63-有界并发模型)、[§6.4 性能配置](../design/solution.md#64-性能占用配置)、[§6.5 状态](../design/solution.md#65-任务批次与进度状态) | 默认前台、显式 `--bg`、多文件/目录批量、持久化调度、有界并发和 50% CPU 默认预算 |
| 阶段 G | [§9 版本、发布与更新日志](../design/solution.md#9-版本发布与更新日志) | 单一版本源、CLI 版本、CHANGELOG、构建安装验证、tag 与 GitHub Release 门禁 |

## 4. 总体进度

| 阶段 | 状态 | 前置条件 | 完成证据 |
|---|---|---|---|
| A 环境、依赖与模型冒烟 | `已完成` | 无 | [阶段 A 验收记录](../acceptance/phase-a.md)：环境可重建、模型已缓存、双人冒烟及资源记录通过 |
| B CLI、任务模型与结构化输出 | `已完成` | 阶段 A 完成 | [阶段 B 验收记录](../acceptance/phase-b.md)：CLI 真实运行、规范 JSON 可读回、导出及错误路径测试通过 |
| C 真实样本评估与离线验收 | `已完成` | 阶段 B 完成 | [评估矩阵](../acceptance/evaluation-matrix.md)及[断网验收](../acceptance/offline-verification.md)：六类样本已运行，限制已记录，缓存模型断网运行成功 |
| D Hermes 调用集成 | `已完成` | 阶段 C 完成 | [阶段 D 验收记录](../acceptance/hermes-integration.md)：Hermes 后台调用、产物验证和 Telegram 回传通过；无需插件/MCP |
| E 真实转写进度与动态 ETA | `已完成` | 阶段 D 完成 | [阶段 E 验收记录](../acceptance/progress-and-eta.md)：实际工作量进度、动态 ETA、脱敏状态查询、Hermes 按需报告及三次长音频校准通过 |
| F 前后台双模式、批量队列与资源控制 | `已完成` | 阶段 E 完成 | [阶段 F 验收记录](../acceptance/batch-background-resources.md)：默认前台、显式 `--bg`、批量、恢复、离线及资源自动降级均通过真实验收 |
| G 版本化发布与更新日志 | `已完成` | 阶段 F 完成 | [阶段 G 发布验收](../acceptance/release.md)：0.2.1 版本、CHANGELOG、构建安装、tag、Release 及远端核验通过 |

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

在阶段 E 加入后，原阶段 A-D 的历史验收结论保持有效；阶段 E 已完成，计划总体保持 `进行中`，下一阶段为 F。

## 9. 阶段 E：真实转写进度与动态 ETA

**阶段状态：** `已完成`

### 9.1 目标

在不制造匀速假进度的前提下，为长音频转写提供可持久化、可查询的阶段、百分比和动态剩余时间范围，并让 Hermes 能在用户询问或约定通知频率下报告真实进展。

### 9.2 进度语义

- 进度必须由实际执行事件驱动，不得仅以“已运行时间 ÷ 历史预计总时间”生成；
- 总进度采用阶段权重：媒体探测与标准化 `0%–5%`、模型加载与 VAD `5%–15%`、ASR 与说话人处理 `15%–95%`、结果整理与导出 `95%–100%`；
- 核心推理阶段使用当前 FunASR `progress_callback(current, total)`，将实际上游批次进度映射到 `15%–95%`；
- 百分比只能单调递增，任务未成功前不得显示 `100%`；失败和取消必须保留最后可信进度并显示终态；
- ETA 根据已完成批次的实际速度动态修正，以时间范围而非虚假精确到秒的单点值展示；样本不足或波动过大时显示“计算中”；
- UI/消息必须明确百分比和 ETA 是工程估算，不代表模型按匀速运行。

### 9.3 任务

#### E1. 定义持久化进度数据模型

**状态：** `已完成`

- 在任务记录中加入 `stage`、`progress_percent`、`processed_units`、`total_units`、`eta_low_seconds`、`eta_high_seconds` 和 `updated_at`；
- 定义 `probing/normalizing/loading/vad/transcribing/finalizing` 等稳定阶段值；
- 旧任务记录缺少新字段时必须安全读回，并返回明确默认值；
- 所有进度更新使用原子写入，不破坏现有单 worker 锁和终态迁移。

**预计文件：**

- `src/local_transcriber/jobs.py`
- `src/local_transcriber/schema.py`（仅当 canonical result 需要记录最终进度摘要）
- `tests/test_jobs.py`
- `tests/test_schema.py`

**验证：** 先写失败测试，再验证合法更新、单调性、兼容旧记录、失败/取消终态及并发安全。

#### E2. 接入阶段事件和 FunASR 原生进度回调

**状态：** `已完成`

- 在 CLI 的媒体探测、标准化、模型初始化、推理和导出边界更新阶段；
- `TranscriptionEngine.transcribe()` 接收项目内部进度回调，并转接 FunASR `progress_callback(current, total)`；
- 回调异常不得中断转写，只记录安全诊断；
- 禁止解析 tqdm 文本作为正式进度协议；必要时关闭上游进度条，避免终端控制字符污染日志；
- 上游回调缺失、总量为零或数值异常时保持最近可信进度，不伪造推进。

**预计文件：**

- `src/local_transcriber/engine.py`
- `src/local_transcriber/cli.py`
- `tests/test_engine.py`
- `tests/test_cli.py`

**验证：** 用 fake engine/FunASR 回调覆盖正常、重复、倒退、越界、零总量和异常回调；确认成功前最高为 `99%`、成功写出后为 `100%`。

#### E3. 实现动态 ETA 和稳定化策略

**状态：** `已完成`

- 使用已完成工作单元、单调时钟和近期批次速度计算 ETA；
- 设置最小观测门槛，在数据不足时不显示 ETA；
- 对短时速度波动进行平滑，但不得让 ETA 长时间掩盖真实停滞；
- 输出 `eta_low_seconds` 与 `eta_high_seconds`，范围应覆盖正常批次波动；
- 模型加载、最终聚类和导出等非线性阶段采用已测量的阶段开销，不把核心回调直接当作全流程百分比；
- 机器负载显著变化或回调长时间无更新时，扩大 ETA 范围并标记低置信度。

**预计文件：**

- 新建 `src/local_transcriber/progress.py`
- 新建 `tests/test_progress.py`
- 修改 `src/local_transcriber/cli.py`

**验证：** 使用确定性虚拟时钟测试快速、慢速、抖动、停滞和恢复；ETA 不得为负，百分比不得倒退或提前完成。

#### E4. 提供可查询状态并接入 Hermes 通知

**状态：** `已完成`

- 增加只读任务状态命令，按任务 ID 返回机器可读 JSON；不得为此引入 HTTP 服务或监听端口；
- Hermes 启动转写后记录任务 ID，可在用户询问时读取阶段、百分比和 ETA 范围；
- 只有用户要求定时通知时才主动发送；默认不紧密轮询，不输出每个上游批次；
- 通知去重：阶段未变化且百分比变化低于阈值时不重复发送；
- 任务完成、失败或取消时发送一次终态，并继续按既有流程验证产物。

**预计文件：**

- `src/local_transcriber/cli.py`
- `tests/test_cli.py`
- `.hermes/skills/local-speaker-transcription/SKILL.md`
- `tests/test_skill.py`

**验证：** CLI 状态 JSON 可解析；Hermes 能读取一个运行中任务的进度，且通知不会启动第二个 worker、泄露输入内容或绕过产物验证。

#### E5. 真实长音频校准与验收

**状态：** `已完成`

- 使用现有获授权的约 27 分钟中文音频，在固定 `--threads 2` 下至少运行三次；
- 每次保存阶段时间点、回调样本、百分比、预测 ETA 范围和实际完成时间；
- 统计各检查点的进度偏差及 ETA 覆盖率，不以同一文件重复运行代替跨场景质量结论；
- 最低验收目标：正常空闲主机上，核心阶段百分比与已处理工作量一致；稳定后 ETA 范围覆盖实际完成时间的比例达到 `≥80%`，且大多数稳定区间误差控制在 `±15%` 内；
- 噪声、长静音、多人重叠或主机负载变化时允许扩大范围，但必须如实标记低置信度；
- 更新 README、验收记录和本计划状态，记录未达标项，不把估算描述为精确进度。

**预计文件：**

- 新建 `docs/acceptance/progress-and-eta.md`
- 修改 `README.md`
- 修改本计划

**验证：** 真实运行退出码、任务终态、回调轨迹、ETA 统计和全部产物均读回；全量测试、Ruff lint/format、`git diff --check` 和 Markdown 链接检查通过。

### 9.4 阶段完成定义

只有满足以下条件，阶段 E 才能改为 `已完成`：

- 进度由阶段事件和 FunASR 原生回调驱动，不依赖匀速假进度；
- 任务状态可持久化、跨进程只读查询，并兼容旧任务记录；
- 百分比单调、成功前不达 `100%`，失败和取消状态准确；
- ETA 以动态范围展示，并通过真实长音频校准达到约定覆盖目标；
- Hermes 能按需报告进度且不会紧密轮询、重复刷屏或扩大网络暴露面；
- 全量质量门禁和真实验收通过，文档明确估算边界。

---

## 10. 阶段 F：前后台双模式、批量队列与资源控制

**阶段状态：** `待开始`

### 10.1 目标与执行边界

把现有单文件前台 CLI 扩展为共享同一调度核心的两种模式：默认前台等待，用户显式传入 `--bg` 时后台运行。两种模式均支持单文件、多文件和目录批量，并在 CPU、内存和用户并发上限内执行。

本阶段不引入 Web UI、HTTP 服务、MCP 或公网监听。前台和后台不得实现两套转写流水线；现有 `TranscriptionEngine`、canonical JSON 和导出器继续作为单文件执行核心。

### 10.2 执行顺序与提交纪律

```text
F1 配置与资源预算
  → F2 批次/任务持久化模型
    → F3 多文件与目录扫描
      → F4 统一调度器和有界并发
        → F5 默认前台批量
          → F6 显式 --bg 与后台管理器
            → F7 状态/取消/重试/恢复
              → F8 Hermes 接入与真实验收
```

每个任务必须按 RED → GREEN → REFACTOR 执行；先运行指定失败测试，完成最小实现后再运行目标测试。每个任务形成独立提交，阶段验收完成后再统一更新状态、推送并核对远端。

### 10.3 任务

#### F1. 定义配置、资源快照和有效预算

**状态：** `待开始`

**目标：** 建立可测试的资源预算计算，默认 CPU 上限为整机逻辑 CPU 容量的 50%，用户只能在普通配置中调低，并发取用户、CPU 和内存安全上限的最小值。

**预计文件：**

- 新建 `src/local_transcriber/config.py`
- 新建 `src/local_transcriber/resources.py`
- 新建 `tests/test_config.py`
- 新建 `tests/test_resources.py`
- 修改 `src/local_transcriber/environment.py`

**实施步骤：**

1. 先写失败测试，覆盖 `cpu_limit_percent=50`、合法范围 `10–50`、越界拒绝、CLI/项目配置/默认值优先级；
2. 实现不可变配置对象，至少包含 `cpu_limit_percent`、`memory_limit_percent`、`max_workers`、`threads_per_worker` 和 `nice`；
3. 先写预算失败测试，固定逻辑 CPU、可用内存、实测单 worker 峰值 RSS，验证方案中的 `effective_workers` 公式；
4. 实现资源快照与纯函数预算计算；所有 worker 线程总和不得超过 `floor(logical_cpu × cpu_limit_percent / 100)`；
5. 内存不足以容纳一个 worker 时返回明确拒绝结果，不用 `max(1, ...)` 掩盖内存不足；
6. 将最终有效预算序列化为任务可记录的 JSON 字典。

**目标测试：**

```bash
uv run pytest tests/test_config.py tests/test_resources.py -v
```

**完成条件：** 默认 50%、用户调低、自动降并发、内存拒绝和配置优先级均有确定性测试。

**提交：** `feat: add bounded transcription resource policy`

#### F2. 扩展持久化批次、任务和运行模式模型

**状态：** `待开始`

**目标：** 在兼容现有任务记录的前提下，建立一个批次对应多个文件任务的持久化模型，并明确 `foreground/background` 运行模式。

**预计文件：**

- 修改 `src/local_transcriber/jobs.py`
- 新建 `src/local_transcriber/batches.py`
- 修改 `src/local_transcriber/schema.py`（仅记录必要的任务/批次引用，不无故升级 canonical schema）
- 修改 `tests/test_jobs.py`
- 新建 `tests/test_batches.py`
- 修改 `tests/test_schema.py`

**实施步骤：**

1. 写失败测试定义批次 ID、任务 ID、运行模式、输入顺序、有效预算、重试次数和产物路径；
2. 增加 `interrupted` 状态以及合法迁移，终态不得重新进入 `running`；
3. 使用临时文件 + `fsync` + 原子替换保存 JSON，避免后台崩溃留下半个状态文件；
4. 兼容读取旧的单任务 JSON，缺失字段给出明确默认值；
5. 实现批次聚合：`succeeded/failed/cancelled/interrupted/skipped` 全部计入结束数，不能永久保持运行中；
6. 增加单运行目录调度锁，锁所有权记录 PID/启动时间并安全识别陈旧锁，不以删除锁文件绕过活跃所有者。

**目标测试：**

```bash
uv run pytest tests/test_jobs.py tests/test_batches.py tests/test_schema.py -v
```

**完成条件：** 旧记录可读、原子持久化、状态迁移、部分失败聚合和锁竞争测试全部通过。

**提交：** `feat: persist transcription batches and run modes`

#### F3. 实现多文件参数与安全目录扫描

**状态：** `待开始`

**目标：** 将显式文件列表和目录稳定展开为批次任务，不启动模型即可 dry-run。

**预计文件：**

- 新建 `src/local_transcriber/discovery.py`
- 修改 `src/local_transcriber/media.py`
- 修改 `src/local_transcriber/cli.py`
- 新建 `tests/test_discovery.py`
- 修改 `tests/test_media.py`
- 修改 `tests/test_cli.py`

**实施步骤：**

1. 写失败测试：多个文件保持用户顺序；目录默认不递归；`--recursive` 才遍历子目录；
2. 实现扩展名预筛选，但最终仍逐个调用 ffprobe 确认音轨；
3. 默认拒绝/跳过符号链接，排除输入目录下解析出的 runtime/output/cache/work/state 路径；
4. 目录结果按规范化相对路径稳定排序；显式输入按用户顺序；
5. 使用绝对路径、大小和内容哈希去重，并记录每个跳过原因；
6. 输出目录保留相对结构并附任务 ID，测试两个同名文件不会覆盖；
7. 为 `transcribe INPUT...` 增加多文件参数，为 `transcribe-dir DIRECTORY` 增加 `--recursive` 和 `--dry-run`；
8. dry-run 只输出机器可读清单/人类摘要，不创建运行任务、不加载模型。

**目标测试：**

```bash
uv run pytest tests/test_discovery.py tests/test_media.py tests/test_cli.py -v
```

**完成条件：** 文件顺序、递归边界、符号链接、排除目录、去重、同名输出和 dry-run 均有回归测试。

**提交：** `feat: add deterministic batch input discovery`

#### F4. 提取单文件执行器并实现统一有界调度器

**状态：** `已完成（2026-08-01）`

**目标：** 让前台和后台共用同一个调度器，同时在多个文件间提供受 CPU/内存预算约束的并发。

**预计文件：**

- 新建 `src/local_transcriber/executor.py`
- 新建 `src/local_transcriber/scheduler.py`
- 修改 `src/local_transcriber/cli.py`
- 修改 `src/local_transcriber/engine.py`
- 新建 `tests/test_executor.py`
- 新建 `tests/test_scheduler.py`
- 修改 `tests/test_cli.py`
- 修改 `tests/test_engine.py`

**实施步骤：**

1. 先用现有 CLI 测试锁定单文件退出码、产物和错误语义；
2. 从 `_transcribe` 提取只处理一个持久化任务的执行器，不复制 probe/normalize/engine/export 流程；
3. 写调度失败测试：同时运行数不超过 `effective_workers`，所有运行 worker 的线程总和不超预算；
4. 实现有界进程 worker 池；每个 worker 使用独立模型实例、临时目录、取消事件和进度写入器；
5. 单文件失败仅更新该任务，其他任务继续；调度器汇总批次终态；
6. 周期采样整个进程树的 CPU/RSS；持续超预算或内存低于安全线时暂停启动新任务，并记录降级原因；
7. 保持 CPU/内存保护为调度上限；若安装为 systemd 服务，再附加 cgroup 保护，但测试不得依赖 systemd；
8. 验证 `effective_workers=1` 时行为与原单 worker 路径等价。

**目标测试：**

```bash
uv run pytest tests/test_executor.py tests/test_scheduler.py tests/test_cli.py tests/test_engine.py -v
```

**完成条件：** 并发上限、线程总预算、部分失败、动态暂停、单 worker 兼容和取消隔离测试通过。

**提交：** `feat: add shared bounded batch scheduler`

#### F5. 落地默认前台模式

**状态：** `已完成（2026-08-01）`

**目标：** 不带 `--bg` 时始终前台等待，单文件、多文件和目录批次均实时显示进度并返回可用于脚本的退出码。

**预计文件：**

- 修改 `src/local_transcriber/cli.py`
- 新建 `src/local_transcriber/console.py`
- 修改 `tests/test_cli.py`
- 新建 `tests/test_console.py`

**实施步骤：**

1. 写失败测试确认无 `--bg` 时 `run_mode == foreground`，并等待整个批次终态；
2. 将阶段 E 的任务进度和 ETA 格式化为紧凑终端状态，不解析 tqdm 文本；
3. 多文件前台显示批次总进度、运行/完成/失败数和当前任务摘要；非 TTY 输出稳定的逐行事件，避免控制字符；
4. 定义批次退出码：全成功 `0`；输入/扫描错误 `2`；任一执行失败 `3`；调度器忙/资源不足 `4`；用户取消 `130`；
5. `Ctrl+C` 首次触发协作取消并持久化状态，再次中断才强制结束受控子进程；
6. 前台命令退出后不得把普通前台任务静默留给后台管理器继续执行；
7. 单文件现有命令和产物路径保持兼容。

**目标测试：**

```bash
uv run pytest tests/test_cli.py tests/test_console.py -v
```

**完成条件：** 默认前台、退出码、TTY/非 TTY、批次摘要、Ctrl+C 和单文件兼容测试通过。

**提交：** `feat: make foreground the default batch mode`

#### F6. 实现显式 `--bg` 和本地后台管理器

**状态：** `已完成（2026-08-01）`

**目标：** 只有显式传入两个半角连字符的 `--bg` 才快速返回并由后台管理器继续执行；不得支持或文档化 Unicode 长破折号 `—bg`。

**预计文件：**

- 新建 `src/local_transcriber/daemon.py`
- 新建 `src/local_transcriber/ipc.py`
- 修改 `src/local_transcriber/cli.py`
- 新建 `tests/test_daemon.py`
- 新建 `tests/test_ipc.py`
- 修改 `tests/test_cli.py`
- 新建 `packaging/systemd/local-transcriber-worker.service`

**实施步骤：**

1. 写 CLI 失败测试：`--bg` 被接受且立即返回 ID；`--background` 和 `—bg` 均被拒绝；无 `--bg` 仍走前台；
2. 后台提交先原子保存批次，再通过仅限本机用户的 Unix domain socket/受控本地 IPC 通知管理器；不监听 TCP/HTTP；
3. 若管理器未运行，`--bg` 在支持的安装环境中启动/请求启动用户级管理器；无法启动时返回明确错误，不能伪报已提交；
4. 实现 `worker run/start/status/stop/restart`，同一 runtime 只允许一个管理器；
5. `start` 不使用裸 `&`/`nohup` 产生孤儿；systemd 用户服务设置私有运行目录、重启策略、`CPUQuota=50%` 的默认保护及内存保护模板；
6. 后台提交输出固定 JSON（可选）与人类摘要，至少含 `mode=background`、batch ID、task IDs、状态查询命令；
7. 后台管理器日志只含任务元数据、阶段和脱敏错误，不含转写正文；
8. 前台与后台对同一 runtime 的锁和预算必须协调，不允许合计并发越过有效预算。

**目标测试：**

```bash
uv run pytest tests/test_daemon.py tests/test_ipc.py tests/test_cli.py -v
```

**完成条件：** 参数精确性、快速返回、无管理器失败、单实例、本地 IPC、日志隐私和前后台协调测试通过。

**提交：** `feat: add explicit bg transcription mode`

#### F7. 增加状态、取消、重试和重启恢复

**状态：** `已完成（2026-08-01）`

**目标：** 前后台任务均可查询；后台管理器崩溃或重启后不丢失任务，也不把中断任务误报成功。

**预计文件：**

- 修改 `src/local_transcriber/cli.py`
- 修改 `src/local_transcriber/jobs.py`
- 修改 `src/local_transcriber/batches.py`
- 修改 `src/local_transcriber/daemon.py`
- 新建 `tests/test_recovery.py`
- 修改 `tests/test_jobs.py`
- 修改 `tests/test_batches.py`
- 修改 `tests/test_daemon.py`

**实施步骤：**

1. 增加 `job status JOB_ID --json`、`batch status BATCH_ID --json`；JSON 不包含转写正文；
2. 增加任务/批次取消：排队任务立即取消，运行任务先协作取消，超时后终止受控进程树；
3. 增加失败/中断任务重试，新任务保留 `retry_of`，不得覆盖原任务证据；
4. 管理器启动时把遗留 `running` 标为 `interrupted`，重新载入 `queued`；是否重试中断任务必须按明确策略执行，不直接改成成功；
5. 写崩溃注入测试：状态文件写入中断、worker 被杀、管理器被杀、重启后队列恢复；
6. 验证已成功任务及其产物不被重复执行或覆盖；
7. 批次在所有子任务进入终态后正确结束，部分失败不会卡住。

**目标测试：**

```bash
uv run pytest tests/test_recovery.py tests/test_jobs.py tests/test_batches.py tests/test_daemon.py tests/test_cli.py -v
```

**完成条件：** 查询、取消、重试、崩溃恢复、幂等成功产物和批次终态测试通过。

**提交：** `feat: recover and control persisted transcription jobs`

#### F8. 更新 Hermes 流程并完成真实批量资源验收

**状态：** `已完成（2026-08-01）`

**目标：** 证明默认前台和显式后台均真实可用，目录/多文件并发不越过预算，并让 Hermes 按用户意图选择模式。

**预计文件：**

- 修改 `.hermes/skills/local-speaker-transcription/SKILL.md`
- 修改 `tests/test_skill.py`
- 新建 `docs/acceptance/batch-background-resources.md`
- 修改 `README.md`
- 修改本计划

**实施步骤：**

1. 更新 Skill：默认前台；用户明确要求后台、任务需跨会话或终端断开时才使用 `--bg`；保存 ID 并通过状态命令查询；
2. 使用授权媒体构造至少三个文件的验收目录，包含成功文件、无音轨/损坏文件或可控失败夹具，验证部分失败继续；
3. 分别真实运行前台多文件、前台目录、后台多文件、后台目录；读回每个 canonical JSON 和派生产物；
4. 在自动预算及显式较低预算下采样整个进程树 CPU/RSS，记录瞬时波动、持续均值、有效 worker/线程数和自动降级；
5. 验证默认配置的线程预算不超过逻辑 CPU 的 50%，内存预算不越界；若当前机器只能安全运行一个 worker，验收记录必须如实写为自动降级 1，不能伪造并发通过；
6. 真实重启后台管理器，确认 queued 恢复、running 转 interrupted/按策略重试、成功产物不重复；
7. 阻断网络后运行一个批量任务，证明模型缓存后的批量路径仍不访问网络；
8. 运行全量质量门禁并更新状态；不得把方案目标命令提前写成已实现功能。

**验收命令：**

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

**完成条件：** 默认前台、显式 `--bg`、多文件、目录、部分失败、恢复、离线及资源预算都有真实证据；所有产物读回通过。

**完成证据：** [阶段 F/F8 批量、后台恢复与资源验收](../acceptance/batch-background-resources.md)。当前主机在默认 50% CPU 与内存安全预算下如实降级为 1 worker；真实验收还修复了调度内存安全线比较及多任务模型进程回收问题。

**提交：** `docs: record batch and background acceptance`

### 10.4 阶段完成定义

只有满足以下条件，阶段 F 才能改为 `已完成`：

- 无 `--bg` 时始终前台等待，不根据时长、数量或调用来源静默切换；
- 只有 `--bg` 启用后台，`--background` 和 `—bg` 均不接受；
- 前台和后台都支持单文件、多文件和目录，并复用同一调度和执行核心；
- 批次/任务持久化、查询、取消、重试和崩溃恢复通过测试及真实验收；
- 并发受 CPU、内存和用户上限共同约束，默认 CPU 线程预算不超过整机 50%；
- 单文件失败不影响其他文件，批次不会因失败/取消/跳过而卡住；
- 后台管理器不监听网络端口，日志不包含转写正文；
- README、Skill 和验收记录只陈述已真实验证能力。

---

## 11. 阶段 G：版本化发布与更新日志

**阶段状态：** `已完成`

### 11.1 目标

建立可重复的语义化发布流程。普通开发提交不强制改版本，但每次正式发布必须提升版本、更新更新日志、构建并从干净环境验证，再创建不可覆盖的 tag 和 GitHub Release。

### 11.2 任务

#### G1. 建立单一版本源和 CLI `--version`

**状态：** `已完成`

**预计文件：**

- 修改 `pyproject.toml`
- 新建 `src/local_transcriber/version.py` 或改为由 `importlib.metadata` 读取包元数据（二选一，实施时只保留一个权威源）
- 修改 `src/local_transcriber/cli.py`
- 新建 `tests/test_version.py`
- 修改 `tests/test_cli.py`

**实施步骤：**

1. 写失败测试，断言包元数据版本与 `local-transcriber --version` 完全一致；
2. 选择单一权威版本源，禁止在多个文件手工重复版本字符串；
3. CLI 增加顶层 `--version`，输出稳定且适合脚本解析；
4. 增加版本格式测试，必须符合 `MAJOR.MINOR.PATCH`；
5. 增加构建元数据读回测试。

**目标测试：**

```bash
uv run pytest tests/test_version.py tests/test_cli.py -v
```

**完成条件：** 包元数据、运行时和 CLI 版本一致且只有一个权威来源。

**提交：** `build: establish single package version source`

#### G2. 创建更新日志和版本一致性检查器

**状态：** `已完成`

**预计文件：**

- 新建 `CHANGELOG.md`
- 新建 `scripts/check_release.py`
- 新建 `tests/test_release.py`
- 修改 `README.md`
- 修改 `CONTRIBUTING.md`

**实施步骤：**

1. 创建 Keep a Changelog 结构，包含 `Unreleased` 和当前已发布 `0.1.0` 的事实性历史条目；
2. 写失败测试验证 `Unreleased` 存在、发布章节版本唯一、日期格式正确、版本顺序递减；
3. 实现只读检查器，对比包版本、CHANGELOG 目标版本和可选 Git tag；
4. 不兼容变化必须要求迁移说明；空泛条目（如“若干优化”）在评审中拒绝；
5. README 链接更新日志，贡献指南要求用户可感知变化先进入 `Unreleased`。

**目标测试：**

```bash
uv run pytest tests/test_release.py -v
uv run python scripts/check_release.py --allow-unreleased
```

**完成条件：** 更新日志结构和版本一致性可自动验证。

**提交：** `docs: add changelog and release validation`

#### G3. 自动化构建和干净安装验收

**状态：** `已完成`

**预计文件：**

- 新建 `scripts/verify_release.py`
- 修改 `pyproject.toml`（仅在需要构建配置时）
- 修改 `tests/test_release.py`
- 修改 `.gitignore`（仅在新增本地产物时）

**实施步骤：**

1. 写失败测试/脚本检查：工作树发布范围、锁文件、测试、Ruff、构建产物均为必要门禁；
2. 构建 sdist 和 wheel，检查两者包含 LICENSE、README、CHANGELOG 和完整包；
3. 在全新临时虚拟环境安装 wheel，运行 `local-transcriber --version`、`--help` 和不访问模型的 CLI smoke test；
4. 计算并输出构建产物 SHA-256；
5. 发布检查器检测目标 tag 已存在时必须拒绝覆盖；
6. 脚本默认只验证，不自动 push/tag/release，外部写操作由发布步骤显式执行。

**验收命令：**

```bash
uv run python scripts/verify_release.py
```

**完成条件：** 从源码构建、干净安装、CLI 版本和产物内容/校验值全部验证通过。

**提交：** `build: automate release artifact verification`

#### G4. 执行版本发布、远端核验和文档收口

**状态：** `已完成`

**目标：** 将阶段 E/F/G 的用户可见变化作为新的 MINOR 版本发布；目标版本在实施时根据当时最新远端版本确定，不能现在硬编码或复用已有版本。

**预计文件：**

- 修改单一版本源
- 修改 `CHANGELOG.md`
- 新建 `docs/acceptance/release.md`
- 修改本计划
- 可能修改 `README.md` 的当前版本说明

**实施步骤：**

1. 获取远端 tags/Releases，计算高于最新正式版的目标 MINOR 版本；
2. 将对应 `Unreleased` 条目移动到目标版本和实际发布日期下，再建立空的 `Unreleased`；
3. 更新单一版本源和锁文件，运行版本一致性检查；
4. 运行全量测试、Ruff、离线 smoke、阶段 F 关键验收及发布验证脚本；
5. 提交发布变更并推送 `main`，确认本地与远端提交一致；
6. 创建带注释的 `vMAJOR.MINOR.PATCH` tag；若 tag 已存在立即停止，不强制覆盖；
7. 推送 tag，创建 GitHub Release，附该版本更新日志、升级说明和 SHA-256；
8. 通过 GitHub API/`gh release view` 和全新 HTTPS clone 验证 tag、Release、源码版本、CHANGELOG 和构建产物一致；
9. 写入验收证据并将阶段状态改为完成。

**发布门禁：**

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_release.py --release VERSION
uv run python scripts/verify_release.py
git diff --check
```

**完成条件：** 新版本、更新日志、tag、GitHub Release 和远端源码完全一致；本地与远端分支同步，工作树干净。

**提交：** `release: publish VERSION`

### 11.3 阶段完成定义

只有满足以下条件，阶段 G 才能改为 `已完成`：

- 每次正式发布都使用高于上一发布的新语义化版本；
- 版本只有一个权威来源，包元数据、CLI、tag 和 Release 一致；
- `CHANGELOG.md` 同时维护 `Unreleased` 和带日期版本章节；
- sdist/wheel 在干净环境安装并执行 smoke test；
- 发布产物具有 SHA-256，已有 tag 不被移动或覆盖；
- 提交、tag 和 GitHub Release 已推送并从远端重新验证；
- 发布验收证据、README 和计划状态同步。

---

## 12. 计划整体完成定义

只有以下条件全部满足，整体状态才能改为 `已完成`：

- 隔离环境可重建，模型可显式预取；
- FunASR + SenseVoiceSmall + FSMN-VAD + CAM++ 在 CPU 上真实运行；
- CLI、任务状态、规范 JSON 和导出器通过测试与端到端验收；
- 六类真实样本完成评估；
- 模型缓存后的断网运行成功；
- Hermes 真实调用、验证并回传产物；
- 真实进度、动态 ETA、状态查询和 Hermes 按需通知通过长音频校准与验收；
- 默认前台、显式 `--bg`、多文件/目录批量、持久化恢复和资源预算通过真实验收；
- 版本、更新日志、构建产物、tag 和 GitHub Release 通过发布门禁及远端核验；
- 所有阶段状态及验收记录已同步更新。
