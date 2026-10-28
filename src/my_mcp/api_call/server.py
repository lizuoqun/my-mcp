"""每日新闻 MCP Server

通过 60s API (https://60s.viki.moe) 获取每日新闻资讯。
支持指定日期查询，未指定则默认返回今天。
"""

import httpx
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("DailyNews")


@mcp.tool()
async def get_daily_news(date: str | None = None) -> str:
    """
    获取指定日期的每日早报，返回 10-15 条全球热点新闻。

    参数 date 的传值规则（你必须按以下规则把用户的自然语言日期转为 YYYY-MM-DD）：
      - 用户说"今天"、"今日"、"现在"、没提日期 → 传 None
      - 用户说"昨天" → 昨天的 YYYY-MM-DD
      - 用户说"明天" → 明天的 YYYY-MM-DD
      - 用户说具体年月如"2025年3月1日"、"2025-03-01" → 直接传该值
      - 用户只说月日如"十月一号"、"3月1日" → 按今年补全为 YYYY-MM-DD；
        若今年该日期已过且明显指下一次（如春节、国庆等周期性节日），取下一年
      - 用户说"上周五"、"下周一"、"前天"、"大后天"等相对日期 → 换算成绝对日期传入
      - 日期格式必须是严格的 YYYY-MM-DD，如 "2026-10-28"

    返回:
        str: 格式化的新闻列表文本，包含日期标题和编号新闻条目。
    """

    url = "https://60s.viki.moe/v2/60s"
    params = {"date": date} if date else None

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=10)

    if response.status_code != 200:
        return f"❌ 请求失败，状态码: {response.status_code}"

    data = response.json()
    if data.get("code") != 200:
        return f"❌ API 返回错误: {data.get('message', '未知原因')}"

    payload = data["data"]
    api_date = payload.get("date", date or "今天")
    news_list = payload.get("news", [])

    if not news_list:
        return f"❌ {api_date} 暂无新闻数据"

    # 格式化输出
    lines = [f"📰 每日早报 · {api_date}", "=" * 30]
    for i, item in enumerate(news_list, 1):
        lines.append(f"{i}. {item}")
    lines.append(f"\n共 {len(news_list)} 条新闻")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
