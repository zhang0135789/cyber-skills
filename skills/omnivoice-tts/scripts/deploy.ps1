# omnivoice-tts 一键部署（Windows / Docker Desktop）
# 用法:  .\deploy.ps1                     # 常规部署
#        .\deploy.ps1 -Force              # 强制重建容器
#        .\deploy.ps1 -Port 7842 -VoiceSample "参考音频.wav" -VoiceText "参考音频文字"
param(
    [switch]$Force,
    [string]$Port = "7842",
    [string]$VoiceSample = "",
    [string]$VoiceText = ""
)
$ErrorActionPreference = "Stop"
$NAME = "omnivoice-tts"
$IMAGE = "voice-clone-local:0.1.0"
$ROOT = $PSScriptRoot  # skill 根目录（含 server/）

function Fail($msg) { Write-Host "✗ $msg" -ForegroundColor Red; exit 1 }

# 0. docker 就绪检查
docker info *> $null
if ($LASTEXITCODE -ne 0) { Fail "Docker 未运行，请先启动 Docker Desktop" }

# 1. 已部署检查
$existing = docker ps -a --filter "name=$NAME" --format "{{.Names}} {{.Status}}"
if ($existing) {
    if ($existing -match "healthy" -and -not $Force) {
        Write-Host "✓ $NAME 已在运行（$existing），如需重建请加 -Force" -ForegroundColor Green
        Write-Host "  服务地址: http://localhost:$Port"
        exit 0
    }
    Write-Host "移除旧容器..." ; docker rm -f $NAME *> $null
}

# 2. 构建镜像（torch CPU ~2GB，首次 10-20 分钟）
Write-Host "▶ 构建镜像 $IMAGE（首次约 10-20 分钟）..."
docker build -t $IMAGE (Join-Path $ROOT "server") | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "镜像构建失败" }

# 3. 持久卷：音色库 + 模型缓存（重建容器不丢音色、不重复下模型）
docker volume create omnivoice-data *> $null
docker volume create omnivoice-models *> $null

# 4. 启动容器
Write-Host "▶ 启动容器（--restart unless-stopped 开机自启）..."
docker run -d --name $NAME `
    -p "${Port}:7842" `
    -v omnivoice-data:/data `
    -v omnivoice-models:/models/hf `
    --restart unless-stopped `
    $IMAGE *> $null
if ($LASTEXITCODE -ne 0) { Fail "容器启动失败" }

# 5. 等模型加载（首次自动下载 ~3GB，走 hf-mirror，最长 30 分钟）
Write-Host "▶ 等待模型加载（首次会下载 ~3GB，请耐心）..."
$deadline = (Get-Date).AddMinutes(30)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 10
    try {
        $h = Invoke-RestMethod "http://localhost:$Port/health" -TimeoutSec 3
        if ($h.model_loaded) {
            Write-Host "✓ 模型加载完成，服务就绪: http://localhost:$Port" -ForegroundColor Green
            $voices = ($h.voices -join ", ")
            if ($voices) { Write-Host "  已注册音色: $voices" }
            break
        }
        Write-Host "  模型加载中... ($((Get-Date).ToString('HH:mm:ss')))"
    } catch { Write-Host "  等待服务响应..." }
}
if (-not $h.model_loaded) { Fail "30 分钟内模型未加载完成，查看日志: docker logs $NAME" }

# 6. 可选：注册克隆音色
if ($VoiceSample -and (Test-Path $VoiceSample)) {
    $tmp = Join-Path $env:TEMP "ov_ref.wav"
    ffmpeg -y -v error -i $VoiceSample -ar 24000 -ac 1 $tmp
    curl.exe -s -X POST "http://localhost:$Port/voices" `
        -F "name=guoxue_default" -F "ref_audio=@$tmp" -F "ref_text=$VoiceText"
    Write-Host "✓ 已注册克隆音色 guoxue_default" -ForegroundColor Green
}

# 7. 完成提示
Write-Host ""
Write-Host "═══ omnivoice-tts 部署完成 ═══" -ForegroundColor Cyan
Write-Host "试音:  curl -s -X POST http://localhost:$Port/tts -H 'Content-Type: application/json' -d '{\"text\":\"你好，世界。\",\"speed\":1.0}' -o test.wav"
Write-Host "自启:  容器已设 --restart unless-stopped，随 Docker Desktop 启动"
