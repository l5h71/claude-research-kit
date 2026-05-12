#!/usr/bin/env python3
"""arXiv Paper Translator: HTML → bilingual MD → PDF → Zotero attachment."""
import os, sys, re, json, shutil, tempfile, argparse
from pathlib import Path
from datetime import datetime

SKILL_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = SKILL_DIR / "tmp"
TMP_DIR.mkdir(exist_ok=True)

# === Config (set via environment variables) ===
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
ZOTERO_KEY = os.environ.get("ZOTERO_API_KEY", "")
ZOTERO_USER = os.environ.get("ZOTERO_LIBRARY_ID", "")
PROXY_HTTP = os.environ.get("HTTP_PROXY_CC", "http://127.0.0.1:7890")
PROXY = {"http": PROXY_HTTP, "https": PROXY_HTTP}
MODEL = os.environ.get("TRANSLATE_MODEL", "deepseek-v4-flash")

if not DEEPSEEK_KEY:
    print("ERROR: Set DEEPSEEK_API_KEY environment variable", file=sys.stderr)
    sys.exit(1)

from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

# === Step 1: Download arXiv HTML ===

def fetch_html(arxiv_id):
    """Fetch the HTML version of an arXiv paper. Try v3, v2, v1."""
    for v in ["v3", "v2", "v1"]:
        url = f"https://arxiv.org/html/{arxiv_id}{v}"
        try:
            r = requests.get(url, proxies=PROXY, timeout=30)
            if r.status_code == 200 and "<article" in r.text:
                print(f"  Got HTML version: {v}")
                return r.text, v
        except Exception as e:
            print(f"  HTML {v} failed: {e}")
    print("  No HTML version found, falling back to PDF extraction...")
    return None, None

# === Step 2: Parse HTML ===

def parse_html(html, arxiv_id, version):
    """Extract structured content from arXiv LaTeXML HTML."""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article") or soup.find("body")
    if not article:
        return [], []

    elements = []  # List of (type, content, metadata)
    figures_dir = TMP_DIR / f"{arxiv_id}_figures"
    figures_dir.mkdir(exist_ok=True)
    images = []

    # Remove nav, script, style
    for tag in article.find_all(["nav", "script", "style", "head"]):
        tag.decompose()

    # Walk ALL elements in document order (not just top-level)
    seen_headings = set()
    for el in article.find_all():
        tag_name = el.name
        classes = el.get("class", [])
        # Skip deeply nested inline elements
        if tag_name in ("span", "a", "em", "strong", "i", "b", "code", "sub", "sup", "cite"):
            continue

        # Section headings (h2-h6, skip h1 which is the paper title)
        if tag_name in ("h2", "h3", "h4"):
            text = el.get_text(strip=True)
            if text and len(text) > 2 and text not in seen_headings:
                seen_headings.add(text)
                level = int(tag_name[1])
                elements.append(("heading", text, {"level": level}))

        # Figures
        elif tag_name == "figure":
            img = el.find("img")
            caption = el.find("figcaption")
            if img:
                src = img.get("src", "")
                if src.startswith("figures/") or src.startswith("x/"):
                    img_name = os.path.basename(src)
                    img_url = f"https://arxiv.org/html/{arxiv_id}{version}/{src}"
                    img_path = figures_dir / img_name
                    try:
                        r = requests.get(img_url, proxies=PROXY, timeout=30)
                        if r.status_code == 200:
                            img_path.write_bytes(r.content)
                            images.append(str(img_path))
                    except Exception:
                        pass
                    caption_text = caption.get_text(strip=True) if caption else ""
                    elements.append(("figure", caption_text, {"path": str(img_path), "name": img_name}))

        # Paragraphs - only ltx_p paragraphs in the main content
        elif tag_name == "p" and ("ltx_p" in classes or not classes):
            text = el.get_text(strip=True)
            # Keep only substantial paragraphs (skip TOC fragments, navigation)
            if len(text) > 80:
                elements.append(("text", text, {}))

    return elements, images

def _extract_text_with_math(el):
    """Extract text paragraphs preserving inline math."""
    parts = []
    for child in el.descendants:
        if isinstance(child, str):
            parts.append(("text", str(child)))
        elif child.name == "span" and "ltx_Math" in (child.get("class") or []):
            latex = child.get("data-simplenotation", "") or child.get_text(strip=True)
            if latex:
                parts.append(("math", f"${latex}$"))
        elif child.name == "math":
            parts.append(("math", child.get_text(strip=True)))
    return parts

# === Step 3: Build translatable sections ===

def build_sections(elements):
    """Group elements into sections for translation."""
    sections = []
    current_heading = ""
    current_texts = []
    current_figures = []

    for el_type, content, meta in elements:
        if el_type == "heading":
            # Flush previous section
            if current_texts or current_figures:
                sections.append({
                    "heading": current_heading,
                    "texts": current_texts,
                    "figures": current_figures
                })
            current_heading = content
            current_texts = []
            current_figures = []
        elif el_type == "text":
            if len(content) > 100:  # Skip very short text fragments
                current_texts.append(content)
        elif el_type in ("figure", "table", "math"):
            current_figures.append((el_type, content, meta))

    # Flush last section
    if current_texts or current_figures:
        sections.append({
            "heading": current_heading,
            "texts": current_texts,
            "figures": current_figures
        })

    return sections

# === Step 4: Translate via DeepSeek ===

def translate_all_sections(sections):
    """Translate all sections in 2-3 large batches (fast)."""
    # Combine sections into big chunks (~15K chars each)
    chunks = []
    current_chunk = ""
    chunk_sections = []  # Track which sections go in each chunk

    for sec in sections:
        h = sec.get("heading", "")
        texts = sec.get("texts", [])
        sec_text = (f"## {h}\n\n" if h else "") + "\n\n".join(texts[:8])

        if len(current_chunk) + len(sec_text) > 15000 and current_chunk:
            chunks.append(current_chunk)
            current_chunk = sec_text
        else:
            current_chunk += "\n\n" + sec_text if current_chunk else sec_text

    if current_chunk:
        chunks.append(current_chunk)

    print(f"  Split into {len(chunks)} translation batches", flush=True)

    system_prompt = """你是学术论文翻译专家。将以下内容翻译为中文。
要求：1.保留Markdown标题(# ## ###) 2.每段后>保留英文原文 3.专业术语不翻译(LLM,RLHF,benchmark,synergy等) 4.保留引用[1]和数字 5.简洁准确"""

    def translate_chunk(i, chunk):
        try:
            resp = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                json={"model": MODEL, "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"翻译：\n\n{chunk}"}
                ], "temperature": 0.3, "max_tokens": 8192}, timeout=180)
            result = resp.json()
            if "choices" in result:
                t = result["choices"][0]["message"]["content"]
                print(f"  Batch {i}/{len(chunks)} OK ({len(t)} chars)", flush=True)
                return (i, t)
            return (i, "")
        except Exception as e:
            print(f"  Batch {i} failed: {e}", flush=True)
            return (i, "")

    # Parallel translation
    print(f"  Translating {len(chunks)} batches in parallel...", flush=True)
    results = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(translate_chunk, i, c): i for i, c in enumerate(chunks, 1)}
        for f in as_completed(futures):
            i, text = f.result()
            results[i] = text

    ordered = [results[i] for i in sorted(results.keys()) if results[i]]
    return "\n\n".join(ordered)

# === Step 5: Build Markdown ===

def build_markdown(sections, images, title, authors):
    """Assemble the final bilingual Markdown."""
    md = f"# {title}\n\n"
    if authors:
        md += f"*{authors}*\n\n"
    md += f"> 翻译引擎：DeepSeek Chat | {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n\n"

    # Translate all content in one batch
    print("  Translating all sections...", flush=True)
    translated = translate_all_sections(sections)
    md += translated + "\n\n"

    # Add figures
    md += "\n## 图表索引\n\n"
    for sec in sections:
        for fig_type, content, meta in sec.get("figures", []):
            if fig_type == "figure":
                path = meta.get("path", "")
                name = meta.get("name", "")
                md += f"![{content}]({path})\n*Figure: {content}*\n\n"

    return md

# === Step 6: Convert to PDF ===

def md_to_pdf(md_path, pdf_path):
    """Convert Markdown to PDF via markdown→HTML→weasyprint."""
    try:
        import markdown as md_lib
        md_content = md_path.read_text()
        # Convert Markdown to HTML
        html_body = md_lib.markdown(
            md_content, extensions=["extra", "codehilite", "tables", "fenced_code"]
        )
    except ImportError:
        # Fallback: just wrap the raw MD in HTML
        html_body = f"<pre>{md_path.read_text()}</pre>"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"/>
<style>
@page {{ size: A4; margin: 2cm; }}
body {{ font-family: 'Noto Sans CJK SC', 'WenQuanYi Micro Hei', sans-serif; font-size: 11pt; line-height: 1.7; }}
h1 {{ font-size: 18pt; }}
h2 {{ font-size: 14pt; border-bottom: 1px solid #ccc; padding-bottom: 4pt; margin-top: 20pt; }}
h3 {{ font-size: 12pt; }}
img {{ max-width: 100%; height: auto; display: block; margin: 8pt auto; }}
table {{ border-collapse: collapse; width: 100%; margin: 8pt 0; }}
td, th {{ border: 1px solid #ddd; padding: 6px; text-align: left; }}
blockquote {{ border-left: 3px solid #4CAF50; margin-left: 0; padding-left: 12pt; color: #333; }}
pre {{ background: #f5f5f5; padding: 8pt; border-radius: 4pt; overflow-x: auto; }}
figcaption, .caption {{ font-style: italic; text-align: center; color: #666; }}
</style></head>
<body>{html_body}</body>
</html>"""

    html_path = pdf_path.with_suffix(".html")
    html_path.write_text(html)

    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(str(pdf_path))
        html_path.unlink(missing_ok=True)
        return pdf_path.exists()
    except Exception as e:
        print(f"  weasyprint failed: {e}")
        html_path.unlink(missing_ok=True)
        return False

# === Step 7: Attach to Zotero ===

def attach_to_zotero(zotero_key, pdf_path, arxiv_id):
    """Attach PDF to Zotero via local storage (bypass cloud quota)."""
    import os as _os
    for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']:
        _os.environ.pop(k, None)

    from pyzotero import zotero
    z = zotero.Zotero(ZOTERO_USER, "user", ZOTERO_KEY)

    filename = f"arxiv_{arxiv_id}_translated.pdf"
    try:
        # Create attachment metadata via Web API (no file upload)
        att_template = z.item_template("attachment", "imported_file")
        att_template["title"] = f"中文翻译 - {arxiv_id}"
        att_template["contentType"] = "application/pdf"
        att_template["filename"] = filename
        att_template["parentItem"] = zotero_key
        result = z.create_items([att_template])
        if result.get("success"):
            att_key = next(iter(result["success"].values()))
            # Save PDF to local Zotero storage (WebDAV syncs it)
            storage_dir = Path.home() / "Zotero" / "storage" / att_key
            storage_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf_path, storage_dir / filename)
            print(f"  PDF saved locally: {storage_dir / filename}")
            return True
        else:
            print(f"  Attach failed: {result}")
            return False
    except Exception as e:
        print(f"  Zotero error: {e}")
        return False

# === Main ===

def main():
    parser = argparse.ArgumentParser(description="Translate arXiv paper")
    parser.add_argument("arxiv_id", help="arXiv ID (e.g., 2602.01011)")
    parser.add_argument("zotero_key", nargs="?", default="",
                        help="Zotero item key to attach PDF to")
    args = parser.parse_args()

    arxiv_id = args.arxiv_id.strip()
    zotero_key = args.zotero_key.strip()

    print(f"\n{'='*50}")
    print(f"Translating arXiv:{arxiv_id}")
    print(f"{'='*50}\n")

    # Step 1: Download
    print("[1/6] Downloading HTML...")
    html, version = fetch_html(arxiv_id)
    if not html:
        print("  ERROR: No HTML version available")
        sys.exit(1)

    # Step 2: Parse
    print("[2/6] Parsing content...")
    elements, images = parse_html(html, arxiv_id, version)

    # Extract title and authors
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("h1")
    title = title.get_text(strip=True) if title else f"arXiv:{arxiv_id}"
    author_el = soup.find(class_="ltx_authors") or soup.find(class_="authors")
    authors = author_el.get_text(strip=True) if author_el else ""

    # Step 3: Build sections
    print(f"[3/6] Built {len(elements)} content elements, {len(images)} images")
    sections = build_sections(elements)
    print(f"  {len(sections)} sections to translate")

    # Step 4 & 5: Translate and build Markdown
    print("[4/6] Translating via DeepSeek...")
    md_content = build_markdown(sections, images, title, authors)

    md_path = TMP_DIR / f"{arxiv_id}_translated.md"
    md_path.write_text(md_content)
    print(f"  Markdown: {len(md_content)} chars → {md_path}")

    # Step 6: Convert to PDF
    print("[5/6] Converting to PDF...")
    if zotero_key:
        pdf_path = TMP_DIR / f"{arxiv_id}_translated.pdf"
    else:
        pdf_path = Path.home() / "Downloads" / f"arxiv_{arxiv_id}_translated.pdf"

    if md_to_pdf(md_path, pdf_path):
        print(f"  PDF: {pdf_path} ({pdf_path.stat().st_size // 1024} KB)")
    else:
        print("  PDF conversion failed, keeping Markdown only")

    # Step 7: Attach to Zotero
    if zotero_key and pdf_path.exists():
        print("[6/6] Attaching to Zotero...")
        attach_to_zotero(zotero_key, pdf_path, arxiv_id)

    # Cleanup
    print("\nCleaning up...")
    figures_dir = TMP_DIR / f"{arxiv_id}_figures"
    if figures_dir.exists():
        shutil.rmtree(figures_dir)
    # Keep the final MD and PDF in Downloads if no Zotero
    if not zotero_key and md_path.exists():
        dest = Path.home() / "Downloads" / f"arxiv_{arxiv_id}_translated.md"
        shutil.copy(md_path, dest)
        print(f"  Markdown saved to {dest}")

    print("\nDone!")

if __name__ == "__main__":
    main()
