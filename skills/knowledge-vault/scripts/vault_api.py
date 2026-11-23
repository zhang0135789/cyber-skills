#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""vault_api.py — 赛博大脑 vault 远程写入 API（纯标准库 http.server）。

跑在能访问 vault 文件系统的服务器上（推荐 Docker：deploy/vault-api.compose.yaml），
供远程 skill 经 HTTP 写入 vault。保留赛博大脑 frontmatter/署名/双链规范。
kb_ops.py 设 KB_REMOTE_URL 即走本 API。

环境变量：
  KB_VAULT       vault 路径（容器内默认 /vault）
  KB_HOST_VAULT  vault 宿主路径（仅用于 /health 展示，便于排查）
  KB_API_PORT    监听端口（默认 3783）
  KB_API_TOKEN   鉴权 token（强烈建议设置，否则裸奔）

安全与健壮性：
  - /add 的 dir 做路径穿越校验，禁止写出 vault
  - 笔记名子串匹配多命中时返回 candidates，由调用方确认，避免改错文件
  - 覆盖写之前自动快照到 <vault>/.kb_versions/<笔记名>/，每条保留最近 10 份
  - PermissionError 返回修复指引（容器 uid 与文件属主不一致场景）
"""
import os
import re
import json
import shutil
import datetime
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

VAULT = Path(os.environ.get("KB_VAULT", r"D:\work\obsidian\贾维斯"))
PORT = int(os.environ.get("KB_API_PORT", "3783"))
TOKEN = os.environ.get("KB_API_TOKEN", "")
HOST_VAULT = os.environ.get("KB_HOST_VAULT", "")
API_VERSION = "0.2.1"

KEEP_VERSIONS = 10


class AmbiguousNote(Exception):
    """笔记名子串匹配命中多篇时抛出，携带候选列表。"""

    def __init__(self, candidates):
        self.candidates = candidates
        super().__init__("ambiguous note name")


def now_iso():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")


def slugify(s):
    return re.sub(r'[\\/:*?"<>|]', "", s).strip()


def all_notes():
    if not VAULT.exists():
        return []
    # 排除点开头目录（.obsidian/.kb_versions 等系统目录），避免快照被当作笔记
    return sorted(
        p for p in VAULT.rglob("*.md")
        if not any(part.startswith(".") for part in p.relative_to(VAULT).parts)
    )


def find_note(name):
    """精确名优先；子串匹配单命中直接采用，多命中抛 AmbiguousNote。"""
    nl = name.lower().replace(".md", "").strip()
    exact = [p for p in all_notes() if p.stem.lower() == nl]
    if exact:
        return exact[0]
    subs = [p for p in all_notes() if nl and nl in p.stem.lower()]
    if len(subs) == 1:
        return subs[0]
    if len(subs) > 1:
        raise AmbiguousNote([str(p.relative_to(VAULT)) for p in subs])
    return None


def find_note_or_candidates(name):
    """返回 (note, None) 或 (None, candidates)。"""
    try:
        return find_note(name), None
    except AmbiguousNote as e:
        return None, e.candidates


def resolve_dir(subdir):
    """校验子目录在 vault 内，防路径穿越；非法返回 None。"""
    if not subdir:
        return VAULT
    try:
        target = (VAULT / subdir).resolve()
        if not target.is_relative_to(VAULT.resolve()):
            return None
        return target
    except (ValueError, OSError):
        return None


def parse_fm(text):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, m.group(2)


def build_fm(meta):
    return "---\n" + "\n".join(f"{k}: {v}" for k, v in meta.items()) + "\n---"


def backup_note(p):
    """覆盖写之前快照原文到 .kb_versions/<笔记名>/，保留最近 KEEP_VERSIONS 份。"""
    try:
        vdir = VAULT / ".kb_versions" / p.stem
        vdir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(p, vdir / f"{ts}.md")
        versions = sorted(vdir.glob("*.md"))
        for old in versions[:-KEEP_VERSIONS]:
            old.unlink(missing_ok=True)
    except Exception:
        pass  # 备份失败不阻断主流程


def op_list():
    return [{"path": str(p.relative_to(VAULT)), "title": p.stem} for p in all_notes()]


def op_search(q):
    q = (q or "").lower()
    hits = []
    for p in all_notes():
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if q and q in line.lower():
                hits.append({"path": str(p.relative_to(VAULT)), "line": i, "text": line.strip()[:140]})
    return hits


def op_show(name):
    p, candidates = find_note_or_candidates(name)
    if candidates:
        return {"error": "ambiguous", "candidates": candidates}
    if not p:
        return {"error": "not found"}
    return {"path": str(p.relative_to(VAULT)), "content": p.read_text(encoding="utf-8")}


def op_add(title, content, tags, links, subdir, source, author):
    title = title or "未命名"
    fname = slugify(title) + ".md"
    target_dir = resolve_dir(subdir)
    if target_dir is None:
        return {"error": "bad dir", "hint": f"dir 越界：仅允许 vault 内子目录（收到 {subdir!r}）"}
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / fname
    if target.exists():
        return {"error": "exists", "path": str(target.relative_to(VAULT))}
    author = author or os.environ.get("KB_AUTHOR", "用户")
    meta = {
        "title": title,
        "created": now_iso(),
        "updated": now_iso(),
        "author": author,
        "tags": f"[{tags}]" if tags else "[]",
        "source": source or "对话抽取(经AI整理)",
        "status": "active",
    }
    body = content or f"# {title}\n\n（待补充）\n"
    if links:
        link_list = "\n".join(f"- [[{l.strip()}]]" for l in links.split(",") if l.strip())
        body += f"\n\n## 相关\n{link_list}\n"
    out = build_fm(meta) + "\n\n" + body
    target.write_text(out, encoding="utf-8")
    return {"status": "created", "path": str(target.relative_to(VAULT)), "author": author}


def op_update(name, content, append, by, expected_updated=None):
    p, candidates = find_note_or_candidates(name)
    if candidates:
        return {"error": "ambiguous", "candidates": candidates}
    if not p:
        return {"error": "not found"}
    text = p.read_text(encoding="utf-8")
    fm, body = parse_fm(text)
    # 乐观锁：客户端携带 expected_updated 时校验版本，防止并发覆盖丢失改动
    if expected_updated and (fm.get("updated", "") or "") != expected_updated:
        return {
            "error": "conflict",
            "expected_updated": expected_updated,
            "current_updated": fm.get("updated", ""),
            "hint": "该笔记在读取后被其他会话修改过。请重新 show 获取最新内容再改；确认要覆盖时用 kb_ops update --force。",
        }
    backup_note(p)
    if content:
        body = content
    if append:
        body = body.rstrip() + "\n\n" + append + "\n"
    fm["updated"] = now_iso()
    if by:
        existing = fm.get("contributors", "").strip("[]")
        clist = [x.strip() for x in existing.split(",") if x.strip()]
        if by not in clist:
            clist.append(by)
        fm["contributors"] = "[" + ", ".join(clist) + "]"
    p.write_text(build_fm(fm) + "\n\n" + body, encoding="utf-8")
    return {"status": "updated", "updated": fm["updated"], "contributors": fm.get("contributors")}


def op_link(src, dst):
    s, candidates = find_note_or_candidates(src)
    if candidates:
        return {"error": "ambiguous", "candidates": candidates, "field": "src"}
    if not s:
        return {"error": "src not found"}
    d, candidates = find_note_or_candidates(dst)
    if candidates:
        return {"error": "ambiguous", "candidates": candidates, "field": "dst"}
    if not d:
        return {"error": "dst not found"}
    text = s.read_text(encoding="utf-8")
    line = f"- [[{d.stem}]]"
    if line in text:
        return {"status": "exists"}
    backup_note(s)
    if "## 相关" in text:
        text = text.replace("## 相关", f"## 相关\n{line}", 1)
    else:
        text = text.rstrip() + f"\n\n## 相关\n{line}\n"
    s.write_text(text, encoding="utf-8")
    return {"status": "linked", "src": s.stem, "dst": d.stem}


def op_backlinks(name):
    target, candidates = find_note_or_candidates(name)
    if candidates:
        return {"error": "ambiguous", "candidates": candidates}
    if not target:
        return {"error": "not found"}
    stem = target.stem
    pat = re.compile(r"\[\[" + re.escape(stem) + r"(\|[^\]]+)?\]\]", re.IGNORECASE)
    found = []
    for p in all_notes():
        if p == target:
            continue
        try:
            if pat.search(p.read_text(encoding="utf-8")):
                found.append(str(p.relative_to(VAULT)))
        except Exception:
            pass
    return {"note": stem, "backlinks": found}


def op_dedup(q):
    q = (q or "").lower()
    res = []
    for p in all_notes():
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        score = sum(1 for kw in q.split() if kw and (kw in p.stem.lower() or kw in text.lower()))
        if score > 0:
            res.append({"path": str(p.relative_to(VAULT)), "score": score})
    return res


def health_payload():
    info = {
        "status": "ok",
        "vault": str(VAULT),
        "notes": len(all_notes()),
        "version": API_VERSION,
    }
    try:
        info["uid"] = os.geteuid()  # 仅类 Unix（容器）环境存在
    except AttributeError:
        pass
    if HOST_VAULT:
        info["host_vault"] = HOST_VAULT
    return info


def err_payload(e):
    if isinstance(e, PermissionError):
        return {
            "error": str(e),
            "hint": "Errno 13：容器 uid 与文件属主不一致。检查 compose 的 user 与文件属主(ls -ln)是否一致，"
                    "或 docker exec <容器> chmod 放开属主为自己的文件。",
        }
    return {"error": str(e)}


class Handler(BaseHTTPRequestHandler):
    def _auth(self):
        if TOKEN and self.headers.get("X-API-Token") != TOKEN:
            self._send(401, {"error": "unauthorized"})
            return False
        return True

    def _send(self, code, obj):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if not self._auth():
            return
        p = urlparse(self.path)
        q = parse_qs(p.query)
        try:
            if p.path == "/health":
                self._send(200, health_payload())
            elif p.path == "/list":
                self._send(200, op_list())
            elif p.path == "/search":
                self._send(200, op_search(q.get("q", [""])[0]))
            elif p.path == "/show":
                self._send(200, op_show(q.get("name", [""])[0]))
            elif p.path == "/backlinks":
                self._send(200, op_backlinks(q.get("name", [""])[0]))
            elif p.path == "/dedup":
                self._send(200, op_dedup(q.get("q", [""])[0]))
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:
            self._send(500, err_payload(e))

    def do_POST(self):
        if not self._auth():
            return
        p = urlparse(self.path)
        b = self._body()
        try:
            if p.path == "/add":
                self._send(200, op_add(b.get("title"), b.get("content"), b.get("tags"), b.get("links"), b.get("dir"), b.get("source"), b.get("author")))
            elif p.path == "/update":
                self._send(200, op_update(b.get("name"), b.get("content"), b.get("append"), b.get("by"), b.get("expected_updated")))
            elif p.path == "/link":
                self._send(200, op_link(b.get("src"), b.get("dst")))
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:
            self._send(500, err_payload(e))

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if not TOKEN:
        print("⚠️  KB_API_TOKEN 未设，API 无鉴权裸奔！强烈建议 setx KB_API_TOKEN \"<随机串>\"")
    print(f"vault_api 启动 v{API_VERSION}: vault={VAULT}  端口={PORT}  笔记={len(all_notes())}  鉴权={'on' if TOKEN else 'OFF'}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
