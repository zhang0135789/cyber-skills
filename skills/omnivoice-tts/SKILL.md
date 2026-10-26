---
name: omnivoice-tts
description: 本地 omnivoice-tts 中文语音合成与音色克隆（docker 常驻 :7842）。需要给视频/文章配音、生成解说词音频、克隆自定义音色、批量按 SRT 时间轴合成解说轨时使用。触发词：配音、TTS、语音合成、解说、口播、音色克隆。
version: "1.0.0"
metadata:
  openclaw:
    emoji: "🎙️"
    requires:
      bins:
        - docker
        - curl
---

# omnivoice-tts — 本地语音合成/音色克隆服务

docker 常驻服务，**用前先确认存活**：`docker ps | grep omnivoice`（容器名 `omnivoice-tts`，镜像 `voice-clone-local:0.1.0`，健康检查 `/health`）。

## 基址

```
http://localhost:7842
```

## API 一览（FastAPI，openapi 见 /openapi.json）

### POST /tts — 单句合成
```json
{"text": "要说的话", "voice": "guoxue_default", "speed": 1.0, "num_step": 16}
```
- `voice`：留 null 用默认音色；指定注册名用克隆音色
- `speed`：默认 0.92，解说用 1.0（实际语速 ~4 字/秒，比 Audio8 的 2.6 快，适合科普解说）
- 返回 wav 二进制流，直接落盘即可（24kHz mono 16bit）

```bash
curl -s -X POST http://localhost:7842/tts -H "Content-Type: application/json" \
  -d '{"text":"一颗苹果从枝头落下。","voice":"guoxue_default","speed":1.0}' \
  -o out.wav
```

### POST /tts/segments — 批量分段
```json
{"segments": [{"text": "第一句", "gap_after": 0.3}, {"text": "第二句"}], "voice": "guoxue_default"}
```

### GET/POST /voices — 音色库
- `GET /voices` 列出已注册克隆音色
- `POST /voices` 注册克隆音色（multipart form）：
```bash
# ref_audio 建议先转 24kHz mono wav；ref_text 填参考音频的逐字文本
ffmpeg -y -i ref.mp3 -ar 24000 -ac 1 ref.wav
curl -s -X POST http://localhost:7842/voices \
  -F "name=my_voice" -F "ref_audio=@ref.wav" -F "ref_text=参考音频的文字内容"
```

## 已注册音色

| 名字 | 来源 | 用途 |
|------|------|------|
| `guoxue_default` | 03-资产/音色采样/01_默认声线_无指令.mp3（道德经第九章朗读，5.7s） | 科普/国学解说默认音色 |

采样资产库：`D:\work\gx\03-资产\音色采样\`（01-06 共 6 个男声采样，可按需注册更多）。

## 批量解说轨产线（SRT → 时间轴对位 wav）

现成脚本：本仓库 `scripts/tts_omni.py`（本机已部署一份在 `D:\work\gx\06-渲染工作区\frametell-gravity\tts_omni.py`，同目录另有 `tts_audio8.py` 为 Audio8 备胎版）
```bash
python tts_omni.py <字幕.srt> <out.wav> [voice=guoxue_default] [speed=1.0]
```
逐句合成 → 超槽位自动两级 atempo 压缩（上限 2.6）→ 按起始时间 adelay → amix 成 48kHz 立体声。同目录 `tts_audio8.py` 为 Audio8 备胎版（纯 CPU ONNX，同工艺）。

## 成片混音配方（与手搓 S002 管线一致）

```bash
ffmpeg -y -i 视频.mp4 -i narration.wav -i BGM.mp3 -filter_complex \
 "[2:a]volume=-17dB,apad[bg];[1:a][bg]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[aout]" \
 -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k -ar 48000 -t <视频时长> out.mp4
```

## 教训

- **本机已部署的服务先查 `docker ps -a`，别凭记忆说"没有"**（2026-10-26 曾漏记此服务）
- 单句合成耗时 ~20s（默认音色）/ ~110s（克隆音色），批量 28 句预留 10-50 分钟，走后台任务
- edge-tts 被本机网络黑洞；百度 gettts 可用作应急在线备胎
