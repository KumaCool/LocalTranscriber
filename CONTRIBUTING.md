# Contributing to LocalTranscriber

感谢你考虑为 LocalTranscriber 作出贡献。

## 开始之前

- 使用 Issue 描述缺陷、兼容性问题或功能建议。
- 不要上传私人录音、未获授权的媒体、真实转写内容、凭证或机器信息。
- 较大的行为或架构变更建议先通过 Issue 讨论范围。

## 开发环境

项目要求 Python 3.11、uv、FFmpeg 和 ffprobe。

```bash
git clone https://github.com/KumaCool/LocalTranscriber.git
cd LocalTranscriber
uv sync --locked --dev
```

## 质量检查

提交前运行：

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

测试应保持离线且可重复。默认测试不得下载模型、访问外部服务或依赖私人媒体。需要音频 fixture 时，请使用可再分发的小型合成样本，并清楚记录来源与许可证。

## 变更原则

- 保持本地优先，不默认上传音频或转写结果。
- 保持单 worker 和明确的资源边界，除非变更包含相应设计和测试。
- 不把匿名说话人聚类描述为身份识别。
- 不把句段时间戳描述为字级强制对齐。
- 新增或修改 CLI 行为时同步更新 README、帮助信息和测试。
- 避免将本机绝对路径、主机名、邮箱、IP、环境报告或运行产物写入仓库。

## Pull Request

Pull Request 应包含：

- 变更目的和范围；
- 用户可见行为；
- 已运行的验证命令；
- 已知限制或兼容性影响；
- 对相关文档和测试的更新。

提交信息建议采用简洁的 Conventional Commits 风格，例如：

```text
fix: handle silent media without invalid segments
```

提交贡献即表示你有权提供相关内容，并同意按项目的 [MIT License](LICENSE) 发布。
