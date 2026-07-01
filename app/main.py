import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import upload, task, preview, export

settings = get_settings()
logger = logging.getLogger("AutoEdit")

app = FastAPI(
    title="AutoEdit",
    description="图文口播智能切片系统",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api/v1", tags=["upload"])
app.include_router(task.router, prefix="/api/v1", tags=["task"])
app.include_router(preview.router, prefix="/api/v1", tags=["preview"])
app.include_router(export.router, prefix="/api/v1", tags=["export"])


@app.get("/health")
async def health():
    from app.utils.logger import get_logger
    from app.services.ffmpeg_service import FFmpegService

    services = {}
    try:
        redis_url = settings.redis_url
        import redis as redis_lib

        r = redis_lib.from_url(redis_url)
        r.ping()
        services["redis"] = "connected"
    except Exception:
        services["redis"] = "disconnected"

    try:
        ff = FFmpegService()
        import subprocess

        result = subprocess.run(
            [ff.ffmpeg, "-version"], capture_output=True, text=True, timeout=5
        )
        services["ffmpeg"] = "available" if result.returncode == 0 else "unavailable"
    except Exception:
        services["ffmpeg"] = "unavailable"

    services["llm"] = "configured" if settings.llm_api_key else "not_configured"

    all_ok = all(
        v in ("connected", "available", "configured") for v in services.values()
    )

    return {
        "status": "healthy" if all_ok else "degraded",
        "version": "0.1.0",
        "services": services,
    }


@app.on_event("startup")
async def startup():
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.DEBUG),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("AutoEdit starting", extra={"env": settings.app_env})
