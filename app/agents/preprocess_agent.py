import os
import logging
from pathlib import Path

from app.services.ffmpeg_service import FFmpegService
from app.config import UPLOADS_DIR, TEMP_DIR

logger = logging.getLogger("AutoEdit")


class PreprocessAgent:
    def __init__(self):
        self.ffmpeg = FFmpegService()

    def run(self, project_id: str) -> dict:
        logger.info("[PreprocessAgent] project_id=%s", project_id)

        upload_dir = UPLOADS_DIR / project_id
        video_files = list(upload_dir.glob("input.*"))
        if not video_files:
            raise FileNotFoundError(f"No input video in {upload_dir}")

        source_video = str(video_files[0])
        logger.info("[PreprocessAgent] source=%s", source_video)

        video_info = self.ffmpeg.get_info(source_video)
        duration = video_info.get("duration", 0)
        logger.info("[PreprocessAgent] duration=%.1f", duration)

        temp_dir = TEMP_DIR / project_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        audio_path = str(temp_dir / "audio.wav")
        self.ffmpeg.extract_audio(source_video, audio_path)
        logger.info("[PreprocessAgent] audio=%s", audio_path)

        return {
            "project_id": project_id,
            "source_video": source_video,
            "audio_path": audio_path,
            "duration": duration,
            "video_info": video_info,
        }
