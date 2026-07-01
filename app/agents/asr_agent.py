import json
import os
import logging
from typing import Optional

from app.services.whisper_service import WhisperService
from app.services.storage_service import StorageService
from app.utils.text_utils import (
    detect_filler_words,
    detect_silences,
    detect_risk_words,
)
from app.config import TEMP_DIR

logger = logging.getLogger("AutoEdit")


class ASRAgent:
    def __init__(self):
        self.whisper = WhisperService()
        self.storage = StorageService()

    def run(
        self,
        project_id: str,
        audio_path: str,
        language: Optional[str] = None,
        segment_duration: float = 600,
    ) -> dict:
        logger.info("[ASRAgent] project_id=%s audio=%s", project_id, audio_path)

        audio_size = os.path.getsize(audio_path) / 1024 / 1024
        logger.info("[ASRAgent] audio_size=%.1fMB", audio_size)

        from app.services.ffmpeg_service import FFmpegService

        ffmpeg = FFmpegService()
        audio_duration = ffmpeg.get_duration(audio_path)
        logger.info("[ASRAgent] audio_duration=%.1fs", audio_duration)

        if audio_duration > segment_duration:
            logger.info(
                "[ASRAgent] Long audio (%.1fs), segmenting by %.0fs",
                audio_duration,
                segment_duration,
            )
            transcript = self._transcribe_long(
                project_id, audio_path, audio_duration, segment_duration, language
            )
        else:
            transcript = self.whisper.transcribe(audio_path, language=language)

        transcript["filler_words"] = detect_filler_words(transcript["segments"])
        transcript["silences"] = detect_silences(transcript["segments"])
        transcript["risk_words"] = detect_risk_words(transcript["segments"])

        logger.info(
            "[ASRAgent] done segments=%d fillers=%d silences=%d risk=%d",
            len(transcript["segments"]),
            len(transcript["filler_words"]),
            len(transcript["silences"]),
            len(transcript["risk_words"]),
        )

        self.storage.save_json(project_id, "transcript.json", transcript)

        return transcript

    def _transcribe_long(
        self,
        project_id: str,
        audio_path: str,
        total_duration: float,
        segment_duration: float,
        language: Optional[str],
    ) -> dict:
        from app.services.ffmpeg_service import FFmpegService

        ffmpeg = FFmpegService()
        temp_dir = TEMP_DIR / project_id / "segments"
        temp_dir.mkdir(parents=True, exist_ok=True)

        segments_audio = []
        start = 0.0
        idx = 0
        while start < total_duration:
            end = min(start + segment_duration, total_duration)
            seg_path = str(temp_dir / f"segment_{idx:04d}.wav")
            ffmpeg.cut_audio(audio_path, seg_path, start, end)
            segments_audio.append(seg_path)
            start = end
            idx += 1

        all_segments = []
        offset = 0.0
        detected_lang = None

        for i, seg_path in enumerate(segments_audio):
            logger.info(
                "[ASRAgent] transcribing segment %d/%d offset=%.1f",
                i + 1,
                len(segments_audio),
                offset,
            )
            result = self.whisper.transcribe(seg_path, language=language)
            if detected_lang is None:
                detected_lang = result.get("language", "zh")

            for seg in result["segments"]:
                seg["id"] = len(all_segments)
                seg["start"] = round(seg["start"] + offset, 3)
                seg["end"] = round(seg["end"] + offset, 3)
                for w in seg.get("words", []):
                    w["start"] = round(w["start"] + offset, 3)
                    w["end"] = round(w["end"] + offset, 3)
                all_segments.append(seg)

            offset += result.get("duration", 0)

        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

        return {
            "language": detected_lang or "zh",
            "duration": round(total_duration, 3),
            "segments": all_segments,
            "filler_words": [],
            "silences": [],
            "risk_words": [],
        }
