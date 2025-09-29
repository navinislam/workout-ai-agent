# Workout AI Capstone: RAG + Agents Roadmap

A practical plan to evolve this repo into a clean, testable AI engineering project using Retrieval‑Augmented Generation (RAG), small agents, and optional MCP tools. The chat UI is de‑scoped; focus on backend rigor, data, tests, and APIs/CLI.

## Goals
- Build an offline‑first RAG core over exercises and constraints.
- Add small, testable agents: clarity → constraints → program → verify → finalize.
- Expose capabilities via clean APIs and/or CLI; keep UI optional.
- Add MCP later as a thin layer to expose tools to MCP‑aware clients.

## Current Repo Snapshot (Key Notes)
- Backend: FastAPI endpoints in `app/main.py` for `/plan` and `/api/chat` (to be removed/repurposed).
- Planner: Heuristic in `app/agents/programmer.py` with `ExerciseDB` selection.
- Constraints: `app/agents/constraints.py` with a small default ambiguity map.
- Clarity: `app/agents/clarity.py` (OpenAI optional, heuristics fallback).
- Data: Many per‑exercise JSON files under `exercises/`; example constraints in `data/constraints_guidelines.json`.
- Tests: `tests/test_planner.py` checks avoid‑list behavior.
- Gaps to fix early:
  - Missing `exercises/exercises.json` (current `ExerciseDB` expects it).
  - UI calls `/api/health` and `/api/add-document` which do not exist; we’ll scrap the chat UI.

## Strategy
- Start with data consolidation and a minimal RAG core (local vectors + cosine, no external services required).
- Replace keyword exercise picking with retrieval constrained by pattern/equipment/avoid list.
- Keep agents small and deterministic where possible; add verifiers to enforce safety/time constraints.
- Ensure everything is testable with unit + E2E tests.

## Phased Plan

### Phase 1 — Data + RAG Core
- Aggregate `exercises/*.json` into `exercises/exercises.json`.
- Normalize fields: `name`, `equipment`, `primaryMuscles`, `secondaryMuscles`, `category`, `instructions`.
- Expand `data/constraints_guidelines.json` for ambiguous terms and substitutions.
- Implement embeddings + index:
  - Local model: `sentence-transformers/all-MiniLM-L6-v2` (preferred) or a stub embedding for CI.
  - Index: FAISS or a simple NumPy array; use cosine similarity (see `labs/rag_core/retrieve.py`).
- Create `app/rag/`:
  - `embed.py` (embedding interface with local/model switch)
  - `index.py` (build/load/save index)
  - `search.py` (hybrid retrieval: text+metadata filters; return items + scores + citations)

### Phase 2 — Agents (MVP)
- Clarity Agent: parse `UserProfile`; ask 1–2 essential questions (heuristics OK initially).
- Constraints Agent: expand avoid terms (existing) + call RAG to propose safe alternatives with citations.
- Programmer Agent: replace direct `ExerciseDB.best_candidate` with RAG search filtered by pattern/equipment/not‑in‑avoid; fill templates (lower/upper, 3–4 days).
- Verifier Agent: checks:
  - Time fit: estimate session time from sets×reps×rest vs `minutes_per_day`.
  - Balance: push/pull and squat/hinge present weekly.
  - Avoid list respected.
  - Progression sanity: reasonable reps/intensity/rpe.

### Phase 3 — Orchestration
- Simple Python function/state machine calling agents in sequence.
- Inputs: `UserProfile`; Outputs: `WorkoutPlan + citations + assumptions`.
- Persist artifacts for debugging (profile, plan, citations, validation report).

### Phase 4 — API and/or CLI
- Remove chat. Provide minimal, purposeful endpoints:
  - `POST /api/ingest`: (re)build the index from `exercises/` and constraints.
  - `GET /api/search?q=...&k=5`: debug retrieval; returns results + scores + metadata.
  - `POST /api/plan`: input `UserProfile` JSON; returns `WorkoutPlan + citations + verification`.
- Optional CLI:
  - `python -m app.cli ingest`
  - `python -m app.cli search --q "front squat" --k 5`
  - `python -m app.cli plan --profile profile.json`

### Phase 5 — MCP (Optional)
- Implement an MCP server exposing:
  - `search_exercises(query, top_k)` → text + metadata + source.
  - `get_constraints(term)` → variants + recommended substitutions + citations.
  - `program_plan(profile_json)` → calls orchestrator.
- Adapt from `labs/mcp_server/` as a starting point.

## RAG Data Design
- Exercises index
  - Text: `name + instructions + category + equipment + primary/secondary muscles`.
  - Metadata: `pattern` (squat/hinge/push/pull/carry), `equipment`, `difficulty` (optional), IDs/paths to images.
- Constraints index
  - Text: guideline notes and substitution rationale.
  - Metadata: `term_or_constraint`, `alternatives`, `graded_exposure`.
- Queries
  - Planner: pattern + equipment + difficulty filters; hybrid search on text + metadata; exclude avoid expansions.
  - Constraints: ambiguous term → guideline chunks to cite.

## Agents Overview
- Clarity Agent: fill critical `UserProfile` gaps; minimal questions first.
- Constraints Agent: deterministic expansion of ambiguous avoids; propose alternatives via RAG with citations.
- Programmer Agent: builds plan days/blocks and fills with retrieved exercises; ensures constraints.
- Verifier Agent: validates time fit, balance, avoid compliance, and basic progression sanity.

## Orchestration
- Deterministic state machine (no heavy framework required initially):
  1) clarity → 2) constraints → 3) program → 4) verify → 5) finalize.
- Return a structured envelope: `{ profile, plan, citations, verification, assumptions }`.

## Testing
- Unit tests
  - RAG search returns expected top‑k for “front squat”, “barbell back squat alternatives”.
  - Constraints expansion: “squats” expands; alternatives include leg press/split squat.
  - Planner: avoid list enforced; plan fits `minutes_per_day`; push/pull and squat/hinge present weekly.
- E2E tests
  - Given a fixed profile, the plan passes verification and is deterministic (set seed).
- CI tips
  - Provide a tiny fixture dataset for fast tests.
  - Make embeddings injectable; default to a cheap/dummy embedder in tests.

## Repo Cleanup / Migrations
- Remove/park chat UI: delete `templates/index.html`, `static/js/chat.js`, and related routes.
- Align endpoints under `/api/*`; keep `GET /health` lightweight.
- Fix dataset: generate `exercises/exercises.json` or load per‑file JSON automatically.
- Update docs as you change interfaces.

## Suggested Next Actions
- Data consolidation
  - Script: read all `exercises/*.json`, write `exercises/exercises.json` (normalized set of fields).
- RAG skeleton
  - Add `app/rag/{embed.py,index.py,search.py}` with cosine search and a pluggable embedder.
- Planner upgrade
  - Replace `ExerciseDB.best_candidate` with RAG calls filtered by pattern/equipment and avoidance.
- API
  - Add `POST /api/ingest` and `GET /api/search` for debugging retrieval.
- Tests
  - Add tests for ingestion, retrieval, constraints expansion, and planner avoidance/time fit.

## Optional: Tooling & MCP
- Add MCP methods mirroring your API:
  - `search_exercises`, `get_constraints`, `program_plan`.
- Keep strict input/output schemas for tool calls.

---

If you want, we can start with Phase 1 now by:
- Writing a small aggregator to produce `exercises/exercises.json`.
- Creating `app/rag/` with an in‑memory cosine index and search.
- Adding `/api/ingest` and `/api/search` endpoints for fast iteration.
