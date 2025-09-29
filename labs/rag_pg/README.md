# RAG with Supabase Postgres (pgvector)

Commands:
- Setup: `psql "$SUPABASE_URL" -c "\\i labs/rag_pg/setup.sql"`
- Ingest: `python labs/rag_pg/ingest_pg.py --glob 'content/*.md'`
- Ask: `python labs/rag_pg/search_pg.py --query 'What is RAG?'`

