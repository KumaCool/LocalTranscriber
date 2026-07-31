# 阶段 G：LocalTranscriber 0.2.1 发布验收

**验收日期：** 2026-08-01

**目标版本：** `0.2.1`

**发布类型：** 向后兼容的 MINOR 版本

## 发布范围

`0.2.0` 汇总阶段 E、F、G 的用户可见变化；`0.2.1` 修正发布归档严格校验后作为阶段 G 最终版本。范围包括事件驱动进度与动态 ETA、多文件和目录批量、显式后台模式、本机 Unix IPC 管理器、任务/批次控制与恢复、CPU/内存联合资源预算，以及版本化发布工具链。

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

升级前停止后台 worker，切换到 `v0.2.1` 后执行 `uv sync --locked`。需要回滚时停止 worker、切换回旧 tag 并重新同步依赖。`0.2.1` 未改变 canonical JSON `schema_version=1`，也未要求迁移既有任务记录。

## 远端发布核验

发布完成后已执行以下核验：

1. 发布提交已推送且 `origin/main...HEAD` 为 `0 0`；
2. 注释 tag `v0.2.1` 已创建并推送，且未覆盖已有 tag；
3. GitHub Release `v0.2.1` 已创建，包含更新日志、升级说明、wheel、sdist 和 SHA-256；
4. 通过 GitHub API 与全新 HTTPS clone 验证远端 tag、Release、源码版本、CHANGELOG 和附件一致。
