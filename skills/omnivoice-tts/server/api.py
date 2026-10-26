"""OmniVoice 本地 TTS 服务（voice-clone-local skill）

零云端：模型与推理全部本地；首次请求自动下载模型（~3GB，走 HF 镜像）。

端点：
  GET  /health        → {status, model_loaded, voices}
  GET  /voices        → 已保存克隆音色列表
  POST /voices        → multipart(name, ref_audio 文件, ref_text) 注册克隆音色
  POST /tts           → {text, voice?|ref_audio?, ref_text?, instruct?, speed?, num_step?} → audio/wav
  POST /tts/segments  → {segments:[{text,gap_after}...], voice?..., bgm?, bgm_ratio?, total?}
                        → {audio_b64, timing, sample_rate}（多段+停顿+BGM 混音，视频配音主路径）
"""
import base64
import io
import os
import threading
import time
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import numpy as np
import soundfile as sf
from fastapi import FastAPI, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel

DATA = Path(os.environ.get("OV_DATA", "/data"))
VOICES = DATA / "voices"
MODELS = Path(os.environ.get("OV_MODELS", "/models/hf"))
MODELS.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"] = str(MODELS)
VOICES.mkdir(parents=True, exist_ok=True)

SR = 24000
DEFAULT_SPEED = 0.92
DEFAULT_STEPS = 16

app = FastAPI(title="voice-clone-local", version="0.1.0")
_lock = threading.Lock()
_model = None


@app.on_event("startup")
def preload():
    """启动即后台加载模型（首次会自动下载 ~3GB），/health 实时汇报 model_loaded。"""
    threading.Thread(target=get_model, daemon=True).start()


def get_model():
    """惰性加载：首次请求触发模型下载/加载，之后常驻。"""
    global _model
    with _lock:
        if _model is None:
            import torch
            from omnivoice import OmniVoice
            t0 = time.time()
            _model = OmniVoice.from_pretrained(
                "k2-fsa/OmniVoice", device_map="cpu", dtype=torch.float32)
            print(f"[omnivoice] model loaded in {time.time() - t0:.1f}s", flush=True)
    return _model


def _voice_params(voice=None, ref_audio=None, ref_text=None):
    if voice:
        p, t = VOICES / f"{voice}.wav", VOICES / f"{voice}.txt"
        if not p.exists():
            raise HTTPException(404, f"voice '{voice}' 不存在，先 POST /voices 注册")
        return str(p), (t.read_text(encoding="utf-8").strip() if t.exists() else None)
    if ref_audio:
        if not Path(ref_audio).exists():
            raise HTTPException(404, f"ref_audio 不存在: {ref_audio}")
        return ref_audio, ref_text
    return None, None


def _wav_bytes(audio, sr=SR):
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue()


def resample(x, sr_in, sr_out):
    if sr_in == sr_out:
        return x
    n = int(len(x) * sr_out / sr_in)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _model is not None, "device": "cpu",
            "voices": [p.stem for p in VOICES.glob("*.wav")]}


@app.get("/voices")
def list_voices():
    return [{"name": p.stem} for p in sorted(VOICES.glob("*.wav"))]


@app.post("/voices")
async def save_voice(name: str = Form(...), ref_audio: UploadFile = Form(...),
                     ref_text: str = Form("")):
    clean = "".join(c for c in name if c.isalnum() or c in "-_")
    if not clean or clean != name:
        raise HTTPException(400, "name 仅限字母数字、-、_")
    (VOICES / f"{clean}.wav").write_bytes(await ref_audio.read())
    (VOICES / f"{clean}.txt").write_text(ref_text, encoding="utf-8")
    return {"saved": clean}


class TTSReq(BaseModel):
    text: str
    voice: str | None = None
    ref_audio: str | None = None
    ref_text: str | None = None
    instruct: str | None = None
    speed: float = DEFAULT_SPEED
    num_step: int = DEFAULT_STEPS


@app.post("/tts")
def tts(r: TTSReq):
    m = get_model()
    ref, rtext = _voice_params(r.voice, r.ref_audio, r.ref_text)
    kw = dict(text=r.text, num_step=r.num_step, speed=r.speed)
    if ref:
        kw.update(ref_audio=ref, ref_text=rtext)
    if r.instruct:
        kw.update(instruct=r.instruct)
    audio = m.generate(**kw)[0]
    return Response(_wav_bytes(audio), media_type="audio/wav")


class Seg(BaseModel):
    text: str
    gap_after: float = 0.0


class SegReq(BaseModel):
    segments: list[Seg]
    voice: str | None = None
    ref_audio: str | None = None
    ref_text: str | None = None
    instruct: str | None = None
    speed: float = DEFAULT_SPEED
    num_step: int = DEFAULT_STEPS
    total: float | None = None   # 输出总时长(s)，默认最后一句结束 + 0.8
    bgm: str | None = None       # 服务端可读的 BGM wav 路径
    bgm_ratio: float = 0.32      # BGM RMS = VO RMS × ratio（约 -10dB 托底）


@app.post("/tts/segments")
def tts_segments(r: SegReq):
    if not r.segments:
        raise HTTPException(400, "segments 不能为空")
    m = get_model()
    ref, rtext = _voice_params(r.voice, r.ref_audio, r.ref_text)
    sr48 = 48000
    timing, clips, cursor = [], [], 0.0
    for s in r.segments:
        kw = dict(text=s.text, num_step=r.num_step, speed=r.speed)
        if ref:
            kw.update(ref_audio=ref, ref_text=rtext)
        if r.instruct:
            kw.update(instruct=r.instruct)
        a = m.generate(**kw)[0]
        a48 = resample(a, SR, sr48)
        start = round(cursor, 3)
        clips.append((start, a48))
        timing.append({"text": s.text, "start": start, "dur": round(len(a48) / sr48, 3)})
        cursor = start + len(a48) / sr48 + s.gap_after
    last_end = timing[-1]["start"] + timing[-1]["dur"]
    total = r.total or round(last_end + 0.8, 3)
    N = int(total * sr48)
    vo = np.zeros(N)
    for st, a in clips:
        i0 = int(st * sr48)
        i1 = min(i0 + len(a), N)
        vo[i0:i1] += a[:i1 - i0]
    vo *= 0.85 / max(1e-9, float(np.max(np.abs(vo))))   # VO 峰值归一 0.85
    if r.bgm and Path(r.bgm).exists():
        bg, srbg = sf.read(r.bgm)
        if bg.ndim > 1:
            bg = bg.mean(axis=1)
        bg = resample(bg, srbg, sr48)[:N]
        vr = float(np.sqrt(np.mean(vo ** 2))) + 1e-9
        br = float(np.sqrt(np.mean(bg ** 2))) + 1e-9
        vo += bg * (r.bgm_ratio * vr / br)
    out = np.clip(vo, -0.95, 0.95)
    return {"audio_b64": base64.b64encode(_wav_bytes(out.astype(np.float32), sr48)).decode(),
            "timing": {"segments": timing, "total": total, "sample_rate": sr48}}
