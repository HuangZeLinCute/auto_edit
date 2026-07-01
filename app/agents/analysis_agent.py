import json
import logging

from app.services.llm_service import LLMService
from app.services.storage_service import StorageService

logger = logging.getLogger("AutoEdit")


class AnalysisAgent:
    def __init__(self):
        self.llm = LLMService()
        self.storage = StorageService()

    def run(self, project_id: str, transcript: dict) -> dict:
        logger.info("[AnalysisAgent] project_id=%s", project_id)

        segments = transcript.get("segments", [])
        if not segments:
            raise ValueError("Empty transcript, nothing to analyze")

        prompt_template = self.llm.load_prompt("analyze")
        transcript_json = json.dumps(segments, ensure_ascii=False, indent=2)
        user_prompt = prompt_template.replace("{transcript}", transcript_json)

        logger.info(
            "[AnalysisAgent] calling LLM, segments=%d chars=%d",
            len(segments),
            len(transcript_json),
        )

        analysis = self.llm.chat_json(
            system_prompt="你是专业的短视频内容脚本分析师。请严格按照要求的 JSON 格式输出。",
            user_prompt=user_prompt,
        )
        analysis["project_id"] = project_id

        chapters = analysis.get("chapters", [])
        golden = analysis.get("golden_sentences", [])
        topics = analysis.get("main_topics", [])

        logger.info(
            "[AnalysisAgent] done chapters=%d golden=%d topics=%s",
            len(chapters),
            len(golden),
            topics,
        )

        self.storage.save_json(project_id, "analysis.json", analysis)
        return analysis
