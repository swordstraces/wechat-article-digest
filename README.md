# wechat-article-digest

> 微信公众号文章深度摘要生成 + 自动知识库入库。发一条链接，10 秒出 TLDR，3 分钟掌握核心价值，自动分类归档。

## ✨ 特性

- **高速抓取**：4 级回退策略获取微信文章完整内容（0.9s）
- **漏斗模型摘要**：10 秒 TLDR → 3 分钟深度价值，7 模块结构化输出
- **自动分类**：7 大主题分类 + 智能标签系统（关键词匹配）
- **知识库入库**：原文 → 知识库文件夹 + 摘要 → 笔记（IMA API）
- **行动导向**：可执行的 checklist 价值点，方便后续追踪
- **零硬编码**：所有路径使用相对路径，凭证支持 3 种配置方式

## 📂 文件结构

```
wechat-article-digest/
├── scripts/
│   ├── fetch_weixin.py           # 微信文章抓取（4级回退，含代理策略）
│   ├── fetch-and-digest.sh       # 主入口：抓取 + 输出模板 + 入库指引
│   ├── save-to-ima.py            # IMA 知识库 + 笔记入库（纯标准库，无第三方依赖）
│   ├── summarize-template.md     # 摘要结构模板（7模块）
│   └── topic-classification.json # 分类配置（关键词+标签映射）
├── references/
│   ├── summary-guide.md          # 摘要撰写指南（教AI怎么写好摘要）
│   └── output-format.md          # 输出格式规范 + 完整示例
├── SKILL.md                      # 技能描述文件
├── README.md
└── LICENSE
```

**总共 8 个文件**，复制过去就能用。

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install requests beautifulsoup4 lxml
```

就这一个。`save-to-ima.py` 和 `fetch-and-digest.sh` **零第三方依赖**（纯标准库）。

### 2. 配置凭证

三选一：

**方式 A：环境变量（推荐）**
```bash
export IMA_CLIENT_ID="your_client_id"
export IMA_API_KEY="your_api_key"
export IMA_KB_ID="your_knowledge_base_id"
```

**方式 B：配置文件**
```bash
mkdir -p ~/.config/ima
echo "your_client_id" > ~/.config/ima/client_id
echo "your_api_key" > ~/.config/ima/api_key
chmod 600 ~/.config/ima/client_id ~/.config/ima/api_key
```

**方式 C：命令行参数**
```bash
python3 scripts/save-to-ima.py --url "..." --client-id "xxx" --api-key "xxx" --kb-id "xxx"
```

### 3. 使用

```bash
# 仅抓取文章（输出 Markdown + YAML 元数据）
python3 scripts/fetch_weixin.py "https://mp.weixin.qq.com/s/xxxxx"

# 完整流程：抓取 + 输出摘要模板 + 入库指引
bash scripts/fetch-and-digest.sh "https://mp.weixin.qq.com/s/xxxxx"

# 仅入库到 IMA
python3 scripts/save-to-ima.py \
  --url "https://mp.weixin.qq.com/s/xxxxx" \
  --category "AI与科技" \
  --tags "LLM,Agent,工具链" \
  --digest-file /tmp/digest.md

# Dry-run（只分析不入库）
python3 scripts/save-to-ima.py \
  --url "https://mp.weixin.qq.com/s/xxxxx" \
  --dry-run
```

## 📐 摘要结构（漏斗模型）

```
⚡ TLDR (10秒)     → 核心结论一句话
🔬 方法论 (30秒)   → 怎么得出结论的
📌 结论 (1分钟)    → So What? 具体数据支撑
🎯 观点 (2分钟)    → Why? 论证过程
💡 洞察            → 反常识发现
🔥 我的行动 (3分钟) → 具体可执行的 checklist
📎 标签 + 入库信息  → 分类 + 标签 + 存储位置
```

## 🏷️ 主题分类（7 大类）

| 分类 | 覆盖范围 |
|------|---------|
| 📊 宏观策略 | 宏观经济、大类资产、货币财政、地缘风险 |
| 🏭 行业研究 | 行业分析、产业链研究、公司研究 |
| 📈 量化投资 | 因子研究、策略回测、择时体系、风险模型 |
| 🤖 AI与科技 | LLM、Agent、工具链、开源项目 |
| 🧠 投资框架 | 投资方法论、思维模型、决策框架 |
| 🚀 产品与创业 | SaaS、互联网、内容创作、自动化 |
| 📖 日常阅读 | 其他杂项（默认分类） |

## ⚙️ 技术架构

```
┌─────────────────────────────────────────┐
│  第 1 层：文章抓取（fetch_weixin.py）    │
│  4 级回退策略，确保抓到内容                │
│  直连 → UA切换 → defuddle → jina.ai     │
├─────────────────────────────────────────┤
│  第 2 层：AI 生成摘要                    │
│  模板约束 + 撰写指南 → 7 模块结构化输出    │
├─────────────────────────────────────────┤
│  第 3 层：自动入库（save-to-ima.py）      │
│  原文 → IMA 知识库文件夹                   │
│  摘要 → IMA 笔记（标签内嵌正文）          │
└─────────────────────────────────────────┘
```

### 依赖关系

| 文件 | 外部依赖 | 说明 |
|------|---------|------|
| `fetch_weixin.py` | `requests`, `beautifulsoup4`, `lxml` | HTML解析+HTTP请求 |
| `save-to-ima.py` | **无**（纯标准库） | `argparse, json, urllib` |
| `fetch-and-digest.sh` | `bash`, `python3` | Shell 入口脚本 |

**不依赖的东西**：Node.js / Docker / 数据库 / IMA SDK / 任何特定 AI 框架

## 📋 save-to-ima.py 参数

| 参数 | 必需 | 说明 |
|------|------|------|
| `--url` | ✅ | 微信文章链接 |
| `--category` | 推荐 | 7 大分类之一（不传则自动匹配） |
| `--tags` | 推荐 | 额外标签，逗号分隔 |
| `--title` | 推荐 | 笔记标题 |
| `--digest-file` | 推荐 | 摘要文件路径（同时创建带标签的笔记） |
| `--kb-id` | 可选 | 知识库 ID（覆盖环境变量） |
| `--client-id` | 可选 | IMA Client ID |
| `--api-key` | 可选 | IMA API Key |
| `--dry-run` | 可选 | 只分析不执行入库 |
| `--refresh-folders` | 可选 | 强制刷新文件夹缓存 |

## 🔧 自定义

### 修改分类体系

编辑 `scripts/topic-classification.json`：

```json
{
  "categories": {
    "你的分类名": {
      "emoji": "📁",
      "keywords": ["关键词1", "关键词2"],
      "tags": ["基础标签"]
    }
  }
}
```

### 修改摘要模板

编辑 `scripts/summarize-template.md`，按需增减模块。

### 替换知识库后端

不用 IMA？替换 `save-to-ima.py`，对接 Notion、飞书、Obsidian 等即可。核心逻辑：原文按分类归档，摘要带标签可检索。

## 🤖 配合 AI 助手使用

有 Skill 体系的 AI 助手（PicoClaw、OpenClaw 等）：

```bash
cp -r wechat-article-digest/ ~/.your-agent/skills/
```

直接发微信链接，自动触发抓取 → 生成摘要 → 入库。

## 📄 License

[MIT](LICENSE)

## 🙏 致谢

- 微信公众号平台
- [IMA](https://ima.qq.com) 知识管理平台
- [defuddle.md](https://defuddle.md/) 网页转 Markdown 代理
- [r.jina.ai](https://r.jina.ai/) 内容提取代理
