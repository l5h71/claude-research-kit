---
name: arxiv-translate
description: Translate arXiv papers to Chinese with bilingual Markdown + PDF output. Use when user asks to translate any arXiv paper, mentions an arXiv ID, wants paper translation, or says "翻译论文"/"translate paper"/"翻论文". Also use when user wants to add a translated paper PDF to Zotero.
---

# arXiv Paper Translator

Translate arXiv papers into bilingual Chinese-English Markdown, convert to PDF, and optionally attach to Zotero.

## When to Use

Trigger whenever the user:
- Provides an arXiv ID (e.g., 2602.01011) and wants it translated
- Asks to "translate this paper" or "翻译这篇论文"
- Mentions translating a paper and attaching to Zotero
- Says "翻一下" + arXiv URL

## Workflow

### Step 1: Gather information

Ask the user for:
- arXiv ID or URL (required)
- Zotero item key to attach PDF to (optional — if omitted, PDF saves to ~/Downloads)

### Step 2: Run the translation script

```bash
PYTHONUNBUFFERED=1 python3 -u ~/.claude/skills/arxiv-translate/scripts/arxiv_translate.py \
  <arxiv-id> [zotero-item-key]
```

The script handles everything automatically:
1. Downloads arXiv HTML version
2. Extracts text, images, tables, formulas
3. Translates via DeepSeek API (bilingual format)
4. Generates Markdown with embedded figures
5. Converts to PDF via pandoc
6. Attaches PDF to Zotero item (if key provided)
7. Cleans up temporary files

### Step 3: Report results

Tell the user:
- Where the PDF was saved
- Translation token usage
- Any sections that were skipped

## Requirements

All dependencies should already be installed. If `pandoc` or `weasyprint` is missing:
```bash
sudo apt install pandoc
pip install weasyprint
```

## Notes

- The script uses DeepSeek Chat API (128K context, ¥0.14/M tokens)
- arXiv HTML version may not be available for older papers — the script falls back to PDF extraction
- Large papers are split into sections and translated in parallel batches
- All temporary files are cleaned up after completion
