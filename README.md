# My-MCP Project

基于 [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) 构建的 MCP Server 集合。每个子目录是一个独立的 MCP 服务，可单独接入 Trae / Claude Desktop / MCP Inspector 等宿主工具。

## 项目结构

```
my-mcp/
├── src/
│   └── my_mcp/                          # Python 包根（src-layout 规范）
│       ├── __init__.py
│       ├── api_call/                    # 封装 API 调用的 MCP 服务
│       │   ├── __init__.py
│       │   ├── server.py                 # MCPServer：每日新闻获取
│       │   └── client.py                 # 调试用独立客户端（LLM 解析日期）
│       ├── news_analysis_email_flow/    # 舆情分析 + 邮件发送 MCP 服务
│       │   ├── __init__.py
│       │   ├── server.py                 # MCPServer：搜索新闻 → LLM 情感分析 → SMTP 发邮件
│       │   └── client.py                 # 调试用独立客户端
│       ├── note_search/                  # 本地笔记快速检索的 MCP 服务
│       │   └── __init__.py
│       ├── office/                      # Word 表格转 Excel 的 MCP 服务
│       │   ├── __init__.py
│       │   ├── server.py
│       │   └── client.py
│       └── vue_components_docs/         # Vue3 组件文档说明生成的 MCP 服务
│           └── __init__.py
├── pyproject.toml                       # 项目配置 & 依赖
├── .env                                 # 环境变量（密钥等，已加入 .gitignore）
├── .python-version
└── uv.lock
```

## 各子模块说明

### 1. `api_call/` — 封装 API 调用的 MCP 服务

**已实现：每日新闻获取**

通过 [60s API](https://60s.viki.moe) 获取每日早报，支持自然语言日期（"今天"、"上周五"、"2025年3月1日"）。

| 文件 | 作用 |
|------|------|
| `server.py` | `MCPServer("DailyNews")` + `get_daily_news(date)` 工具 |
| `client.py` | 本地调试客户端，内置 LLM 做日期意图解析 |

**接入 Trae 示例：**

```json
{
  "mcpServers": {
    "daily-news": {
      "command": "uv",
      "args": ["run", "--directory", "D:/work/my-mcp", "python", "-m", "my_mcp.api_call.server"]
    }
  }
}
```

---

### 2. `news_analysis_email_flow/` — 舆情分析 + 邮件发送 MCP 服务

**已实现：搜索 → 分析 → 发送邮件 流水线**

三个工具可被 LLM Agent 自动编排串联：

| 工具 | 说明 | 外部依赖 |
|------|------|----------|
| `search_google_news(keyword)` | Serper API 搜 Google 新闻，取前 5 条 | `SERPER_API_KEY` |
| `analyze_sentiment(text, filename)` | DashScope (阿里通义) 情感分析，生成 Markdown 报告 | `DASHSCOPE_API_KEY` |
| `send_email_with_attachment(to, subject, body, filename)` | SMTP 发送带附件的邮件 | `SMTP_SERVER` / `EMAIL_USER` / `EMAIL_PASS` |

---

### 3. `note_search/` — 本地笔记快速检索的 MCP 服务

**规划中**：提供本地笔记内容的快速搜索能力。

---

### 4. `office/` — Word 表格转 Excel 的 MCP 服务

**已实现：Word 文档提取表格并转为 Excel**

| 文件 | 作用 |
|------|------|
| `server.py` | MCPServer 入口，Word 表格解析工具 |
| `client.py` | 调试用独立客户端 |

---

### 5. `vue_components_docs/` — Vue3 组件文档说明生成的 MCP 服务

**规划中**：根据 Vue3 组件源码自动生成说明文档。

---

## 环境准备

### Python 版本

**要求 >= 3.12**（已通过 `.python-version` 锁定）。

### 依赖安装

使用 [uv](https://docs.astral.sh/uv/) 作为包管理器：

```bash
uv sync
```

依赖清单：

| 包 | 版本 | 用途 |
|----|------|------|
| `mcp` | >= 2.3.0 | MCP SDK，提供 `MCPServer` / `ClientSession` |
| `openai` | >= 3.39.0 | LLM 调用（兼容 DeepSeek / DashScope 等） |
| `httpx` | >= 0.28.1 | 异步 HTTP 请求 |
| `python-dotenv` | >= 1.2.4 | 加载 `.env` 文件 |

### 环境变量

复制 `.env` 并填入真实密钥：

```env
# --- LLM (DeepSeek) ---
DEEPSEEK_API_KEY=your_deepseek_key
DEFAULT_API_BASE=https://api.deepseek.com

# --- Serper 新闻搜索 ---
SERPER_API_KEY=your_serper_key           # https://serper.dev/

# --- DashScope 情感分析 ---
DASHSCOPE_API_KEY=your_dashscope_key     # https://dashscope.aliyun.com/
MODEL=qwen-plus
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# --- SMTP 邮件 ---
SMTP_SERVER=smtp.qq.com
SMTP_PORT=465
EMAIL_USER=your_email@qq.com
EMAIL_PASS=your_smtp_auth_code           # QQ 邮箱需使用授权码
```

## 运行

### 启动某个 MCP Server（stdio 模式）

```bash
# 每日新闻
uv run python -m my_mcp.api_call.server

# 舆情分析 + 邮件
uv run python -m my_mcp.news_analysis_email_flow.server

# Word 转 Excel
uv run python -m my_mcp.office.server
```

Server 启动后通过 `stdio` 与 MCP Client 通信，可被 Trae / Claude Desktop / MCP Inspector 等宿主连接。

### 本地调试（自带 client）

```bash
uv run python -m my_mcp.api_call.client
```

## 开发说明

### MCP SDK v2

本项目使用 **mcp >= 2.3.0**（v2 最新版）。v1 的 `FastMCP` 在 v2 中已被重命名：

| v1 (旧) | v2 (本项目使用) |
|---------|----------------|
| `from mcp.server.fastmcp import FastMCP` | `from mcp.server.mcpserver import MCPServer` |
| `mcp = FastMCP("name")` | `mcp = MCPServer("name")` |

`@mcp.tool()`、`mcp.run()` 等 API 保持不变。

### src-layout 规范

项目使用 Python 社区推荐的 **src-layout**，构建后端为 `uv_build`。`src/my_mcp/` 是真正的可导入 Python 包（import 路径为 `my_mcp`），外层项目名 `my-mcp` 是 PyPI 分发名称（连字符自动映射为下划线包名）。

## License

MIT
