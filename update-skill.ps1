# update-skill.ps1 — 一键升级赛博大脑 skill 到最新版（Windows）
# 用法：powershell -ExecutionPolicy Bypass -File update-skill.ps1
param(
    [string]$Repo = "https://github.com/zhang0135789/cyber-skills.git",
    [string]$Skill = "knowledge-vault"
)
$ErrorActionPreference = "Stop"
$tmp = Join-Path $env:TEMP "cyber-skills-update"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
Write-Host "==> 拉取最新代码: $Repo"
git clone --depth 1 $Repo $tmp
$dest = Join-Path $env:USERPROFILE ".workbuddy\skills\$Skill"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Recurse -Force (Join-Path $tmp "skills\$Skill\*") $dest
Remove-Item -Recurse -Force $tmp
Write-Host ""
Write-Host "✅ 已升级 $Skill 到最新版"
Write-Host "   安装位置: $dest"
Write-Host "   重开 WorkBuddy 会话后生效"
