# Changelog

本项目的用户可见变化记录在此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.2.2] - 2026-08-02

### Added

- 增加 Intel macOS x86_64 原生运行支持及实际 SenseVoice/VAD/CAM++ 转写验收。

### Changed

- 依赖锁现在按平台选择版本：Intel macOS 使用最后仍提供 x86_64 wheel 的兼容组，Linux 保持 PyTorch/Torchaudio 2.10.0。

### Fixed

- Unix IPC 现在兼容 Linux `SO_PEERCRED` 与 macOS `LOCAL_PEERCRED`，并在 macOS 路径上限内安全缩短过长的 socket 地址。
- CPU 和内存预算现在可在 `0–100` 范围配置，`0` 表示关闭对应预算；50%/70% 仅为默认值，不再被错误实现为硬上限。
- 转写 CLI 现在实际读取 TOML 资源配置，并允许命令行覆盖 CPU、内存、worker、线程和 nice 设置。
- 后台 systemd 启动不再固定附加 CPU/内存 cgroup 限制，以免覆盖用户选择的资源策略。

## [0.2.1] - 2026-08-01

### Fixed

- 发布归档检查器现在严格要求 LICENSE、README 和 CHANGELOG 位于 sdist 根目录，并拒绝放在 `src/` 下的伪匹配文件。

## [0.2.0] - 2026-08-01

### Added

- 增加由真实处理事件驱动的阶段进度、动态 ETA 和脱敏状态查询。
- 增加多文件及目录批量转写，并保留稳定输入顺序和独立任务产物。
- 增加显式 `--bg` 后台模式、本机 Unix IPC 管理器及用户级 systemd 生命周期命令。
- 增加任务和批次的状态查询、取消、失败/中断任务重试及管理器重启恢复。
- 增加 CPU、内存、worker 和线程联合资源预算；默认 CPU 预算不超过逻辑 CPU 的 50%。
- 增加顶层 `--version`、版本一致性检查和可重复的发布产物验证流程。

### Changed

- 前台执行保持默认；只有显式传入 `--bg` 才提交后台任务。
- 批量任务共享持久化调度器和资源边界，单项失败不会阻塞后续任务。

### Security

- 后台控制仅使用同 UID、权限受限的 Unix socket，不监听 HTTP/TCP。
- 状态及控制输出隐藏输入路径、输出路径、转写正文和执行参数。

### Known limitations

- 匿名说话人标签不是身份识别，句段时间戳也不是字级强制对齐。
- 模型首次预取需要网络；“离线”仅指模型完整缓存后的转写运行。
- 质量仍受语言、口音、噪声、重叠讲话和录音条件影响，输出需要人工复核。

## [0.1.0] - 2026-07-31

### Added

- 首次可用的 CPU 本地转写 CLI。
- 基于 SenseVoiceSmall、FSMN-VAD 和 CAM++ 的文本、句段时间戳及匿名说话人聚类。
- 规范 JSON，以及 Markdown、TXT 和 SRT 派生导出。
- 媒体预检、FFmpeg 标准化、持久任务状态、模型预取和离线缓存验收。
- Hermes Agent 本地 Skill 集成与真实样本评估记录。

[Unreleased]: https://github.com/KumaCool/LocalTranscriber/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/KumaCool/LocalTranscriber/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/KumaCool/LocalTranscriber/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/KumaCool/LocalTranscriber/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/KumaCool/LocalTranscriber/releases/tag/v0.1.0
