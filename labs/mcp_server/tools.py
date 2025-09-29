from typing import Dict, Any
import json
from labs.agents.tools.milvus_tool import search_milvus
from labs.agents.tools.pg_tool import query_supabase
from labs.agents.tools.web_tool import web_fetch


def call_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "milvus.search":
        res = search_milvus(args.get("query", ""), top_k=int(args.get("top_k", 5)))
        return {"ok": True, "data": res}
    if name == "pg.query":
        res = query_supabase(args.get("query", ""), limit=int(args.get("limit", 10)))
        return {"ok": True, "data": res}
    if name == "web.fetch":
        res = web_fetch(args.get("url", ""))
        return {"ok": True, "data": res}
    return {"ok": False, "error": f"Unknown tool: {name}"}

