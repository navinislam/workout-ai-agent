# Env Sanity

Scripts to validate your setup for OpenAI, Milvus, and Supabase.

1) Copy `.env.example` to `.env` and fill values.
2) Run OpenAI check:

```
python labs/env/check_openai.py
```

3) Milvus: ensure service is running, then create collection and index:

```
python labs/env/milvus_setup.py
```

4) Supabase: enable pgvector and create a minimal table:

```
psql "$SUPABASE_URL" -c "\i labs/env/supabase_setup.sql"
```

