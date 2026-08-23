# 网页资料提取入库（defuddle）

用户发来 **URL / 网页资料** 时，先提纯再入库——去导航/广告/杂乱，省 token 且内容干净。

## 工具：defuddle CLI

```bash
npm install -g defuddle        # 安装（需 node）
defuddle parse <url> --md      # 提取干净 markdown（默认方式）
defuddle parse <url> --md -o content.md   # 存文件
defuddle parse <url> -p title  # 只取元数据：title/description/domain
```

- `--md` 输出 markdown；`--json` 输出 HTML+markdown；不带参数输出 HTML
- 或直接走 skill 内置：`python scripts/kb_ops.py fetch "<url>"`（封装了 defuddle 调用）

## 何时用哪个

| 场景 | 用什么 |
|------|--------|
| 标准网页 / 文章 / 博客 | `kb_ops fetch <url>` 或 `defuddle parse <url> --md` |
| URL 以 `.md` 结尾 | 已是 markdown，直接用 WebFetch，不走 defuddle |
| 需要保留完整原始 HTML 结构 | WebFetch |

## 入库流程（网页资料）

1. **识别**：对话中出现 URL / 网页资料 → 主动提议"这条网页资料值得入库"
2. **提纯**：`kb_ops fetch "<url>"` 拿到干净 markdown（若 defuddle 未装，退而用 WebFetch）
3. **确认**：与用户确认拟建标题/归类（按自动归类建议）
4. **整理**：按 note-template 规范生成笔记，**frontmatter `source` 填原 URL**，正文引用关键结论
5. **写入**：`kb_ops add`（自动归类 + 双链 + 署名）
6. **反馈**：告知落点，source 保留原链接便于溯源

## 注意

- defuddle 提取的是正文，**版权内容谨慎**：保留出处（source=URL），只摘录要点不整篇搬运
- 需要登录/动态渲染的页面 defuddle 拿不到 → 提示用户直接提供内容
