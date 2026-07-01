import re
import yaml
import logging
from pathlib import Path
from typing import Optional

from app.config import CONFIGS_DIR, ASSETS_DIR

logger = logging.getLogger("AutoEdit")

_KEYWORD_CONFIG: Optional[dict] = None


def _load_keyword_config() -> dict:
    global _KEYWORD_CONFIG
    if _KEYWORD_CONFIG is not None:
        return _KEYWORD_CONFIG

    config_path = CONFIGS_DIR / "sfx_rules.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    else:
        data = {}

    config = {
        "impact": {
            "words": [
                "崩了",
                "爆了",
                "离谱",
                "太强了",
                "绝了",
                "炸裂",
                "恐怖",
                "有病",
                "疯了",
                "完了",
                "没救了",
                "不可能",
                "绝对",
                "致命",
                "太可怕",
                "震惊",
                "颠覆",
            ],
            "color": "#FF4D4F",
            "effect": "shake",
            "priority": "high",
            "sfx_file": "pop/pop_long.wav",
            "sfx_volume_db": -20,
            "sfx_min_interval": 8,
        },
        "reversal": {
            "words": [
                "但是",
                "然而",
                "没想到",
                "反而",
                "不是",
                "而是",
                "不觉得",
                "其实",
                "事实上",
                "恰恰相反",
                "并不",
                "并非",
                "可惜",
                "遗憾",
            ],
            "color": "#FF6B6B",
            "effect": "pop",
            "priority": "high",
            "sfx_file": "whoosh/whoosh_fast.wav",
            "sfx_volume_db": -24,
            "sfx_min_interval": 8,
        },
        "conclusion": {
            "words": [
                "核心",
                "关键",
                "本质",
                "根本",
                "真正",
                "重点",
                "最重要",
                "归根结底",
                "说白了",
                "底层逻辑",
                "真相",
            ],
            "color": "#4DFFFF",
            "effect": "bold",
            "priority": "high",
            "sfx_file": "ding/ding_uplifting_bells.wav",
            "sfx_volume_db": -22,
            "sfx_min_interval": 10,
        },
        "number": {
            "patterns": [
                r"\d+",
                "几",
                "多少",
                "一半",
                "翻倍",
                "倍",
                "第一",
                "第二",
                "第三",
                "唯一",
            ],
            "color": "#FFD84D",
            "effect": "scale_120",
            "priority": "high",
            "sfx_file": "pop/pop_dry.wav",
            "sfx_volume_db": -22,
            "sfx_min_interval": 6,
        },
        "pain_point": {
            "words": [
                "亏",
                "踩坑",
                "被骗",
                "不知道",
                "没人告诉你",
                "亏大了",
                "焦虑",
                "抑郁",
                "有问题",
                "痛苦",
                "压力",
                "崩溃",
                "迷茫",
                "困惑",
                "无力",
                "尴尬",
                "煎熬",
                "内耗",
                "难受",
                "憋屈",
                "窝囊",
                "不甘心",
            ],
            "color": "#FF8C42",
            "effect": "underline",
            "priority": "medium",
            "sfx_file": "pop/pop_explainer.wav",
            "sfx_volume_db": -22,
            "sfx_min_interval": 6,
        },
        "action": {
            "words": [
                "必须",
                "一定",
                "千万别",
                "务必",
                "赶紧",
                "马上",
                "记住",
                "注意",
                "一定要",
                "千万",
            ],
            "color": "#FFD84D",
            "effect": "pulse",
            "priority": "medium",
            "sfx_file": "pop/pop_long.wav",
            "sfx_volume_db": -20,
            "sfx_min_interval": 8,
        },
    }

    _KEYWORD_CONFIG = config
    return config


def detect_keywords(text: str) -> list[dict]:
    config = _load_keyword_config()
    results = []

    for kw_type, rules in config.items():
        words_list = rules.get("words", [])
        for word in words_list:
            if word in text:
                results.append(
                    {
                        "word": word,
                        "type": kw_type,
                        "color": rules["color"],
                        "effect": rules["effect"],
                        "priority": rules["priority"],
                    }
                )

        patterns = rules.get("patterns", [])
        for pat in patterns:
            if pat.startswith("\\") or pat.startswith(r"\\"):
                try:
                    if re.search(pat, text):
                        for m in re.finditer(pat, text):
                            results.append(
                                {
                                    "word": m.group(),
                                    "type": kw_type,
                                    "color": rules["color"],
                                    "effect": rules["effect"],
                                    "priority": rules["priority"],
                                }
                            )
                except re.error:
                    pass
            elif pat in text:
                results.append(
                    {
                        "word": pat,
                        "type": kw_type,
                        "color": rules["color"],
                        "effect": rules["effect"],
                        "priority": rules["priority"],
                    }
                )

    seen = set()
    unique = []
    for kw in results:
        key = (kw["word"], kw["type"])
        if key not in seen:
            seen.add(key)
            unique.append(kw)

    return unique


def generate_ass(
    subtitles: list[dict],
    output_path: str,
    resolution: str = "1080x1920",
    font_name: str = "Alibaba PuHuiTi",
    font_size: int = 72,
    max_line_chars: int = 12,
) -> str:
    import os

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    w, h = resolution.split("x")

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {w}",
        f"PlayResY: {h}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,6,3,2,30,30,60,1",
        f"Style: Highlight,{font_name},{font_size},&H0000D8FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,120,120,2,0,1,6,3,2,30,30,60,1",
        f"Style: GoldHit,{font_name},90,&H0000D8FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,150,150,2,0,1,8,4,2,30,30,60,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for sub in subtitles:
        start_time = _format_ass_time(sub["start"])
        end_time = _format_ass_time(sub["end"])
        text = sub["text"]
        highlights = sub.get("highlight_words", [])

        if len(text) > max_line_chars:
            text = _split_text_with_highlights(text, highlights, max_line_chars)

        if highlights:
            text = _apply_highlight_tags(text, highlights)

        lines.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}")

    content = "\n".join(lines) + "\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(
        "[SubtitleService] ASS 生成完成: %d 条字幕 -> %s",
        len(subtitles),
        output_path,
    )
    return output_path


def _format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _split_text_with_highlights(
    text: str, highlights: list[dict], max_chars: int
) -> str:
    mid = len(text) // 2
    best_break = mid
    for i in range(max(1, mid - 5), min(len(text) - 1, mid + 5)):
        if text[i] in "，。！？、；：,!?;:":
            best_break = i + 1
            break
    else:
        best_break = mid

    return text[:best_break] + "\\N" + text[best_break:]


def _apply_highlight_tags(text: str, highlights: list[dict]) -> str:
    result = text
    for hl in sorted(highlights, key=lambda h: len(h.get("word", "")), reverse=True):
        word = hl["word"]
        color = hl.get("color", "#FFD84D")

        if color == "#FFD84D":
            style = "GoldHit"
        elif color == "#4DFFFF":
            style = "Highlight"
        elif color == "#FF6B6B":
            style = "Highlight"
        else:
            style = "Highlight"

        if word in result:
            result = result.replace(word, r"{\r" + style + r"}" + word + r"{\rDefault}")
    return result
