# wechat-article-digest

> 微信公众号文章深度摘要生成 + 自动知识库入库技能（OpenClaw AgentSkill）

## ✨ 特性

- **快速抓取**：通过 4 级回退策略获取微信文章完整内容
- **漏斗模型摘要**：10 秒 TLDR → 3 分钟深度价值，结构化输出
- **自动分类**：7 大主题分类 + 智能标签系统
- **知识库入库**：原文 + 摘要笔记自动存入 IMA 知识库
- **行动导向**：可执行的 checklist 价值点，方便后续追踪

## 📂 结构

```
wechat-article-digest/
├── scripts/
│   ├── fetch-and-digest.sh      # 一键脚本（抓取 + 摘要指引）
│   ├── save-to-ima.py           # IMA 知识库入库脚本
│   ├── summarize-template.md    # 摘要模板
│   └── topic-classification.json # 分类配置
├── references/
│   ├── summary-guide.md         # 摘要撰写指南
│   └── output-format.md         # 输出格式规范
├── SKILL.md                     # 技能描述文件
├── README.md
└── LICENSE
```

## 🚀 使用方法

### 前置依赖

- [OpenClaw](https://github.com/openclaw/openclaw) Agent 运行环境
- `markdown-proxy` 技能（提供 `fetch_weixin.py` 微信抓取脚本）
- `ima-skill` 技能（提供 IMA 知识库/笔记 API）
- IMA API 凭证（`~/.config/ima/client_id` + `~/.config/ima/api_key`）

### 基本用法

将 `scripts/` 和 `references/` 放置到 OpenClaw 技能目录，然后：

```bash
# Step 1: 抓取文章并生成摘要指引
bash scripts/fetch-and-digest.sh "https://mp.weixin.qq.com/s/xxxxx"

# Step 2: Agent 按模板生成摘要（AI 完成）

# Step 3: 入库到 IMA 知识库
python3 scripts/save-to-ima.py \
  --url "https://mp.weixin.qq.com/s/xxxxx" \
  --category "AI与科技" \
  --tags "知识管理,LLM,Agent" \
  --title "[AI与科技] Karpathy知识库方法论" \
  --digest-file /tmp/digest_xxx.md
```

### 仅导入原文

```bash
python3 scripts/save-to-ima.py \
  --url "https://mp.weixin.qq.com/s/xxxxx" \
  --category "宏观策略"
```

## 📐 摘要结构（漏斗模型）

```
⚡ TLDR (10秒)     → 核心结论一句话
🔬 方法论 (30秒)   → 怎么得出结论的
📌 结论 (1分钟)    → So What? 具体数据支撑
🎯 观点 (2分钟)    → Why? 论证过程
💡 洞察            → 反常识发现
🔥 我的行动 (3分钟) → 具体可执行的 checklist
```

## 🏷️ 主题分类

| 分类 | 覆盖范围 |
|------|---------|
| 📊 宏观策略 | 宏观经济、大类资产、货币财政、地缘风险 |
| 🏭 行业研究 | 行业分析、产业链研究、公司研究 |
| 📈 量化投资 | 因子研究、策略回测、择时体系、风险模型 |
| 🤖 AI与科技 | LLM、Agent、工具链、开源项目 |
| 🧠 投资框架 | 投资方法论、思维模型、决策框架 |
| 🚀 产品与创业 | SaaS、互联网、内容创作、自动化 |
| 📖 日常阅读 | 其他杂项（默认分类） |

## ⚙️ 配置

### IMA 凭证

```bash
# 创建配置目录
mkdir -p ~/.config/ima

# 设置 API 凭证
echo "your_client_id" > ~/.config/ima/client_id
echo "your_api_key" > ~/.config/ima/api_key
```

### 知识库 ID

编辑 `scripts/save-to-ima.py`，修改 `KB_ID` 为你的 IMA 知识库 ID：

```python
KB_ID = "your_knowledge_base_id_here"
```

## 📋 save-to-ima.py 参数

| 参数 | 必需 | 说明 |
|------|------|------|
| `--url` | ✅ | 微信文章链接 |
| `--category` | 推荐 | 7 大分类之一 |
| `--tags` | 推荐 | 额外标签，逗号分隔 |
| `--title` | 推荐 | 笔记标题 |
| `--digest-file` | 可选 | 摘要文件路径 |
| `--dry-run` | 可选 | 只分析不执行入库 |

## 🔧 依赖关系

| 技能 | 说明 |
|------|------|
| `markdown-proxy` | 提供微信文章抓取能力 |
| `ima-skill` | 提供 IMA 知识库/笔记 API |

## 📄 License

[MIT](LICENSE)

## 🙏 致谢

- 微信公众号平台
- [IMA](https://ima.qq.com) 知识管理平台
- [OpenClaw](https://github.com/openclaw/openclaw) Agent 框架
