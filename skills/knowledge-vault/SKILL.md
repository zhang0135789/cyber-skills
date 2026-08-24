---
name: knowledge-vault
version: 0.1.0
description: 赛博大脑——个人知识库桥梁 skill。把对话中的核心知识、信息、习惯、技能、重要资料整理成 Obsidian 双链笔记写入本地 vault，经 DeepTutor 实现远程访问与 AI 检索；对话中可链接、修订、增量补充、双链关联、合并去重。当用户说"存入知识库/入库/记进知识库/查知识库/升级知识库/链接知识库/赛博大脑/升级赛博大脑/升级skill"，或对话中出现值得长期沉淀的核心知识、可复用技能、用户习惯、重要决策、踩坑经验，或用户发来 URL/网页资料（走 defuddle 提纯入库）时触发。
agent_created: true
---

# Knowledge Vault

## 概述

本 skill 充当「WorkBuddy 对话 ↔ 个人知识库」的双向桥梁。知识库底层复用用户已部署的三层架构：

1. **存储与体系层 — Obsidian vault**：`D:\work\obsidian\贾维斯`。所有条目是本地 `.md` 文件，用 `[[双链]]` 互连，治"内容孤立、连不成体系"的痛点。
2. **远程访问与 AI 检索层 — DeepTutor**：本地 `http://127.0.0.1:3782`，局域网 `http://192.168.0.4:3782`。已挂接 `obsidian-vault` 知识库（type=obsidian，免索引就地读写）。任何设备开浏览器即可远程读/问/辅导。
3. **桥梁层 — 本 skill**：在对话中抽取价值内容、整理入库、链接升级。

## 配置

| 项 | 默认值 | 环境变量覆盖 |
|----|--------|-------------|
| vault 路径 | `D:\work\obsidian\贾维斯` | `KB_VAULT` |
| DeepTutor 本地地址 | `http://127.0.0.1:3782` | `DEEPTUTOR_URL` |
| DeepTutor 局域网地址 | `http://192.168.0.4:3782` | `DEEPTUTOR_LAN_URL` |
| 默认署名 | `用户` | `KB_AUTHOR` |
| 公网访问地址 | （未配置） | `KB_PUBLIC_URL` |
| 远程写入 API | （未配置→本地文件模式） | `KB_REMOTE_URL` |
| 写入 API 鉴权 token | （未配置→裸奔） | `KB_API_TOKEN` |

变更路径前先用 `kb_ops.py remote` 确认 DeepTutor 在跑、vault 挂载正常。

## 工作流（对话中入库/升级）

按以下顺序执行，任何一步用户否定则中止当次入库。

### 0. 配置自检 Preflight
首次使用本 skill、或怀疑配置变更时，先自检知识库地址是否就绪：
```
python scripts/kb_ops.py config
```
- 输出 `[OK] 所有关键配置就绪` → 静默继续。
- 输出 `[需配置]` → **暂停入库**，向用户提示缺失项与配置命令（vault 路径 / DeepTutor 地址 / 公网地址 / 署名），待用户配置后再继续。例：
  > 知识库地址还没配好：① vault 路径未设 → `setx KB_VAULT "..."`；② 公网地址未配 → `setx KB_PUBLIC_URL "http://..."`。配好后重开会话即可。
- 已知配置稳定的后续触发可跳过本步，避免打扰。

### 1. 识别 Identify
主动判断对话中是否出现值得长期沉淀的内容。判断标准见下方「AI 入库准则」。识别到时，不要沉默——向用户点明"这条值得入库"并简述理由。

### 2. 确认 Confirm
向用户提议入库，给出拟用标题与归类，等待用户点头。格式示例：
> 这条（关于 X 的方法论）值得入库，拟建笔记《X》挂到 [[主题MOC]]，是否整理？

用户说"存入知识库/入库"等显式指令时跳过本步主动识别，直接进入下一步。

### 3. 去重 Dedup
入库前先检索 vault，避免重复。优先用内置 Grep 工具搜 vault 目录，或执行：
```
python scripts/kb_ops.py search "<关键词>"
python scripts/kb_ops.py dedup "<拟用标题>"
```
- 命中高度相似条目 → 走「修订已有」而非新建。
- 命中相关条目 → 记下，后续做双链关联。
- 无命中 → 新建。

### 4. 整理 Compose
按 `references/note-template.md` 的规范生成笔记：
- **自动归类**：`kb_ops add` 无 `--dir` 时自动按标题+内容关键词决定目录/标签/挂哪个 MOC（规则见 `references/classify-rules.md`，可自改）。归错时用 `--dir` 覆写
- YAML frontmatter：`title / created / updated / author / tags / source / status`（`author` 必填，见「署名与追溯」）
- **Obsidian 语法**：wikilink/embed/callout/property 等按 `references/obsidian-syntax.md` 写（吸收自 Obsidian 官方 agent skills，保证渲染正确）
- 正文：先一句话定义/结论，再展开，末尾「相关」段放 `[[]]` 双链；关键结论可用 `> [!tip]` callout 高亮
- 标签：1-3 个，复用已有标签优先
- 双链：每个新条目至少链 1 个相关旧条目（自动归类会挂到主题 MOC）

### 4.5 网页资料入库（URL 触发）
用户发来 URL / 网页资料时走此分支：
1. `python scripts/kb_ops.py fetch "<url>"` 用 defuddle 提纯网页（未装 defuddle 则退用 WebFetch；`.md` 结尾 URL 直接 WebFetch）
2. 与用户确认拟建标题/归类 → 按步骤 4 整理，frontmatter `source` 填原 URL
3. 细节与注意见 `references/web-extraction.md`

### 5. 写入/升级 Write/Upgrade
- 新建：用 Write 工具写到 `<vault>/<主题目录>/<标题>.md`；或 `python scripts/kb_ops.py add ...`
- 修订：先 Read 原文，Edit 更新内容并把 `updated` 时间戳刷掉；或 `python scripts/kb_ops.py update ...`
- 双链关联：在相关旧条目里补一条 `[[新条目]]`；或 `python scripts/kb_ops.py link <src> <dst>`
- 合并去重：把重复内容并到一条，另一条改为指针（`已合并至 [[主条目]]`）或删除

### 6. 反馈 Feedback
告知用户落点与访问入口（公网入口仅当 `KB_PUBLIC_URL` 已配时给出）：
> 已入库：《标题》→ vault/主题目录/。
> 本机 http://127.0.0.1:3782 ｜ 局域网 http://192.168.0.4:3782 ｜ 公网 $KB_PUBLIC_URL （选 obsidian-vault 知识库）

## AI 入库准则（本 skill 自带要求）

### 该收 Worth keeping
- 核心概念与方法论（能复用的思维框架、决策模型）
- 可复用技能 / SOP（步骤化操作流程、配置方法）
- 用户习惯与偏好（沟通风格、技术栈选择、工具偏好）
- 重要决策及其理由（为什么选 A 不选 B）
- 踩坑经验与修复方案（报错→根因→解法）
- 高价值参考资料来源（链接 + 为什么有价值）

### 不该收 Do NOT keep
- 临时性信息（一次性任务状态、即将过期内容）
- 敏感凭据：密钥 / token / 密码 / AppID 明文 —— 绝不入库，打码也不存
- 闲聊与情绪表达
- 可一键再查的常识事实（不如存"怎么查"的方法）

### 分类与命名
- 不用深文件夹层级，靠 MOC + 标签 + 双链组织
- 概念用名词（《护城河》《安全边际》）；事件/日志带日期（《2026-08-13 投资日志》）；案例带主体（《贵州茅台分析》）
- 每个主题领域建一张 MOC 地图笔记作为入口

### 维护纪律
- 入库前必检索去重，宁修订不新建
- 每条至少 1 条双链，孤立笔记是债务
- 过时条目改 `status: outdated` 并链接继任条目，不直接删
- 敏感信息零容忍：宁可漏收不可泄密

### 署名与追溯
- 每条新笔记 frontmatter 必填 `author`（提供/整理者），默认读 `KB_AUTHOR` 环境变量，未设为 `用户`
- AI 整理的条目：`author` 填用户（知识归属用户），`source` 标 `对话抽取(经AI整理)` 体现参与
- 外部资料：`author` 填原作者/来源，`source` 标出处链接
- 修订时用 `update --by <修订者>`，自动追加到 `contributors` 列表，形成修订追溯链
- 目的：任意条目可回溯"谁加的、谁改过、从哪来"

## 远程访问

知识库具备三层访问入口，按需启用：

| 入口 | 认证 | 范围 |
|------|------|------|
| `http://127.0.0.1:3782` | 无 | 本机 |
| `http://192.168.0.4:3782` | 无 | 局域网 |
| `https://<你的域名>` | Cloudflare Access 邮箱白名单 | 公网（指定几人） |

1. **DeepTutor Web（局域网，默认）**：浏览器开 `http://192.168.0.4:3782` → 左侧 Knowledge 选 `obsidian-vault` → AI 就地读 vault 笔记辅导/问答/出题。
2. **Obsidian 客户端（本机）**：用 Obsidian 打开 vault，享完整双链/图谱/插件。
3. **公网访问（可选，需部署）**：经 Cloudflare Tunnel + Access 把 DeepTutor 安全暴露到公网，仅白名单邮箱可访问。完整部署见 `references/public-access.md`，一键脚本 `scripts/setup_cloudflare_tunnel.ps1`。也可用 **frp 内网穿透**（需自建公网服务器，见 `references/public-access.md` 方案 B）。

### 公网访问部署要点
- 安全模型：**Access 在 CF 边缘做认证，DeepTutor 自身保持免 AUTH**（本地/局域网/MCP 桥接零摩擦）。
- 前置：CF 账号 + 一个托管到 CF 的域名 + cloudflared（`winget install --id Cloudflare.cloudflared`，已装于 `C:\Program Files (x86)\cloudflared\`）。
- `cloudflared tunnel login` 需浏览器交互，AI 无法代劳——运行脚本后按提示完成。
- 部署后设 `KB_PUBLIC_URL=https://<域名>`，skill 反馈入库时会一并给出公网入口。
- vault 原始文件不暴露：公网用户经 DeepTutor 间接读，拿不到 .md 路径。

## 脚本：scripts/kb_ops.py

纯标准库 Python，无需额外依赖。封装常用 vault 操作，AI 可直接用内置工具（Read/Write/Grep/Glob）替代，脚本主要用于批量与用户自运行。

```
python scripts/kb_ops.py list                      # 列出所有笔记（含 frontmatter 摘要）
python scripts/kb_ops.py search "<关键词>"          # 全文搜索，返回文件+匹配行
python scripts/kb_ops.py show "<笔记名>"            # 读笔记全文
python scripts/kb_ops.py add "<标题>" --tags a,b    # 新建笔记（交互或 --content 传内容）
python scripts/kb_ops.py update "<笔记名>"          # 修订（刷 updated 时间戳）
python scripts/kb_ops.py backlinks "<笔记名>"       # 列出谁链接了它
python scripts/kb_ops.py link "<源>" "<目标>"       # 在源笔记补一条 [[目标]] 双链
python scripts/kb_ops.py dedup "<关键词>"           # 找潜在重复条目
python scripts/kb_ops.py remote                     # 打印 DeepTutor 地址并做健康检查
python scripts/kb_ops.py config                     # 配置自检（vault/DeepTutor/公网/署名/远程API），缺失项提醒
python scripts/kb_ops.py classify "<文本>"           # 预览自动归类建议（目录/标签/MOC）
python scripts/kb_ops.py organize                   # 扫描根目录散乱笔记，预览归类建议（加 --apply 实际移动+补标签/MOC双链）
python scripts/kb_ops.py fetch "<url>"              # 用 defuddle 提取网页干净 markdown（网页资料入库）
python scripts/kb_ops.py upgrade                    # 自升级：从 GitHub 拉最新版覆盖本 skill
```

笔记名匹配不区分大小写，可省略 `.md` 后缀。

## 远程写入模式（跨机器集中入库）

默认 `kb_ops` 写本地 vault 文件（`KB_VAULT`）。设了 `KB_REMOTE_URL` 后，`add/update/link/search/list/show/backlinks/dedup` 全部走 HTTP 调远端 `vault_api`，实现**任何机器的 skill 都能写入服务器 vault**，且保留署名/去重/双链流程。

### 服务器端（vault 所在机器）
1. 设鉴权：`setx KB_API_TOKEN "<随机串>"`
2. 启动写入 API：`python scripts/vault_api.py`（监听 3783，需能访问 vault 文件系统）
3. 公网暴露 3783（frp/Cloudflare Tunnel），例如 frp 远程端口 10312

### 客户端（其他龙虾）
```
setx KB_REMOTE_URL "http://<服务器公网地址>:10312"
setx KB_API_TOKEN  "<与服务器相同的 token>"
```
之后 `kb_ops add ...` 自动经公网写入服务器 vault，`config` 自检会显示远程 API 状态。

> 安全：`vault_api` 靠 `X-API-Token` 鉴权，务必设 `KB_API_TOKEN`。公网暴露建议再叠 IP 白名单。
> 写入仍带完整 frontmatter（author/tags/source/status）+ 双链，与本地模式一致。

## 自升级

用户说「升级赛博大脑 / 升级 skill」时，执行 `python scripts/kb_ops.py upgrade`：
从 GitHub 拉取最新版（默认 `https://github.com/zhang0135789/cyber-skills.git`）覆盖本 skill 目录。
- 完成后提示：重开 WorkBuddy 会话生效；本地对 skill 的手动改动会被覆盖（建议先备份）
- 可选：`upgrade --repo <地址> --skill <名称>` 指定来源

## 与 DeepTutor 联动

vault 已被 DeepTutor 登记为 `obsidian-vault` 知识库（id `admin:kb:obsidian-vault`，type=obsidian，免索引）。写入 vault 的笔记，DeepTutor 下次对话即可读到——无需重建索引、无需 embedding。这是本 skill"对话中链接知识库"的远程侧实现。

## 参考资源

- `references/note-template.md` — 笔记模板与 frontmatter 规范
- `references/obsidian-syntax.md` — Obsidian 语法速查（wikilink/embed/callout/property，吸收官方）
- `references/classify-rules.md` — 自动归类体系（主题/目录/MOC/关键词，可自改）
- `references/web-extraction.md` — 网页资料提取入库（defuddle 用法）
- `references/public-access.md` — 公网访问部署指南（Cloudflare Tunnel + Access / frp）
- `scripts/kb_ops.py` — vault 操作 CLI（本地/远程双模式）
- `scripts/vault_api.py` — 远程写入 API 服务端（跑在 vault 所在机器）
- `scripts/setup_cloudflare_tunnel.ps1` — 公网隧道一键部署脚本
