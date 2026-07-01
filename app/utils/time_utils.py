from typing import Optional


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:06.3f}"
    return f"{m:02d}:{s:06.3f}"


def parse_timestamp(ts: str) -> float:
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(ts)


def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


def compute_target_time(keep_segments: list[dict], hook_duration: float) -> list[dict]:
    current = hook_duration
    result = []
    for seg in keep_segments:
        duration = seg["source_end"] - seg["source_start"]
        result.append(
            {
                **seg,
                "target_start": round(current, 3),
                "target_end": round(current + duration, 3),
            }
        )
        current += duration
    return result


def find_closest_silence(
    silences: list[dict], target: float, tolerance: float = 0.5
) -> Optional[dict]:
    best = None
    best_dist = tolerance
    for s in silences:
        mid = (s["start"] + s["end"]) / 2
        dist = abs(mid - target)
        if dist < best_dist:
            best = s
            best_dist = dist
    return best
