# setup_cloudflare_tunnel.ps1
# 引导式部署 Cloudflare Tunnel，把本地 DeepTutor(3782) 暴露到公网，
# 配合 Cloudflare Access 邮箱白名单实现"指定几人"访问。
#
# 用法：在 PowerShell 里运行  .\setup_cloudflare_tunnel.ps1
#   - 非管理员可跑完前 5 步；注册开机自启服务(第6步)需管理员。
#   - cloudflared tunnel login 会开浏览器，需本机交互。

$ErrorActionPreference = "Stop"

function Find-Cloudflared {
    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in @(
        "C:\Program Files (x86)\cloudflared\cloudflared.exe",
        "C:\Program Files\cloudflared\cloudflared.exe"
    )) { if (Test-Path $p) { return $p } }
    return $null
}

$CF = Find-Cloudflared
if (-not $CF) {
    Write-Host "未找到 cloudflared。先装：winget install --id Cloudflare.cloudflared" -ForegroundColor Red
    exit 1
}
Write-Host "cloudflared: $CF" -ForegroundColor Green
& $CF --version

$CF_DIR = Join-Path $env:USERPROFILE ".cloudflared"
if (-not (Test-Path $CF_DIR)) { New-Item -ItemType Directory -Path $CF_DIR | Out-Null }

# 0. 前置：DeepTutor 在跑
Write-Host "`n=== 0. 检查 DeepTutor (localhost:3782) ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest "http://127.0.0.1:3782/api/v1/knowledge/list" -UseBasicParsing -TimeoutSec 5
    Write-Host "DeepTutor 可达: HTTP $($r.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "DeepTutor 不可达！先确保容器在跑：docker start deeptutor" -ForegroundColor Red
    exit 1
}

# 1. 登录 Cloudflare
Write-Host "`n=== 1. 登录 Cloudflare（会开浏览器授权）===" -ForegroundColor Cyan
$certFile = Join-Path $CF_DIR "cert.pem"
if (Test-Path $certFile) {
    Write-Host "已登录（cert.pem 存在），跳过。" -ForegroundColor Yellow
} else {
    & $CF tunnel login
    if (-not (Test-Path $certFile)) {
        Write-Host "登录未完成（cert.pem 未生成）。完成浏览器授权后重跑本脚本。" -ForegroundColor Red
        exit 1
    }
    Write-Host "登录成功。" -ForegroundColor Green
}

# 2. 创建/选用隧道
Write-Host "`n=== 2. 创建隧道 ===" -ForegroundColor Cyan
$TUNNEL = Read-Host "隧道名（回车默认 deeptutor）"
if (-not $TUNNEL) { $TUNNEL = "deeptutor" }
$createOut = (& $CF tunnel create $TUNNEL 2>&1 | Out-String)
Write-Host $createOut
$uuid = ([regex]::Match($createOut, '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')).Value
if (-not $uuid) {
    Write-Host "可能已存在，列出隧道：" -ForegroundColor Yellow
    & $CF tunnel list
    $uuid = Read-Host "输入要用的隧道 UUID（从上面复制，回车跳过用 config 里现存的）"
}
$credJson = Join-Path $CF_DIR "$uuid.json"
Write-Host "隧道: $TUNNEL  UUID: $uuid" -ForegroundColor Green
Write-Host "凭证: $credJson"

# 3. 绑定域名
Write-Host "`n=== 3. 绑定域名 ===" -ForegroundColor Cyan
$HOSTNAME = Read-Host "公网访问域名（如 kb.yourdomain.com，域名需已托管到 Cloudflare）"
if (-not $HOSTNAME) { Write-Host "域名必填。" -ForegroundColor Red; exit 1 }
& $CF tunnel route dns $TUNNEL $HOSTNAME
Write-Host "DNS 已绑定: $HOSTNAME -> $TUNNEL" -ForegroundColor Green

# 4. 写 config.yml
Write-Host "`n=== 4. 写 config.yml ===" -ForegroundColor Cyan
$config = @"
tunnel: $uuid
credentials-file: $credJson

ingress:
  - hostname: $HOSTNAME
    service: http://localhost:3782
  - service: http_status:404
"@
$configPath = Join-Path $CF_DIR "config.yml"
$config | Out-File -FilePath $configPath -Encoding utf8
Write-Host "已写: $configPath" -ForegroundColor Green

# 5. Access 白名单
Write-Host "`n=== 5. 配置 Cloudflare Access 白名单（指定几人）===" -ForegroundColor Cyan
Write-Host @"
去 Cloudflare Zero Trust Dashboard：
  https://one.dash.cloudflare.com/  ->  Access  ->  Applications  ->  Add an application
  - Type: Self-hosted
  - Application domain: $HOSTNAME
  - Identity providers: 勾选 One-time PIN（邮箱验证码，无需第三方登录）
  - Policy: Include  ->  Emails  ->  填入指定几人的邮箱
  - 保存
配置后，访问 https://$HOSTNAME 会先要求邮箱收验证码，通过才进 DeepTutor。
"@ -ForegroundColor Yellow
Read-Host "配好 Access 后回车继续"

# 6. 启动
Write-Host "`n=== 6. 启动隧道 ===" -ForegroundColor Cyan
$svc = Read-Host "注册为开机自启服务？(y/N，需管理员 PowerShell)"
if ($svc -eq "y" -or $svc -eq "Y") {
    & $CF service install
    & $CF service start
    Write-Host "已注册并启动服务（开机自启）。" -ForegroundColor Green
} else {
    $run = Read-Host "现在前台跑一次测试？(y/N)"
    if ($run -eq "y" -or $run -eq "Y") {
        Write-Host "前台运行中（Ctrl+C 停止）..." -ForegroundColor Yellow
        & $CF tunnel run $TUNNEL
    } else {
        Write-Host "手动启动: & '$CF' tunnel run $TUNNEL" -ForegroundColor Yellow
    }
}

Write-Host @"
`n========== 部署完成 ==========
公网访问: https://$HOSTNAME        (需 Access 邮箱白名单)
知识库:   进页面后选 obsidian-vault
本地:     http://127.0.0.1:3782    (免认证，局域网内用)
局域网:   http://192.168.0.4:3782  (免认证)
==============================
"@ -ForegroundColor Green
