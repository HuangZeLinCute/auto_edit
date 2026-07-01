import re
import yaml
import logging
from pathlib import Path
from typing import Optional

from app.config import CONFIGS_DIR

logger = logging.getLogger("AutoEdit")

_filler_words_cache: Optional[list[str]] = None
_forbidden_words_cache: Optional[list[dict]] = None


def load_filler_words() -> list[str]:
    global _filler_words_cache
    if _filler_words_cache is not None:
        return _filler_words_cache

    path = CONFIGS_DIR / "filler_words.yaml"
    if not path.exists():
        _filler_words_cache = []
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    words = []
    for category in [
        "standalone_fillers",
        "sentence_fillers",
        "connectors",
        "hesitation_sounds",
    ]:
        words.extend(data.get(category, []))

    _filler_words_cache = words
    return words


def load_forbidden_words() -> list[dict]:
    global _forbidden_words_cache
    if _forbidden_words_cache is not None:
        return _forbidden_words_cache

    path = CONFIGS_DIR / "forbidden_words.yaml"
    if not path.exists():
        _forbidden_words_cache = []
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    result = []
    for level in ["high", "medium", "low"]:
        for group in data.get(level, []):
            for w in group.get("words", []):
                result.append(
                    {
                        "word": w,
                        "level": level,
                        "action": group.get("action", "keep"),
                    }
                )

    _forbidden_words_cache = result
    return result


def detect_filler_words(segments: list[dict]) -> list[dict]:
    filler_list = load_filler_words()
    results = []

    for seg in segments:
        text = seg["text"]
        for fw in filler_list:
            if fw in text:
                for word_info in seg.get("words", []):
                    if word_info["word"].strip() == fw:
                        results.append(
                            {
                                "word": fw,
                                "start": word_info["start"],
                                "end": word_info["end"],
                                "segment_id": seg["id"],
                                "type": "filler",
                            }
                        )
    return results


def detect_silences(segments: list[dict], threshold: float = 0.5) -> list[dict]:
    results = []
    for i in range(1, len(segments)):
        gap = segments[i]["start"] - segments[i - 1]["end"]
        if gap >= threshold:
            results.append(
                {
                    "start": segments[i - 1]["end"],
                    "end": segments[i]["start"],
                    "duration": round(gap, 3),
                }
            )
    return results


def detect_risk_words(segments: list[dict]) -> list[dict]:
    forbidden = load_forbidden_words()
    results = []

    for seg in segments:
        text = seg["text"]
        for fw in forbidden:
            if fw["word"] in text:
                start = seg["start"]
                end = seg["end"]
                for word_info in seg.get("words", []):
                    if fw["word"] in word_info["word"]:
                        start = word_info["start"]
                        end = word_info["end"]
                        break
                results.append(
                    {
                        "word": fw["word"],
                        "start": start,
                        "end": end,
                        "segment_id": seg["id"],
                        "level": fw["level"],
                    }
                )
    return results


def split_into_lines(text: str, max_chars: int = 12) -> list[str]:
    lines = []
    current = ""
    for char in text:
        current += char
        if len(current) >= max_chars:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines


def count_effective_words(text: str) -> int:
    punctuation = r"[，。！？、；：\u201c\u201d\u2018\u2019（）\s]+"
    cleaned = re.sub(punctuation, " ", text).strip()
    if not cleaned:
        return 0
    parts = cleaned.split()
    count = 0
    for p in parts:
        has_cjk = any("\u4e00" <= c <= "\u9fff" for c in p)
        count += len(p) if has_cjk else 1
    return count


def compute_information_density(text: str, duration: float) -> float:
    if duration <= 0:
        return 0
    return count_effective_words(text) / duration
