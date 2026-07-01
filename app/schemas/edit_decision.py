from pydantic import BaseModel
from typing import Optional


class HookSegment(BaseModel):
    source_start: float
    source_end: float
    target_start: float = 0
    target_end: float = 5
    text: str
    keep_original_video: bool = True
    keep_original_audio: bool = True


class KeepSegment(BaseModel):
    source_start: float
    source_end: float
    text: str
    target_start: float = 0
    target_end: float = 0


class RemoveSegment(BaseModel):
    source_start: float
    source_end: float
    text: str
    reason: str = "low_value"


class MuteWord(BaseModel):
    word: str
    start: float
    end: float
    action: str = "mute"


class EditDecision(BaseModel):
    project_id: str = ""
    clip_id: str = ""
    edited_script: str = ""
    target_duration: float = 0
    hook: Optional[HookSegment] = None
    keep_segments: list[KeepSegment] = []
    remove_segments: list[RemoveSegment] = []
    mute_words: list[MuteWord] = []
