# voice-clone-local (omnivoice-tts) — CPU 推理镜像
# 模型 k2-fsa/OmniVoice 首次请求自动下载（~3GB，走 hf-mirror.com）
FROM python:3.12

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

ENV HF_ENDPOINT=https://hf-mirror.com \
    HF_HUB_DISABLE_TELEMETRY=1 \
    HF_HOME=/models/hf \
    OV_DATA=/data \
    OV_MODELS=/models/hf

WORKDIR /app

# torch/torchaudio 用 CPU 版（~940MB×2，GPU 机器可换 cu121 索引）
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --force-reinstall --no-deps torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir omnivoice soundfile fastapi "uvicorn[standard]" python-multipart pydantic

COPY server/api.py api.py

EXPOSE 7842
# start-period 30m：首次启动要下载 ~3GB 模型
HEALTHCHECK --interval=15s --timeout=5s --start-period=30m --retries=3 \
    CMD curl -sf http://127.0.0.1:7842/health || exit 1
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7842"]
