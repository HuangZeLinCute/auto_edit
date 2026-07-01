from pydantic import BaseModel
from typing import Optional


class WordTimestamp(BaseModel):
    word: str
    start: float
    end: float
    score: Optional[float] = None


class TranscriptSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    words: list[WordTimestamp] = []


class Transcript(BaseModel):
    language: str = "zh"
    duration: float = 0
    segments: list[TranscriptSegment] = []
    filler_words: list[dict] = []
    silences: list[dict] = []
    risk_words: list[dict] = []


class FillerWord(BaseModel):
    word: str
    start: float
    end: float
    segment_id: int
    type: str = "filler"


class Silence(BaseModel):
    start: float
    end: float
    duration: float


class RiskWord(BaseModel):
    word: str
    start: float
    end: float
    segment_id: int
    level: str = "low"
