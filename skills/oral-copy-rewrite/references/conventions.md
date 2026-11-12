# 「下饭的史」账号发布规范与选题池结构

## 一、账号底盘

- 账号名「下饭的史」，三平台同步：抖音 / 视频号 / 快手
- 定位：金融+心理学+历史三领域；受众30-50岁
- 节奏：每周3-5条；主发视频号；长文（复利/美债类）为收藏转发引擎
- 数据规律（持续验证中）：数字悬念钩最强（跳出率历史新低30.66%）；长文=收藏引擎；情绪狠话线持续吃流量；链式互动已死（2.5-3%）

## 二、发布格式

- **首句钩子兼作发布标题**：口播第一句直接用作视频标题，必须独立成立
- 标题字数：下饭的史≤16字（职场心理学号≤8字，勿混淆）
- 描述≤50字，公式：首句=冲突，次句=代价或互动，#标签收尾
- 标签：10个 `#` 标签，无分号
- 常规稿120-180字；单条视频制作上限2000字
- **拆集规则**：正文>2000字必须拆上下/上中下集；选题、标题、描述三列统一「系列名第N集副题」格式；上下集隔天发（上集发次日发下集）

## 三、腾讯文档选题池（file_id=HUbUPTDlAMxT, sheet_id=BB08J2）

13列（A-M）：
| 列 | 内容 |
|---|---|
| 0 A | 序号 |
| 1 B | 选题名 |
| 2 C | 分类 |
| 3 D | 备注（来源/批次/警示/拆集说明） |
| 4 E | 首句钩子 |
| 5 F | 标签 |
| 6 G | 标题 |
| 7 H | 描述 |
| 8 I | 选题评级（⭐） |
| 9 J | 爆款潜力（🔥） |
| 10 K | 状态（对标采集·待仿写 / 待发布 / 已确认定稿 / 已发布（日期+数据）） |
| 11 L | 正文（口播全文） |
| 12 M | 发表评论（发布后用户截图转写） |

### 写入方法（CLI）
- 前置：`export CODEBUDDY_MCP_CONFIG=$(cat /c/Users/Administrator/.workbuddy/agent-cli-mcp-config/c9a210de-01ec-4d3c-914e-9b067c3a62a8.mcp-config.json) TDOC_API_BASE_URL=https://docs.qq.com`
- CLI 路径：`C:/Users/Administrator/.workbuddy/plugins/cache/workbuddy-builtin/tencent-docs-plugin/<版本>/skills/tencent-docs/tencentdocs.py`（用 ls 取当前版本目录）
- 写入：`tdoc_call sheet-mcp set_range_value '<json>'`，values=[{"row":N,"col":C,"value_type":"STRING","string_value":"..."}]
- 读取：`tdoc_call sheet-mcp get_cell_data '<json>'` + `return_csv:true`，解析 `result.structuredContent.csv_data`
- **行号=序号-1**（表头占row0）。写前读目标行确认序号，写后必须回读核验。
- 描述栏可能存有口播全文，补缺不覆盖。

## 四、每日循环

1. 每日三平台数据截图→复盘→记录 `.workbuddy/memory/YYYY-MM-DD.md`
2. 文案投递→查重→赛博大脑拉对标（附2篇对标原文）→体检→分级加工
3. 用户确认→入选题池对应行→发布
4. 发布后用户发评论区截图→转写进对应行M列→评论分析（共鸣/抬杠/高频提问→下一条选题线索）
5. T+3/T+7 爆款补拍（抖音>4000播放触发）

## 五、资产索引

- 赛博大脑 vault：目录「抖音文案」「财经文案」「心理文案」「运营/下饭的史·文案库」；检索 `kb_ops.py search "关键词"`
- 选题池「对标采集·待仿写」行＝C档复刻队列，不可直接发布
- 定稿归档：工作区 `output/职场心理学_定稿文案记录.md`
- 二创流程全文：工作区 `output/下饭的史_二次创作加工流程v1.md`
