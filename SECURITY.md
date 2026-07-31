# Security Policy

## Supported versions

安全修复以当前 `main` 分支为准。项目尚未承诺维护多个历史版本分支。

## Reporting a vulnerability

请不要通过公开 Issue 披露尚未修复的漏洞、凭证、私人媒体或可识别个人身份的转写内容。

请使用 GitHub 仓库的 **Security → Report a vulnerability** 私下提交报告：

https://github.com/KumaCool/LocalTranscriber/security/advisories/new

报告中请尽量包含：

- 受影响版本或提交；
- 复现步骤和最小必要样本；
- 潜在影响；
- 建议修复方向（如有）。

请对敏感数据进行脱敏，并且不要附加无权分享的录音。维护者会在合理时间内确认报告、评估影响，并在修复可用后协调披露。

## Security and privacy boundaries

LocalTranscriber 设计为本地批处理工具，不提供 HTTP 服务，也不需要云端转写凭证。模型首次下载仍会访问对应模型提供方；之后可使用本地缓存离线运行。

运行产物可能包含敏感语音内容、文件路径、哈希和机器环境信息。请保护 `var/`，不要将其提交到 Git 或公开分享。
