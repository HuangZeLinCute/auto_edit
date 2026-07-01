from pydantic import BaseModel
from typing import Optional


class ClipScores(BaseModel):
    hook_score: float = 0
    information_density: float = 0
    completeness_score: float = 0
    shareability_score: float = 0
    emotion_score: float = 0
    visualizable_score: float = 0
    risk_score: float = 0


class HookInfo(BaseModel):
    start: float
    end: float
    text: str
    reason: str = ""


class ClipCandidate(BaseModel):
    clip_id: str
    topic: str
    source_start: float
    source_end: float
    duration: float
    score: float
    reason: str = ""
    hook: Optional[HookInfo] = None
    scores: Optional[ClipScores] = None


class ClipPlan(BaseModel):
    project_id: str = ""
    candidates: list[ClipCandidate] = []
