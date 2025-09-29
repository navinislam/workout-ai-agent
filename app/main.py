from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.models.schemas import UserProfile, WorkoutPlan, ChatRequest
from app.agents.programmer import generate_plan
from app.agents.orchestrator import program_and_verify
from app.agents.clarity import clarify_profile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse

from dotenv import load_dotenv

from app.rag.templates_rag import search_templates, ingest_workouts

load_dotenv()
app = FastAPI(title="Workout AI MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main chat interface."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/plan", response_model=WorkoutPlan)
def create_plan(profile: UserProfile):
    plan = generate_plan(profile)
    return plan

class ChatInput(BaseModel):
    message: str


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Chat endpoint:
    - Uses the Clarity Agent (LLM when available) to parse the user's message into a profile patch and questions.
    - Generates a plan from the merged profile.
    """
    patch, questions = await clarify_profile(request.message)
    base = request.profile or UserProfile()
    data = base.model_dump()
    data.update(patch or {})
    profile = UserProfile(**data)
    
    # Add follow-up questions based on missing or ambiguous info
    followups = []
    # Ask about equipment if still unknown/empty
    if not profile.equipment_available:
        followups.append("What equipment do you have access to (barbell, dumbbells, machines, bands)?")
    # Ask about training experience if missing
    if profile.training_age_years is None and (not profile.training_history):
        followups.append("How long have you been training consistently?")
    # Ask about availability if not provided explicitly (best-effort: check if provided in patch)
    if "days_per_week" not in patch:
        followups.append("How many days per week can you train?")
    if "minutes_per_day" not in patch:
        followups.append("About how many minutes per session (e.g., 45, 60)?")

    # Let the Clarity Agent handle ambiguous avoid term questions via its tool

    # Merge and deduplicate questions (cap 3 to keep it concise)
    all_qs = []
    for q in (questions or []) + followups:
        if q and q not in all_qs:
            all_qs.append(q)
    all_qs = all_qs[:3]

    plan = generate_plan(profile)
    print({"profile": profile.model_dump(),
        "questions": all_qs,
        "plan": plan.model_dump(),})
    return {
        "profile": profile.model_dump(),
        "questions": all_qs,
        "plan": plan.model_dump(),
    }

# --- RAG + Milvus endpoints ---
try:
    from app.rag.milvus_rag import ingest_exercises, search_exercises
except Exception:
    ingest_exercises = None  # type: ignore
    search_exercises = None  # type: ignore


@app.post("/api/ingest_exercises")
def api_ingest():
    """Ingest exercises into Milvus; returns count. Requires OPENAI_API_KEY and Milvus running."""
    if ingest_exercises is None:
        raise HTTPException(status_code=500, detail="RAG ingestion not available (missing deps)")
    try:
        n = ingest_exercises()
        return {"inserted": n, "collection": "exercises"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ingest_templates")
def api_ingest_templates():
    """Ingest exercises into Milvus; returns count. Requires OPENAI_API_KEY and Milvus running."""

    try:
        n = ingest_workouts()
        return {"inserted": n, "collection": "templates"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
def api_search(q: str, k: int = 5, pattern: str | None = None):
    """Search exercises via Milvus vector index. Optional filter a  by movement pattern."""
    if search_exercises is None:
        raise HTTPException(status_code=500, detail="RAG search not available (missing deps)")
    try:
        pat = pattern.lower() if isinstance(pattern, str) else None
        results = search_exercises(q.lower(), top_k=k, pattern=pat)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search_templates")
def api_search_templates(q: str, equipment:Optional[str]=None, days=3, k: int = 5):
    """Search exercises via Milvus vector index. Optional filter a  by movement pattern."""
    try:
        results = search_templates(q.lower(), top_k=k, days=days, equipment=equipment)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plan")
def api_plan(profile: UserProfile):
    """Program and verify a plan.

    Request body
    - `UserProfile` JSON.

    Response
    - Envelope dict: `{ profile, plan, verification, assumptions, citations }`.
    """
    try:
        return program_and_verify(profile)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
