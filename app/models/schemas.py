from enum import Enum
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


class TrainingHistory(str, Enum):
    advanced = "advanced"
    intermediate = "intermediate"
    beginner = "beginner"


class Exercise(BaseModel):
    id: str
    name: str
    force: Optional[str] = None
    level: Optional[str] = None
    mechanic: Optional[str] = None
    equipment: Optional[str] = None
    primaryMuscles: List[str] = []
    secondaryMuscles: List[str] = []
    instructions: Optional[List[str]] = None
    category: Optional[str] = None
    images: Optional[List[str]] = None


class UserProfile(BaseModel):
    sex: Optional[Literal["male", "female", "other"]] = None
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    training_history: Optional[TrainingHistory] = None
    training_age_years: Optional[float] = None
    days_per_week: int = 4
    minutes_per_day: int = 60
    equipment_available: List[str] = Field(default_factory=list)
    goal: str = "strength - squat focus"
    estimated_1rm: Optional[dict] = None  # e.g., {"squat": 140}
    avoid_exercises: List[str] = Field(default_factory=list)


class WorkoutExercise(BaseModel):
    name: str
    sets: int
    reps: str  # e.g., "3-5", or exact int as str
    intensity: Optional[str] = None  # e.g., "%1RM 80%" or "RPE 7"
    rest_seconds: Optional[int] = None
    notes: Optional[str] = None


class WorkoutBlock(BaseModel):
    name: str  # e.g., "Main Lift", "Accessories"
    exercises: List[WorkoutExercise]


class WorkoutDay(BaseModel):
    name: str
    focus: Optional[str] = None
    blocks: List[WorkoutBlock]


class WorkoutPlan(BaseModel):
    days: List[WorkoutDay]
    metadata: dict = Field(default_factory=dict)


class ConstraintGuideline(BaseModel):
    term_or_constraint: str
    clarify_options: List[str] = Field(default_factory=list)
    recommended_alternatives: List[str] = Field(default_factory=list)
    graded_exposure_examples: Optional[List[str]] = None
    references: Optional[List[str]] = None

class ChatResponse(BaseModel):
    response: str = Field(..., description="AI response")
    sources: List[Dict[str, Any]] = Field(default=[], description="RAG sources")


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Content of the message")

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    profile: Optional[UserProfile] = Field(default=None, description="Current working profile to merge with parsed patch")
    # conversation_history: List[ChatMessage] = Field(default_factory=list, description="Conversation history")