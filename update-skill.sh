#!/usr/bin/env bash
# update-skill.sh — 一键升级赛博大脑 skill 到最新版（macOS / Linux）
# 用法：bash update-skill.sh
set -e
REPO="https://github.com/zhang0135789/cyber-skills.git"
SKILL="knowledge-vault"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "==> 拉取最新代码: $REPO"
git clone --depth 1 "$REPO" "$TMP"
DEST="${HOME}/.workbuddy/skills/${SKILL}"
mkdir -p "$DEST"
cp -r "$TMP/skills/${SKILL}/"* "$DEST/"
echo ""
echo "✅ 已升级 ${SKILL} 到最新版"
echo "   安装位置: ${DEST}"
echo "   重开 WorkBuddy 会话后生效"
