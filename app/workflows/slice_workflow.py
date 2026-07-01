import json
import os
import logging
from typing import TypedDict, Optional, Annotated
from pathlib import Path

from langgraph.graph import StateGraph, END

from app.services.ffmpeg_service import FFmpegService
from app.services.whisper_service import WhisperService
from app.services.llm_service import LLMService
from app.services.storage_service import StorageService
from app.config import UPLOADS_DIR, OUTPUTS_DIR, TEMP_DIR

logger = logging.getLogger("AutoEdit")


class PipelineState(TypedDict, total=False):
    project_id: str
    source_video: str
    audio_path: str
    params: dict
    transcript: dict
    analysis: dict
    clip_plan: dict
    selected_clip_id: str
    clip_outputs: list
    edit_decision: dict
    subtitle_plan: dict
    audio_plan: dict
    render_result: dict
    output_package: dict
    current_step: str
    completed_steps: list
    error: Optional[str]


def _project_dir(project_id: str) -> str:
    d = OUTPUTS_DIR / project_id
    os.makedirs(d, exist_ok=True)
    return str(d)


def _save_json(project_id: str, filename: str, data: dict) -> str:
    path = os.path.join(_project_dir(project_id), filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def _format_user_intent(params: dict) -> str:
    user_intent = (params or {}).get("user_intent", "")
    user_intent = str(user_intent).strip()
    if not user_intent:
        return "用户没有提供额外剪辑需求，请按默认爆款短视频标准决策。"
    return (
        "用户剪辑需求：\n"
        f"{user_intent}\n\n"
        "请优先满足该需求：选片主题、开头钩子、保留/删除内容、目标时长、语气风格和标题方向都要围绕它。"
    )


def _clip_project_id(project_id: str, clip_id: str, index: int) -> str:
    safe_clip_id = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(clip_id or "")
    ).strip("_")
    if not safe_clip_id:
        safe_clip_id = f"clip_{index + 1:03d}"
    return f"{project_id}/clips/{safe_clip_id}"


def _clip_plan_for_clip(clip: dict, base_clip_plan: dict) -> dict:
    result = dict(base_clip_plan or {})
    result["candidates"] = [clip]
    return result


def _load_checkpoint(project_id: str) -> Optional[dict]:
    path = OUTPUTS_DIR / project_id / "_checkpoint.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_checkpoint(project_id: str, state: dict):
    cp = OUTPUTS_DIR / project_id / "_checkpoint.json"
    saveable = {}
    for k, v in state.items():
        if k in (
            "completed_steps",
            "current_step",
            "project_id",
            "selected_clip_id",
            "error",
            "params",
            "source_video",
        ):
            saveable[k] = v
        elif isinstance(v, dict):
            saveable[k] = True
        elif isinstance(v, str):
            saveable[k] = v
    with open(cp, "w", encoding="utf-8") as f:
        json.dump(saveable, f, ensure_ascii=False, indent=2)


ffmpeg_svc = FFmpegService()
whisper_svc = WhisperService()
llm_svc = LLMService()
storage_svc = StorageService()


def preprocess_node(state: dict) -> dict:
    logger.info("[preprocess] project_id=%s", state["project_id"])
    try:
        project_id = state["project_id"]
        params = state.get("params", {})
        source_video = params.get("source_video") or state.get("source_video", "")

        if source_video:
            source_video = str(Path(source_video).expanduser())
            if not os.path.exists(source_video):
                state["error"] = f"本地视频文件不存在: {source_video}"
                return state
        else:
            upload_dir = UPLOADS_DIR / project_id
            video_files = list(upload_dir.glob("input.*"))
            if not video_files:
                state["error"] = "未找到上传的视频文件"
                return state
            source_video = str(video_files[0])

        audio_path = str(TEMP_DIR / project_id / "audio.wav")
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)

        ffmpeg_svc.extract_audio(source_video, audio_path)

        state["source_video"] = source_video
        state["audio_path"] = audio_path
        state["current_step"] = "preprocess"
        logger.info("[preprocess] 完成 audio=%s", audio_path)
    except Exception as e:
        state["error"] = str(e)
        logger.error("[preprocess] 失败: %s", e)
    return state


def asr_node(state: dict) -> dict:
    logger.info("[asr] project_id=%s", state["project_id"])
    try:
        transcript = whisper_svc.transcribe(state["audio_path"])
        state["transcript"] = transcript
        _save_json(state["project_id"], "transcript.json", transcript)
        state["current_step"] = "asr"
        logger.info("[asr] 完成 segments=%d", len(transcript["segments"]))
    except Exception as e:
        state["error"] = str(e)
        logger.error("[asr] 失败: %s", e)
    return state


def analyze_node(state: dict) -> dict:
    logger.info("[analyze] project_id=%s", state["project_id"])
    try:
        prompt_template = llm_svc.load_prompt("analyze")
        transcript_json = json.dumps(
            state["transcript"]["segments"], ensure_ascii=False, indent=2
        )
        user_prompt = prompt_template.replace("{transcript}", transcript_json)

        analysis = llm_svc.chat_json(
            system_prompt="你是专业的短视频内容分析师。请严格按照要求的 JSON 格式输出。",
            user_prompt=user_prompt,
        )
        analysis["project_id"] = state["project_id"]

        state["analysis"] = analysis
        _save_json(state["project_id"], "analysis.json", analysis)
        state["current_step"] = "analyze"
        logger.info("[analyze] 完成 topics=%d", len(analysis.get("main_topics", [])))
    except Exception as e:
        state["error"] = str(e)
        logger.error("[analyze] 失败: %s", e)
    return state


def select_clip_node(state: dict) -> dict:
    logger.info("[select_clip] project_id=%s", state["project_id"])
    try:
        params = state.get("params", {})
        prompt_template = llm_svc.load_prompt("clip_select")
        analysis_json = json.dumps(state["analysis"], ensure_ascii=False, indent=2)
        transcript_json = json.dumps(
            state["transcript"]["segments"], ensure_ascii=False, indent=2
        )
        user_prompt = (
            _format_user_intent(params)
            + "\n\n"
            + prompt_template.replace("{analysis}", analysis_json).replace(
                "{transcript}", transcript_json
            )
        )

        clip_plan = llm_svc.chat_json(
            system_prompt="你是短视频切片编导。请严格按照要求的 JSON 格式输出。",
            user_prompt=user_prompt,
        )
        clip_plan["project_id"] = state["project_id"]
        if params.get("user_intent"):
            clip_plan["user_intent"] = params.get("user_intent")

        candidates = clip_plan.get("candidates", [])
        all_candidates = list(candidates)

        valid = [
            c
            for c in candidates
            if c.get("hook")
            and c.get("duration", 0) >= 10
            and "放弃" not in c.get("reason", "")
        ]

        if not valid:
            valid = [c for c in candidates if c.get("hook")]
        if not valid:
            valid = [c for c in candidates if "放弃" not in c.get("reason", "")]
        if not valid:
            valid = all_candidates[:1]
        if not valid:
            default = {
                "clip_id": "fallback",
                "topic": state.get("analysis", {})
                .get("summaries", [{}])[0]
                .get("topic", "精彩片段"),
                "source_start": 60,
                "source_end": 180,
                "duration": 120,
                "hook": {"start": 60, "end": 65, "text": "精彩内容"},
                "scores": {},
            }
            valid = [default]
            logger.warning("[select_clip] using fallback candidate")

        clip_plan["candidates"] = valid
        candidates = valid

        if candidates:
            state["selected_clip_id"] = candidates[0]["clip_id"]

        state["clip_plan"] = clip_plan
        _save_json(state["project_id"], "clip_plan.json", clip_plan)
        state["current_step"] = "select_clip"
        logger.info(
            "[select_clip] 完成 candidates=%d (过滤后=%d)",
            len(clip_plan.get("candidates", [])),
            len(candidates),
        )
    except Exception as e:
        state["error"] = str(e)
        logger.error("[select_clip] 失败: %s", e)
    return state


def trim_script_node(state: dict) -> dict:
    logger.info("[trim_script] project_id=%s", state["project_id"])
    try:
        from app.agents.script_trim_agent import ScriptTrimAgent

        params = state.get("params", {})
        batch_clip_count = int(params.get("batch_clip_count") or 1)
        candidates = state["clip_plan"].get("candidates", [])
        candidates.sort(
            key=lambda c: (
                c.get("scores", {}).get("completeness_score", 0)
                + c.get("duration", 0) * 0.1
            ),
            reverse=True,
        )

        if not candidates:
            state["error"] = "未找到有效候选切片（无hook）"
            return state

        agent = ScriptTrimAgent()
        clip_outputs = []
        best_decision = None

        for clip in candidates:
            if len(clip_outputs) >= batch_clip_count:
                break
            if not clip.get("source_start") or not clip.get("source_end"):
                logger.warning(
                    "[trim_script] clip %s missing source times, skipping",
                    clip.get("clip_id"),
                )
                continue
            logger.info(
                "[trim_script] trying clip_id=%s topic=%s duration=%.1f",
                clip.get("clip_id", ""),
                clip.get("topic", ""),
                clip.get("duration", 0),
            )
            try:
                clip_index = len(clip_outputs)
                clip_project_id = _clip_project_id(
                    state["project_id"], clip.get("clip_id", ""), clip_index
                )
                decision = agent.run(
                    project_id=clip_project_id,
                    clip=clip,
                    transcript=state["transcript"],
                    source_video=state["source_video"],
                    audio_path=state["audio_path"],
                    user_intent=params.get("user_intent", ""),
                )
                dur = decision.get("target_duration", 0)
                if dur >= 5:
                    clip_output = {
                        "project_id": clip_project_id,
                        "clip_id": clip.get("clip_id", f"clip_{clip_index + 1:03d}"),
                        "clip": clip,
                        "edit_decision": decision,
                        "status": "trimmed",
                    }
                    clip_outputs.append(clip_output)
                    if best_decision is None:
                        state["selected_clip_id"] = clip_output["clip_id"]
                        best_decision = decision
                    logger.info(
                        "[trim_script] accepted clip %s (%.1fs) [%d/%d]",
                        clip.get("clip_id"),
                        dur,
                        len(clip_outputs),
                        batch_clip_count,
                    )
                    continue

                if best_decision is None or dur > best_decision.get(
                    "target_duration", 0
                ):
                    best_decision = decision
                    state["selected_clip_id"] = clip.get("clip_id", "")
                logger.warning(
                    "[trim_script] clip %s too short (%.1fs), trying next",
                    clip.get("clip_id"),
                    dur,
                )
            except Exception as e:
                logger.warning(
                    "[trim_script] clip %s failed: %s", clip.get("clip_id"), e
                )

        if best_decision is None:
            state["error"] = "所有候选切片裁剪失败"
            return state

        if not clip_outputs:
            state["error"] = "未生成有效切片"
            return state

        state["clip_outputs"] = clip_outputs
        state["edit_decision"] = best_decision
        state["current_step"] = "trim_script"
        logger.info(
            "[trim_script] 完成 clips=%d selected=%s dur=%.1f",
            len(clip_outputs),
            state.get("selected_clip_id"),
            best_decision.get("target_duration", 0),
        )
    except Exception as e:
        state["error"] = str(e)
        logger.error("[trim_script] 失败: %s", e)
    return state


def generate_visuals_node(state: dict) -> dict:
    logger.info(
        "[generate_visuals] project_id=%s (跳过 - 图片生成待接入)", state["project_id"]
    )
    state["current_step"] = "generate_visuals"
    return state


def generate_subtitles_node(state: dict) -> dict:
    logger.info("[generate_subtitles] project_id=%s", state["project_id"])
    try:
        from app.agents.subtitle_agent import SubtitleAgent

        agent = SubtitleAgent()
        clip_outputs = state.get("clip_outputs") or []
        if clip_outputs:
            for clip_output in clip_outputs:
                result = agent.run(
                    project_id=clip_output["project_id"],
                    edit_decision=clip_output.get("edit_decision", {}),
                    transcript=state["transcript"],
                )
                clip_output["subtitle_plan"] = result
            state["subtitle_plan"] = clip_outputs[0].get("subtitle_plan", {})
        else:
            result = agent.run(
                project_id=state["project_id"],
                edit_decision=state.get("edit_decision", {}),
                transcript=state["transcript"],
            )
            state["subtitle_plan"] = result
        state["current_step"] = "generate_subtitles"
        logger.info(
            "[generate_subtitles] 完成: %d 个切片", len(clip_outputs) or 1
        )
    except Exception as e:
        state["error"] = str(e)
        logger.error("[generate_subtitles] 失败: %s", e)
    return state


def plan_audio_node(state: dict) -> dict:
    logger.info("[plan_audio] project_id=%s (仅标准化人声)", state["project_id"])
    try:
        import os
        import shutil

        def build_audio_plan(project_id: str) -> dict:
            project_dir = _project_dir(project_id)
            trim_dir = os.path.join(project_dir, "trim")
            edited_audio = os.path.join(trim_dir, "edited_audio.wav")

            audio_dir = os.path.join(project_dir, "audio")
            os.makedirs(audio_dir, exist_ok=True)
            final_audio = os.path.join(audio_dir, "final_audio.wav")

            if os.path.exists(edited_audio):
                try:
                    ffmpeg_svc.normalize_audio(edited_audio, final_audio, target_db=-1.0)
                except Exception:
                    shutil.copy2(edited_audio, final_audio)
            else:
                raise FileNotFoundError(f"edited_audio.wav 不存在: {edited_audio}")

            result = {
                "project_id": project_id,
                "mixed_audio_path": final_audio,
                "sfx_count": 0,
                "bgm_plan": {},
                "note": "音效/BGM 已弃用，仅标准化人声",
            }
            _save_json(project_id, "audio_plan.json", result)
            return result

        clip_outputs = state.get("clip_outputs") or []
        if clip_outputs:
            for clip_output in clip_outputs:
                clip_output["audio_plan"] = build_audio_plan(clip_output["project_id"])
            result = clip_outputs[0].get("audio_plan", {})
        else:
            result = build_audio_plan(state["project_id"])

        state["audio_plan"] = result
        state["current_step"] = "plan_audio"
        logger.info("[plan_audio] 完成: %d 个切片", len(clip_outputs) or 1)
    except Exception as e:
        state["error"] = str(e)
        logger.error("[plan_audio] 失败: %s", e)
    return state


def render_node(state: dict) -> dict:
    logger.info("[render] project_id=%s", state["project_id"])
    try:
        params = state.get("params", {})
        platform = params.get("platform", "douyin")
        platform_preset = _get_platform_preset(platform)

        def render_one(
            project_id: str,
            edit_decision: dict,
            audio_plan: dict,
            subtitle_plan: dict,
        ) -> dict:
            project_dir = _project_dir(project_id)
            trim_dir = os.path.join(project_dir, "trim")

            final_audio = audio_plan.get("mixed_audio_path", "")
            if not final_audio or not os.path.exists(final_audio):
                fallback = os.path.join(trim_dir, "edited_audio.wav")
                if os.path.exists(fallback):
                    final_audio = fallback
                else:
                    raise FileNotFoundError(f"无可用音频: {project_id}")

            render_dir = os.path.join(project_dir, "render")
            os.makedirs(render_dir, exist_ok=True)

            target_duration = edit_decision.get("target_duration", 0)
            video_segments = edit_decision.get("video_segments", [])
            video_only = os.path.join(render_dir, "video_only.mp4")

            if video_segments and all(os.path.exists(vf) for vf in video_segments):
                ffmpeg_svc.concat_videos(video_segments, video_only)
                logger.info("[render] 视频拼接: %d segments -> %s", len(video_segments), project_id)
            else:
                ffmpeg_svc._run(
                    [
                        ffmpeg_svc.ffmpeg,
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        f"color=c=black:s=1080x1920:d={target_duration:.2f}:r=30",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-preset",
                        "ultrafast",
                        video_only,
                    ]
                )
                logger.warning("[render] 无视频片段, 使用黑底: %s", project_id)

            with_audio = os.path.join(render_dir, "with_audio.mp4")
            ffmpeg_svc.mux_audio_video(video_only, final_audio, with_audio)

            subtitle_path = subtitle_plan.get("subtitle_path", "")
            final_video = with_audio
            if subtitle_path and os.path.exists(subtitle_path):
                burned = os.path.join(render_dir, "subtitled.mp4")
                try:
                    ffmpeg_svc.burn_subtitles(with_audio, subtitle_path, burned)
                    final_video = burned
                except Exception as e:
                    logger.warning("[render] 字幕烧录失败: %s", e)

            output_video = os.path.join(project_dir, "output.mp4")
            _transcode_output(final_video, output_video, platform_preset)

            video_dur = ffmpeg_svc.get_duration(output_video)
            file_size = os.path.getsize(output_video)
            render_result = {
                "project_id": project_id,
                "video_path": output_video,
                "duration": video_dur,
                "file_size": file_size,
                "platform": platform,
                "resolution": platform_preset.get("resolution", "1080x1920"),
            }
            _save_json(project_id, "render_result.json", render_result)
            return render_result

        clip_outputs = state.get("clip_outputs") or []
        if clip_outputs:
            for clip_output in clip_outputs:
                clip_output["render_result"] = render_one(
                    clip_output["project_id"],
                    clip_output.get("edit_decision", {}),
                    clip_output.get("audio_plan", {}),
                    clip_output.get("subtitle_plan", {}),
                )
            state["render_result"] = clip_outputs[0].get("render_result", {})
        else:
            state["render_result"] = render_one(
                state["project_id"],
                state.get("edit_decision", {}),
                state.get("audio_plan", {}),
                state.get("subtitle_plan", {}),
            )

        state["current_step"] = "render"
        logger.info("[render] 完成: %d 个切片", len(clip_outputs) or 1)
    except Exception as e:
        state["error"] = str(e)
        logger.error("[render] 失败: %s", e)
    return state


def generate_titles_node(state: dict) -> dict:
    logger.info("[generate_titles] project_id=%s", state["project_id"])
    try:
        from app.agents.title_agent import TitleAgent

        params = state.get("params", {})
        agent = TitleAgent()
        clip_outputs = state.get("clip_outputs") or []
        if clip_outputs:
            packages = []
            for index, clip_output in enumerate(clip_outputs):
                clip = clip_output.get("clip", {})
                titles_data = agent.run(
                    project_id=clip_output["project_id"],
                    edit_decision=clip_output.get("edit_decision", {}),
                    clip_plan=_clip_plan_for_clip(clip, state.get("clip_plan", {})),
                    user_intent=params.get("user_intent", ""),
                )
                package = {
                    "project_id": clip_output["project_id"],
                    "parent_project_id": state["project_id"],
                    "clip_id": clip_output.get("clip_id", f"clip_{index + 1:03d}"),
                    "clip_index": index + 1,
                    "topic": clip.get("topic", ""),
                    "viewpoint": clip.get("reason", ""),
                    "source_start": clip.get("source_start", 0),
                    "source_end": clip.get("source_end", 0),
                    "video": clip_output.get("render_result", {}),
                    "titles": titles_data.get("titles", {}),
                    "cover_texts": titles_data.get("cover_texts", []),
                    "topics": titles_data.get("topics", []),
                    "descriptions": titles_data.get("descriptions", []),
                }
                clip_output["titles"] = titles_data
                clip_output["output_package"] = package
                _save_json(clip_output["project_id"], "output_package.json", package)
                packages.append(package)

            output_package = {
                "project_id": state["project_id"],
                "user_intent": params.get("user_intent", ""),
                "clip_count": len(packages),
                "clips": packages,
                "video": packages[0].get("video", {}) if packages else {},
                "titles": packages[0].get("titles", {}) if packages else {},
                "cover_texts": packages[0].get("cover_texts", []) if packages else [],
                "topics": packages[0].get("topics", []) if packages else [],
                "descriptions": packages[0].get("descriptions", []) if packages else [],
            }
        else:
            titles_data = agent.run(
                project_id=state["project_id"],
                edit_decision=state.get("edit_decision", {}),
                clip_plan=state.get("clip_plan", {}),
                user_intent=params.get("user_intent", ""),
            )
            output_package = {
                "project_id": state["project_id"],
                "user_intent": params.get("user_intent", ""),
                "clip_id": state.get("selected_clip_id", ""),
                "video": state.get("render_result", {}),
                "titles": titles_data.get("titles", {}),
                "cover_texts": titles_data.get("cover_texts", []),
                "topics": titles_data.get("topics", []),
                "descriptions": titles_data.get("descriptions", []),
            }
        state["output_package"] = output_package
        _save_json(state["project_id"], "output_package.json", output_package)
        state["current_step"] = "generate_titles"
        logger.info("[generate_titles] 完成: %d 个切片", len(clip_outputs) or 1)
    except Exception as e:
        state["error"] = str(e)
        logger.error("[generate_titles] 失败: %s", e)
    return state


def _get_platform_preset(platform: str) -> dict:
    import yaml
    from app.config import CONFIGS_DIR

    path = CONFIGS_DIR / "platform_presets.yaml"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get(platform, data.get("douyin", {}))
    return {
        "resolution": "1080x1920",
        "video_codec": "libx264",
        "audio_codec": "aac",
        "audio_bitrate": "128k",
        "crf": 23,
    }


def _transcode_output(input_path: str, output_path: str, preset: dict):
    cmd = [
        ffmpeg_svc.ffmpeg,
        "-y",
        "-i",
        input_path,
        "-c:v",
        preset.get("video_codec", "libx264"),
        "-preset",
        "ultrafast",
        "-crf",
        str(preset.get("crf", 28)),
        "-r",
        str(preset.get("fps", 30)),
        "-threads",
        "1",
        "-refs",
        "1",
        "-c:a",
        preset.get("audio_codec", "aac"),
        "-b:a",
        preset.get("audio_bitrate", "128k"),
        output_path,
    ]
    ffmpeg_svc._run(cmd)


def _should_continue(state: dict) -> str:
    if state.get("error"):
        return "end"
    return "continue"


def build_graph() -> StateGraph:
    graph = StateGraph(dict)

    graph.add_node("preprocess", preprocess_node)
    graph.add_node("asr", asr_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("select_clip", select_clip_node)
    graph.add_node("trim_script", trim_script_node)
    graph.add_node("generate_visuals", generate_visuals_node)
    graph.add_node("generate_subtitles", generate_subtitles_node)
    graph.add_node("plan_audio", plan_audio_node)
    graph.add_node("render", render_node)
    graph.add_node("generate_titles", generate_titles_node)

    graph.set_entry_point("preprocess")

    graph.add_conditional_edges(
        "preprocess",
        _should_continue,
        {"continue": "asr", "end": END},
    )
    graph.add_conditional_edges(
        "asr",
        _should_continue,
        {"continue": "analyze", "end": END},
    )
    graph.add_conditional_edges(
        "analyze",
        _should_continue,
        {"continue": "select_clip", "end": END},
    )
    graph.add_conditional_edges(
        "select_clip",
        _should_continue,
        {"continue": "trim_script", "end": END},
    )
    graph.add_conditional_edges(
        "trim_script",
        _should_continue,
        {"continue": "generate_visuals", "end": END},
    )
    graph.add_conditional_edges(
        "generate_visuals",
        _should_continue,
        {"continue": "generate_subtitles", "end": END},
    )
    graph.add_conditional_edges(
        "generate_subtitles",
        _should_continue,
        {"continue": "plan_audio", "end": END},
    )
    graph.add_conditional_edges(
        "plan_audio",
        _should_continue,
        {"continue": "render", "end": END},
    )
    graph.add_conditional_edges(
        "render",
        _should_continue,
        {"continue": "generate_titles", "end": END},
    )
    graph.add_edge("generate_titles", END)

    return graph


_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        graph = build_graph()
        _pipeline = graph.compile()
    return _pipeline


def run_full_pipeline(project_id: str, params: Optional[dict] = None) -> dict:
    checkpoint = _load_checkpoint(project_id)
    completed = checkpoint.get("completed_steps", []) if checkpoint else []

    state: dict = {
        "project_id": project_id,
        "params": params or {},
        "completed_steps": completed,
        "current_step": "preprocess",
        "error": None,
    }

    pipeline = get_pipeline()
    result = pipeline.invoke(state)

    if not result.get("error"):
        result["completed_steps"] = completed + [
            "preprocess",
            "asr",
            "analyze",
            "select_clip",
            "trim_script",
            "generate_visuals",
            "generate_subtitles",
            "plan_audio",
            "render",
            "generate_titles",
        ]
        _save_checkpoint(project_id, result)

    return result


def resume_pipeline(project_id: str) -> dict:
    checkpoint = _load_checkpoint(project_id)
    if not checkpoint:
        return {"error": f"项目 {project_id} 无检查点记录，无法续跑"}

    completed = checkpoint.get("completed_steps", [])
    if "generate_titles" in completed:
        return {"error": "该项目已完成，无需续跑"}

    logger.info("[resume] project_id=%s 从步骤 %s 继续", project_id, completed)

    state: dict = {
        "project_id": project_id,
        "params": checkpoint.get("params", {}),
        "completed_steps": completed,
        "current_step": checkpoint.get("current_step", "preprocess"),
        "error": None,
    }

    step_files = {
        "preprocess": ("transcript.json", None),
        "asr": ("transcript.json", "transcript"),
        "analyze": ("analysis.json", "analysis"),
        "select_clip": ("clip_plan.json", "clip_plan"),
        "trim_script": ("edit_decision.json", "edit_decision"),
        "generate_subtitles": ("subtitle_plan.json", "subtitle_plan"),
        "plan_audio": ("audio_plan.json", "audio_plan"),
        "render": ("render_result.json", "render_result"),
    }

    project_dir = _project_dir(project_id)
    for step, (fname, key) in step_files.items():
        if step in completed:
            continue
        fpath = os.path.join(project_dir, fname)
        if os.path.exists(fpath) and key:
            with open(fpath, "r", encoding="utf-8") as f:
                state[key] = json.load(f)

    if checkpoint.get("source_video"):
        state["source_video"] = checkpoint["source_video"]
    else:
        upload_dir = UPLOADS_DIR / project_id
        video_files = list(upload_dir.glob("input.*"))
        if video_files:
            state["source_video"] = str(video_files[0])

    audio_path = str(TEMP_DIR / project_id / "audio.wav")
    if os.path.exists(audio_path):
        state["audio_path"] = audio_path

    candidates = state.get("clip_plan", {}).get("candidates", [])
    if candidates:
        state["selected_clip_id"] = candidates[0].get("clip_id", "")

    pipeline = get_pipeline()
    result = pipeline.invoke(state)

    if not result.get("error"):
        _save_checkpoint(project_id, result)

    return result
