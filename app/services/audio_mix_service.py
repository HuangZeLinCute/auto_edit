import os
import re
import yaml
import logging
from pathlib import Path
from typing import Optional, Tuple

from app.config import CONFIGS_DIR, ASSETS_DIR

logger = logging.getLogger("AutoEdit")


class AudioMixService:
    def __init__(self):
        self.sfx_dir = ASSETS_DIR / "sfx"
        self.bgm_dir = ASSETS_DIR / "bgm"
        self.rules = self._load_rules()

    def _load_rules(self) -> dict:
        rules_path = CONFIGS_DIR / "sfx_rules.yaml"
        if rules_path.exists():
            with open(rules_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def find_sfx_file(self, sfx_type: str, sfx_name: str = "") -> Optional[str]:
        type_dir = self.sfx_dir / sfx_type
        if type_dir.exists():
            if sfx_name:
                path = type_dir / sfx_name
                if path.exists():
                    return str(path)

            wav_files = sorted(type_dir.glob("*.wav"))
            if wav_files:
                return str(wav_files[0])

        for subdir in self.sfx_dir.iterdir():
            if subdir.is_dir():
                for f in sorted(subdir.glob("*.wav")):
                    return str(f)

        return None

    def find_bgm_file(self, category: str = "knowledge") -> Optional[str]:
        if not self.bgm_dir.exists():
            return None

        bgm_files = sorted(self.bgm_dir.glob("*.wav"))
        if not bgm_files:
            bgm_files = sorted(self.bgm_dir.glob("*.mp3"))

        if bgm_files:
            return str(bgm_files[0])
        return None

    def plan_sfx_from_rules(
        self,
        edit_decision: dict,
        subtitle_plan: dict,
        transcript: Optional[dict] = None,
    ) -> list[dict]:
        subtitles = subtitle_plan.get("subtitles", [])
        keep_segments = edit_decision.get("keep_segments", [])
        target_duration = edit_decision.get("target_duration", 0)
        hook = edit_decision.get("hook", {})

        sfx_plan: list[dict] = []

        self._add_structural_sfx(sfx_plan, hook, target_duration)

        self._add_keyword_sfx(sfx_plan, subtitles, keep_segments, transcript)

        sfx_plan = self._deduplicate(sfx_plan, target_duration)

        sfx_plan.sort(key=lambda x: x["time"])
        return sfx_plan

    def _add_structural_sfx(
        self,
        sfx_plan: list[dict],
        hook: dict,
        target_duration: float,
    ):
        hook_end = hook.get("target_end", 5.0) if hook else 5.0
        if 3 < hook_end < target_duration - 3:
            sfx_plan.append(
                {
                    "time": round(hook_end, 2),
                    "type": "whoosh",
                    "file": "whoosh/whoosh_fast.wav",
                    "volume_db": -24,
                    "reason": "转场: 钩子→正文",
                    "layer": "structural",
                }
            )

    def _add_keyword_sfx(
        self,
        sfx_plan: list[dict],
        subtitles: list[dict],
        keep_segments: list[dict],
        transcript: Optional[dict],
    ):
        from app.services.subtitle_service import _load_keyword_config

        kw_config = _load_keyword_config()

        all_words = []
        if transcript:
            for seg in transcript.get("segments", []):
                all_words.extend(seg.get("words", []))

        for sub in subtitles:
            highlights = sub.get("highlight_words", [])
            if not highlights:
                continue

            sub_start = sub.get("start", 0)
            sub_end = sub.get("end", 0)
            text = sub.get("text", "")

            for hl in highlights:
                word = hl.get("word", "")
                kw_type = hl.get("type", "")
                if not word:
                    continue

                rules = kw_config.get(kw_type, {})
                sfx_file = rules.get("sfx_file", "")
                if not sfx_file:
                    continue

                precise_time = self._find_word_time(
                    word, sub_start, sub_end, keep_segments, all_words
                )

                sfx_plan.append(
                    {
                        "time": round(precise_time, 2),
                        "type": kw_type,
                        "file": sfx_file,
                        "volume_db": rules.get("sfx_volume_db", -12),
                        "reason": f"L2: 重点词「{word}」({kw_type})",
                        "layer": "keyword",
                        "word": word,
                    }
                )

    def _find_word_time(
        self,
        keyword: str,
        sub_target_start: float,
        sub_target_end: float,
        keep_segments: list[dict],
        all_words: list[dict],
    ) -> float:
        if not all_words or not keep_segments:
            return sub_target_start

        source_start, source_end = self._target_to_source_range(
            sub_target_start, sub_target_end, keep_segments
        )
        if source_start is None or source_end is None:
            return sub_target_start

        ss: float = source_start
        se: float = source_end

        best_time = None
        best_dist = float("inf")
        for w in all_words:
            w_text = w.get("word", "") or w.get("text", "")
            w_start = w.get("start", 0)

            if w_start < ss - 0.5 or w_start > se + 0.5:
                continue

            clean_w = w_text.strip().strip(",.!?，。！？、")
            if keyword in clean_w or clean_w in keyword:
                mid = sub_target_start + (sub_target_end - sub_target_start) * 0.5
                target_time = self._source_to_target(w_start, keep_segments)
                if target_time is not None:
                    dist = abs(target_time - mid)
                    if dist < best_dist:
                        best_dist = dist
                        best_time = target_time

        if best_time is not None:
            return best_time

        return sub_target_start + (sub_target_end - sub_target_start) * 0.4

    def _target_to_source_range(
        self,
        target_start: float,
        target_end: float,
        keep_segments: list[dict],
    ) -> Tuple[Optional[float], Optional[float]]:
        src_starts = []
        src_ends = []
        for seg in keep_segments:
            ts = seg.get("target_start", -1)
            te = seg.get("target_end", -1)
            if ts < 0:
                continue
            if te >= target_start and ts <= target_end:
                ss = seg.get("snapped_source_start", seg.get("source_start", 0))
                se = seg.get("snapped_source_end", seg.get("source_end", 0))
                if ts <= target_start:
                    offset = target_start - ts
                    src_starts.append(ss + offset)
                else:
                    src_starts.append(ss)
                if te >= target_end:
                    offset = te - target_end
                    src_ends.append(se - offset)
                else:
                    src_ends.append(se)

        if not src_starts:
            return None, None
        return min(src_starts), max(src_ends)

    def _source_to_target(
        self,
        source_time: float,
        keep_segments: list[dict],
    ) -> Optional[float]:
        for seg in keep_segments:
            ss = seg.get("snapped_source_start", seg.get("source_start", 0))
            se = seg.get("snapped_source_end", seg.get("source_end", 0))
            ts = seg.get("target_start", -1)
            te = seg.get("target_end", -1)
            if ts < 0:
                continue
            if ss <= source_time <= se:
                ratio = (source_time - ss) / max(se - ss, 0.001)
                return ts + ratio * (te - ts)
        return None

    def _deduplicate(self, sfx_plan: list[dict], target_duration: float) -> list[dict]:
        GLOBAL_MIN = 1.5
        MAX_TOTAL = 6

        by_time = sorted(sfx_plan, key=lambda x: x["time"])

        result: list[dict] = []
        last_by_type: dict[str, float] = {}

        from app.services.subtitle_service import _load_keyword_config

        kw_config = _load_keyword_config()

        for sfx in by_time:
            layer = sfx.get("layer", "")

            if layer == "structural":
                result.append(sfx)
                last_by_type[sfx["type"]] = sfx["time"]
                continue

            t = sfx["time"]
            sfx_type = sfx.get("type", "")
            rules = kw_config.get(sfx_type, {})
            min_interval = rules.get("sfx_min_interval", 4)

            if any(abs(t - existing["time"]) < GLOBAL_MIN for existing in result):
                logger.debug("[SfxPlan] 去重: %.1fs %s 太近", t, sfx.get("word", ""))
                continue

            last_t = last_by_type.get(sfx_type, -999)
            if t - last_t < min_interval:
                logger.debug(
                    "[SfxPlan] 间隔不足: %.1fs %s (last=%.1f, need>=%.0f)",
                    t,
                    sfx.get("word", ""),
                    last_t,
                    min_interval,
                )
                continue

            if len(result) >= MAX_TOTAL:
                logger.debug("[SfxPlan] 超过最大数量 %d", MAX_TOTAL)
                break

            result.append(sfx)
            last_by_type[sfx_type] = t

        return result

    def select_bgm(self, category: str = "knowledge") -> dict:
        bgm_file = self.find_bgm_file(category)
        bgm_rules = self.rules.get("bgm", {})

        return {
            "file": bgm_file or "",
            "category": category,
            "volume_db": bgm_rules.get("default_volume_db", -24),
            "fade_in": bgm_rules.get("fade_in_s", 1.0),
            "fade_out": bgm_rules.get("fade_out_s", 2.0),
        }
