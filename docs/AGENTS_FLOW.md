# Agents Flow (Current)

This document summarizes how the system flows after migrating agents to the OpenAI Agents SDK pattern.

## High-Level Sequence

- User submits a request via either:
  - `POST /api/chat` with a freeform message, or
  - `POST /api/plan` with a `UserProfile`.
- Agents run in this order depending on the endpoint:
  - `/api/chat`: Clarity → Merge → Programmer
  - `/api/plan`: Programmer → Verifier (via orchestrator)

## Components

- Clarity Agent (`app/agents/clarity.py`)
  - SDK: `Agent`, `Runner.run`, `@function_tool`.
  - Tool: `get_constraint_options(term)` reads `data/constraints_guidelines.json` for clarify options and suggestions.
  - Input: user's freeform message.
  - Output: strict JSON with `profile_patch` and up to 3 `questions`.
  - Notes: No heuristic parsing; fully LLM/tool-driven. Async function `clarify_profile`.

- Programmer Agent (`app/agents/programmer.py`)
  - SDK: `Agent`, `Runner.run_sync`, `@function_tool`.
  - Tool: `search_exercise(query, pattern?, top_k?)` proxies to RAG search (`app/rag/milvus_rag.search_exercises`).
  - Input: structured constraints `{ days_per_week, minutes_per_day, goal, equipment_available, avoid_exercises_expanded }`.
  - Output: strict JSON matching the `WorkoutPlan` shape, then coerced to Pydantic models.
  - Notes: Heuristic templates and DB keyword selection removed.

- Verifier Agent (`app/agents/verifier.py`)
  - SDK: `Agent`, `Runner.run_sync`.
  - Input: `{ profile, plan, avoid_expanded }` as JSON.
  - Output: strict JSON report with keys: `ok`, `time_fit`, `balance`, `avoidance`, `progression`.
  - Notes: Heuristic calculations removed; the agent reasons to produce the report shape.

- Orchestrator (`app/agents/orchestrator.py`)
  - Calls Programmer → Verifier and returns an envelope `{ profile, plan, verification, assumptions, citations }`.

- Substitution Agent Example (`app/agents/subber.py`)
  - Demonstrates SDK usage with a simple tool (`search_exercise_sub`). Not wired to an endpoint.

## Endpoints

- `POST /api/chat`
  - Parses message via `await clarify_profile(message)`.
  - Merges `profile_patch` into a base `UserProfile` (endpoint still adds general follow-ups for missing fields: equipment, experience, days, minutes).
  - Calls `generate_plan(profile)` (Programmer Agent) and returns `{ profile, questions, plan }`.

- `POST /api/plan`
  - Calls `program_and_verify(profile)` (Programmer → Verifier) and returns an envelope: `{ profile, plan, verification, assumptions, citations }`.

- `POST /plan` (legacy/simple)
  - Returns a `WorkoutPlan` by calling `generate_plan(profile)` directly.

- RAG Support Endpoints
  - `POST /api/ingest`: Ingests exercises into Milvus using OpenAI embeddings.
  - `GET /api/search`: Queries Milvus for exercises; used by the Programmer tool.

## Data and Dependencies

- Constraints data: `data/constraints_guidelines.json` supports clarity and constraints tools.
- RAG index: `app/rag/milvus_rag.py` (Milvus + OpenAI embeddings) powers exercise search.
- Env vars: `OPENAI_API_KEY`, Milvus connection (`MILVUS_URI` or `MILVUS_HOST`/`MILVUS_PORT`), and `RAG_EMBED_DIM` must match collection.
- Requirements: see `requirements.txt` (includes `agents`, `openai`, `pymilvus`, etc.).

## Error Handling & Fallbacks

- Clarity: If parsing of agent output fails, returns empty patch and no questions.
- Programmer: If strict JSON parsing fails, returns an empty `WorkoutPlan` with a note.
- Verifier: If parsing fails, returns a report with `ok: false` and empty sections.

## Notes on Tests

- Tests that relied on heuristic, deterministic selection may need updates to mock agent outputs or validate structure rather than specific choices.

