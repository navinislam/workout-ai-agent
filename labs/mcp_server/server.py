from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any
from .tools import call_tool


app = FastAPI(title="MCP-Style Tool Server")


class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any] = {}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": "milvus.search", "schema": {"query": "str", "top_k": "int"}},
            {"name": "pg.query", "schema": {"query": "str", "limit": "int"}},
            {"name": "web.fetch", "schema": {"url": "str"}},
        ]
    }


@app.post("/tools/call")
def tools_call(req: ToolCall):
    return call_tool(req.name, req.args)

