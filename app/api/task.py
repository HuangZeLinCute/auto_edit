import logging

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.config import OUTPUTS_DIR, UPLOADS_DIR

logger = logging.getLogger("AutoEdit")
router = APIRouter()


@router.post("/task/{project_id}/start")
async def start_task(
    project_id: str,
    platform: str = "douyin",
    style: str = "business_tech",
    target_duration: int = 90,
):
    if not (UPLOADS_DIR / project_id).exists():
        return {
            "project_id": project_id,
            "status": "error",
            "message": "项目不存在，请先上传视频",
        }

    try:
        from app.workers.tasks import process_video

        process_video.delay(project_id)
    except (ImportError, AttributeError):
        from app.workers.tasks import process_video_sync
        import threading

        params = {
            "platform": platform,
            "style": style,
            "target_duration": target_duration,
        }

        def _run():
            process_video_sync(project_id, params=params)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    return {
        "project_id": project_id,
        "status": "processing",
        "params": {
            "platform": platform,
            "style": style,
            "target_duration": target_duration,
        },
        "message": "任务已启动",
    }


@router.get("/task/{project_id}/status")
async def get_status(project_id: str):
    output_dir = OUTPUTS_DIR / project_id

    step_checks = [
        ("preprocess", "transcript.json"),
        ("asr", "transcript.json"),
        ("analyze", "analysis.json"),
        ("select_clip", "clip_plan.json"),
        ("trim_script", "edit_decision.json"),
        ("generate_visuals", None),
        ("generate_subtitles", "subtitle_plan.json"),
        ("plan_audio", "audio_plan.json"),
        ("render", "render_result.json"),
        ("generate_titles", "output_package.json"),
    ]

    completed = []
    for step_name, fname in step_checks:
        if fname and (output_dir / fname).exists():
            completed.append(step_name)

    total = len(step_checks)
    progress = len(completed) / total if total > 0 else 0

    error = None
    cp_path = output_dir / "_checkpoint.json"
    if cp_path.exists():
        import json

        with open(cp_path, "r", encoding="utf-8") as f:
            ckpt = json.load(f)
        error = ckpt.get("error")

    status = (
        "completed"
        if "generate_titles" in completed
        else ("failed" if error else "processing")
    )

    return {
        "project_id": project_id,
        "status": status,
        "progress": round(progress, 2),
        "completed_steps": completed,
        "error": error,
    }


@router.get("/task/{project_id}/preview")
async def get_preview(project_id: str):
    import json

    output_dir = OUTPUTS_DIR / project_id
    clip_plan_path = output_dir / "clip_plan.json"

    if not clip_plan_path.exists():
        return {
            "project_id": project_id,
            "candidates": [],
            "message": "切片选择尚未完成",
        }

    with open(clip_plan_path, "r", encoding="utf-8") as f:
        clip_plan = json.load(f)

    candidates = clip_plan.get("candidates", [])
    preview_list = []
    for c in candidates:
        preview_list.append(
            {
                "clip_id": c.get("clip_id", ""),
                "topic": c.get("topic", ""),
                "duration": c.get("duration", 0),
                "score": c.get("final_score", c.get("score", 0)),
                "hook_text": c.get("hook", {}).get("text", ""),
                "reason": c.get("reason", ""),
            }
        )

    analysis_path = output_dir / "analysis.json"
    analysis = {}
    if analysis_path.exists():
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis = json.load(f)

    return {
        "project_id": project_id,
        "candidates": preview_list,
        "chapters": analysis.get("chapters", []),
        "golden_sentences": analysis.get("golden_sentences", []),
    }


@router.post("/task/{project_id}/render")
async def render(project_id: str, clip_index: int = 0, platform: str = "douyin"):
    output_dir = OUTPUTS_DIR / project_id
    result_path = output_dir / "output_package.json"

    if result_path.exists():
        import json

        with open(result_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
        return {"project_id": project_id, "status": "completed", "result": pkg}

    return {
        "project_id": project_id,
        "status": "not_ready",
        "message": "请先启动处理任务",
    }


@router.get("/task/{project_id}/result/{clip_id}")
async def get_result(project_id: str, clip_id: str):
    import json

    output_dir = OUTPUTS_DIR / project_id
    pkg_path = output_dir / "output_package.json"

    if not pkg_path.exists():
        return {"project_id": project_id, "clip_id": clip_id, "status": "not_found"}

    with open(pkg_path, "r", encoding="utf-8") as f:
        pkg = json.load(f)

    render_path = output_dir / "render_result.json"
    render_info = {}
    if render_path.exists():
        with open(render_path, "r", encoding="utf-8") as f:
            render_info = json.load(f)

    return {
        "project_id": project_id,
        "clip_id": clip_id,
        "status": "completed",
        "video": render_info,
        "titles": pkg.get("titles", {}),
        "cover_texts": pkg.get("cover_texts", []),
        "topics": pkg.get("topics", []),
        "descriptions": pkg.get("descriptions", []),
    }


@router.get("/download/{project_id}/{clip_id}/{filename}")
async def download_file(project_id: str, clip_id: str, filename: str):
    output_dir = OUTPUTS_DIR / project_id
    file_path = output_dir / filename

    if not file_path.exists():
        file_path = output_dir / "render" / filename

    if not file_path.exists():
        file_path = output_dir / "trim" / filename

    if not file_path.exists():
        return {"error": f"文件 {filename} 不存在"}

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )
