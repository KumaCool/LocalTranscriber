# Tests

测试覆盖 CLI、环境与媒体探测、模型清单、任务状态、结果规范、导出器和项目 Skill。

默认测试必须离线、可重复，并且不得：

- 下载模型或访问外部服务；
- 依赖私人录音或本机专属路径；
- 在被 Git 跟踪的目录写入运行产物。

运行完整质量检查：

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

真实模型组合和离线缓存运行的开发验证证据位于 [`docs/acceptance/`](../docs/acceptance/)，详细本地产物保存在被忽略的 `var/acceptance/`。
