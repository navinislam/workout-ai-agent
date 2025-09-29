# Minimal MCP-Style Server

This is a lightweight, MCP-inspired JSON HTTP server exposing tools:
- `milvus.search`
- `pg.query`
- `web.fetch`

Note: This is not a full MCP stdio implementation; it mirrors the concepts to practice tool exposure and consumption.

Run server:
```
uvicorn labs.mcp_server.server:app --reload
```

Call tools via the demo client:
```
python labs/mcp_server/client_demo.py --tool milvus.search --args '{"query":"What is RAG?","top_k":3}'
```

