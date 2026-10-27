# My-MCP Project

基于 [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) 构建的舆情分析工作流项目，包含一个 MCP Server 端和一个 Client 端。Server 提供新闻搜索、情感分析、邮件发送三个工具，可被 LLM Agent 自动编排调用，实现"搜索 → 分析 → 邮件发送"的完整流水线。

## 功能概览

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  search_google_news  │ ──▶ │  analyze_sentiment   │ ──▶ │ send_email_with_... │
│  Serper API 搜新闻   │     │  LLM 情感分析        │     │  SMTP 发送邮件        │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

### MCP Server (`src/my_mcp/server.py`)

| 工具 | 说明 | 外部依赖 |
|------|------|----------|
| `search_google_news(keyword)` | 调用 Serper API 根据关键词搜索 Google 新闻，返回前 5 条标题/描述/链接并保存为本地 JSON 文件 | `SERPER_API_KEY` |
| `analyze_sentiment(text, filename)` | 使用 DashScope (阿里通义) 对文本进行情感分析，生成 Markdown 格式报告 | `DASHSCOPE_API_KEY`、`MODEL`、`BASE_URL` |
| `send_email_with_attachment(to, subject, body, filename)` | 通过 SMTP 发送带附件的邮件（与上一步的 Markdown 报告配合） | `SMTP_SERVER`、`SMTP_PORT`、`EMAIL_USER`、`EMAIL_PASS` |

### MCP Client (`src/my_mcp/client.py`)

Client 端骨架代码，封装了：
- `OpenAI` 兼容 SDK（指向 DeepSeek API）
- `AsyncExitStack` 异步上下文自动管理
- `ClientSession` 用于后续连接 MCP Server

## 项目结构

```
my-mcp/
├── src/
│   └── my_mcp/
│       ├── __init__.py
│       ├── server.py          # MCP Server 入口
│       └── client.py          # MCP Client 骨架
├── pyproject.toml             # 项目配置 & 依赖
├── .env                       # 环境变量（密钥等）
├── .python-version
└── uv.lock
```

## 环境准备

### 1. Python 版本

要求 **Python >= 3.12**（已通过 `.python-version` 锁定）。

### 2. 依赖安装

本项目使用 [uv](https://docs.astral.sh/uv/) 作为包管理器：

```bash
uv sync
```

依赖清单：

| 包 | 版本 | 用途 |
|----|------|------|
| `mcp` | >= 2.3.0 | MCP SDK，`MCPServer` / `ClientSession` |
| `openai` | >= 3.39.0 | LLM 调用（兼容 DeepSeek / DashScope 等） |
| `httpx` | >= 0.28.1 | Serper API 异步 HTTP 请求 |
| `python-dotenv` | >= 1.2.4 | 加载 `.env` 文件 |

### 3. 环境变量

复制 `.env` 并填入真实密钥：

```env
# --- Client 端 (DeepSeek) ---
DEEPSEEK_API_KEY=your_deepseek_key
DEFAULT_API_BASE=https://api.deepseek.com

# --- Server 端 (Serper 新闻搜索) ---
SERPER_API_KEY=your_serper_key     # https://serper.dev/

# --- Server 端 (DashScope 情感分析) ---
DASHSCOPE_API_KEY=your_dashscope_key   # https://dashscope.aliyun.com/
MODEL=qwen-plus
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# --- Server 端 (SMTP 邮件) ---
SMTP_SERVER=smtp.qq.com
SMTP_PORT=465
EMAIL_USER=your_email@qq.com
EMAIL_PASS=your_smtp_auth_code       # QQ 邮箱需使用授权码而非登录密码
```

## 运行

### 启动 MCP Server（stdio 模式）

```bash
uv run python -m my_mcp.server
# 或直接
uv run server
```

Server 启动后通过 `stdio` 与 MCP Client 通信，可被 Trae / Claude Desktop / MCP Inspector 等宿主工具连接。

### 作为 MCP 配置接入客户端

例如在 Claude Desktop 的 `claude_desktop_config.json` 中：

```json
{
  "mcpServers": {
    "news-server": {
      "command": "uv",
      "args": ["run", "--directory", "D:/work/my-mcp", "python", "-m", "my_mcp.server"]
    }
  }
}
```

## 开发说明

### MCP SDK v2 重命名

本项目使用 **mcp >= 2.3.0**（v2 最新版）。v1 的 `FastMCP` 在 v2 中已被重命名：

| v1 (旧) | v2 (本项目使用) |
|---------|----------------|
| `from mcp.server.fastmcp import FastMCP` | `from mcp.server.mcpserver import MCPServer` |
| `mcp = FastMCP("name")` | `mcp = MCPServer("name")` |

`@mcp.tool()`、`mcp.run()` 等 API 保持不变。如需继续使用 v1 FastMCP 风格，可降级：

```bash
uv add "mcp<2"
```

### src-layout 目录规范

项目使用 Python 社区推荐的 **src-layout** 布局，构建后端为 `uv_build`。`src/my_mcp/` 是真正的可导入 Python 包（import 路径为 `my_mcp`），外层项目名 `my-mcp` 是 PyPI 分发名称（连字符自动映射为下划线包名）。

## License

MIT
