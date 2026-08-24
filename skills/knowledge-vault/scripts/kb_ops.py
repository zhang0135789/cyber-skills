#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""kb_ops.py — Knowledge Vault operations CLI (pure stdlib).

操作 Obsidian vault（默认 D:\\work\\obsidian\\贾维斯）并对接 DeepTutor 远程访问。
无第三方依赖，仅用标准库。环境变量：KB_VAULT / DEEPTUTOR_URL / DEEPTUTOR_LAN_URL。
"""
import os
import sys
import re
import argparse
import datetime
from pathlib import Path

VAULT = Path(os.environ.get("KB_VAULT", r"D:\work\obsidian\贾维斯"))
DEEPTUTOR_URL = os.environ.get("DEEPTUTOR_URL", "http://127.0.0.1:3782")
DEEPTUTOR_LAN_URL = os.environ.get("DEEPTUTOR_LAN_URL", "http://192.168.0.4:3782")
REMOTE_URL = os.environ.get("KB_REMOTE_URL", "").rstrip("/")
REMOTE_TOKEN = os.environ.get("KB_API_TOKEN", "")


def remote_call(path, params=None, method="GET"):
    """经 HTTP 调用 vault_api（远程写入模式）。设了 KB_REMOTE_URL 即启用。"""
    import urllib.request, urllib.parse, json as _json
    url = REMOTE_URL + path
    headers = {"Content-Type": "application/json"}
    if REMOTE_TOKEN:
        headers["X-API-Token"] = REMOTE_TOKEN
    data = None
    if method == "GET" and params:
        url += "?" + urllib.parse.urlencode(params)
    elif method == "POST":
        data = _json.dumps(params or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=15)
        return _json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def now_iso():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")


# ── 自动归类体系（基于关键词规则评分；可在 references/classify-rules.md 调整）──
CLASSIFY_RULES = [
    {"topic": "技术部署", "dir": "技术类", "moc": "技术类-MOC", "tags": ["技术", "部署"],
     "keywords": ["部署经验", "部署", "环境配置", "wsl", "docker", "安装", "启动", "配置"]},
    {"topic": "数字人", "dir": "数字人", "moc": "数字人-MOC", "tags": ["数字人"],
     "keywords": ["数字人", "avatar", "虚拟人", "虚拟形象", "digital human"]},
    {"topic": "视频生成", "dir": "技术类/视频", "moc": "视频生成-MOC", "tags": ["技术", "视频生成"],
     "keywords": ["视频生成", "文生图", "文生视频", "video", "diffusion", "tts", "图生视频", "选型"]},
    {"topic": "金融投资", "dir": "金融类/金融案例", "moc": "投资研究体系", "tags": ["投资"],
     "keywords": ["投资", "股票", "基金", "财报", "估值", "持仓", "护城河", "安全边际", "房产", "个税", "茅台", "价值投资"]},
    {"topic": "传统文化", "dir": "文化类", "moc": "文化-MOC", "tags": ["文化"],
     "keywords": ["中医", "易经", "八字", "命理", "调鼎集", "六十四卦", "辨证", "少阴"]},
    {"topic": "工具方法", "dir": "工具", "moc": "工具箱", "tags": ["工具"],
     "keywords": ["工具", "skill", "技能", "obsidian", "deeptutor", "提示词", "方法论", "知识库", "mcp"]},
    {"topic": "运营", "dir": "运营", "moc": "运营-MOC", "tags": ["运营"],
     "keywords": ["运营", "排期", "爬取", "视频号", "抖音", "读书号", "涨粉"]},
    {"topic": "日志", "dir": "日志", "moc": "", "tags": ["日志"],
     "keywords": ["日志", "日报", "周报", "复盘"]},
]
DEFAULT_CLASSIFY = {"topic": "未分类", "dir": "", "moc": "", "tags": ["未分类"]}


def classify_text(text):
    """按关键词归类：具体主题(数字人/视频/金融/文化/工具/运营/日志)优先，技术部署兜底。"""
    t = (text or "").lower()
    if not t.strip():
        return dict(DEFAULT_CLASSIFY)
    # 具体主题优先匹配（命中任一关键词即采用）
    for rule in CLASSIFY_RULES:
        if rule["topic"] == "技术部署":
            continue
        if any(kw.lower() in t for kw in rule["keywords"]):
            return {"topic": rule["topic"], "dir": rule["dir"], "moc": rule["moc"], "tags": list(rule["tags"])}
    # 兜底：技术部署（通用部署/配置类）
    for rule in CLASSIFY_RULES:
        if rule["topic"] == "技术部署" and any(kw.lower() in t for kw in rule["keywords"]):
            return {"topic": rule["topic"], "dir": rule["dir"], "moc": rule["moc"], "tags": list(rule["tags"])}
    return dict(DEFAULT_CLASSIFY)


def slugify(s):
    return re.sub(r'[\\/:*?"<>|]', "", s).strip()


def all_notes():
    if not VAULT.exists():
        return []
    return sorted(VAULT.rglob("*.md"))


def find_note(name):
    name_l = name.lower().replace(".md", "").strip()
    for p in all_notes():
        if p.stem.lower() == name_l:
            return p
    for p in all_notes():
        if name_l in p.stem.lower():
            return p
    return None


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm_text, body = m.group(1), m.group(2)
    fm = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, body


def build_frontmatter(meta):
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def refresh_updated(text):
    fm, body = parse_frontmatter(text)
    fm["updated"] = now_iso()
    return build_frontmatter(fm) + "\n\n" + body


def cmd_list(args):
    if REMOTE_URL:
        res = remote_call("/list")
        if isinstance(res, dict) and "error" in res:
            print("远程错误:", res["error"]); return
        print(f"[远程 {REMOTE_URL}] 共 {len(res)} 篇\n")
        for n in res:
            print(f"- {n.get('path')}")
        return
    notes = all_notes()
    if not notes:
        print(f"(空) vault 不存在或无笔记: {VAULT}")
        return
    print(f"vault: {VAULT}  共 {len(notes)} 篇\n")
    for p in notes:
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            text = ""
        fm, _ = parse_frontmatter(text)
        tags = fm.get("tags", "")
        rel = p.relative_to(VAULT)
        tagstr = f"  [#{tags}]" if tags and tags != "[]" else ""
        print(f"- {rel}{tagstr}")


def cmd_search(args):
    if REMOTE_URL:
        res = remote_call("/search", {"q": args.query})
        if isinstance(res, dict) and "error" in res:
            print("远程错误:", res["error"]); return
        for h in res:
            print(f"{h.get('path')}:{h.get('line')}: {h.get('text')}")
        if not res:
            print(f"(无匹配) query={args.query}")
        return
    q = args.query.lower()
    hits = 0
    for p in all_notes():
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if q in line.lower():
                rel = p.relative_to(VAULT)
                print(f"{rel}:{i}: {line.strip()[:140]}")
                hits += 1
                if hits >= args.limit:
                    print(f"... (已达 --limit {args.limit})")
                    return
    if hits == 0:
        print(f"(无匹配) query={args.query}")


def cmd_show(args):
    if REMOTE_URL:
        res = remote_call("/show", {"name": args.name})
        if isinstance(res, dict) and res.get("error"):
            print("远程错误/未找到:", res["error"]); return
        print(res.get("content", ""))
        return
    p = find_note(args.name)
    if not p:
        print(f"(未找到) {args.name}")
        sys.exit(1)
    print(p.read_text(encoding="utf-8"))


def cmd_add(args):
    # 自动归类：未指定 --dir 时，按标题+内容关键词决定目录/标签/挂MOC
    if not args.dir:
        cls = classify_text((args.title or "") + " " + (args.content or ""))
        if cls["dir"]:
            args.dir = cls["dir"]
            if not args.tags:
                args.tags = ",".join(cls["tags"])
            if not args.links and cls["moc"]:
                args.links = cls["moc"]
            print(f"🏷 自动归类: {cls['topic']} → {cls['dir']}/  挂 [[{cls['moc'] or '无'}]]")
    if REMOTE_URL:
        res = remote_call("/add", {"title": args.title, "content": args.content, "tags": args.tags,
                                    "links": args.links, "dir": args.dir, "source": args.source,
                                    "author": args.author or os.environ.get("KB_AUTHOR", "用户")}, "POST")
        if isinstance(res, dict) and res.get("error"):
            print("远程错误:", res["error"]); return
        print(f"✅ [远程] 已新建: {res.get('path')}  作者: {res.get('author')}")
        return
    title = args.title
    fname = slugify(title) + ".md"
    target_dir = VAULT / args.dir if args.dir else VAULT
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / fname
    if target.exists():
        print(f"(已存在) {target} —— 改用 update 修订，或换标题")
        sys.exit(1)
    content = args.content
    if not content and not sys.stdin.isatty():
        content = sys.stdin.read()
    if not content:
        content = f"# {title}\n\n（待补充）\n"
    tags = args.tags or ""
    links = args.links or ""
    author = args.author or os.environ.get("KB_AUTHOR", "用户")
    meta = {
        "title": title,
        "created": now_iso(),
        "updated": now_iso(),
        "author": author,
        "tags": f"[{tags}]" if tags else "[]",
        "source": args.source or "对话抽取",
        "status": "active",
    }
    body = content
    if links:
        link_list = "\n".join(f"- [[{l.strip()}]]" for l in links.split(",") if l.strip())
        body += f"\n\n## 相关\n{link_list}\n"
    out = build_frontmatter(meta) + "\n\n" + body
    target.write_text(out, encoding="utf-8")
    print(f"✅ 已新建: {target.relative_to(VAULT)}")


def cmd_update(args):
    if REMOTE_URL:
        res = remote_call("/update", {"name": args.name, "content": args.content,
                                       "append": args.append, "by": args.by}, "POST")
        if isinstance(res, dict) and res.get("error"):
            print("远程错误:", res["error"]); return
        print(f"✅ [远程] 已更新: {args.name}  updated={res.get('updated')}  contributors={res.get('contributors','')}")
        return
    p = find_note(args.name)
    if not p:
        print(f"(未找到) {args.name}")
        sys.exit(1)
    text = p.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    if args.content:
        body = args.content
    if args.append:
        body = body.rstrip() + "\n\n" + args.append + "\n"
    fm["updated"] = now_iso()
    if args.by:
        existing = fm.get("contributors", "").strip("[]")
        clist = [x.strip() for x in existing.split(",") if x.strip()]
        if args.by not in clist:
            clist.append(args.by)
        fm["contributors"] = "[" + ", ".join(clist) + "]"
    out = build_frontmatter(fm) + "\n\n" + body
    p.write_text(out, encoding="utf-8")
    print(f"✅ 已更新 (updated={fm['updated']}): {p.name}")


def cmd_backlinks(args):
    if REMOTE_URL:
        res = remote_call("/backlinks", {"name": args.name})
        if isinstance(res, dict) and res.get("error"):
            print("远程错误:", res["error"]); return
        found = res.get("backlinks", [])
        if found:
            print(f"[远程] 反向链接到《{res.get('note')}》({len(found)}):")
            for f in found:
                print(f"  - {f}")
        else:
            print(f"[远程] 《{res.get('note')}》无反向链接")
        return
    target = find_note(args.name)
    if not target:
        print(f"(未找到目标笔记) {args.name}")
        sys.exit(1)
    stem = target.stem
    pat = re.compile(r"\[\[" + re.escape(stem) + r"(\|[^\]]+)?\]\]", re.IGNORECASE)
    found = []
    for p in all_notes():
        if p == target:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if pat.search(text):
            found.append(p.relative_to(VAULT))
    if found:
        print(f"反向链接到《{stem}》的笔记 ({len(found)}):")
        for f in found:
            print(f"  - {f}")
    else:
        print(f"(无反向链接) 《{stem}》目前是孤立笔记 —— 建议补双链")


def cmd_link(args):
    if REMOTE_URL:
        res = remote_call("/link", {"src": args.src, "dst": args.dst}, "POST")
        if isinstance(res, dict) and res.get("error"):
            print("远程错误:", res["error"]); return
        print(f"✅ [远程] 已加双链: {args.src} -> [[{args.dst}]]  ({res.get('status')})")
        return
    src = find_note(args.src)
    dst = find_note(args.dst)
    if not src:
        print(f"(未找到源) {args.src}")
        sys.exit(1)
    if not dst:
        print(f"(未找到目标) {args.dst}")
        sys.exit(1)
    text = src.read_text(encoding="utf-8")
    link_line = f"- [[{dst.stem}]]"
    if link_line in text:
        print(f"(已存在该链接) {src.stem} -> {dst.stem}")
        return
    if "## 相关" in text:
        text = text.replace("## 相关", f"## 相关\n{link_line}", 1)
    else:
        text = text.rstrip() + f"\n\n## 相关\n{link_line}\n"
    src.write_text(refresh_updated(text), encoding="utf-8")
    print(f"✅ 已加双链: {src.stem} -> [[{dst.stem}]]")


def cmd_dedup(args):
    if REMOTE_URL:
        res = remote_call("/dedup", {"q": args.query})
        if isinstance(res, dict) and res.get("error"):
            print("远程错误:", res["error"]); return
        if not res:
            print("[远程] (无相关条目，可新建)"); return
        print(f"[远程] 潜在相关条目 (query={args.query}):")
        for r in res:
            print(f"  - {r.get('path')}  (命中 {r.get('score')})")
        return
    q = args.query.lower()
    print(f"潜在相关条目 (query={args.query}):\n")
    found = False
    for p in all_notes():
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        score = 0
        for kw in q.split():
            if kw and (kw in p.stem.lower() or kw in text.lower()):
                score += 1
        if score > 0:
            rel = p.relative_to(VAULT)
            print(f"  - {rel}  (命中 {score} 关键词)")
            found = True
    if not found:
        print("  (无相关条目，可新建)")


def cmd_remote(args):
    import urllib.request
    print(f"DeepTutor 本地:   {DEEPTUTOR_URL}")
    print(f"DeepTutor 局域网: {DEEPTUTOR_LAN_URL}")
    print(f"vault:            {VAULT}")
    print(f"知识库 KB:        obsidian-vault (id admin:kb:obsidian-vault, type=obsidian, 免索引)")
    for label, url in [("本地", DEEPTUTOR_URL), ("局域网", DEEPTUTOR_LAN_URL)]:
        try:
            r = urllib.request.urlopen(url + "/api/v1/knowledge/list", timeout=4)
            print(f"[{label}] 健康: HTTP {r.getcode()} OK")
        except Exception as e:
            print(f"[{label}] 不可达: {e}")


def cmd_classify(args):
    text = args.text
    cls = classify_text(text)
    print(f"输入: {text[:60]}{'...' if len(text)>60 else ''}")
    print(f"归类: {cls['topic']}")
    print(f"目录: {cls['dir'] or '(根目录)'}")
    print(f"标签: {','.join(cls['tags'])}")
    print(f"挂MOC: [[{cls['moc']}]]" if cls["moc"] else "挂MOC: (无)")


def cmd_organize(args):
    if REMOTE_URL:
        print("organize 是服务器端文件操作，需在 vault 所在机器本地运行（不走远程）。"); return
    if not VAULT.exists():
        print(f"vault 不存在: {VAULT}"); return
    root_notes = [p for p in VAULT.glob("*.md")]
    if not root_notes:
        print("根目录无散乱笔记。"); return
    import shutil
    print(f"根目录散乱笔记 {len(root_notes)} 篇，归类建议：\n")
    moved = 0
    for p in root_notes:
        # 跳过 Obsidian 默认笔记与 MOC 入口（留在根目录做入口）
        try:
            fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        except Exception:
            fm = {}
        if p.stem == "欢迎" or "MOC" in p.stem or "MOC" in fm.get("tags", ""):
            print(f"- {p.name}  →  (保留根目录)  [MOC/系统笔记]")
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        # 标题优先，标题未命中再看全文（减少内容噪声误归）
        cls = classify_text(p.stem)
        if cls["topic"] == "未分类":
            cls = classify_text(p.stem + " " + text)
        target_dir = cls["dir"]
        print(f"- {p.name}  →  {target_dir or '(根目录)'}/  [{cls['topic']}]  tags:{','.join(cls['tags'])}" + (f"  MOC:[[{cls['moc']}]]" if cls["moc"] else ""))
        if args.apply and target_dir:
            new_dir = VAULT / target_dir
            new_dir.mkdir(parents=True, exist_ok=True)
            dst = new_dir / p.name
            if dst.exists():
                print(f"    跳过(目标已存在): {dst}"); continue
            shutil.move(str(p), str(dst))
            # 补 tags / MOC 双链
            try:
                t = dst.read_text(encoding="utf-8")
                fm, body = parse_frontmatter(t)
                if not fm.get("tags") or fm.get("tags") == "[]":
                    fm["tags"] = "[" + ",".join(cls["tags"]) + "]"
                if cls["moc"] and f"[[{cls['moc']}]]" not in t:
                    if "## 相关" in body:
                        body = body.replace("## 相关", f"## 相关\n- [[{cls['moc']}]]", 1)
                    else:
                        body = body.rstrip() + f"\n\n## 相关\n- [[{cls['moc']}]]\n"
                dst.write_text(build_frontmatter(fm) + "\n\n" + body, encoding="utf-8")
            except Exception as e:
                print(f"    补元数据失败: {e}")
            moved += 1
    if args.apply:
        print(f"\n✅ 已移动 {moved} 篇到对应目录并补标签/MOC双链")
        # 扫描全库 MOC 链接 + 体系内 MOC，补建缺失的（根目录入口）
        known = {r["moc"] for r in CLASSIFY_RULES if r["moc"]}
        linked = set(known)
        for note in all_notes():
            try:
                txt = note.read_text(encoding="utf-8")
            except Exception:
                continue
            for m in re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", txt):
                nm = m.strip()
                if nm in known or "MOC" in nm:
                    linked.add(nm)
        created = []
        for moc in sorted(linked):
            if find_note(moc):
                continue
            moc_path = VAULT / f"{slugify(moc)}.md"
            meta = {
                "title": moc, "created": now_iso(), "updated": now_iso(),
                "author": os.environ.get("KB_AUTHOR", "用户"), "tags": "[MOC]",
                "source": "organize自动创建", "status": "active",
            }
            body = (f"# {moc}\n\n（自动创建的知识库入口）\n\n"
                    f"> 指向本 MOC 的笔记会自动出现在右侧反向链接面板。\n")
            moc_path.write_text(build_frontmatter(meta) + "\n\n" + body, encoding="utf-8")
            created.append(moc)
        if created:
            print(f"🆕 自动补建缺失 MOC {len(created)} 个: {', '.join(created)}（根目录）")
        else:
            print(f"✅ 体系内 MOC 均已存在（{len(known)} 个）")
    else:
        print(f"\n(预览模式，加 --apply 实际移动并补标签/MOC双链)")


def _find_defuddle():
    import shutil
    cands = [
        shutil.which("defuddle"),
        r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2\defuddle.cmd",
        r"C:\Program Files\nodejs\defuddle.cmd",
        os.path.expandvars(r"%APPDATA%\npm\defuddle.cmd"),
    ]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def cmd_fetch(args):
    """用 defuddle CLI 提取网页干净 markdown（网页资料入库用）。"""
    import subprocess
    url = args.url
    defuddle = _find_defuddle()
    if not defuddle:
        print("(defuddle 未安装：npm install -g defuddle，或改用 WebFetch)")
        return
    try:
        if defuddle.lower().endswith(".cmd") or defuddle.lower().endswith(".bat"):
            r = subprocess.run(["cmd.exe", "/c", defuddle, "parse", url, "--md"],
                               capture_output=True, text=True, timeout=90)
        else:
            r = subprocess.run([defuddle, "parse", url, "--md"],
                               capture_output=True, text=True, timeout=90)
        md = r.stdout
        if not md.strip():
            md = f"(defuddle 无输出: {(r.stderr or '未知')[:300]})"
    except Exception as e:
        md = f"(defuddle 失败: {e})"
    if args.save:
        p = VAULT / f"{slugify(args.save)}.md"
        p.write_text(md, encoding="utf-8")
        print(f"✅ 已存: {p.relative_to(VAULT)}")
    else:
        print(md)


def cmd_upgrade(args):
    """自升级：从 GitHub 拉取最新版覆盖本 skill（用户说'升级赛博大脑'时执行）。"""
    import subprocess
    import tempfile
    import shutil
    repo = args.repo or "https://github.com/zhang0135789/cyber-skills.git"
    skill = args.skill or "knowledge-vault"
    dest = Path(__file__).resolve().parent.parent  # 本 skill 根目录
    tmp = Path(tempfile.mkdtemp(prefix="cyber-skills-"))
    try:
        print(f"==> 拉取最新代码: {repo}")
        r = subprocess.run(["git", "clone", "--depth", "1", repo, str(tmp)],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print(f"(git clone 失败: {(r.stderr or '')[:300]})")
            return
        src = tmp / "skills" / skill
        if not src.exists():
            print(f"(仓库里没找到 skills/{skill})")
            return
        # 清空本 skill（保留 .git/__pycache__），再覆盖
        for f in dest.iterdir():
            if f.name in (".git", "__pycache__"):
                continue
            if f.is_dir():
                shutil.rmtree(f, ignore_errors=True)
            else:
                f.unlink(missing_ok=True)
        for f in src.iterdir():
            if f.is_dir():
                shutil.copytree(f, dest / f.name, dirs_exist_ok=True)
            else:
                shutil.copy2(f, dest / f.name)
        print(f"✅ 已升级 {skill} 到最新版: {dest}")
        print("   重开 WorkBuddy 会话后生效（新功能/新命令）")
        print("   提示：本地对 skill 的手动改动会被仓库版覆盖，建议先备份")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_config(args):
    import urllib.request
    print("=== 赛博大脑 配置自检 ===\n")
    issues = []

    vault_ok = VAULT.exists()
    notes_n = len(all_notes())
    print(f"vault 路径 (KB_VAULT): {VAULT}  [{'OK, ' + str(notes_n) + ' 篇' if vault_ok else '不存在'}]")
    if not vault_ok:
        issues.append("vault 不存在：setx KB_VAULT \"<你的 Obsidian vault 路径>\"")

    for label, var, url in [
        ("本地", "DEEPTUTOR_URL", DEEPTUTOR_URL),
        ("局域网", "DEEPTUTOR_LAN_URL", DEEPTUTOR_LAN_URL),
    ]:
        try:
            urllib.request.urlopen(url + "/api/v1/knowledge/list", timeout=4)
            print(f"DeepTutor {label} ({var}): {url}  [OK]")
        except Exception:
            print(f"DeepTutor {label} ({var}): {url}  [不可达]")
            issues.append(f"{label} DeepTutor 不可达：确认服务在跑，或 setx {var} \"http://<地址>:3782\"")

    pub = os.environ.get("KB_PUBLIC_URL", "")
    if pub:
        try:
            urllib.request.urlopen(pub + "/api/v1/knowledge/list", timeout=5)
            print(f"公网 (KB_PUBLIC_URL): {pub}  [OK]")
        except Exception:
            print(f"公网 (KB_PUBLIC_URL): {pub}  [不可达]")
            issues.append("公网地址不可达：检查 frpc/隧道是否在跑")
    else:
        print("公网 (KB_PUBLIC_URL): (未配置)")
        issues.append("公网地址未配置：如需远程访问 setx KB_PUBLIC_URL \"http://<公网地址>:端口\"")

    print(f"默认署名 (KB_AUTHOR): {os.environ.get('KB_AUTHOR', '用户')}")

    if REMOTE_URL:
        try:
            h = remote_call("/health")
            if isinstance(h, dict) and h.get("status") == "ok":
                print(f"远程写入 API (KB_REMOTE_URL): {REMOTE_URL}  [OK, {h.get('notes')} 篇]")
            else:
                print(f"远程写入 API (KB_REMOTE_URL): {REMOTE_URL}  [不可达: {h}]")
                issues.append("远程写入 API 不可达：检查 vault_api 是否在跑 + frp 隧道")
        except Exception as e:
            print(f"远程写入 API (KB_REMOTE_URL): {REMOTE_URL}  [不可达: {e}]")
            issues.append("远程写入 API 不可达")
    else:
        print("远程写入 API (KB_REMOTE_URL): (未配置 → 本地文件模式)")
    print()
    if issues:
        print("[需配置] 以下项需处理后再入库：")
        for i in issues:
            print(f"  - {i}")
    else:
        print("[OK] 所有关键配置就绪。")


def main():
    ap = argparse.ArgumentParser(description="Knowledge Vault operations CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=50)
    sub.add_parser("show").add_argument("name")
    a = sub.add_parser("add")
    a.add_argument("title")
    a.add_argument("--content")
    a.add_argument("--tags")
    a.add_argument("--links")
    a.add_argument("--dir")
    a.add_argument("--source")
    a.add_argument("--author")
    u = sub.add_parser("update")
    u.add_argument("name")
    u.add_argument("--content")
    u.add_argument("--append")
    u.add_argument("--by")
    sub.add_parser("backlinks").add_argument("name")
    l = sub.add_parser("link")
    l.add_argument("src")
    l.add_argument("dst")
    sub.add_parser("dedup").add_argument("query")
    sub.add_parser("remote")
    sub.add_parser("config")
    sub.add_parser("classify").add_argument("text")
    o = sub.add_parser("organize")
    o.add_argument("--apply", action="store_true")
    f = sub.add_parser("fetch")
    f.add_argument("url")
    f.add_argument("--save")
    g = sub.add_parser("upgrade")
    g.add_argument("--repo")
    g.add_argument("--skill")
    args = ap.parse_args()
    {
        "list": cmd_list, "search": cmd_search, "show": cmd_show, "add": cmd_add,
        "update": cmd_update, "backlinks": cmd_backlinks, "link": cmd_link,
        "dedup": cmd_dedup, "remote": cmd_remote, "config": cmd_config,
        "classify": cmd_classify, "organize": cmd_organize, "fetch": cmd_fetch,
        "upgrade": cmd_upgrade,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
