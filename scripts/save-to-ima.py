#!/usr/bin/env python3
"""
save-to-ima.py — 将微信文章原文存入 IMA 知识库对应分类文件夹 + 摘要存入 IMA 笔记

核心能力:
  - 原文通过 import_urls 导入知识库，自动放入对应分类文件夹
  - 摘要通过 import_doc 创建 IMA 笔记
  - tags 不走 API（IMA 不支持），而是内嵌在笔记 Markdown 中便于检索

用法:
  python3 save-to-ima.py --url "https://mp.weixin.qq.com/s/xxx"
  python3 save-to-ima.py --url "..." --category "AI与科技"
  python3 save-to-ima.py --url "..." --category "AI与科技" --digest-file /tmp/digest.md
  python3 save-to-ima.py --url "..." --dry-run   # 只分析不执行

环境变量（可选）:
  IMA_KB_ID        — 知识库 ID（默认: 需在代码中配置）
  IMA_CLIENT_ID    — IMA Client ID（默认: 从 ~/.config/ima/client_id 读取）
  IMA_API_KEY      — IMA API Key（默认: 从 ~/.config/ima/api_key 读取）
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
CLASSIFICATION_FILE = SCRIPT_DIR / "topic-classification.json"
CONFIG_DIR = Path(os.path.expanduser("~/.config/ima"))

# 凭证来源: 环境变量 > 配置文件
DEFAULT_CLIENT_ID_FILE = CONFIG_DIR / "client_id"
DEFAULT_API_KEY_FILE = CONFIG_DIR / "api_key"

FOLDERS_CACHE_FILE = CONFIG_DIR / "kb_folders.json"

# ⚠️ 知识库 ID — 请替换为你自己的
# 优先级: 环境变量 IMA_KB_ID > 命令行 --kb-id > 下面的默认值
KB_ID = os.environ.get("IMA_KB_ID", "")


# ── IMA API ───────────────────────────────────────────
def load_credentials():
    """加载 IMA 凭证，支持环境变量和配置文件两种方式"""
    client_id = os.environ.get("IMA_CLIENT_ID", "")
    api_key = os.environ.get("IMA_API_KEY", "")

    if not client_id and DEFAULT_CLIENT_ID_FILE.exists():
        client_id = DEFAULT_CLIENT_ID_FILE.read_text().strip()
    if not api_key and DEFAULT_API_KEY_FILE.exists():
        api_key = DEFAULT_API_KEY_FILE.read_text().strip()

    if not client_id or not api_key:
        print("❌ 缺少 IMA 凭证，请通过以下任一方式配置：")
        print("   方式1: 环境变量  export IMA_CLIENT_ID=xxx  export IMA_API_KEY=xxx")
        print("   方式2: 配置文件  ~/.config/ima/client_id  +  ~/.config/ima/api_key")
        print("   方式3: 命令行    --client-id xxx --api-key xxx")
        sys.exit(1)

    return client_id, api_key


def ima_post(path, body, client_id, api_key, timeout=30):
    url = f"https://ima.qq.com/{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("ima-openapi-clientid", client_id)
    req.add_header("ima-openapi-apikey", api_key)
    req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        return {"code": -1, "msg": f"HTTP {e.code}: {error_body}"}
    except Exception as e:
        return {"code": -1, "msg": str(e)}


# ── 文件夹管理 ────────────────────────────────────────
def get_or_refresh_folders(client_id, api_key, kb_id, force=False):
    """获取知识库文件夹列表，带本地缓存"""
    cache = {}
    if not force and FOLDERS_CACHE_FILE.exists():
        try:
            cache = json.loads(FOLDERS_CACHE_FILE.read_text())
            ts = cache.get("_cached_at", 0)
            if datetime.now().timestamp() - ts < 86400 and cache.get("kb_id") == kb_id:
                return {k: v for k, v in cache.items() if not k.startswith("_")}
        except (json.JSONDecodeError, KeyError):
            pass

    result = ima_post(
        "openapi/wiki/v1/get_knowledge_list",
        {"knowledge_base_id": kb_id, "cursor": "", "limit": 50},
        client_id, api_key
    )

    if result.get("code") != 0:
        print(f"⚠️ 获取文件夹列表失败: {result.get('msg', '')}")
        return {}

    folders = {}
    for item in result.get("data", {}).get("knowledge_list", []):
        if item.get("media_type") == 99 or item.get("is_folder"):
            folders[item["title"]] = item["media_id"]

    cache_data = {**folders, "_cached_at": datetime.now().timestamp(), "kb_id": kb_id}
    FOLDERS_CACHE_FILE.write_text(json.dumps(cache_data, ensure_ascii=False))
    return folders


def get_folder_id(category, folders):
    """获取分类对应的文件夹 ID"""
    if category in folders:
        return folders[category]
    return ""


# ── 分类逻辑 ──────────────────────────────────────────
def load_classification():
    with open(CLASSIFICATION_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def classify_article(title, content=""):
    config = load_classification()
    text = f"{title} {content}".lower()
    scores = {}
    for cat_name, cat_info in config["categories"].items():
        if cat_name == "日常阅读" or cat_name == "待整理":
            scores[cat_name] = 0
            continue
        score = sum(1 for kw in cat_info["keywords"] if kw.lower() in text)
        scores[cat_name] = score
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "日常阅读"
    return best


def detect_article_type(title, content=""):
    config = load_classification()
    text = f"{title} {content}".lower()
    for type_name, keywords in config["article_types"].items():
        if any(kw.lower() in text for kw in keywords):
            return type_name
    return "观点评论"


def detect_importance(title, content=""):
    config = load_classification()
    text = f"{title} {content}".lower()
    if any(kw in text for kw in config["importance_markers"]["high"]):
        return 5
    if any(kw in text for kw in config["importance_markers"]["medium"]):
        return 4
    return 3


def get_category_emoji(category):
    config = load_classification()
    return config["categories"].get(category, {}).get("emoji", "📁")


def build_tag_string(category, article_type, extra_tags=None):
    config = load_classification()
    tags = []
    cat_tags = config["categories"].get(category, {}).get("tags", [])
    tags.extend(cat_tags)
    type_tag_map = {
        "宏观报告": "宏观报告", "行业研究": "行业研究",
        "策略框架": "策略框架", "技术分析": "技术分析",
        "观点评论": "观点评论", "深度长文": "深度长文",
    }
    if article_type in type_tag_map:
        tags.append(type_tag_map[article_type])
    if extra_tags:
        for t in extra_tags.split(","):
            t = t.strip()
            if t:
                tags.append(t)
    seen = set()
    unique = []
    for t in tags:
        tl = t.lower().lstrip("#")
        if tl not in seen:
            seen.add(tl)
            unique.append(t.lstrip("#"))
    return unique


# ── 知识库操作 ────────────────────────────────────────
def check_url_exists(url, folder_id, client_id, api_key, kb_id):
    search_body = {"query": url[:50], "knowledge_base_id": kb_id, "cursor": ""}
    if folder_id:
        search_body["folder_id"] = folder_id
    result = ima_post("openapi/wiki/v1/search_knowledge", search_body, client_id, api_key)
    if result.get("code") == 0:
        for item in result.get("data", {}).get("info_list", []):
            title = item.get("title", "")
            if "mp.weixin.qq.com" in title:
                return True
    return False


def import_url_to_kb(url, kb_id, folder_id, client_id, api_key):
    body = {
        "knowledge_base_id": kb_id,
        "folder_id": folder_id,
        "urls": [url]
    }
    result = ima_post("openapi/wiki/v1/import_urls", body, client_id, api_key)
    if result.get("code") == 0:
        results = result.get("data", {}).get("results", {})
        for url_key, info in results.items():
            if info.get("ret_code") == 0:
                mid = info.get("media_id", "")
                return True, mid
            else:
                print(f"  ⚠️ 导入返回: {info.get('errmsg', '未知错误')}")
                return False, ""
    else:
        print(f"  ❌ 导入失败: {result.get('msg', '未知错误')}")
        return False, ""


_folder_name_cache = {}
def _folder_name(folder_id):
    if not folder_id:
        return "根目录"
    if folder_id in _folder_name_cache:
        return _folder_name_cache[folder_id]
    try:
        cache = json.loads(FOLDERS_CACHE_FILE.read_text())
        for name, mid in cache.items():
            if mid == folder_id:
                _folder_name_cache[folder_id] = name
                return name
    except:
        pass
    return folder_id[:20] + "..."


def create_note(content, title, client_id, api_key):
    result = ima_post(
        "openapi/note/v1/import_doc",
        {"content_format": 1, "content": content, "title": title},
        client_id, api_key
    )
    if result.get("code") == 0:
        data = result.get("data", {})
        doc_id = data.get("doc_id", "") or data.get("note_id", "")
        return doc_id, None
    else:
        return None, result.get("msg", "未知错误")


# ── 主流程 ────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="将微信文章存入 IMA 知识库 + 笔记")
    parser.add_argument("--url", required=True, help="微信文章链接")
    parser.add_argument("--category", help="手动指定分类")
    parser.add_argument("--tags", help="额外标签，逗号分隔")
    parser.add_argument("--digest-file", help="摘要文件路径")
    parser.add_argument("--title", help="手动指定标题")
    parser.add_argument("--kb-id", help="知识库 ID（覆盖环境变量 IMA_KB_ID）")
    parser.add_argument("--client-id", help="IMA Client ID")
    parser.add_argument("--api-key", help="IMA API Key")
    parser.add_argument("--dry-run", action="store_true", help="只分析不执行")
    parser.add_argument("--refresh-folders", action="store_true", help="强制刷新文件夹缓存")
    args = parser.parse_args()

    # 解析凭证
    if args.client_id and args.api_key:
        client_id, api_key = args.client_id, args.api_key
    else:
        client_id, api_key = load_credentials()

    # 解析知识库 ID
    kb_id = args.kb_id or KB_ID
    if not kb_id:
        print("❌ 缺少知识库 ID，请通过以下任一方式配置：")
        print("   方式1: 环境变量  export IMA_KB_ID=xxx")
        print("   方式2: 命令行    --kb-id xxx")
        print("   方式3: 代码中    修改 save-to-ima.py 中的 KB_ID 变量")
        sys.exit(1)

    # 文件夹列表
    folders = get_or_refresh_folders(client_id, api_key, kb_id, force=args.refresh_folders)

    print("━━━ IMA 知识库入库 ━━━")
    print(f"🔗 链接: {args.url}")
    print(f"📚 知识库: {kb_id[:20]}...")
    print(f"📁 已有文件夹: {', '.join(folders.keys()) or '(无)'}")
    print()

    # 分类分析
    if args.category:
        category = args.category
    else:
        category = classify_article(args.url)

    emoji = get_category_emoji(category)
    article_type = detect_article_type(args.url)
    importance = detect_importance(args.url)
    tag_list = build_tag_string(category, article_type, args.tags)
    stars = "⭐" * importance
    tag_str = " ".join(f"#{t}" for t in tag_list)

    print(f"📂 分类: {emoji} {category}")
    print(f"📝 类型: {article_type}")
    print(f"⭐ 重要度: {stars}")
    print(f"🏷️ 标签: {tag_str}")
    print()

    folder_id = get_folder_id(category, folders)

    if args.dry_run:
        print("🔍 [DRY RUN] 以上为分析结果，未执行入库操作")
        if folder_id:
            print(f"📁 将导入到: {category}")
        else:
            print("⚠️ 未找到对应文件夹，需要先手动创建")
        return

    # 导入原文
    print("━━━ [1/2] 导入原文到知识库 ━━━")
    if not folder_id:
        print("  ❌ 没有对应的分类文件夹，无法导入原文")
        print("  💡 请在 IMA 中手动创建文件夹后重试，或传入有效的 --category")
        return

    if check_url_exists(args.url, folder_id, client_id, api_key, kb_id):
        print(f"  ⚠️ 该链接可能已存在于「{category}」文件夹中，跳过导入")
    else:
        ok, media_id = import_url_to_kb(args.url, kb_id, folder_id, client_id, api_key)
        if ok:
            print(f"  ✅ 原文已导入文件夹「{category}」")
            print(f"     media_id: {media_id[:40]}...")
        else:
            print("  ⚠️ 原文导入失败，继续创建笔记...")

    # 创建摘要笔记
    if args.digest_file:
        print()
        print("━━━ [2/2] 创建摘要笔记 ━━━")
        digest_path = Path(args.digest_file)
        if not digest_path.exists():
            print(f"  ❌ 摘要文件不存在: {args.digest_file}")
            return

        with open(digest_path, "r", encoding="utf-8") as f:
            digest_content = f.read().strip()

        note_title = args.title or f"[{category}] 微信文章摘要"
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        meta_block = f"""

---

## 📂 入库信息

| 字段 | 内容 |
|------|------|
| **分类** | {emoji} {category} |
| **文件夹** | {category} |
| **类型** | {article_type} |
| **重要度** | {stars} |
| **标签** | {tag_str} |
| **原文链接** | {args.url} |
| **入库时间** | {now} |

*wechat-article-digest 自动入库 | IMA 不支持原生 tags，标签内嵌在正文中便于检索*"""
        full_content = digest_content + meta_block

        doc_id, err = create_note(full_content, note_title, client_id, api_key)
        if doc_id:
            print(f"  ✅ 笔记已创建（doc_id: {doc_id}）")
            print()
            print("━━━ ✅ 入库完成 ━━━")
            print(f"  📁 知识库: 原文 → [{category}] 文件夹")
            print(f"  📝 笔记: {note_title}")
            print(f"  🏷️ 标签: {tag_str}")
        else:
            print(f"  ❌ 笔记创建失败: {err}")
    else:
        print()
        print("━━━ ✅ 入库完成（仅原文） ━━━")
        print(f"  📁 知识库: 原文 → [{category}] 文件夹")
        print(f"  💡 传入 --digest-file 可同时创建带标签的摘要笔记")


if __name__ == "__main__":
    main()
