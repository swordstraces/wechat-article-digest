#!/bin/bash
# wechat-article-digest: 微信公众号文章摘要生成脚本（独立版）
# 优化版：抓取 + 总结 + 自动入库 IMA 知识库 + 笔记
# 用途：获取文章 → Agent 生成摘要 → 自动分类 → 原文入库 + 笔记入库

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── 路径配置（基于脚本自身位置，无需硬编码）──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FETCH_SCRIPT="${SCRIPT_DIR}/fetch_weixin.py"
TEMPLATE_FILE="${SCRIPT_DIR}/summarize-template.md"
GUIDE_FILE="${SCRIPT_DIR}/../references/summary-guide.md"
SAVE_SCRIPT="${SCRIPT_DIR}/save-to-ima.py"
TEMP_DIR="/tmp/wechat-digest"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEMP_MD="${TEMP_DIR}/article_${TIMESTAMP}.md"
META_FILE="${TEMP_DIR}/meta_${TIMESTAMP}.txt"

mkdir -p "$TEMP_DIR"

# 检查参数
if [ $# -eq 0 ]; then
    echo -e "${RED}错误：缺少文章链接${NC}"
    echo "用法: $0 \"<微信文章链接>\""
    exit 1
fi

URL="$1"

# 验证 URL
if [[ "$URL" != *"mp.weixin.qq.com"* ]]; then
    echo -e "${RED}错误：仅支持微信公众号文章 (mp.weixin.qq.com)${NC}"
    echo "提示：普通网页请使用其他抓取工具"
    exit 1
fi

echo -e "${GREEN}━━━ 微信文章摘要生成 ━━━${NC}"
echo -e "${CYAN}链接${NC}: ${URL}"
echo -e "${CYAN}时间${NC}: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# ── Step 1: 抓取文章 ──
echo -e "${GREEN}[1/3] 抓取文章内容...${NC}"

if [ ! -f "$FETCH_SCRIPT" ]; then
    echo -e "${RED}错误：抓取脚本不存在 (${FETCH_SCRIPT})${NC}"
    echo "请确保 fetch_weixin.py 在同一目录下"
    exit 1
fi

RAW_OUTPUT=$(python3 "$FETCH_SCRIPT" "$URL" 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo -e "${RED}抓取失败 (exit code: $EXIT_CODE)${NC}"
    echo "$RAW_OUTPUT" | tail -5
    exit 1
fi

# 保存完整 Markdown（包含 YAML frontmatter）
echo "$RAW_OUTPUT" > "$TEMP_MD"

# 提取 YAML 元数据
extract_yaml_field() {
    echo "$RAW_OUTPUT" | awk -v field="$1" '
        /^---$/ { in_yaml = !in_yaml; next }
        in_yaml && $0 ~ "^" field ":" { sub("^" field ":[[:space:]]*", ""); print; exit }
    '
}

TITLE=$(extract_yaml_field "title")
AUTHOR=$(extract_yaml_field "author")
ACCOUNT=$(extract_yaml_field "account")
WORD_COUNT=$(extract_yaml_field "word_count")
FETCHED_BY=$(extract_yaml_field "fetched_by")

# 估算阅读时间（中文约 400 字/分钟）
if [ -n "$WORD_COUNT" ] && [ "$WORD_COUNT" -gt 0 ] 2>/dev/null; then
    READ_MIN=$(( (WORD_COUNT + 399) / 400 ))
    READ_TIME="${READ_MIN} 分钟"
else
    READ_TIME="未知"
fi

# 保存元数据供 agent 使用
cat > "$META_FILE" << EOF
TITLE=${TITLE}
AUTHOR=${AUTHOR}
ACCOUNT=${ACCOUNT}
WORD_COUNT=${WORD_COUNT}
READ_TIME=${READ_TIME}
URL=${URL}
FETCHED_BY=${FETCHED_BY}
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
FILE=${TEMP_MD}
EOF

echo -e "${GREEN}  ✓ 标题${NC}: ${TITLE}"
echo -e "${GREEN}  ✓ 来源${NC}: ${ACCOUNT}"
[ -n "$AUTHOR" ] && echo -e "${GREEN}  ✓ 作者${NC}: ${AUTHOR}"
echo -e "${GREEN}  ✓ 字数${NC}: ${WORD_COUNT}"
echo -e "${GREEN}  ✓ 预计阅读${NC}: ${READ_TIME}"
echo -e "${GREEN}  ✓ 抓取方式${NC}: ${FETCHED_BY}"
echo -e "${GREEN}  ✓ 保存到${NC}: ${TEMP_MD}"

# ── Step 2: 输出总结指令 ──
echo ""
echo -e "${GREEN}[2/3] 生成标准化摘要...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}>>> 请按照以下指南和模板，对文章进行深度总结 <<<${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 输出元数据块
echo "### 📋 文章元数据（自动提取）"
echo "> 标题: ${TITLE}"
echo "> 来源: ${ACCOUNT}"
echo "> 作者: ${AUTHOR:-未署名}"
echo "> 字数: ${WORD_COUNT}"
echo "> 阅读时间: ${READ_TIME}"
echo "> 链接: ${URL}"
echo "> 抓取方式: ${FETCHED_BY}"
echo "> 保存时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 输出模板
echo "### 📐 总结模板"
cat "$TEMPLATE_FILE"
echo ""

# 输出指南要点
echo ""
echo "### 📖 总结指南要点"
if [ -f "$GUIDE_FILE" ]; then
    cat "$GUIDE_FILE" | grep -A 3 "^## " | head -60
    echo ""
    echo "(完整指南见: ${GUIDE_FILE})"
else
    echo "(未找到指南文件)"
fi

# ── Step 3: 输出文章内容 ──
echo ""
echo -e "${GREEN}[3/3] 输出文章全文...${NC}"
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}>>> 以下为文章全文，请据此生成摘要 <<<${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 去掉 YAML frontmatter，只输出正文
awk '/^---$/{n++; next} n>=2{print}' "$TEMP_MD"

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}>>> 文章全文结束 <<<${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ── Step 4: 入库指令 ──
echo -e "${GREEN}━━━ 任务完成 ━━━${NC}"
echo -e "  文章内容: ${TEMP_MD}"
echo -e "  元数据文件: ${META_FILE}"
echo ""
echo -e "${YELLOW}━━━ 下一步：生成摘要后自动入库 ━━━${NC}"
echo ""
echo "摘要生成完成后，请按以下步骤入库："
echo ""
echo "1. 将完整摘要保存到文件（如 /tmp/digest_xxx.md）"
echo "2. 确定分类和标签"
echo ""
echo "3. 执行入库命令:"
echo ""
echo "   python3 ${SAVE_SCRIPT} \\"
echo "     --url \"${URL}\" \\"
echo "     --category \"<分类>\" \\"
echo "     --tags \"标签1,标签2,标签3\" \\"
echo "     --title \"[分类] 文章标题\" \\"
echo "     --digest-file /tmp/digest_xxx.md"
