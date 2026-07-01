import json
import os
import logging
from typing import Optional

from app.services.llm_service import LLMService
from app.services.ffmpeg_service import FFmpegService
from app.services.audio_mix_service import AudioMixService
from app.services.storage_service import StorageService
from app.config import ASSETS_DIR

logger = logging.getLogger("AutoEdit")


class AudioAgent:
    def __init__(self):
        self.llm = LLMService()
        self.ffmpeg = FFmpegService()
        self.audio_mix = AudioMixService()
        self.storage = StorageService()

    def run(
        self,
        project_id: str,
        edit_decision: dict,
        subtitle_plan: dict,
        transcript: Optional[dict] = None,
    ) -> dict:
        logger.info("[AudioAgent] project_id=%s", project_id)

        sfx_plan = self.audio_mix.plan_sfx_from_rules(
            edit_decision, subtitle_plan, transcript
        )

        bgm_category = self._guess_bgm_category(edit_decision)
        bgm_plan = self.audio_mix.select_bgm(bgm_category)

        llm_l3 = self._llm_plan_l3(edit_decision, subtitle_plan)
        sfx_plan = self._merge_l3(sfx_plan, llm_l3)

        sfx_plan.sort(key=lambda x: x["time"])

        if llm_l3.get("bgm"):
            bgm_plan["category"] = llm_l3["bgm"].get("category", bgm_plan["category"])

        project_dir = self._project_dir(project_id)
        edited_audio = os.path.join(project_dir, "trim", "edited_audio.wav")

        mixed_audio = self._apply_audio_pipeline(
            edited_audio, project_dir, sfx_plan, bgm_plan
        )

        result = {
            "project_id": project_id,
            "sfx_plan": sfx_plan,
            "bgm_plan": bgm_plan,
            "mixed_audio_path": mixed_audio,
            "sfx_count": len(sfx_plan),
        }

        self.storage.save_json(project_id, "audio_plan.json", result)
        logger.info(
            "[AudioAgent] done: %d sfx (L1+L2+L3), BGM=%s, mixed=%s",
            len(sfx_plan),
            bgm_plan.get("category", ""),
            mixed_audio,
        )
        return result

    def _guess_bgm_category(self, edit_decision: dict) -> str:
        script = edit_decision.get("edited_script", "")
        hook = edit_decision.get("hook", {})
        hook_text = hook.get("text", "") if hook else ""
        combined = script + " " + hook_text

        emotional_words = ["焦虑", "痛苦", "崩溃", "压力", "迷茫", "抑郁", "煎熬"]
        business_words = ["商业", "创业", "赚钱", "模式", "认知", "变现", "流量"]
        energy_words = ["突破", "改变", "逆袭", "翻盘", "爆发"]

        if any(w in combined for w in emotional_words):
            return "emotional"
        if any(w in combined for w in business_words):
            return "business"
        if any(w in combined for w in energy_words):
            return "high_energy"
        return "knowledge"

    def _llm_plan_l3(self, edit_decision: dict, subtitle_plan: dict) -> dict:
        try:
            prompt_template = self.llm.load_prompt("sfx_plan")
            edited_script = edit_decision.get("edited_script", "")

            keywords = []
            for sub in subtitle_plan.get("subtitles", []):
                for hl in sub.get("highlight_words", []):
                    keywords.append(
                        f"{hl['word']}@{sub['start']:.1f}s({hl.get('type', '')})"
                    )
            keywords_str = ", ".join(keywords[:20])

            user_prompt = prompt_template.replace(
                "{edited_script}", edited_script
            ).replace("{keywords_with_time}", keywords_str)

            return self.llm.chat_json(
                system_prompt="你是短视频声音设计师，只负责 L3 层（金句落点+递进氛围）。严格 JSON。",
                user_prompt=user_prompt,
            )
        except Exception as e:
            logger.warning("[AudioAgent] L3 LLM 规划失败: %s", e)
            return {}

    def _merge_l3(self, sfx_plan: list[dict], llm_l3: dict) -> list[dict]:
        llm_sfx = llm_l3.get("sfx", [])
        if not llm_sfx:
            return sfx_plan

        existing_times = {round(s["time"], 1) for s in sfx_plan}
        added = 0

        for s in llm_sfx:
            t = round(s.get("time", 0), 1)

            if any(abs(t - et) < 1.0 for et in existing_times):
                logger.debug("[AudioAgent] L3 去重: %.1fs 太近", t)
                continue

            sfx_type = s.get("type", "")
            if sfx_type not in ("impact", "rise"):
                continue

            file_map = {
                "impact": "ding/ding_uplifting_bells.wav",
                "rise": "pop/pop_long.wav",
            }
            sfx_file = file_map.get(sfx_type, "")
            if not sfx_file:
                continue

            sfx_plan.append(
                {
                    "time": t,
                    "type": sfx_type,
                    "file": sfx_file,
                    "volume_db": -22 if sfx_type == "impact" else -24,
                    "reason": f"L3: {s.get('reason', 'LLM金句')}",
                    "layer": "llm",
                }
            )
            existing_times.add(t)
            added += 1

        logger.info("[AudioAgent] L3 合并: +%d sfx", added)
        return sfx_plan

    def _apply_audio_pipeline(
        self,
        edited_audio: str,
        project_dir: str,
        sfx_plan: list[dict],
        bgm_plan: dict,
    ) -> str:
        if not os.path.exists(edited_audio):
            logger.warning("[AudioAgent] edited_audio.wav 不存在，跳过混音")
            return ""

        audio_dir = os.path.join(project_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)

        resolved_sfx = []
        for sfx in sfx_plan:
            sfx_file = self._resolve_sfx_path(sfx)
            if not sfx_file or not os.path.exists(sfx_file):
                logger.warning(
                    "[AudioAgent] sfx 不存在: %s (%s)",
                    sfx.get("file", ""),
                    sfx.get("reason", ""),
                )
                continue
            resolved_sfx.append(
                {
                    "file": sfx_file,
                    "time": sfx["time"],
                    "volume_db": sfx.get("volume_db", -10),
                }
            )
            logger.debug(
                "[AudioAgent] sfx %.1fs %s vol=%ddB",
                sfx["time"],
                os.path.basename(sfx_file),
                sfx.get("volume_db", -10),
            )

        if resolved_sfx:
            sfx_mixed = os.path.join(audio_dir, "sfx_mixed.wav")
            try:
                self.ffmpeg.mix_sfx_batch(edited_audio, resolved_sfx, sfx_mixed)
                current_audio = sfx_mixed
                logger.info(
                    "[AudioAgent] 单次混入 %d 个音效 -> %s",
                    len(resolved_sfx),
                    os.path.basename(sfx_mixed),
                )
            except Exception as e:
                logger.warning("[AudioAgent] 批量音效混入失败: %s, 使用原音", e)
                current_audio = edited_audio
        else:
            current_audio = edited_audio

        mixed_output = os.path.join(audio_dir, "mixed_audio.wav")
        bgm_file = bgm_plan.get("file", "")

        if bgm_file and os.path.exists(bgm_file):
            try:
                self.ffmpeg.mix_audio(
                    current_audio,
                    bgm_file,
                    mixed_output,
                    bgm_volume_db=bgm_plan.get("volume_db", -24),
                    fade_in=bgm_plan.get("fade_in", 1.0),
                    fade_out=bgm_plan.get("fade_out", 2.0),
                )
                current_audio = mixed_output
            except Exception as e:
                logger.warning("[AudioAgent] BGM 混音失败: %s", e)

        final_output = os.path.join(audio_dir, "final_audio.wav")
        try:
            self.ffmpeg.normalize_audio(current_audio, final_output, target_db=-1.0)
            current_audio = final_output
        except Exception as e:
            logger.warning("[AudioAgent] 音频标准化失败: %s", e)

        return current_audio

    def _resolve_sfx_path(self, sfx: dict) -> Optional[str]:
        sfx_file = sfx.get("file", "")
        if sfx_file:
            full_path = str(ASSETS_DIR / "sfx" / sfx_file)
            if os.path.exists(full_path):
                return full_path

            import os.path as op

            base = op.basename(sfx_file)
            for subdir in ("pop", "ding", "whoosh", "click", "notification"):
                p = ASSETS_DIR / "sfx" / subdir / base
                if p.exists():
                    return str(p)

        for subdir in ("pop", "ding", "whoosh", "click", "notification"):
            d = ASSETS_DIR / "sfx" / subdir
            if d.exists():
                wavs = sorted(d.glob("*.wav"))
                if wavs:
                    return str(wavs[0])
        return None

    def _project_dir(self, project_id: str) -> str:
        from app.config import OUTPUTS_DIR

        d = OUTPUTS_DIR / project_id
        os.makedirs(d, exist_ok=True)
        return str(d)
