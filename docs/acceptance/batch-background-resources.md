# 阶段 F/F8：批量、后台恢复与资源验收

验收日期：2026-08-01。原始媒体、任务状态、日志和生成产物均保存在被 Git 忽略的 `var/acceptance/phase-f/`，不入库。本记录仅提交脱敏结论。

## 验收矩阵

| 能力 | 真实证据 | 结论 |
|---|---|---|
| 默认前台多文件 | 两个授权模型示例文件，退出码 0 | 通过 |
| 默认前台目录 | 三个授权文件及一个损坏 WAV；损坏项扫描跳过，三个有效项成功 | 通过 |
| 显式后台多文件 | 管理器确认提交，batch/task ID 可查询，两个任务成功 | 通过 |
| 显式后台目录 | 三任务运行中杀死管理器；重启后 queued 恢复、running 变 interrupted；显式 retry 生成新 ID 并成功 | 通过 |
| 严格离线批量 | `unshare -Urn` 无网络命名空间内公开 CLI 处理两个文件，退出码 0 | 通过 |
| 资源预算 | 4 逻辑 CPU、默认 50% CPU 预算；请求 2 workers 自动降为 1 worker × 2 threads | 通过（当前主机不宣称双 worker 并发） |
| 产物读回 | 所有成功任务解析 canonical JSON、media JSON，并读取 MD/TXT/SRT | 通过 |
| 网络暴露 | 管理器只使用本地 Unix IPC；验收期间无 LocalTranscriber TCP listener | 通过 |

## 样本与扫描

验收输入来自已缓存 SenseVoice 示例中的真实、可再分发人声：中文、英文、粤语各一份，时长分别约 5.616 s、7.176 s、5.184 s；另放置一个内容为非媒体数据的 `04-broken.wav`。

`transcribe-dir --dry-run --json` 稳定接受三个有效文件，并以 `invalid_media` 跳过损坏文件。目录批次随后只执行三个有效任务。该结果证明扫描和部分无效输入不会阻塞有效任务；不代表损坏媒体进入执行器后也会成功。

## 真实前台运行

- 多文件：2/2 成功，墙钟时间 50.09 s，最大 RSS 3,272,336 KiB。
- 目录：3/3 成功，损坏文件在发现阶段跳过；墙钟时间 62.57 s，最大 RSS 3,272,488 KiB。
- 两次运行均请求 `--max-workers 2 --threads 2`，持久化预算均为：`cpu_thread_limit=2`、`cpu_worker_limit=1`、`memory_worker_limit=1`、`effective_workers=1`。

首次真实运行还发现两个资源缺陷并以回归测试修复：

1. 调度器错误地把“当前可用内存”与“启动时可用内存预算”比较，可能永久暂停后续任务；现改为比较 LocalTranscriber 整个进程树 RSS 与预算。
2. 多文件单 worker 曾在线程中复用同一进程，第一项完成后模型内存未可靠释放，第二项可能卡在加载；现对真实多任务使用受控进程 worker，并设置每个子进程最多处理一个模型任务。单文件仍保留同进程路径，便于精确单元测试 monkeypatch，且不产生跨任务模型累积。

## 后台与重启恢复

环境没有用户级 systemd bus，`worker start` 如实返回退出码 4 和 `Failed to connect to bus`，未伪报启动成功。验收因此按设计的无 systemd 降级路径，用受跟踪的前台 `worker run` 启动管理器；未使用 `nohup` 或裸 `&`。

- 后台多文件：提交命令快速返回 `mode=background`、batch ID 和两个 task ID；最终 2/2 成功。
- 后台目录：提交三个有效任务后，在第一项运行期间真实终止管理器；重启管理器后，原 running 任务变为 `interrupted`，另外两个 queued 任务恢复并成功；已成功任务未被重复执行。
- 显式 `batch retry` 只为 interrupted 项创建新的 batch/task ID；新任务成功，旧证据和已成功产物均保留。

这证明恢复策略是 queued 自动恢复、running 如实转 interrupted、成功任务幂等保留；中断项不会被误报成功，也不会未经授权自动重试。

## 严格离线批量

在 `unshare -Urn` 创建的进程级网络命名空间中运行公开 `local-transcriber transcribe` 多文件命令，使用固定本地模型缓存。两个文件均成功，退出码 0，并生成及读回全部五类产物。首次模型预取不属于离线结论。

FunASR 日志中的 `download models from model hub: ms` 是库的通用解析文案；同一运行处于无接口/无路由网络命名空间，实际 checkpoint 路径均为本地 `var/cache/models/`，且运行成功，因此没有发生远端下载或云 API 调用。

## 产物与语义核验

共读回前台多文件 2 项、前台目录 3 项、后台多文件 2 项、后台目录（含 retry）3 项、离线批量 2 项：

- `schema_version == 1`；
- `job.status == succeeded`；
- 每项均有可解析 `result.json` 和 `media.json`；
- Markdown、TXT、SRT 均非空且可读；
- 句段时间为合法整数范围；
- speaker 标签均为匿名 `SPEAKER_` 前缀；
- engine threads 与对应预算一致。

这些样本只证明批量、恢复、离线和产物链路。它们不改变阶段 C 的质量结论：多人聚类与重叠讲话仍不可靠，句段时间也不是字级对齐。

## 结论

F8 通过。默认前台、显式 `--bg`、多文件、目录扫描、无效媒体跳过、后台恢复、显式 retry、缓存后严格离线、资源自动降级和产物读回都有真实证据。当前 4 CPU / 8 GiB 主机安全计算结果是 1 worker，不将“代码支持有界 worker 池”误述为本机已安全实现双模型并发。

## 后续资源配置语义修正

2026-08-01 根据需求澄清修正：CPU 50% 和内存 70% 均为默认值，不是硬上限。`cpu_limit_percent` 与 `memory_limit_percent` 接受 `0–100`，其中 `0` 关闭对应预算；CLI 已接通 TOML 配置及命令行覆盖，systemd 启动也不再固定追加 CPU/内存 cgroup 限制。关闭内存百分比预算后仍检查当前实际可用内存，不能容纳一个 worker 时继续拒绝启动。

该修正已通过配置、预算、CLI、调度器、daemon 和 systemd 自动化测试；本节不改写上方历史真实验收所使用的默认 50% CPU 条件。
