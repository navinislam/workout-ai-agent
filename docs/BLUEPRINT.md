# Workout AI Capstone Blueprint

A practical, end‑to‑end plan to build an AI workout chatbot that generates safe, personalized training programs. Includes MVP path and optional multi‑agent orchestration.

## Architecture Overview

- Orchestrator: Small state machine (e.g., LangGraph or custom) controlling agent handoffs and tool calls.
- Agents:
  - Clarity Agent: Gathers missing profile fields; enforces schema.
  - Constraints/Avoidance Agent (RAG): Resolves "exercises to avoid" ambiguity; retrieves safe substitutions and flags related patterns.
  - Programmer Agent: Synthesizes weekly plan using heuristics + RAG for exercise selection.
  - Verifier Agent: Validates constraints (volume, balance, progression, safety).
  - Main Agent: Summarizes, formats, and returns a user‑friendly program; handles follow‑ups.
- Knowledge + RAG:
  - Vector DB for exercise library and constraints/substitution guidelines.
  - Hybrid retrieval (BM25 + vectors) and optional reranking.
- App:
  - Backend: Python + FastAPI for chat and plan endpoints.
  - Frontend: React/Next.js chat + plan viewer; downloadable PDF.
  - Storage: SQLite/Postgres for users + plans; Chroma/FAISS for vectors (local, easy).
- Safety:
  - Medical disclaimers; PAR‑Q style screening; gating for red flags.
  - Keep Constraints/Avoidance Agent grounded to your corpus only (no speculative advice).

## Core Data Models

- UserProfile: sex, age, height, weight, training history, training age, availability (days/min per day), equipment, goals (e.g., “4‑day strength, squat focus”), 1RM or estimated 1RM, avoid_exercises (names or categories) with optional reasons.
- AvoidanceProfile: avoid_exercises (explicit), avoid_patterns (squat/hinge/push/pull/carry), ambiguity_resolutions (e.g., “barbell back squat” vs “machine squat”), notes.
- WorkoutPlan:
  - days[]: name, focus, blocks[] (e.g., main lift, accessories), exercises[] with fields: name, pattern (squat/hinge/push/pull/carry), equipment, sets, reps, intensity (RPE/%1RM), rest, tempo, notes, progression.
  - metadata: weekly volume per muscle group, intensity distribution, deload logic, assumptions.
- KnowledgeDoc (Vector): id, title, type (“exercise”, “guideline”, “constraint”), tags, text, source, url.

## Agent Responsibilities

- Clarity Agent
  - Goal: fill UserProfile gaps; ask minimal questions first; collect exercises the user wants to avoid. If a term is ambiguous (e.g., “squats”), ask to clarify (all squats vs barbell back/front vs machine vs goblet).
  - Output: structured JSON and human confirmation prompt.
- Constraints/Avoidance Agent (RAG)
  - Tools: `resolve_avoid_term(term)`, `retrieve_substitutions(tags)`, `retrieve_exercises(tags)`.
  - Output: resolved avoid list (expanded variants), related patterns to limit, and safe substitutions with citations.
- Programmer Agent
  - Heuristics: split based on days; allocate main lifts; balance patterns; weekly hard sets per muscle; undulation (e.g., intensity vs volume days); specificity to goal.
  - RAG: pull candidate exercises matching pattern/equipment/difficulty and avoidance filters.
  - Output: draft WorkoutPlan.
- Verifier Agent
  - Checks: volume targets, symmetry (push/pull, squat/hinge), rest/intensity sanity, progression safety, avoid list respected, time fits availability.
  - Can suggest patch edits or trigger a fix‑up cycle.
- Main Agent
  - Finalize plan, explanations and “how to progress” notes; attach warm‑up guidance and reminders.

## RAG & Vector DB

- DB choice: start with Chroma or FAISS locally; swap to Pinecone/Weaviate later if needed.
- Embeddings:
  - Local/offline: `sentence-transformers/all-MiniLM-L6-v2` (fast, decent quality).
  - API: `text-embedding-3-large` (higher quality, if allowed).
- Indexes:
  - exercises: one doc per exercise card with rich metadata (pattern, equipment, primary muscles, spinal load, knee shear risk, difficulty).
  - constraints_guidelines: structured notes on common constraints/avoidances and substitutions (e.g., alternatives for barbell back squats; general contraindications and progressions).
- Retrieval:
  - Hybrid: BM25 over title/tags + vector similarity over description/notes.
  - Optional rerank with cross‑encoder or LLM reranker when quality matters.
- Chunking:
  - Exercises: per exercise.
  - Injuries/guidelines: 300–800 tokens per chunk, overlap 50–100.
- Grounding guardrails:
  - Return citations with each recommendation; LLM must only use retrieved snippets for constraint/avoidance‑related claims.

## Prompt Skeletons

- System (global)
  - “You are a certified strength coach assistant. Provide evidence‑based, safe, personalized programming. Do not give medical advice; recommend professional care when needed.”
- Clarity Agent
  - “Given the schema, list missing fields. Ask 1–3 concise questions to fill critical gaps. Ask what exercises the user wants to avoid; if a term is ambiguous (e.g., ‘squats’), ask to clarify (all squats vs barbell vs machine vs front/goblet). Output JSON matching UserProfile.”
- Constraints/Avoidance Agent
  - “Given profile and goals, resolve the avoid list (expand ambiguous terms into variants) and list: related patterns to limit, safe substitutions, and optional progressions (with sources). Only use retrieved text; include citations.”
- Programmer Agent
  - “Synthesize a 1‑week microcycle for N days, squat‑focused strength. Respect constraints, equipment, time. Prioritize specificity, balance patterns, target 12–16 hard sets for quads if squat focus, include accessory balance. Include progression notes for 4–8 weeks.”
- Verifier Agent
  - “Validate plan against checklist. If violations, propose exact JSON patches. Do not invent exercises outside corpus.”

## MVP First, Then Iterate

- Week 1: MVP without multi‑agent complexity
  - Intake form → single Planner that asks 2–3 clarifying Qs → produce plan using heuristic rules + small exercise JSON.
  - Avoidance support: simple rules (no RAG yet): e.g., if “squats” are avoided, clarify which variants; prefer front/goblet or hinge‑dominant alternatives.
- Week 2: Add RAG for constraints + exercises
  - Build small knowledge base (50–150 exercises; 10–20 constraint/substitution notes summarized into your own words).
  - Add hybrid retrieval + citations. Add Verifier checks.
- Week 3+: Multi‑agent orchestration + nicer UI
  - Move to LangGraph; add persistence, plan editing, PDF export; multi‑week progression.

## Programmer Agent Algorithm (High‑Level)

Inputs: UserProfile, avoidance_constraints, exercise_db.

Steps:
1) Choose split (e.g., 4‑day: Upper/Lower/Upper/Lower or Full/Rest/Lower/Upper).
2) Assign main lift focus days (squat intensities: heavy 3–5 reps day, volume 5–8 reps day).
3) Allocate weekly volume per pattern and target muscles.
4) Select exercises via filter: pattern + equipment + difficulty + allowed by avoid list; rerank by relevance to goal.
5) Generate set/rep/intensity with progression (linear load, double‑progression, or RPE caps).
6) Time budget check (estimate min per exercise); trim accessories to fit.
7) Output JSON + rationale.

## Verifier Rules (Checklist)

- Volume: quads 12–20 sets/wk if squat focus; hamstrings 8–16; glutes 8–16; chest/back/shoulders 8–12 unless goals dictate otherwise.
- Balance: push ≈ pull; squat and hinge both present over the week.
- Intensity: main lifts spread 70–90% 1RM; accessories 60–75% or RPE 6–8.
- Rest: main lifts 2–4 min; accessories 60–120s.
- Constraints: avoid list honored; safe substitutions applied; include optional mobility/prep block.
- Time: sum of estimated durations <= daily budget.
- Progression: clear overload and deload week every 4–6 weeks.

## Data To Prepare

- `data/exercises.json`: 100–200 curated exercises with metadata:
  - id, name, pattern, primary/secondary muscles, equipment, unilateral/bilateral, difficulty, spinal_load (low/med/high), knee_shear (low/med/high), requires_barbell (bool), tags.
- `data/constraints_guidelines.json`: short, structured notes:
  - term_or_constraint, clarify_options, recommended_alternatives, graded_exposure_examples (optional), references.
- `data/program_principles.md`: concise principles on volume ranges, intensity, rest, tempo, progression models.

## Tech Stack (Pragmatic)

- Backend: Python 3.11, FastAPI, LangGraph (or LangChain), Pydantic for schemas.
- Vector DB: Chroma (local) to start; embeddings with `all-MiniLM-L6-v2` or `text-embedding-3-large`.
- Retrieval: Chroma + BM25 (Whoosh/rapidfuzz), simple reranker optional.
- Frontend: Next.js + shadcn/ui or Chakra; minimal chat + plan view.
- PDF: `react-pdf` or server‑side WeasyPrint.
- Storage: SQLite via SQLAlchemy.

## API Endpoints (Draft)

- POST `/chat`: chat turn; stateful; returns follow‑up question or final plan.
- POST `/plan`: direct plan generation for given profile JSON.
- GET `/plan/{id}`: fetch plan by id.
- POST `/feedback`: accept adherence, RPE logs, pain flags for next iteration.

## File / Module Layout

```
app/
  main.py            # FastAPI app bootstrap
  graph.py           # LangGraph orchestration (intake → constraints → program → verify → finalize)
  agents/
    clarity.py
    constraints.py
    programmer.py
    verifier.py
    main.py
  tools/
    retrieval.py
    calculators.py   # 1RM, time estimation
    validators.py
  models/
    schemas.py       # Pydantic models for UserProfile, WorkoutPlan, Exercise, ConstraintGuideline

data/
  exercises.json
  constraints_guidelines.json
  program_principles.md

frontend/
  ...                # Next.js app (optional for MVP)

tests/
  test_validators.py
  test_planner.py
notebooks/
  retrieval_sanity.ipynb
```

## Evaluation & QA

- Unit tests
  - Validators: volume, balance, time, avoid constraints.
  - Planner: given preset profile, ensure outputs pass validation.
- Retrieval tests
  - Query “barbell back squat alternatives” returns expected top‑k docs.
- Hallucination guard
  - Constraints/Avoidance Agent answers must include citations from your corpus; reject outputs otherwise.
- Human eval rubric
  - Safety, specificity to goal, time fit, clarity, progression logic.

## Safety & Compliance

- PAR‑Q style screening: if red flags (e.g., chest pain, medical conditions), advise medical clearance.
- Disclaimer on every plan: “Educational purposes; not medical advice.”
- Privacy: store only needed fields, allow deletion; prefer local‑first.

## Nice‑to‑Have Extensions

- Warm‑ups and mobility prep based on day’s main lifts.
- Equipment‑adaptive logic (home vs gym).
- Logging + adaptation: take RPE/adherence feedback and auto‑adjust upcoming weeks.
- Coach Agent for weekly check‑ins and plan tweaks.
- Export to Apple Health/Garmin or Calendar reminders.

## Build Order (Where To Start)

1. Define schemas: UserProfile, WorkoutPlan, Exercise, ConstraintGuideline.
2. Curate a small dataset: ~100 exercises + ~10 constraints/substitution notes in JSON.
3. Build MVP planner (single agent): simple clarifier → heuristic planner → JSON plan.
4. Add validators; write tests; ensure deterministic plan passes.
5. Add vector DB + retrieval tools; wire Constraints lookups; add citations in outputs.
6. Move to LangGraph multi‑agent flow; keep each agent small and testable.
7. Build minimal UI and PDF export.
8. Add telemetry (latency, token/cost), prompts as templates, and configuration.

---

If you want, we can scaffold the FastAPI + LangGraph skeleton next, add Pydantic schemas, and stub the planner with a few sample exercises and constraints notes.
