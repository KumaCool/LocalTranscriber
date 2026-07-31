# 阶段 C 断网验收

**状态：** `已完成`

**执行环境：** 匿名受限 CPU 验收主机

**执行日期：** 2026-07-31

## 1. 前置条件

阶段 A 已将以下固定 revision 完整缓存到项目本地 `var/cache/models/`：

- `iic/SenseVoiceSmall`
- `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch`
- `iic/speech_campplus_sv_zh-cn_16k-common`

生产引擎把三个模型都解析为本地绝对路径，并设置 `disable_update=True`。

## 2. 网络隔离方式

使用 Linux 用户和网络命名空间运行完整 CLI：

```bash
unshare --user --map-root-user --net \
  uv run local-transcriber transcribe \
    var/input/phase-c/quiet-two-speaker.wav \
    --output-dir var/output/phase-c/offline-unshare \
    --runtime-dir var/work/phase-c/offline-unshare \
    --cache-dir var/cache/models \
    --threads 2
```

在同样的命名空间参数下检查网络状态：

```text
NETWORK_INTERFACES
lo               DOWN
ROUTES
```

隔离环境只有关闭的 loopback，无默认路由和外部网络接口。没有修改宿主机防火墙、路由或 Hermes 配置。

## 3. 实际结果

```text
退出码：          0
音频时长：        23.770 s
总墙钟时间：      20.70 s
RTF：             0.8708
峰值 RSS：        3,269,788 KiB
句段：            2
匿名 speaker：    SPEAKER_00、SPEAKER_01
任务状态：        succeeded
```

FunASR 日志确认 ASR、VAD 和 speaker checkpoint 均从项目本地绝对路径加载。运行生成并成功读回：

- `result.json`
- `media.json`
- `transcript.md`
- `transcript.txt`
- `transcript.srt`

本地详细 `/usr/bin/time -v`、标准输出、标准错误、规范 JSON 和校验值保存在 `.gitignore` 排除的：

```text
var/acceptance/phase-c/
var/output/phase-c/offline-unshare/
```

## 4. 验收结论

固定模型快照预取后，LocalTranscriber 在没有可用网络接口和路由的独立网络命名空间中完成了真实媒体的探测、标准化、ASR、VAD、speaker 聚类、规范 JSON 及三种导出。

这证明当前已缓存模型组合可以离线运行，且没有依赖云 API。此结论不表示 `models pull` 本身可以离线执行；首次预取仍然需要网络。
