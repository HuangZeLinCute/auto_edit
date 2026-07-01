import json
import os
import logging

from app.services.llm_service import LLMService
from app.services.storage_service import StorageService
from app.utils.text_utils import load_forbidden_words

logger = logging.getLogger("AutoEdit")


class TitleAgent:
    def __init__(self):
        self.llm = LLMService()
        self.storage = StorageService()

    def run(
        self,
        project_id: str,
        edit_decision: dict,
        clip_plan: dict,
        user_intent: str = "",
    ) -> dict:
        logger.info("[TitleAgent] project_id=%s", project_id)

        candidates = clip_plan.get("candidates", [])
        topic = candidates[0].get("topic", "") if candidates else ""
        edited_script = edit_decision.get("edited_script", "")

        prompt_template = self.llm.load_prompt("title_gen")
        user_intent = str(user_intent or "").strip()
        intent_prompt = (
            "用户没有提供额外剪辑需求，请按默认短视频标题标准生成。"
            if not user_intent
            else (
                "用户剪辑需求：\n"
                f"{user_intent}\n\n"
                "标题、话题标签、封面文案和简介必须贴合这个需求。"
            )
        )
        user_prompt = intent_prompt + "\n\n" + prompt_template.replace(
            "{edited_script}", edited_script
        ).replace(
            "{topic}", topic
        )

        titles_data = self.llm.chat_json(
            system_prompt="你是短视频标题专家。请严格按照要求的 JSON 格式输出。",
            user_prompt=user_prompt,
        )

        titles_data = self._filter_forbidden(titles_data)

        titles_data["project_id"] = project_id
        self.storage.save_json(project_id, "titles.json", titles_data)

        logger.info(
            "[TitleAgent] done: %d 类标题, %d 话题, %d 封面文案",
            len(titles_data.get("titles", {})),
            len(titles_data.get("topics", [])),
            len(titles_data.get("cover_texts", [])),
        )
        return titles_data

    def _filter_forbidden(self, titles_data: dict) -> dict:
        forbidden = load_forbidden_words()
        forbidden_set = {
            fw["word"] for fw in forbidden if fw["level"] in ("high", "medium")
        }

        titles = titles_data.get("titles", {})
        filtered_titles = {}
        for title_type, title_list in titles.items():
            filtered = []
            for title in title_list:
                has_forbidden = any(fw in title for fw in forbidden_set)
                if not has_forbidden:
                    filtered.append(title)
                else:
                    logger.warning("[TitleAgent] 过滤违禁标题: %s", title[:30])
            filtered_titles[title_type] = filtered

        titles_data["titles"] = filtered_titles

        topics = titles_data.get("topics", [])
        filtered_topics = [
            t for t in topics if not any(fw in t for fw in forbidden_set)
        ]
        titles_data["topics"] = filtered_topics

        return titles_data
