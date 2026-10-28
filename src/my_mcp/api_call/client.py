"""每日新闻 MCP Client

连接 api_call.server，让用户用自然语言获取每日新闻。
集成 LLM 做日期意图解析（如 "今天十月一号" → "2026-10-01"）。
"""

import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from contextlib import AsyncExitStack
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

load_dotenv()


def build_date_system_prompt() -> str:
    """构建日期解析的 system prompt，注入当前日期上下文。"""
    today = datetime.now()
    context_lines = [
        f"今天是 {today.strftime('%Y-%m-%d')}（{today.strftime('%A')}）。",
        f"昨天是 {(today - timedelta(days=1)).strftime('%Y-%m-%d')}。",
        f"明天是 {(today + timedelta(days=1)).strftime('%Y-%m-%d')}。",
    ]
    return (
        "你是一个日期解析助手。把用户的自然语言日期描述转换为 YYYY-MM-DD 格式。\n"
        "规则：\n"
        "1. 如果用户没提日期（如 '获取今天的新闻'、'看看新闻'），返回 null。\n"
        "2. 用户说 '今天'、'今日'、'现在' → null（表示取今天）。\n"
        "3. 用户说 '昨天' → 昨天日期，'明天' → 明天日期。\n"
        "4. 用户说 '十月一号'、'3月1日' 这种只有月日的，按今年补全；如果今年该日期已过且明显指下一次（如春节），取下一年。\n"
        "5. 用户说具体年份如 '2025年3月1日' → 直接转。\n"
        "6. 只返回 JSON，不要任何解释文字。格式: {\"date\": \"YYYY-MM-DD\"} 或 {\"date\": null}\n"
        "当前日期参考：\n" + "\n".join(context_lines)
    )


class NewsClient:
    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEFAULT_API_BASE")
        model = os.getenv("DEEPSEEK_MODEL")

        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY 未配置")

        self.llm = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def resolve_date(self, query: str) -> str | None:
        """调用 LLM 把自然语言日期解析成 YYYY-MM-DD 或 None。"""
        try:
            resp = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": build_date_system_prompt()},
                    {"role": "user", "content": query},
                ],
                response_format={"type": "json_object"},
            )
            text = resp.choices[0].message.content.strip()
            data = json.loads(text)
            return data.get("date")
        except Exception as e:
            print(f"⚠️ 日期解析失败: {e}，默认取今天")
            return None


async def main():
    server_script = str(Path(__file__).parent / "server.py")

    if not os.path.exists(server_script):
        print(f"❌ 找不到服务端脚本: {server_script}")
        sys.exit(1)

    # 初始化 LLM 客户端
    try:
        news_client = NewsClient()
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    async with AsyncExitStack() as stack:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_script],
            env=None,
        )
        stdio_transport = await stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport

        session = await stack.enter_async_context(ClientSession(stdio, write))
        await session.initialize()

        tools_resp = await session.list_tools()
        print(f"✅ 已连接，可用工具: {[t.name for t in tools_resp.tools]}")

        print("\n🤖 每日新闻客户端已启动！输入 'quit' 退出")
        print("   可输入：'今天的新闻'、'2025年3月1日的新闻'、'十月一号有什么大事'\n")

        while True:
            try:
                query = input("你: ").strip()
                if query.lower() in ("quit", "exit", "q"):
                    break

                # 1) LLM 解析日期
                target_date = news_client.resolve_date(query)
                print(f"   🧠 LLM 解析日期 → {target_date or '今天'}")

                # 2) 调用 MCP 工具
                args = {"date": target_date} if target_date else {}
                result = await session.call_tool("get_daily_news", args)
                news_text = result.content[0].text
                print(f"\n🤖 AI:\n{news_text}")

            except KeyboardInterrupt:
                print("\n👋 再见！")
                break
            except Exception as e:
                print(f"\n⚠️ 发生错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())
