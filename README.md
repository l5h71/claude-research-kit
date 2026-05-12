# Claude Research Kit

Claude Code 科研工具市场：arXiv 论文翻译 + Zotero 本地存储 MCP。

## 安装

### Linux / macOS

```bash
# 克隆仓库
git clone https://github.com/liusihan/claude-research-kit.git ~/dev/claude-research-kit
cd ~/dev/claude-research-kit

# 配置 API Key（复制后填入真实 key）
cp .env.example .env
# 编辑 .env：DEEPSEEK_API_KEY=sk-xxx, ZOTERO_API_KEY=xxx, ZOTERO_LIBRARY_ID=xxx

# 一键安装
bash install.sh
```

### Windows

```powershell
# PowerShell 中克隆
git clone https://github.com/liusihan/claude-research-kit.git $env:USERPROFILE\dev\claude-research-kit
cd $env:USERPROFILE\dev\claude-research-kit

# 复制并编辑环境变量文件
copy .env.example .env
notepad .env

# 运行安装
powershell -File install.ps1
```

Windows 还需要手动确保：
- Python 3.10+ 已安装并在 PATH 中（[python.org](https://python.org)）
- Zotero 7 已安装，本地 API 已开启（编辑 → 设置 → 高级 → 勾选「允许其他应用与 Zotero 通信」）
- 安装后把 `%USERPROFILE%\.local\bin` 加入系统 PATH

## 环境变量

复制 `.env.example` 为 `.env`，填入：

| 变量 | 说明 | 哪里获取 |
|------|------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | [platform.deepseek.com](https://platform.deepseek.com/api_keys) |
| `ZOTERO_API_KEY` | Zotero API Key | [zotero.org/settings/keys](https://www.zotero.org/settings/keys) |
| `ZOTERO_LIBRARY_ID` | Zotero 用户 ID | zotero.org 账户页面的数字 ID |
| `HTTP_PROXY_CC` | HTTP 代理地址（国内用户） | 默认 `http://127.0.0.1:7890` |
| `TRANSLATE_MODEL` | 翻译模型 | 默认 `deepseek-v4-flash` |

## 在 Claude Code 中启用

重启 Claude Code 后：

```
/plugin marketplace add github.com/liusihan/claude-research-kit
/plugin install arxiv-translate
/plugin install zotero-local
```

## 插件

### arxiv-translate —— arXiv 论文翻译

给定 arXiv ID，自动下载 HTML 版本 → 提取正文+图表 → 调 DeepSeek 并行翻译 → 生成中英对照 PDF → 挂到 Zotero 条目下。

**使用：**
```
翻译 arXiv 论文 2602.01011，加到 Zotero 条目 E9ITAXK7 下
```

或在终端直接运行：
```bash
PYTHONUNBUFFERED=1 python3 -u \
  ~/.claude/skills/arxiv-translate/scripts/arxiv_translate.py \
  <arxiv-id> [zotero-item-key]
```

**功能：**
- 中英双语对照（段落级 > 引用格式）
- 自动下载并嵌入论文图片（最多 30+ 张）
- 保留公式、表格、引用标记
- 并行调用 DeepSeek V4 Flash（1M 上下文，4 批并发）
- PDF 存入本地 Zotero storage，走 WebDAV/坚果云同步

**依赖：** `pip install beautifulsoup4 markdown weasyprint requests pyzotero`

### zotero-local —— 修改版 Zotero MCP

基于 [54yyyu/zotero-mcp](https://github.com/54yyyu/zotero-mcp) 的自建修改版，额外支持：

- `attach_mode=local`（默认）：PDF 下载后存本地 Zotero storage，通过 WebDAV 同步，**不消耗 Zotero 云端 300MB 配额**
- `attach_mode=linked_url`：arXiv 论文只存 PDF 链接
- PDF 下载绕过代理，API 调用走代理
- 默认 DeepSeek V4 Flash 翻译引擎

**依赖：** `pip install fastmcp pyzotero requests markitdown feedparser unidecode beautifulsoup4`

## 许可证

MIT
