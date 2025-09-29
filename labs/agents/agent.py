import os
import json
from typing import Any, Dict
from dotenv import load_dotenv
from openai import OpenAI
from .tools.milvus_tool import search_milvus
from .tools.pg_tool import query_supabase
from .tools.web_tool import web_fetch
from .policies import MAX_TOOL_CALLS


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_milvus",
            "description": "Semantic search over RAG documents in Milvus",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_supabase",
            "description": "Run safe parameterized SELECT queries on Supabase",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch text from an allowed URL",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
]


def dispatch_tool(name: str, args: Dict[str, Any]) -> str:
    if name == "search_milvus":
        res = search_milvus(args["query"], top_k=int(args.get("top_k", 5)))
        return json.dumps(res)
    if name == "query_supabase":
        res = query_supabase(args["query"], limit=int(args.get("limit", 10)))
        return json.dumps(res)
    if name == "web_fetch":
        return web_fetch(args["url"])[:5000]
    raise ValueError(f"Unknown tool: {name}")


def run_agent(question: str, max_calls: int = MAX_TOOL_CALLS) -> str:
    load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    messages = [
        {"role": "system", "content": "You can use tools. If tools are not needed, answer directly."},
        {"role": "user", "content": question},
    ]

    for _ in range(max_calls):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            # execute tools and append results
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments or "{}")
                try:
                    result = dispatch_tool(name, args)
                except Exception as e:
                    result = json.dumps({"error": str(e)})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": result,
                })
            continue
        # No tool call → final answer
        return msg.content or ""
    return "Tool call limit reached without final answer."

