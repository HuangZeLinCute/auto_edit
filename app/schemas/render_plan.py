from pydantic import BaseModel
from typing import Optional


class OutputConfig(BaseModel):
    aspect_ratio: str = "9:16"
    resolution: str = "1080x1920"
    fps: int = 30
    duration: float = 0


class TimelineItem(BaseModel):
    target_start: float
    target_end: float
    type: str = "ai_image_with_audio"
    source_start: Optional[float] = None
    source_end: Optional[float] = None
    text: str = ""
    image_prompt: str = ""
    image_path: str = ""
    motion: str = "slow_zoom_in"
    transition: str = "none"


class BgmConfig(BaseModel):
    file: str = ""
    volume_db: float = -24
    fade_in: float = 1.0
    fade_out: float = 2.0
    category: str = "business"


class SfxItem(BaseModel):
    time: float
    file: str
    volume_db: float = -10
    reason: str = ""


class HighlightWord(BaseModel):
    word: str
    type: str = "conclusion"
    color: str = "#FFD84D"
    effect: str = "scale_120"


class SubtitleItem(BaseModel):
    start: float
    end: float
    text: str
    highlight_words: list[HighlightWord] = []


class RenderPlan(BaseModel):
    project_id: str = ""
    output: OutputConfig = OutputConfig()
    visual_style: str = "business_tech"
    timeline: list[TimelineItem] = []
    subtitles: list[SubtitleItem] = []
    sfx: list[SfxItem] = []
    bgm: Optional[BgmConfig] = None
