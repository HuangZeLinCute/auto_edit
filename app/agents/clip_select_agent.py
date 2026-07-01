import json
import logging

from app.services.llm_service import LLMService
from app.services.storage_service import StorageService
from app.utils.text_utils import (
    count_effective_words,
    compute_information_density,
    load_forbidden_words,
)

logger = logging.getLogger("AutoEdit")


class ClipSelectAgent:
    def __init__(self):
        self.llm = LLMService()
        self.storage = StorageService()

    def run(self, project_id: str, transcript: dict, analysis: dict) -> dict:
        logger.info("[ClipSelectAgent] project_id=%s", project_id)

        prompt_template = self.llm.load_prompt("clip_select")
        analysis_json = json.dumps(analysis, ensure_ascii=False, indent=2)
        transcript_text = self._format_transcript(transcript)

        user_prompt = prompt_template.replace("{analysis}", analysis_json).replace(
            "{transcript}", transcript_text
        )

        logger.info("[ClipSelectAgent] calling LLM")

        clip_plan = self.llm.chat_json(
            system_prompt="你是短视频切片编导。请严格按照要求的 JSON 格式输出。",
            user_prompt=user_prompt,
        )
        clip_plan["project_id"] = project_id

        candidates = clip_plan.get("candidates", [])
        for cand in candidates:
            rule_score = self._compute_rule_score(cand, transcript)
            cand["rule_score"] = rule_score
            llm_score = cand.get("score", 5)
            cand["final_score"] = round(llm_score * 0.6 + rule_score * 0.4, 1)

        candidates.sort(key=lambda c: c.get("final_score", 0), reverse=True)
        clip_plan["candidates"] = candidates

        if candidates:
            logger.info(
                "[ClipSelectAgent] top candidate: topic=%s score=%.1f",
                candidates[0].get("topic", ""),
                candidates[0].get("final_score", 0),
            )

        self.storage.save_json(project_id, "clip_plan.json", clip_plan)
        return clip_plan

    def _format_transcript(self, transcript: dict) -> str:
        segments = transcript.get("segments", [])
        lines = []
        for seg in segments:
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            text = seg.get("text", "")
            lines.append(f"[{start:.1f}s-{end:.1f}s] {text}")
        return "\n".join(lines)

    def _compute_rule_score(self, candidate: dict, transcript: dict) -> float:
        segments = transcript.get("segments", [])
        source_start = candidate.get("source_start", 0)
        source_end = candidate.get("source_end", 0)
        duration = source_end - source_start

        if duration <= 0:
            return 0

        relevant = [
            s
            for s in segments
            if s["start"] >= source_start - 1 and s["end"] <= source_end + 1
        ]
        full_text = "".join(s["text"] for s in relevant)

        density = compute_information_density(full_text, duration)

        density_score = min(density * 10, 10)

        completeness = candidate.get("scores", {}).get("completeness_score", 5)
        duration_score = min(completeness, 10)

        hook = candidate.get("hook", {})
        hook_text = hook.get("text", "")
        hook_score = 0
        hook_words = [
            "不是",
            "而是",
            "其实",
            "但是",
            "为什么",
            "怎么",
            "千万不要",
            "必须",
        ]
        for w in hook_words:
            if w in hook_text:
                hook_score += 1.5
        has_number = any(c.isdigit() for c in hook_text)
        if has_number:
            hook_score += 2
        hook_score = min(hook_score, 10)

        risk_words = load_forbidden_words()
        risk_count = sum(
            1
            for rw in risk_words
            if rw["word"] in full_text and rw["level"] in ("high", "medium")
        )
        risk_penalty = min(risk_count * 2, 10)

        score = (
            density_score * 0.25
            + duration_score * 0.20
            + hook_score * 0.25
            + min(len(relevant), 10) * 0.3
            - risk_penalty * 0.2
        )
        return round(max(0, min(10, score)), 1)
