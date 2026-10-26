#!/usr/bin/env bash
# omnivoice-tts 一键部署（Linux / macOS / Docker）
# 用法:  ./deploy.sh                # 常规部署
#        ./deploy.sh --force        # 强制重建容器
#        ./deploy.sh --port 7842 --voice 参考音频.wav --voice-text "参考音频文字"
set -euo pipefail
NAME=omnivoice-tts
IMAGE=voice-clone-local:0.1.0
PORT=7842
FORCE=0
VOICE=""
VTEXT=""
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift;;
    --port) PORT="$2"; shift 2;;
    --voice) VOICE="$2"; shift 2;;
    --voice-text) VTEXT="$2"; shift 2;;
    *) echo "未知参数: $1"; exit 1;;
  esac
done

fail() { echo "✗ $1" >&2; exit 1; }

docker info >/dev/null 2>&1 || fail "Docker 未运行"

existing=$(docker ps -a --filter "name=$NAME" --format '{{.Status}}' || true)
if [[ -n "$existing" ]]; then
  if [[ "$existing" == *healthy* && "$FORCE" != "1" ]]; then
    echo "✓ $NAME 已在运行（$existing），如需重建请加 --force"
    echo "  服务地址: http://localhost:$PORT"
    exit 0
  fi
  echo "移除旧容器..."; docker rm -f "$NAME" >/dev/null
fi

echo "▶ 构建镜像 $IMAGE（首次约 10-20 分钟）..."
docker build -t "$IMAGE" "$ROOT/server" >/dev/null

docker volume create omnivoice-data >/dev/null
docker volume create omnivoice-models >/dev/null

echo "▶ 启动容器..."
docker run -d --name "$NAME" \
  -p "${PORT}:7842" \
  -v omnivoice-data:/data \
  -v omnivoice-models:/models/hf \
  --restart unless-stopped \
  "$IMAGE" >/dev/null

echo "▶ 等待模型加载（首次会下载 ~3GB，最长等 30 分钟）..."
deadline=$((SECONDS + 1800))
loaded=0
while (( SECONDS < deadline )); do
  sleep 10
  if h=$(curl -sf "http://localhost:$PORT/health" 2>/dev/null); then
    if echo "$h" | grep -q '"model_loaded":true'; then
      echo "✓ 模型加载完成，服务就绪: http://localhost:$PORT"
      loaded=1; break
    fi
    echo "  模型加载中..."
  fi
done
(( loaded )) || fail "30 分钟内模型未加载完成，查看日志: docker logs $NAME"

if [[ -n "$VOICE" && -f "$VOICE" ]]; then
  ffmpeg -y -v error -i "$VOICE" -ar 24000 -ac 1 /tmp/ov_ref.wav
  curl -s -X POST "http://localhost:$PORT/voices" \
    -F "name=guoxue_default" -F "ref_audio=@/tmp/ov_ref.wav" -F "ref_text=$VTEXT"
  echo "✓ 已注册克隆音色 guoxue_default"
fi

echo ""
echo "═══ omnivoice-tts 部署完成 ═══"
echo "试音:  curl -s -X POST http://localhost:$PORT/tts -H 'Content-Type: application/json' -d '{\"text\":\"你好，世界。\",\"speed\":1.0}' -o test.wav"
