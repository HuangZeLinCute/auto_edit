from pydantic import BaseModel


class OutputVideo(BaseModel):
    path: str = ""
    duration: float = 0
    resolution: str = "1080x1920"
    file_size: float = 0


class OutputPackage(BaseModel):
    project_id: str = ""
    clip_id: str = ""
    video: OutputVideo = OutputVideo()
    subtitle_path: str = ""
    titles: dict[str, list[str]] = {}
    cover_texts: list[str] = []
    topics: list[str] = []
    descriptions: list[str] = []
    edit_decision_path: str = ""
    render_plan_path: str = ""
