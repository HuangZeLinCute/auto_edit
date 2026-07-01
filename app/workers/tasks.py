import logging

from app.workflows.slice_workflow import run_full_pipeline

logger = logging.getLogger("AutoEdit")

try:
    from app.workers.celery_app import celery_app

    @celery_app.task(bind=True, name="process_video")
    def process_video(self, project_id: str, params: dict = None):
        logger.info("Celery task started: project_id=%s", project_id)
        try:
            self.update_state(state="PROCESSING", meta={"step": "preprocess"})
            result = run_full_pipeline(project_id, params=params)

            if result.get("error"):
                self.update_state(state="FAILURE", meta={"error": result["error"]})
                return {"status": "failed", "error": result["error"]}

            self.update_state(state="SUCCESS", meta={"project_id": project_id})
            return {"status": "completed", "project_id": project_id}
        except Exception as e:
            logger.error("Task failed: project_id=%s error=%s", project_id, e)
            self.update_state(state="FAILURE", meta={"error": str(e)})
            return {"status": "failed", "error": str(e)}

except ImportError:
    logger.warning("Celery not available, creating synchronous fallback")

    def process_video_sync(project_id: str, params: dict = None):
        logger.info("Sync task started: project_id=%s", project_id)
        try:
            result = run_full_pipeline(project_id, params=params)
            if result.get("error"):
                return {"status": "failed", "error": result["error"]}
            return {"status": "completed", "project_id": project_id}
        except Exception as e:
            logger.error("Task failed: project_id=%s error=%s", project_id, e)
            return {"status": "failed", "error": str(e)}
