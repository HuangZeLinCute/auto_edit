import json
import os
import logging

from app.services.llm_service import LLMService
from app.services.subtitle_service import detect_keywords, generate_ass
from app.services.storage_service import StorageService
from app.utils.text_utils import split_into_lines

logger = logging.getLogger("AutoEdit")


class SubtitleAgent:
    def __init__(self):
        self.llm = LLMService()
        self.storage = StorageService()

    def run(self, project_id: str, edit_decision: dict, transcript: dict) -> dict:
        logger.info("[SubtitleAgent] project_id=%s", project_id)

        keep_segments = edit_decision.get("keep_segments", [])
        hook = edit_decision.get("hook", {})
        hook_text = hook.get("text", "") if hook else ""

        subtitles = self._build_subtitles(keep_segments, hook_text, transcript)

        for sub in subtitles:
            keywords = detect_keywords(sub["text"])
            sub["highlight_words"] = keywords

        project_dir = self._project_dir(project_id)
        ass_path = os.path.join(project_dir, "subtitles.ass")
        generate_ass(subtitles, ass_path)

        result = {
            "project_id": project_id,
            "subtitle_count": len(subtitles),
            "subtitle_path": ass_path,
            "subtitles": subtitles,
        }

        self.storage.save_json(project_id, "subtitle_plan.json", result)
        logger.info(
            "[SubtitleAgent] done: %d 条字幕, %d 个重点词",
            len(subtitles),
            sum(len(s.get("highlight_words", [])) for s in subtitles),
        )
        return result

    def _build_subtitles(
        self,
        keep_segments: list[dict],
        hook_text: str,
        transcript: dict,
    ) -> list[dict]:
        subtitles = []

        if hook_text:
            hook_seg = keep_segments[0] if keep_segments else None
            if hook_seg:
                subtitles.append(
                    {
                        "start": hook_seg.get("target_start", 0),
                        "end": hook_seg.get("target_end", 3),
                        "text": hook_text,
                        "highlight_words": [],
                    }
                )

        all_words = []
        for seg in transcript.get("segments", []):
            all_words.extend(seg.get("words", []))

        start_idx = 0 if not subtitles else 1

        for seg in keep_segments[start_idx:]:
            text = seg.get("text", "")
            t_start = seg.get("target_start", 0)
            t_end = seg.get("target_end", 0)
            duration = t_end - t_start

            if not text or duration <= 0:
                continue

            if len(text) <= 12:
                subtitles.append(
                    {
                        "start": t_start,
                        "end": t_end,
                        "text": text,
                        "highlight_words": [],
                    }
                )
            else:
                lines = split_into_lines(text, max_chars=12)
                per_line_dur = duration / len(lines)
                for i, line in enumerate(lines):
                    subtitles.append(
                        {
                            "start": round(t_start + i * per_line_dur, 3),
                            "end": round(t_start + (i + 1) * per_line_dur, 3),
                            "text": line,
                            "highlight_words": [],
                        }
                    )

        return subtitles

    def _project_dir(self, project_id: str) -> str:
        from app.config import OUTPUTS_DIR

        d = OUTPUTS_DIR / project_id
        os.makedirs(d, exist_ok=True)
        return str(d)
