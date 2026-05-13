#!/bin/bash
set -e
echo "=== Sihan's Claude Code Config ==="

CLAUDE_SKILLS="$HOME/.claude/skills"
SRC="$(cd "$(dirname "$0")" && pwd)"

# 1. Install Skills
echo "[1/3] Installing Skills..."
mkdir -p "$CLAUDE_SKILLS"
for skill_dir in "$SRC"/plugins/*/skills/*/; do
    [ -d "$skill_dir" ] || continue
    name=$(basename "$skill_dir")
    rm -rf "$CLAUDE_SKILLS/$name"
    cp -r "$skill_dir" "$CLAUDE_SKILLS/$name"
    echo "  $name → $CLAUDE_SKILLS/$name"
done

# 2. Install Zotero MCP launcher + source
echo "[2/3] Installing Zotero MCP launcher..."
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/zotero-local"
cp "$SRC/plugins/zotero-local/bin/zotero-mcp-local" "$HOME/.local/bin/"
chmod +x "$HOME/.local/bin/zotero-mcp-local"
cp -r "$SRC/plugins/zotero-local/src" "$HOME/.local/share/zotero-local/"
echo "  zotero-mcp-local → $HOME/.local/bin/"
echo "  src/ → $HOME/.local/share/zotero-local/src/"

# 3. Install Python deps
echo "[3/3] Installing Python dependencies..."
pip3 install --user fastmcp pyzotero requests markitdown feedparser unidecode beautifulsoup4 markdown weasyprint 2>&1 | tail -3

echo ""
echo "Done! Restart Claude Code."
echo "Then run: /plugin marketplace add <repo-url>"
echo "Or manually: claude mcp add zotero -- zotero-mcp-local"
