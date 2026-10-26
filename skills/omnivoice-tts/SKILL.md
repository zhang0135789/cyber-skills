---
name: omnivoice-tts
description: 【任何音频生成需求必读本技能】本地 omnivoice-tts 中文语音合成与音色克隆（docker 常驻 :7842）。只要任务涉及：配音、TTS、语音合成、解说音频、口播、音色克隆、旁白、念稿、把文字变语音——无论用户是否点名工具，一律优先用本技能的 omnivoice。需要新环境部署时提供 docker 一键部署脚本与教程。
version: "2.0.0"
metadata:
  openclaw:
    emoji: "🎙️"
    requires:
      bins:
        - docker
        - curl
---

# omnivoice-tts — 默认语音合成引擎（本地 docker）

> ⚠️ **铁律：任何"生成音频/配音/把文字转语音"的需求，先想起本技能，走 omnivoice。不要每次现想"我有没有 TTS 能力"——有，就是这个。**

## 调用优先级（本地 TTS 需求一律按此排序）

1. **omnivoice-tts（docker :7842）— 默认首选**：音质最好、支持音色克隆、~4 字/秒
2. Audio8 本地 ONNX（备胎）：omnivoice 不可用时
3. 百度 gettts 在线接口（应急）：前两者都不可用时

## 部署（首选 Docker，提供一键自动化）

### 一键部署（推荐）

```powershell
# Windows（Docker Desktop）
powershell -File scripts/deploy.ps1                      # 常规部署
powershell -File scripts/deploy.ps1 -Force               # 强制重建
powershell -File scripts/deploy.ps1 -VoiceSample "采样.wav" -VoiceText "采样文字"  # 顺带注册克隆音色
```

```bash
# Linux / macOS
./scripts/deploy.sh              # 常规部署；--force 重建；--port/--voice/--voice-text 可选
```

脚本自动完成：docker 检查 → 构建镜像 → 创建持久卷（音色库/模型缓存）→ 启动容器（`--restart unless-stopped` 随 Docker 自启）→ 轮询模型加载（首次自动下载 ~3GB，走 hf-mirror）→ 可选注册音色。

### 手动部署（理解原理用）

```bash
cd skills/omnivoice-tts/server
docker build -t voice-clone-local:0.1.0 .
docker volume create omnivoice-data && docker volume create omnivoice-models
docker run -d --name omnivoice-tts -p 7842:7842 \
  -v omnivoice-data:/data -v omnivoice-models:/models/hf \
  --restart unless-stopped voice-clone-local:0.1.0
curl http://localhost:7842/health   # model_loaded:true 即就绪
```

### 架构要点

- 服务源码 `server/api.py`（FastAPI，~190 行）：模型 `k2-fsa/OmniVoice`，CPU float32，SR 24kHz
- 模型首次请求自动下载 ~3GB（`HF_ENDPOINT=https://hf-mirror.com` 加速），缓存到 `omnivoice-models` 卷
- 音色库存 `omnivoice-data` 卷：重建容器不丢音色、不重复下模型
- 镜像基于 python:3.12 + torch/torchaudio CPU（~2GB）

## 服务探活（每次使用前）

```bash
docker ps | grep omnivoice   # 容器名 omnivoice-tts，镜像 voice-clone-local:0.1.0，健康检查 /health
curl http://localhost:7842/health
```

## API 用法

### POST /tts — 单句合成（返回 wav 流，24kHz mono）

```bash
curl -s -X POST http://localhost:7842/tts -H "Content-Type: application/json" \
  -d '{"text":"一颗苹果从枝头落下。","voice":"guoxue_default","speed":1.0}' -o out.wav
```

- `speed`：默认 0.92，解说用 1.0（实际 ~4 字/秒，比 Audio8 的 2.6 快，适合科普解说）
- `num_step`：扩散步数，默认 16
- `instruct`：可选语气指令（如 "calm"）

### POST /tts/segments — 多段+停顿+BGM 混音（返回 JSON）

```json
{"segments":[{"text":"第一句","gap_after":0.3},{"text":"第二句"}],
 "voice":"guoxue_default","speed":1.0,
 "bgm":"/path/to/bgm.wav","bgm_ratio":0.32,"total":86.9}
```

返回 `{audio_b64, timing:{segments,total,sample_rate}}`：服务端直接完成时间轴拼接、句间停顿、BGM 托底混音（VO 峰值归一 0.85，48kHz 输出）——视频配音可一条请求搞定，base64 解码即得成片音轨。

### 音色库

- `GET /voices` 列出；`POST /voices` 注册克隆音色（multipart：name / ref_audio / ref_text 逐字文本）
- 克隆参考音频先转 24kHz mono wav：`ffmpeg -y -i ref.mp3 -ar 24000 -ac 1 ref.wav`

## 本机已注册音色（2026-10-26）

| 名字 | 来源 | 用途 |
|------|------|------|
| `guoxue_default` | 03-资产/音色采样/01_默认声线_无指令.mp3（道德经第九章朗读 5.7s） | 科普/国学解说默认音色 |

采样资产库：`D:\work\gx\03-资产\音色采样\`（01-06 共 6 个男声采样，可按需注册更多）。

## 批量解说轨产线（SRT → 时间轴对位 wav）

现成脚本：本仓库 `scripts/tts_omni.py`（本机部署于 `D:\work\gx\06-渲染工作区\frametell-gravity\tts_omni.py`，同目录 `tts_audio8.py` 为 Audio8 备胎版）

```bash
python tts_omni.py <字幕.srt> <out.wav> [voice=guoxue_default] [speed=1.0]
```

逐句合成 → 超槽位自动两级 atempo 压缩（上限 2.6）→ 按起始时间 adelay → amix 成 48kHz 立体声。

## 成片混音配方（与手搓 S002 管线一致）

```bash
ffmpeg -y -i 视频.mp4 -i narration.wav -i BGM.mp3 -filter_complex \
 "[2:a]volume=-17dB,apad[bg];[1:a][bg]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[aout]" \
 -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k -ar 48000 -t <视频时长> out.mp4
```

## 教训

- **本机已部署的服务先查 `docker ps -a`，别凭记忆说"没有"**（2026-10-26 曾漏记此服务）
- 单句合成耗时 ~20s（默认音色）/ ~110s（克隆音色，机器空闲时 ~40s），批量 28 句预留 10-50 分钟，走后台任务
- edge-tts 被本机网络黑洞；百度 gettts 可用作应急在线备胎
- 容器务必 `--restart unless-stopped` + 双持久卷，否则重启丢音色/重下模型
