# WorkBuddy Skills 集合

一组 [WorkBuddy](https://www.workbuddy.cn) 技能包，持续积累。每个子目录是一个独立 skill，可单独安装。

> 给龙虾（WorkBuddy 用户）：clone 一次，按需挑技能装，或全装。

## Skills 一览

| 技能 | 简介 | 状态 |
|------|------|------|
| [knowledge-vault](./skills/knowledge-vault) | 个人知识库桥梁：对话↔Obsidian vault↔DeepTutor，6步入库+署名追溯 | ✅ 可用 |

> 新技能会持续加到 `skills/` 下，star 一下不错过。

## 通用安装

整个仓库 clone 到本地任意位置：

```bash
git clone https://github.com/zhang0135789/workbuddy-skills.git
```

然后把想用的技能**拷贝**（或软链）到 WorkBuddy 用户级 skill 目录：

```bash
# Windows (PowerShell)
Copy-Item -Recurse workbuddy-skills/skills/knowledge-vault "$HOME/.workbuddy/skills/knowledge-vault"

# macOS / Linux
cp -r workbuddy-skills/skills/knowledge-vault ~/.workbuddy/skills/knowledge-vault
```

> 用户级 skill 路径 `~/.workbuddy/skills/<技能名>/`，所有项目通用。
> 项目级则放 `<项目>/.workbuddy/skills/<技能名>/`，仅团队共享。

每个技能的具体前置与配置见各自目录下的 `SKILL.md`。

## 目录约定

```
workbuddy-skills/
├── README.md                 # 本文件（技能索引）
├── LICENSE
└── skills/
    └── <技能名>/
        ├── SKILL.md          # 技能入口（frontmatter + 工作流）
        ├── scripts/          # 可选：脚本
        └── references/       # 可选：参考文档
```

新增技能时在 `skills/` 下建同名子目录，并更新本 README 的表格。

## License

MIT — 自由使用、修改、分发。欢迎 PR 交流新技能。
