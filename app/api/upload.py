import uuid
import os
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form

from app.config import UPLOADS_DIR

logger = logging.getLogger("AutoEdit")
router = APIRouter()


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    platform: str = Form(default="douyin"),
    style: str = Form(default="business_tech"),
    target_duration: int = Form(default=90),
):
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    filename = file.filename or "input.mp4"
    ext = Path(filename).suffix or ".mp4"
    upload_dir = UPLOADS_DIR / project_id
    os.makedirs(upload_dir, exist_ok=True)
    file_path = upload_dir / f"input{ext}"

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(
        "Video uploaded: project_id=%s file=%s size=%.2fMB",
        project_id,
        filename,
        len(content) / 1024 / 1024,
    )

    return {
        "project_id": project_id,
        "status": "uploaded",
        "file_info": {
            "filename": filename,
            "size_mb": round(len(content) / 1024 / 1024, 2),
        },
        "params": {
            "platform": platform,
            "style": style,
            "target_duration": target_duration,
        },
    }
