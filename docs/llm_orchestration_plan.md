# LLM‑First Orchestration Plan

## Implementation Status: ✅ COMPLETE

All phases implemented with architectural improvements over original plan.

## Goals
- Make the entire programming → substitution → verification loop LLM‑centric. ✅
- Keep outputs strictly machine‑applyable (stable JSON schemas). ✅
- Allow iterative refinement until the plan passes verification or a max iteration cap. ✅

## Current State (Summary)
- Orchestrator selects an SBS template via RAG, maps it to a `WorkoutPlan`, falls back to the Programmer, runs Subber directly to replace exercises, runs Verifier once, returns.
- Programmer LLM agent generates a plan from `UserProfile` using a `search_exercise` tool. A `search_template` tool exists but is not registered.
- Subber LLM agent finds and applies substitutions itself (mutates the plan).
- Verifier LLM agent validates time fit, balance, avoidance, progression; no concrete edit suggestions.
- API `/api/plan` runs a single pass, no iterative refinement.

## Target Flow
1. Orchestrator → Programmer: provide `UserProfile`; get initial `WorkoutPlan`.
2. Orchestrator → Subber: provide `WorkoutPlan + UserProfile`; get substitution suggestions (do not mutate plan).
3. Orchestrator → Programmer (revise): apply substitution suggestions and harmonize volume; get revised plan.
4. Orchestrator → Verifier: evaluate plan; get report with actionable edit suggestions.
5. Orchestrator: if issues remain, loop Programmer (revise) with verifier edits up to `max_iters`; else return plan + reports.

## Components & Responsibilities
- Programmer Agent: generate initial plan; revise plan given substitutions and/or verifier edits; use tools for search.
- Subber Agent: propose substitutions per avoid terms with rationale; return a suggestions list (non‑mutating).
- Verifier Agent: evaluate plan and produce both a verdict and a structured set of edit suggestions.
- Orchestrator: coordinate the sequence and loop until convergence or cap.

## Data Schemas (Strict JSON)

### Substitution Suggestion
```
{
  "day_idx": int,
  "block_idx": int,
  "ex_idx": int,
  "original": string,
  "best": string,
  "candidates": [string],
  "rationale": string | null
}
```

### Edit (Verifier → Programmer)
- Common fields: `type: string`, `reason: string`, `loc: { day_idx: int, block_idx: int, ex_idx?: int }`, `payload: { ... }`
- Supported types and payloads:
  - `replace_exercise`: `{ "new_name": string }`
  - `tune_sets`: `{ "sets": int }`
  - `tune_reps`: `{ "reps": string }`
  - `add_rest`: `{ "rest_seconds": int }`
  - `remove_exercise`: `{}` (uses `loc`)
  - `add_exercise`: `{ "exercise": {"name": string, "sets": int, "reps": string, "intensity"?: string, "rest_seconds"?: int, "notes"?: string} }`
  - `reorder_days`: `{ "order": [int] }` (no `loc` needed; apply to plan)
  - `add_note`: `{ "note": string }` (if no `loc`, append to plan metadata notes)

### Verifier Report (extended)
```
{
  "ok": bool,
  "time_fit": { "ok": bool, "per_day_minutes": [number], "limit": int },
  "balance": { "ok": bool, "weekly_presence_days": {"squat_like": int, "hinge_like": int, "push_like": int, "pull_like": int} },
  "avoidance": { "ok": bool, "violations": [string], "expanded_terms": [string] },
  "progression": { "ok": bool, "issues": [string], "notes": string },
  "suggested_edits": [Edit]
}
```

## Orchestrator Loop (pseudocode)
```
plan = Programmer.generate_plan(profile)
subs = Subber.suggest_substitutions(plan, profile)
plan = Programmer.revise_plan(plan, profile, substitutions=subs)
for i in range(MAX_REVISIONS):
  report = Verifier.verify_plan(profile, plan)
  if report.ok or not report.suggested_edits:
    break
  plan = Programmer.revise_plan(plan, profile, verifier_edits=report.suggested_edits)
return { profile, plan, verification: report, iterations: i+1 }
```

## Phased Implementation

### Phase 0 — Prep & Wiring
- Register `search_template` on Programmer agent tools.
- Add config flags: `USE_TEMPLATE_BOOTSTRAP=false`, `MAX_REVISIONS=2` (env or settings).
- Keep current RAG template path behind flag for optional bootstrap.

### Phase 1 — Subber Suggest Mode (Non‑mutating)
- Add `suggest_substitutions(plan, profile) -> List[SubSuggestion]` to `app/agents/subber.py`.
- Use existing `search_exercise_sub` tool and return best + candidates; include indices and rationale.
- Keep legacy `substitute_plan_exercises` for compatibility but stop using it in the new flow.

### Phase 2 — Programmer Revise (with substitutions)
- Add `revise_plan(plan, profile, substitutions=None, verifier_edits=None) -> WorkoutPlan` in `app/agents/programmer.py`.
- Update agent instructions to accept structured inputs and return strict JSON plan in current schema.
- Ensure both tools are registered: `search_exercise`, `search_template`.

### Phase 3 — Verifier Edit Suggestions
- Extend `app/agents/verifier.py` to emit `suggested_edits: [Edit]` in addition to the current report.
- Tighten instruction to return edits only in the specified set; include exact `loc` and `payload`.

### Phase 4 — Orchestrator Loop
- Rework `program_and_verify` to:
  - Call Programmer → Subber (suggest) → Programmer (revise with subs).
  - Call Verifier; if not ok, call Programmer (revise with edits) and iterate up to `MAX_REVISIONS`.
  - Return final envelope with `iterations_log` (prompts + summaries) for traceability.
- Keep current template bootstrap behind `USE_TEMPLATE_BOOTSTRAP` for optional seeding.

### Phase 5 — Deterministic Edit Applier (Optional but Recommended)
- Implement a tiny pure‑Python applier that takes `WorkoutPlan + [Edit]` and returns a new plan deterministically.
- Allows Orchestrator to apply trivial edits locally and reserve LLM reviser for semantic re‑balancing.

### Phase 6 — Telemetry, UX, and Docs
- Capture per‑iteration prompts/outputs for capstone reporting.
- Expand `/api/plan` response with `iterations`, `iterations_log` (summaries), and `citations` (template source if used).
- Add README/Docs on the LLM loop and configuration.

## API Considerations
- Endpoint: `/api/plan` remains; response envelope includes `{ profile, plan, verification, assumptions, citations, iterations, iterations_log? }`.
- Backward compatibility: keep keys stable; add new keys rather than rename.

## Risks & Mitigations
- Strict JSON adherence: enforce with clear system prompts; consider JSON mode where available; retry once on parse error.
- Hallucinated schema fields: validate and coerce; drop unknown keys.
- Rate limits/cost: cap `MAX_REVISIONS`; batch calls where possible; cache embeddings.
- Milvus availability: guard RAG calls; provide informative HTTP 500 with actionables.

## Configuration
- `MAX_REVISIONS` (default 2–3)
- `USE_TEMPLATE_BOOTSTRAP` (default false)
- `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL`, `RAG_EMBED_MODEL`
- Milvus: `MILVUS_URI` or `MILVUS_HOST/PORT`, `MILVUS_DB_NAME`, `MILVUS_TOKEN`

## Acceptance Criteria
- Programmer generates an initial plan from a `UserProfile` without template fallback when `USE_TEMPLATE_BOOTSTRAP=false`.
- Subber returns a non‑empty list of structured substitution suggestions when avoid terms apply; Programmer revision applies them.
- Verifier returns `suggested_edits` for plans that violate constraints; Orchestrator loops once to address them.
- End‑to‑end run returns a verified plan (`report.ok=true`) or stops after `MAX_REVISIONS` with a clear report and applied edits.

