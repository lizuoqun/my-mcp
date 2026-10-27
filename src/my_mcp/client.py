import os
import json
import re
import asyncio
from contextlib import AsyncExitStack
from typing import Optional, List
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from datetime import datetime
from openai import OpenAI

load_dotenv()


class MCPClient:
    def __init__(self):
        # 用于托管所有异步资源释放，这是为了后续连接 MCP Server 时使用 `async with` 语法自动管理上下文
        self.exit_stack = AsyncExitStack()

        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEFAULT_API_BASE")

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY为空，在.env文件里面进行配置！")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.session: Optional[ClientSession] = None

    async def connect_to_server(self, server_script_path: str):
        # 对服务器脚本进行判断，只允许是 .py 或 .js
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("服务器脚本必须是 .py 或 .js 文件")

        # 确定启动命令，.py 用 python，.js 用 node
        command = "python" if is_python else "node"

        # 构造 MCP 所需的服务器参数，包含启动命令、脚本路径参数、环境变量（为 None 表示默认）
        server_params = StdioServerParameters(command=command, args=[server_script_path], env=None)

        # 启动 MCP 工具服务进程（并建立 stdio 通信）
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))

        # 拆包通信通道，读取服务端返回的数据，并向服务端发送请求
        self.stdio, self.write = stdio_transport

        # 创建 MCP 客户端会话对象
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        # 初始化会话
        await self.session.initialize()

        # 获取工具列表并打印
        response = await self.session.list_tools()
        tools = response.tools
        print("\n已连接到服务器，支持以下工具:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        # 准备初始消息和获取工具列表
        messages = [{"role": "user", "content": query}]
        response = await self.session.list_tools()

        available_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                }
            } for tool in response.tools
        ]

        # 提取问题的关键词，对文件名进行生成。
        # 在接收到用户提问后就应该生成出最后输出的 md 文档的文件名，
        # 因为导出时若再生成文件名会导致部分组件无法识别该名称。
        keyword_match = re.search(r'(关于|分析|查询|搜索|查看)([^的\s，。、？\n]+)', query)
        keyword = keyword_match.group(2) if keyword_match else "分析对象"
        safe_keyword = re.sub(r'[\\/:*?"<>|]', '', keyword)[:20]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        md_filename = f"sentiment_{safe_keyword}_{timestamp}.md"
        md_path = os.path.join("./sentiment_reports", md_filename)

        # 更新查询，将文件名添加到原始查询中，使大模型在调用工具链时可以识别到该信息
        # 然后调用 plan_tool_usage 获取工具调用计划
        query = query.strip() + f" [md_filename={md_filename}] [md_path={md_path}]"
        messages = [{"role": "user", "content": query}]

        tool_plan = await self.plan_tool_usage(query, available_tools)

        tool_outputs = {}
        messages = [{"role": "user", "content": query}]

        # 依次执行工具调用，并收集结果
        for step in tool_plan:
            tool_name = step["name"]
            tool_args = step["arguments"]

            for key, val in tool_args.items():
                if isinstance(val, str) and val.startswith("{{") and val.endswith("}}"):
                    ref_key = val.strip("{} ")
                    resolved_val = tool_outputs.get(ref_key, val)
                    tool_args[key] = resolved_val

            # 注入统一的文件名或路径（用于分析和邮件）
            if tool_name == "analyze_sentiment" and "filename" not in tool_args:
                tool_args["filename"] = md_filename
            if tool_name == "send_email_with_attachment" and "attachment_path" not in tool_args:
                tool_args["attachment_path"] = md_path

            result = await self.session.call_tool(tool_name, tool_args)

            tool_outputs[tool_name] = result.content[0].text
            messages.append({
                "role": "tool",
                "tool_call_id": tool_name,
                "content": result.content[0].text
            })

        # 调用大模型生成回复信息，并输出保存结果
        final_response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        final_output = final_response.choices[0].message.content

        # 对辅助函数进行定义，目的是把文本清理成合法的文件名
        def clean_filename(text: str) -> str:
            text = text.strip()
            text = re.sub(r'[\\/:*?\"<>|]', '', text)
            return text[:50]

        # 使用清理函数处理用户查询，生成用于文件命名的前缀，并添加时间戳、设置输出目录
        # 最后构建出完整的文件路径用于保存记录
        safe_filename = clean_filename(query)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{safe_filename}_{timestamp}.txt"
        output_dir = "./llm_outputs"
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, filename)

        # 将对话内容写入 md 文档，其中包含用户的原始提问以及模型的最终回复结果
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"🗣 用户提问：{query}\n\n")
            f.write(f"🤖 模型回复：\n{final_output}\n")

        print(f"📄 对话记录已保存为：{file_path}")

        return final_output

    async def chat_loop(self):
        # 初始化提示信息
        print("\n🤖 MCP 客户端已启动！输入 'quit' 退出")

        # 进入主循环中等待用户输入
        while True:
            try:
                query = input("\n你: ").strip()
                if query.lower() == 'quit':
                    break

                # 处理用户的提问，并返回结果
                response = await self.process_query(query)
                print(f"\n🤖 AI: {response}")

            except Exception as e:
                print(f"\n⚠️ 发生错误: {str(e)}")

    async def plan_tool_usage(self, query: str, tools: List[dict]) -> List[dict]:
        # 构造系统提示词 system_prompt。
        # 将所有可用工具组织为文本列表插入提示中，并明确指出工具名，
        # 限定返回格式是 JSON，防止其输出错误格式的数据。
        print("\n📤 提交给大模型的工具定义:")
        print(json.dumps(tools, ensure_ascii=False, indent=2))
        tool_list_text = "\n".join([
            f"- {tool['function']['name']}: {tool['function']['description']}"
            for tool in tools
        ])
        system_prompt = {
            "role": "system",
            "content": (
                "你是一个智能任务规划助手，用户会给出一句自然语言请求。\n"
                "你只能从以下工具中选择（严格使用工具名称）：\n"
                f"{tool_list_text}\n"
                "如果多个工具需要串联，后续步骤中可以使用 {{上一步工具名}} 占位。\n"
                "返回格式：JSON 数组，每个对象包含 name 和 arguments 字段。\n"
                "不要返回自然语言，不要使用未列出的工具名。"
            )
        }

        # 构造对话上下文并调用模型。
        # 将系统提示和用户的自然语言一起作为消息输入，并选用当前的模型。
        planning_messages = [
            system_prompt,
            {"role": "user", "content": query}
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=planning_messages,
            tools=tools,
            tool_choice="none"
        )

        # 提取出模型返回的 JSON 内容
        content = response.choices[0].message.content.strip()
        match = re.search(r"```(?:json)?\\s*([\s\S]+?)\\s*```", content)
        if match:
            json_text = match.group(1)
        else:
            json_text = content

        # 在解析 JSON 之后返回调用计划
        try:
            plan = json.loads(json_text)
            return plan if isinstance(plan, list) else []
        except Exception as e:
            print(f"❌ 工具调用链规划失败: {e}\n原始返回: {content}")
            return []

    async def cleanup(self):
        await self.exit_stack.aclose()


async def main():
    server_script_path = "D:\\work\\my-mcp\\src\\my_mcp\\server.py"
    client = MCPClient()
    try:
        await client.connect_to_server(server_script_path)
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
