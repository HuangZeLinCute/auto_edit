import os
import shutil
import logging
from pathlib import Path

from app.config import UPLOADS_DIR, OUTPUTS_DIR, TEMP_DIR

logger = logging.getLogger("AutoEdit")


class StorageService:
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or UPLOADS_DIR.parent

    def get_upload_dir(self, project_id: str) -> Path:
        d = UPLOADS_DIR / project_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_output_dir(self, project_id: str) -> Path:
        d = OUTPUTS_DIR / project_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_temp_dir(self, project_id: str) -> Path:
        d = TEMP_DIR / project_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_upload(self, project_id: str, filename: str, content: bytes) -> str:
        d = self.get_upload_dir(project_id)
        path = d / filename
        path.write_bytes(content)
        logger.info("Saved upload: %s (%d bytes)", path, len(content))
        return str(path)

    def save_output(self, project_id: str, filename: str, content: bytes) -> str:
        d = self.get_output_dir(project_id)
        path = d / filename
        path.write_bytes(content)
        return str(path)

    def save_json(self, project_id: str, filename: str, data: dict) -> str:
        import json

        d = self.get_output_dir(project_id)
        path = d / filename
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return str(path)

    def load_json(self, project_id: str, filename: str) -> dict:
        import json

        path = self.get_output_dir(project_id) / filename
        return json.loads(path.read_text(encoding="utf-8"))

    def file_exists(self, project_id: str, filename: str) -> bool:
        path = self.get_output_dir(project_id) / filename
        return path.exists()

    def list_outputs(self, project_id: str) -> list[str]:
        d = self.get_output_dir(project_id)
        return [f.name for f in d.iterdir() if f.is_file()]

    def cleanup_temp(self, project_id: str):
        d = TEMP_DIR / project_id
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            logger.info("Cleaned temp: %s", d)

    def get_output_path(self, project_id: str, filename: str) -> str:
        return str(self.get_output_dir(project_id) / filename)
