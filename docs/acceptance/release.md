# LocalTranscriber 0.2.2 发布验收

**验收日期：** 2026-08-02

**目标版本：** `0.2.2`

**发布类型：** 向后兼容的 PATCH 版本

## 发布范围

`0.2.2` 在 `0.2.1` 基础上增加 Intel macOS x86_64 原生运行支持，按平台锁定兼容依赖，并让本机 Unix IPC 同时兼容 Linux `SO_PEERCRED` 与 macOS `LOCAL_PEERCRED`。过长的 Unix socket 地址会使用同 UID、基于运行目录摘要的短路径。canonical JSON `schema_version=1` 和任务状态格式均未改变。

版本号以 `src/local_transcriber/__init__.py` 的 `__version__` 为唯一权威源；Hatch 构建元数据和 CLI `--version` 均从该值派生。

## 已执行门禁

- 版本、包元数据和 CLI 一致性测试。
- `CHANGELOG.md` 的 `Unreleased`、版本唯一性、日期格式及递减顺序检查。
- 全量 pytest、Ruff lint、Ruff format check、Markdown 相对链接和 `git diff --check`。
- 从源码构建一个 wheel 和一个 sdist。
- 检查两类归档包含 LICENSE、README、CHANGELOG 和完整 `local_transcriber` 包。
- 在全新 Python 3.11 虚拟环境安装 wheel，执行导入、`--version` 和 `--help` smoke test；该 smoke 不加载模型也不访问网络。
- 阶段 F 已完成并记录默认前台、显式后台、管理器恢复、批量部分失败、缓存模型离线运行和资源预算真实验收；本次发布不重复宣称新的音频质量结果。

## 发布产物

最终 GitHub Release 附件由 `scripts/verify_release.py` 在发布提交上重新构建。脚本输出每个产物的 SHA-256 和大小；发布后通过 GitHub API重新读取并下载附件核对。

## 升级与回滚

升级前停止后台 worker，切换到 `v0.2.2` 后执行 `uv sync --locked`。需要回滚时停止 worker、切换回旧 tag 并重新同步依赖。`0.2.2` 未改变 canonical JSON `schema_version=1`，也未要求迁移既有任务记录。

## 远端发布核验

发布完成后已执行以下核验：

发布后记录发布提交、`v0.2.2` 注释标签、GitHub Release、附件 SHA-256、远端同步结果及全新 HTTPS clone 验收证据。
