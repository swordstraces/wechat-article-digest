#!/usr/bin/env python3
"""
fetch_weixin.py — Unified WeChat article fetcher with multi-strategy fallback.

Strategies (in order):
  1. Direct fetch with WeChat-in-App UA  — fastest, works for most articles
  2. Direct fetch with iPhone Mobile UA  — alternative UA fallback
  3. defuddle.md proxy                    — good Markdown, YAML metadata
  4. r.jina.ai proxy                      — last resort, may hit CAPTCHA

Usage:
  python3 fetch_weixin.py <url> [--json] [--save] [--output-dir DIR]
"""

import sys
import os
import re
import json
import time
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError as e:
    print(f"Missing dependency: {e}\nInstall: pip install requests beautifulsoup4 lxml", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT_DIR = os.path.expanduser("~/Downloads")
MIN_CONTENT_LENGTH = 200

HEADERS_DIRECT = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36 "
        "MicroMessenger/8.0.44.2502(0x28002E37) "
        "Process/tools WeChat/arm64 Weixin NetType/WIFI "
        "Language/zh_CN ABI/arm64"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://mp.weixin.qq.com/",
}

HEADERS_MOBILE = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1 "
        "MicroMessenger/8.0.44"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://mp.weixin.qq.com/",
}

BLOCK_TAGS = frozenset({
    "p", "section", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "ul", "ol", "li", "pre", "table", "img",
})

# ---------------------------------------------------------------------------
# HTML → Markdown
# ---------------------------------------------------------------------------

def _clean(el):
    """Get clean text, collapse whitespace."""
    t = el.get_text(" ", strip=True) if hasattr(el, "get_text") else str(el)
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def _process_table(table_el, lines):
    rows = table_el.find_all("tr")
    if not rows:
        return
    lines.append("")
    for i, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        texts = [_clean(c) for c in cells]
        lines.append("| " + " | ".join(texts) + " |")
        if i == 0 and row.find("th"):
            lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
    lines.append("")


def _html_to_markdown(content_el):
    """Convert #js_content to Markdown with proper paragraph separation."""
    if not content_el:
        return ""

    # Remove noise
    for tag in content_el.find_all(["script", "style", "svg", "noscript"]):
        tag.decompose()

    # ---- Phase 1: Collect block-level elements ----
    blocks = []  # list of (tag_name, element_or_string)

    def collect(el):
        if isinstance(el, NavigableString):
            t = str(el).strip()
            if t:
                blocks.append(("text", t))
            return
        if not isinstance(el, Tag):
            return
        name = el.name
        if name in ("script", "style", "svg", "noscript"):
            return
        # Block tags that are true containers (always recurse into children)
        if name in ("section", "div"):
            for child in el.children:
                collect(child)
        elif name in BLOCK_TAGS:
            blocks.append((name, el))
        else:
            for child in el.children:
                collect(child)

    # Start from children, not content_el itself (which is a <div>)
    for child in content_el.children:
        collect(child)

    # ---- Phase 2: Convert each block to Markdown ----
    md = []

    for btype, bel in blocks:
        # --- Images ---
        if btype == "img":
            src = bel.get("data-src") or bel.get("src") or ""
            if src:
                clean = src.split("?")[0] if "mmbiz.qpic.cn" in src else src
                md.append(f"\n![image]({clean})\n")
            continue

        text = _clean(bel)
        if not text:
            continue

        # --- Headings ---
        if btype in ("h1", "h2", "h3", "h4", "h5", "h6"):
            lvl = int(btype[1])
            md.append("")
            md.append(f"{'#' * lvl} {text}")
            md.append("")
            continue

        # --- Blockquote ---
        if btype == "blockquote":
            md.append("")
            for ln in text.split("\n"):
                md.append(f"> {ln.strip()}")
            md.append("")
            continue

        # --- Lists ---
        if btype in ("ul", "ol"):
            for li in bel.find_all("li", recursive=False):
                lt = _clean(li)
                if lt:
                    md.append(f"- {lt}")
            continue

        # --- Code ---
        if btype == "pre":
            code_el = bel.find("code")
            ct = code_el.get_text() if code_el else bel.get_text()
            if ct.strip():
                md.append("")
                md.append("```")
                md.append(ct.strip())
                md.append("```")
                md.append("")
            continue

        # --- Table ---
        if btype == "table":
            _process_table(bel, md)
            continue

        # --- WeChat-styled heading heuristics ---
        style = bel.get("style", "") if hasattr(bel, "get") else ""
        is_heading = False
        if style:
            big_font = re.search(r"font-size\s*:\s*(1[4-9]|[2-9]\d)\s*px", style)
            bold_font = re.search(r"font-weight\s*:\s*(bold|[6-9]\d{2})", style)
            centered = re.search(r"text-align\s*:\s*center", style)
            if big_font and centered and len(text) < 80:
                is_heading = True
            elif bold_font and len(text) < 60 and not text.startswith("http"):
                is_heading = True

        if is_heading:
            md.append("")
            md.append(f"## {text}")
            md.append("")
        elif btype in ("p", "section", "div"):
            # Paragraphs get blank lines around them
            md.append("")
            md.append(text)
            md.append("")
        else:
            md.append(text)

    result = "\n".join(md)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def _parse_html(html, url):
    """Extract metadata + markdown from raw HTML."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.get_text()

    if "环境异常" in body and "验证" in body:
        return None

    title = _clean(soup.select_one("#activity-name") or soup.select_one(".rich_media_title") or "")
    author = _clean(soup.select_one("#js_author_name") or soup.select_one(".rich_media_meta_nickname") or "")
    account = _clean(soup.select_one("#js_name") or soup.select_one(".rich_media_meta_primary_category_name") or "")
    pub_time = _clean(soup.select_one("#publish_time") or "")

    content_el = soup.select_one("#js_content")
    if not content_el:
        return None

    md = _html_to_markdown(content_el)
    if len(md) < MIN_CONTENT_LENGTH:
        return None

    return {
        "title": title or "无标题",
        "author": author,
        "account": account,
        "publish_time": pub_time,
        "content": md,
        "url": url,
        "word_count": len(md),
    }


def _strategy_direct(url, headers, label):
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        result = _parse_html(r.text, url)
        if result:
            result["_strategy"] = label
        return result
    except Exception as e:
        return {"error": str(e)}


def strategy_defuddle(url):
    try:
        r = requests.get(f"https://defuddle.md/{url}", timeout=30)
        text = r.text
        if len(text) < MIN_CONTENT_LENGTH:
            return {"error": "too short"}

        result = {"url": url, "_strategy": "defuddle.md", "content": ""}

        # Parse YAML frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split("\n"):
                    if ":" not in line:
                        continue
                    k, _, v = line.partition(":")
                    k, v = k.strip().lower(), v.strip().strip("\"'")
                    if k == "title":
                        result["title"] = v
                    elif k == "author":
                        result["author"] = v
                    elif k == "description":
                        result["description"] = v
                result["content"] = parts[2].strip()
            else:
                result["content"] = text
        else:
            result["content"] = text

        if not result.get("title"):
            for ln in text.split("\n"):
                if ln.startswith("# "):
                    result["title"] = ln[2:].strip()
                    break

        # Clean
        content = result["content"]
        content = re.sub(r"!\[.*?\]\(data:image/[^)]+\)", "", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        result["content"] = content.strip()
        result["word_count"] = len(result["content"])

        return result if result["word_count"] >= MIN_CONTENT_LENGTH else {"error": "too short"}
    except Exception as e:
        return {"error": str(e)}


def strategy_jina(url):
    try:
        r = requests.get(f"https://r.jina.ai/{url}", timeout=30)
        text = r.text
        if "CAPTCHA" in text or "环境异常" in text or len(text) < MIN_CONTENT_LENGTH:
            return {"error": "blocked"}

        result = {"url": url, "_strategy": "r.jina.ai", "content": ""}
        clines = []
        for ln in text.split("\n"):
            if ln.startswith("Title: "):
                result["title"] = ln[7:].strip()
            elif ln.startswith(("URL Source:", "Authors:", "Published:", "Description:",
                                "Markdown Content:", "Warning:", "Image:")):
                continue
            else:
                clines.append(ln)

        result["content"] = "\n".join(clines).strip()
        result["word_count"] = len(result["content"])
        return result if result["word_count"] >= MIN_CONTENT_LENGTH else {"error": "too short"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

STRATEGIES = [
    ("直连 (WeChat UA)", lambda u: _strategy_direct(u, HEADERS_DIRECT, "direct (WeChat UA)")),
    ("直连 (iPhone UA)", lambda u: _strategy_direct(u, HEADERS_MOBILE, "direct (iPhone UA)")),
    ("defuddle.md", strategy_defuddle),
    ("r.jina.ai", strategy_jina),
]


def fetch(url):
    for name, fn in STRATEGIES:
        try:
            print(f"  🔄 {name}...", file=sys.stderr, flush=True)
            t0 = time.time()
            r = fn(url)
            dt = time.time() - t0
            if r and "error" not in r and r.get("word_count", 0) >= MIN_CONTENT_LENGTH:
                print(f"  ✅ {name} 成功！({r['word_count']} 字, {dt:.1f}s)", file=sys.stderr, flush=True)
                return r
            err = r.get("error", "too short") if r else "no result"
            print(f"  ❌ {name}: {err}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"  ❌ {name}: {e}", file=sys.stderr, flush=True)
    return {"error": "all strategies failed"}


def fmt_md(r):
    p = ["---"]
    p.append(f'title: "{r.get("title","无标题").replace(chr(34), chr(92)+chr(34))}"')
    for k, fk in [("author","author"),("account","account"),("publish_time","date")]:
        if r.get(k):
            p.append(f'{fk}: "{r[k].replace(chr(34),chr(92)+chr(34))}"')
    p.append(f'url: "{r["url"]}"')
    p.append(f'word_count: {r.get("word_count",0)}')
    if r.get("_strategy"):
        p.append(f'fetched_by: "{r["_strategy"]}"')
    p.append("---\n")
    if r.get("title"):
        p.append(f"# {r['title']}\n")
    meta = []
    if r.get("author"):
        meta.append(f"**作者**: {r['author']}")
    if r.get("account"):
        meta.append(f"**公众号**: {r['account']}")
    if r.get("publish_time"):
        meta.append(f"**发布时间**: {r['publish_time']}")
    if meta:
        p.append("\n".join(meta) + "\n")
    p.append(r.get("content", ""))
    return "\n".join(p)


def save(content, title, outdir):
    os.makedirs(outdir, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|\s]+', '_', title)[:80] or "wechat_article"
    fp = os.path.join(outdir, f"{safe}.md")
    if os.path.exists(fp):
        fp = os.path.join(outdir, f"{safe}_{int(time.time())}.md")
    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)
    return fp


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: fetch_weixin.py <url> [--json] [--save] [--output-dir DIR]", file=sys.stderr)
        sys.exit(1)

    url = args[0]
    use_json = "--json" in args
    do_save = "--save" in args
    outdir = DEFAULT_OUTPUT_DIR
    if "--output-dir" in args:
        idx = args.index("--output-dir")
        if idx + 1 < len(args):
            outdir = args[idx + 1]

    if "mp.weixin.qq.com/s/" not in url:
        print("⚠️  这不是微信公众号文章链接", file=sys.stderr)

    print("📡 正在抓取微信公众号文章...", file=sys.stderr, flush=True)
    r = fetch(url)

    if "error" in r:
        print(f"\n❌ 抓取失败: {r['error']}", file=sys.stderr)
        print("\n建议:", file=sys.stderr)
        print("  1. 将文章内容复制粘贴发给我", file=sys.stderr)
        print("  2. 截图文章用 OCR 识别", file=sys.stderr)
        print("  3. 在微信里「复制链接」后稍等几秒重试", file=sys.stderr)
        sys.exit(1)

    if use_json:
        out = {k: v for k, v in r.items() if not k.startswith("_")}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        md = fmt_md(r)
        print(md)
        if do_save:
            fp = save(md, r.get("title", ""), outdir)
            print(f"\n💾 已保存到: {fp}", file=sys.stderr)


if __name__ == "__main__":
    main()
