# Claude Code Plugins by Sihan

Personal marketplace for Claude Code: arXiv paper translator + modified Zotero MCP.

## Quick Install

```bash
git clone <this-repo> ~/dev/claude-config
cd ~/dev/claude-config && bash install.sh
```

Then in Claude Code:

```
/plugin marketplace add github.com/liusihan/claude-config
/plugin install arxiv-translate
/plugin install zotero-local
```

## Plugins

### arxiv-translate
Translate arXiv papers to bilingual Chinese-English PDF with figures, attach to Zotero.

```
PYTHONUNBUFFERED=1 python3 -u \
  ~/.claude/skills/arxiv-translate/scripts/arxiv_translate.py \
  2602.01011 E9ITAXK7
```

### zotero-local
Modified Zotero MCP with:
- `attach_mode=local` default (PDF saved to ~/Zotero/storage, synced via WebDAV)
- `attach_mode=linked_url` support for arXiv papers
- Proxy bypass for PDF downloads
- Proxy awareness for external API calls

## Dependencies

- Python 3.10+
- Zotero 7+
- pip: fastmcp, pyzotero, requests, markitdown, beautifulsoup4, markdown, weasyprint
