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


def now_iso():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")


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
    p = find_note(args.name)
    if not p:
        print(f"(未找到) {args.name}")
        sys.exit(1)
    print(p.read_text(encoding="utf-8"))


def cmd_add(args):
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
    args = ap.parse_args()
    {
        "list": cmd_list, "search": cmd_search, "show": cmd_show, "add": cmd_add,
        "update": cmd_update, "backlinks": cmd_backlinks, "link": cmd_link,
        "dedup": cmd_dedup, "remote": cmd_remote, "config": cmd_config,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
