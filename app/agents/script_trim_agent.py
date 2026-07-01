import json
import logging
import os
import wave
from typing import Optional

from app.services.llm_service import LLMService
from app.services.ffmpeg_service import FFmpegService
from app.services.storage_service import StorageService
from app.utils.text_utils import load_forbidden_words
from app.config import TEMP_DIR

logger = logging.getLogger("AutoEdit")


class ScriptTrimAgent:
    def __init__(self):
        self.llm = LLMService()
        self.ffmpeg = FFmpegService()
        self.storage = StorageService()

    def run(
        self,
        project_id: str,
        clip: dict,
        transcript: dict,
        source_video: str,
        audio_path: str,
        user_intent: str = "",
    ) -> dict:
        logger.info("[ScriptTrimAgent] project_id=%s", project_id)

        edit_decision = self._llm_trim(project_id, clip, transcript, user_intent)

        clip_hook = clip.get("hook")
        if clip_hook and clip_hook.get("text") and clip_hook.get("start"):
            edit_hook = edit_decision.get("hook", {})
            edit_hook["text"] = clip_hook.get("text", "")
            edit_hook["_clip_hook_start"] = clip_hook.get("start", 0)
            edit_hook["_clip_hook_end"] = clip_hook.get(
                "end", clip_hook.get("start", 0) + 4
            )
            logger.info(
                "[ScriptTrimAgent] hook from clip_plan: %s",
                clip_hook.get("text", "")[:40],
            )

        self._validate_edit_decision(edit_decision, transcript)

        self._check_remove_overlap(edit_decision)

        project_dir = self._ensure_project_dir(project_id)

        self._build_edited_media(
            source_video, audio_path, project_dir, edit_decision, transcript
        )

        if edit_decision.get("mute_words"):
            self._apply_mutes(project_dir, edit_decision)

        self._check_target_duration(edit_decision)

        edit_decision["project_id"] = project_id
        edit_decision["clip_id"] = clip.get("clip_id", "clip_001")

        self.storage.save_json(project_id, "edit_decision.json", edit_decision)
        logger.info(
            "[ScriptTrimAgent] done keep=%d remove=%d video=%d target_dur=%.1f",
            len(edit_decision.get("keep_segments", [])),
            len(edit_decision.get("remove_segments", [])),
            len(edit_decision.get("video_segments", [])),
            edit_decision.get("target_duration", 0),
        )
        return edit_decision

    def _llm_trim(
        self, project_id: str, clip: dict, transcript: dict, user_intent: str = ""
    ) -> dict:
        prompt_template = self.llm.load_prompt("script_trim")
        hook = clip.get("hook")
        if not hook or not hook.get("text"):
            clip_start = clip.get("source_start", 0)
            clip_end = clip.get("source_end", 0)
            segments = transcript.get("segments", [])
            nearby_texts = [
                s["text"]
                for s in segments
                if s["start"] >= clip_start and s["end"] <= clip_start + 8
            ]
            hook_text = "".join(nearby_texts[:3]) or clip.get("topic", "精彩内容")
            hook = {
                "source_start": clip_start,
                "source_end": clip_start + 5,
                "text": hook_text,
            }
            clip["hook"] = hook
            logger.warning(
                "[ScriptTrimAgent] no hook from LLM, using default: %s",
                hook_text[:40],
            )

        logger.info("[ScriptTrimAgent] calling LLM for trim")

        segments = transcript.get("segments", [])
        source_start = clip["source_start"]
        source_end = clip["source_end"]
        relevant = [
            s
            for s in segments
            if s["start"] >= source_start - 2 and s["end"] <= source_end + 2
        ]

        hook_source = clip.get("hook", {})
        user_intent = str(user_intent or "").strip()
        intent_prompt = (
            "用户没有提供额外剪辑需求，请按默认爆款短视频标准裁剪。"
            if not user_intent
            else (
                "用户剪辑需求：\n"
                f"{user_intent}\n\n"
                "请优先满足该需求：保留相关论点、删除无关铺垫/闲聊/重复，钩子和成片节奏要贴合用户目标。"
            )
        )
        user_prompt = (
            intent_prompt
            + "\n\n"
            + prompt_template.replace("{topic}", clip.get("topic", ""))
            .replace("{source_start}", str(source_start))
            .replace("{source_end}", str(source_end))
            .replace("{hook_text}", hook_source.get("text", ""))
            .replace("{hook_start}", str(hook_source.get("start", "")))
            .replace("{hook_end}", str(hook_source.get("end", "")))
            .replace(
                "{transcript_segment}",
                json.dumps(relevant, ensure_ascii=False, indent=2),
            )
        )

        edit_decision = self.llm.chat_json(
            system_prompt="你是短视频精剪师。请严格按照要求的 JSON 格式输出。",
            user_prompt=user_prompt,
        )
        return edit_decision

    def _validate_edit_decision(self, edit_decision: dict, transcript: dict):
        remove = edit_decision.get("remove_segments", [])
        valid_reasons = {
            "filler",
            "silence",
            "repetition",
            "off_topic",
            "risk_word",
            "low_value",
        }
        for rs in remove:
            reason = rs.get("reason", "")
            if reason not in valid_reasons:
                logger.warning(
                    "[ScriptTrimAgent] invalid remove reason: %s, defaulting to low_value",
                    reason,
                )
                rs["reason"] = "low_value"

        keep = edit_decision.get("keep_segments", [])
        if not keep:
            logger.warning("[ScriptTrimAgent] no keep_segments in LLM output")
            return

        source_texts = set()
        for seg in transcript.get("segments", []):
            source_texts.add(seg["text"].strip())

        for ks in keep:
            text = ks.get("text", "").strip()
            found = any(text in st or st in text for st in source_texts)
            if not found and text:
                logger.warning(
                    "[ScriptTrimAgent] keep_segment text not in source: %s",
                    text[:50],
                )

    def _ensure_project_dir(self, project_id: str) -> str:
        from app.config import OUTPUTS_DIR

        d = OUTPUTS_DIR / project_id / "trim"
        os.makedirs(d, exist_ok=True)
        return str(d)

    def _build_edited_media(
        self,
        source_video: str,
        audio_path: str,
        project_dir: str,
        edit_decision: dict,
        transcript: Optional[dict] = None,
    ):
        keep_segments = edit_decision.get("keep_segments", [])
        if not keep_segments:
            logger.warning("[ScriptTrimAgent] no keep_segments, skipping")
            return

        keep_segments.sort(key=lambda s: s.get("source_start", 0))

        PAD = 0.15
        SEARCH_WINDOW = 0.30

        word_boundaries = self._extract_word_boundaries(transcript)

        hook = edit_decision.get("hook")
        if hook and keep_segments:
            clip_hook_start = hook.pop("_clip_hook_start", None)
            clip_hook_end = hook.pop("_clip_hook_end", None)
            if clip_hook_start is not None:
                hook_segs = [
                    s
                    for s in keep_segments
                    if s["source_start"] >= clip_hook_start - 1
                    and s["source_end"] <= clip_hook_end + 1
                ]
                if hook_segs:
                    hook["source_start"] = hook_segs[0]["source_start"]
                    hook["source_end"] = hook_segs[-1]["source_end"]
            if hook.get("source_end", 0) - hook.get("source_start", 0) < 3:
                hook["source_start"] = keep_segments[0]["source_start"]
                end = keep_segments[0]["source_end"]
                for seg in keep_segments[1:]:
                    if seg["source_start"] - end < 0.3:
                        end = seg["source_end"]
                    else:
                        break
                hook["source_end"] = end
            hook["target_start"] = 0
            hook["target_end"] = round(hook["source_end"] - hook["source_start"], 3)
            logger.info(
                "[ScriptTrimAgent] hook: %.1f-%.1fs text=%s",
                hook["source_start"],
                hook["source_end"],
                hook.get("text", "")[:40],
            )

        seg_files = []
        video_files = []
        target_offset = 0.0
        last_audio_end = 0.0

        video_dir = os.path.join(project_dir, "video_segments")
        os.makedirs(video_dir, exist_ok=True)

        for i, seg in enumerate(keep_segments):
            src_start = seg["source_start"]
            src_end = seg["source_end"]

            audio_start = max(
                0,
                self._snap_to_word_boundary(
                    src_start, "start", word_boundaries, audio_path, SEARCH_WINDOW
                )
                - PAD,
            )
            audio_end = (
                self._snap_to_word_boundary(
                    src_end, "end", word_boundaries, audio_path, SEARCH_WINDOW
                )
                + PAD
            )
            if audio_start < last_audio_end:
                logger.info(
                    "[ScriptTrimAgent] adjust overlapping boundary: %.3f -> %.3f",
                    audio_start,
                    last_audio_end,
                )
                audio_start = last_audio_end
            if audio_end <= audio_start:
                logger.warning(
                    "[ScriptTrimAgent] skip empty segment after boundary adjust: %.3f-%.3f",
                    audio_start,
                    audio_end,
                )
                continue
            last_audio_end = audio_end

            seg_path = os.path.join(project_dir, f"keep_{i:03d}.wav")
            self.ffmpeg.cut_audio(audio_path, seg_path, audio_start, audio_end)
            seg_files.append(seg_path)
            seg["snapped_source_start"] = round(audio_start, 3)
            seg["snapped_source_end"] = round(audio_end, 3)

            vid_path = os.path.join(video_dir, f"seg_{i:03d}.mp4")
            duration = audio_end - audio_start
            try:
                self.ffmpeg._run(
                    [
                        self.ffmpeg.ffmpeg,
                        "-y",
                        "-i",
                        source_video,
                        "-ss",
                        f"{audio_start:.3f}",
                        "-t",
                        f"{duration:.3f}",
                        "-an",
                        "-vf",
                        "setpts=PTS-STARTPTS",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-preset",
                        "ultrafast",
                        "-threads",
                        "1",
                        "-refs",
                        "1",
                        "-crf",
                        "28",
                        "-avoid_negative_ts",
                        "make_zero",
                        vid_path,
                    ]
                )
                video_files.append(vid_path)
            except Exception as e:
                logger.warning(
                    "[ScriptTrimAgent] video extraction failed for seg %d: %s", i, e
                )

            actual_dur = self.ffmpeg.get_duration(seg_path)
            seg["target_start"] = round(target_offset, 3)
            seg["target_end"] = round(target_offset + actual_dur, 3)
            target_offset += actual_dur

        edited_audio = os.path.join(project_dir, "edited_audio.wav")
        if len(seg_files) == 1:
            import shutil

            shutil.copy2(seg_files[0], edited_audio)
        else:
            self.ffmpeg.concat_audio(seg_files, edited_audio)

        faded_audio = os.path.join(project_dir, "edited_audio_faded.wav")
        final_duration = self.ffmpeg.get_duration(edited_audio)
        self.ffmpeg._run(
            [
                self.ffmpeg.ffmpeg,
                "-y",
                "-i",
                edited_audio,
                "-af",
                f"afade=t=in:d=0.03,afade=t=out:st={max(0, final_duration - 0.05):.3f}:d=0.05",
                "-c:a",
                "pcm_s16le",
                faded_audio,
            ]
        )
        import shutil

        shutil.move(faded_audio, edited_audio)
        final_duration = self.ffmpeg.get_duration(edited_audio)
        edit_decision["target_duration"] = round(final_duration, 2)
        edit_decision["video_segments"] = video_files

        for f in seg_files:
            if os.path.exists(f):
                os.remove(f)

        logger.info(
            "[ScriptTrimAgent] built media: audio=%.1fs video=%d segments",
            final_duration,
            len(video_files),
        )

    def _extract_word_boundaries(
        self, transcript: Optional[dict]
    ) -> list[tuple[float, float]]:
        """Extract (start, end) tuples of all ASR words for boundary snapping."""
        if not transcript:
            return []
        boundaries: list[tuple[float, float]] = []
        for seg in transcript.get("segments", []):
            words = seg.get("words", [])
            if words:
                for w in words:
                    s = w.get("start", 0)
                    e = w.get("end", s)
                    if e > s:
                        boundaries.append((s, e))
            else:
                s = seg.get("start", 0)
                e = seg.get("end", s)
                if e > s:
                    boundaries.append((s, e))
        boundaries.sort()
        return boundaries

    def _snap_to_word_boundary(
        self,
        target_time: float,
        kind: str,
        word_boundaries: list[tuple[float, float]],
        audio_path: str,
        window: float = 0.30,
    ) -> float:
        """Snap cut point to nearest ASR word boundary.

        For 'start': snap to a word START (so we don't cut into a word's tail).
        For 'end': snap to a word END (so we don't cut into a word's head).
        Falls back to low-energy snap if no word boundaries available.
        """
        if not word_boundaries:
            return self._snap_to_low_energy(audio_path, target_time, kind, window)

        lo = target_time - window
        hi = target_time + window

        candidates: list[float] = []
        for ws, we in word_boundaries:
            if kind == "start":
                if lo <= ws <= hi:
                    candidates.append(ws)
            else:
                if lo <= we <= hi:
                    candidates.append(we)

        if not candidates:
            nearest = None
            best_dist = float("inf")
            for ws, we in word_boundaries:
                boundary = ws if kind == "start" else we
                d = abs(boundary - target_time)
                if d < best_dist:
                    best_dist = d
                    nearest = boundary
            if nearest is not None and best_dist <= window * 2:
                candidates.append(nearest)

        if not candidates:
            return self._snap_to_low_energy(audio_path, target_time, kind, window)

        if kind == "start":
            snapped = max(candidates)
            pad_offset = -0.05
        else:
            snapped = min(candidates)
            pad_offset = 0.05

        snapped = max(0.0, snapped + pad_offset)

        logger.debug(
            "[ScriptTrimAgent] snap %s %.3f -> %.3f (word boundary, %d candidates)",
            kind,
            target_time,
            snapped,
            len(candidates),
        )
        return snapped

    def _check_remove_overlap(self, edit_decision: dict):
        """Detect remove_segments that overlap with keep_segments.

        If a remove_segment overlaps any keep_segment by >0.1s,
        it's likely a bad cut — remove it from remove_segments
        and extend the overlapping keep_segment to cover the gap.
        """
        keep = edit_decision.get("keep_segments", [])
        remove = edit_decision.get("remove_segments", [])
        if not keep or not remove:
            return

        keep.sort(key=lambda s: s.get("source_start", 0))

        bad_indices: set[int] = set()
        for ri, rs in enumerate(remove):
            rs_start = rs.get("source_start", 0)
            rs_end = rs.get("source_end", 0)
            if rs_end <= rs_start:
                continue

            for ki, ks in enumerate(keep):
                ks_start = ks.get("source_start", 0)
                ks_end = ks.get("source_end", 0)

                overlap_start = max(rs_start, ks_start)
                overlap_end = min(rs_end, ks_end)
                overlap = overlap_end - overlap_start

                if overlap > 0.1:
                    bad_indices.add(ri)
                    logger.warning(
                        "[ScriptTrimAgent] remove[%d] (%.2f-%.2f '%s') overlaps "
                        "keep[%d] (%.2f-%.2f '%s') by %.2fs — merging into keep",
                        ri,
                        rs_start,
                        rs_end,
                        rs.get("text", "")[:20],
                        ki,
                        ks_start,
                        ks_end,
                        ks.get("text", "")[:20],
                        overlap,
                    )

                    if rs_start < ks_start:
                        ks["source_start"] = rs_start
                    if rs_end > ks_end:
                        ks["source_end"] = rs_end
                    ks["text"] = ks.get("text", "") + " " + rs.get("text", "")
                    break

        if bad_indices:
            new_remove = [rs for i, rs in enumerate(remove) if i not in bad_indices]
            edit_decision["remove_segments"] = new_remove
            logger.info(
                "[ScriptTrimAgent] removed %d overlapping remove-segments, "
                "%d remaining",
                len(bad_indices),
                len(new_remove),
            )

            keep.sort(key=lambda s: s.get("source_start", 0))
            merged = [keep[0]]
            for ks in keep[1:]:
                last = merged[-1]
                if ks["source_start"] <= last["source_end"]:
                    last["source_end"] = max(last["source_end"], ks["source_end"])
                    last["text"] = last.get("text", "") + " " + ks.get("text", "")
                else:
                    merged.append(ks)
            edit_decision["keep_segments"] = merged

    def _snap_to_low_energy(
        self, audio_path: str, target_time: float, kind: str, window: float = 0.30
    ) -> float:
        """Snap a cut point to the lowest-energy frame near target_time.

        This avoids cutting inside a word. It only uses Python stdlib WAV reading,
        because ffmpeg silence filters were unstable in this Windows environment.
        """
        try:
            with wave.open(audio_path, "rb") as wf:
                rate = wf.getframerate()
                channels = wf.getnchannels()
                width = wf.getsampwidth()
                total_frames = wf.getnframes()

                start_t = max(0.0, target_time - window)
                end_t = min(total_frames / rate, target_time + window)
                start_f = int(start_t * rate)
                end_f = int(end_t * rate)
                if end_f <= start_f:
                    return target_time

                wf.setpos(start_f)
                raw = wf.readframes(end_f - start_f)
                if width != 2 or not raw:
                    return target_time

                import array

                samples = array.array("h")
                samples.frombytes(raw)
                if not samples:
                    return target_time

                frame_ms = 20
                frame_samples = max(1, int(rate * frame_ms / 1000) * channels)
                best_i = 0
                best_energy = None
                for i in range(0, len(samples), frame_samples):
                    chunk = samples[i : i + frame_samples]
                    if not chunk:
                        continue
                    energy = sum(abs(x) for x in chunk) / len(chunk)
                    if best_energy is None or energy < best_energy:
                        best_energy = energy
                        best_i = i

                snapped = start_t + (best_i / channels) / rate
                logger.debug(
                    "[ScriptTrimAgent] snap %s %.3f -> %.3f energy=%.1f",
                    kind,
                    target_time,
                    snapped,
                    best_energy or 0,
                )
                return snapped
        except Exception as e:
            logger.warning("[ScriptTrimAgent] energy snap failed: %s", e)
            return target_time

    def _concat_with_crossfade(
        self, seg_files: list[str], output_path: str, crossfade_dur: float = 0.04
    ):
        if len(seg_files) == 1:
            import shutil

            shutil.copy2(seg_files[0], output_path)
            return

        if len(seg_files) == 2:
            self._crossfade_pair(seg_files[0], seg_files[1], output_path, crossfade_dur)
            return

        temp_dir = os.path.dirname(output_path)
        current = seg_files[0]
        for i in range(1, len(seg_files)):
            merged = os.path.join(temp_dir, f"_merge_{i:03d}.wav")
            self._crossfade_pair(current, seg_files[i], merged, crossfade_dur)
            if i > 1 and os.path.exists(current) and current.startswith(temp_dir):
                os.remove(current)
            current = merged

        import shutil

        shutil.move(current, output_path)

        for f in os.listdir(temp_dir):
            if f.startswith("_merge_") and f.endswith(".wav"):
                fp = os.path.join(temp_dir, f)
                if os.path.exists(fp):
                    os.remove(fp)

    def _crossfade_pair(
        self, audio_a: str, audio_b: str, output: str, crossfade_dur: float = 0.04
    ):
        dur_a = self.ffmpeg.get_duration(audio_a)
        if crossfade_dur >= dur_a:
            crossfade_dur = max(dur_a * 0.1, 0.005)

        filter_complex = (
            f"[0:a][1:a]acrossfade=d={crossfade_dur:.3f}:c1=tri:c2=tri[aout]"
        )
        self.ffmpeg._run(
            [
                self.ffmpeg.ffmpeg,
                "-y",
                "-i",
                audio_a,
                "-i",
                audio_b,
                "-filter_complex",
                filter_complex,
                "-map",
                "[aout]",
                "-c:a",
                "pcm_s16le",
                output,
            ]
        )

    def _apply_mutes(self, project_dir: str, edit_decision: dict):
        mute_words = edit_decision.get("mute_words", [])
        if not mute_words:
            return

        edited_audio = os.path.join(project_dir, "edited_audio.wav")
        if not os.path.exists(edited_audio):
            logger.warning("[ScriptTrimAgent] edited_audio.wav not found for muting")
            return

        forbidden = load_forbidden_words()
        mute_positions = []

        for mw in mute_words:
            word = mw.get("word", "")
            action = mw.get("action", "mute")
            level = "high"
            for fw in forbidden:
                if fw["word"] == word:
                    level = fw["level"]
                    break

            if action == "mute" or level == "high":
                mute_positions.append(mw)

        if not mute_positions:
            return

        mute_filters = []
        for mp in mute_positions:
            start = mp.get("start", 0)
            end = mp.get("end", 0)
            if end > start:
                mute_filters.append(
                    f"volume=0:enable='between(t,{start:.3f},{end:.3f})'"
                )

        if not mute_filters:
            return

        filter_str = ",".join(mute_filters)
        muted_audio = os.path.join(project_dir, "edited_audio_muted.wav")
        self.ffmpeg._run(
            [
                self.ffmpeg.ffmpeg,
                "-y",
                "-i",
                edited_audio,
                "-af",
                filter_str,
                "-c:a",
                "pcm_s16le",
                muted_audio,
            ]
        )

        import shutil

        shutil.move(muted_audio, edited_audio)
        logger.info("[ScriptTrimAgent] applied %d mutes", len(mute_positions))

    def _check_target_duration(self, edit_decision: dict):
        duration = edit_decision.get("target_duration", 0)
        if duration < 10:
            logger.warning(
                "[ScriptTrimAgent] target duration %.1fs is very short",
                duration,
            )
