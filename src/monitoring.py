"""Scheduled news monitoring service with APScheduler."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.api import create_app
from src.config import get_settings
from src.database import get_database
from src.evidence_analyzer import EvidenceAnalyzer
from src.evidence_retrieval import EvidenceRetriever
from src.input_processor import InputProcessor
from src.language_detector import LanguageDetector
from src.predictor import NewsClassifier
from src.translation_service import TranslationService

LOGGER = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: BackgroundScheduler | None = None
_app_instance = None


class MonitoringService:
    """Background monitoring service for scheduled news verification."""

    def __init__(
        self,
        scheduler: BackgroundScheduler | None = None,
        app_factory: Callable[[], Any] | None = None,
    ):
        global _app_instance
        self.scheduler = scheduler or BackgroundScheduler()
        self.app_factory = app_factory or (lambda: create_app())
        self._app = None
        self._initialized = False
        self.jobs: dict[str, dict[str, Any]] = {}

    def _get_app(self):
        """Get or create app instance."""
        if self._app is None:
            self._app = self.app_factory()
        return self._app

    def start(self) -> None:
        """Start the scheduler."""
        if not self._initialized:
            self._initialized = True
        if not self.scheduler.running:
            self.scheduler.start()
            LOGGER.info("Monitoring scheduler started")

    def stop(self, wait: bool = True) -> None:
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            LOGGER.info("Monitoring scheduler stopped")

    def add_monitoring_job(
        self,
        job_id: str,
        query: str,
        schedule: str | dict[str, Any],
        callback: Optional[Callable[[dict[str, Any]], None]] = None,
        **kwargs: Any,
    ) -> str:
        """Add a scheduled monitoring job.

        Args:
            job_id: Unique identifier for the job
            query: Search query or topic to monitor
            schedule: Cron expression (str) or interval dict (e.g., {"hours": 1})
            callback: Optional callback function to process results
            **kwargs: Additional job options

        Returns:
            Job ID
        """
        app = self._get_app()

        def run_verification():
            """Execute verification for the monitored query."""
            correlation_id = str(uuid.uuid4())[:8]
            LOGGER.info(
                "Running scheduled verification",
                extra={"correlation_id": correlation_id, "job_id": job_id, "query": query},
            )

            try:
                # Run the verification pipeline
                with app.container() as container:
                    # We need to call the verify endpoint logic directly
                    # For now, we'll use the evidence retriever and analyzer
                    from src.evidence_retrieval import build_search_query

                    retriever = app.state.evidence_retriever
                    analyzer = app.state.evidence_analyzer

                    search_query = build_search_query(query)
                    retrieval = retriever.retrieve(query, 1)

                    if retrieval.get("evidence"):
                        analysis = analyzer.analyze(
                            claim=query,
                            claim_id=1,
                            evidence=retrieval["evidence"],
                            retrieval_status=retrieval.get("retrieval_status", "completed"),
                        )

                        result = {
                            "job_id": job_id,
                            "query": query,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "verdict": analysis.get("verdict"),
                            "confidence": analysis.get("confidence"),
                            "explanation": analysis.get("explanation"),
                            "evidence_count": len(retrieval["evidence"]),
                        }

                        if callback:
                            callback(result)

                        LOGGER.info(
                            "Scheduled verification completed",
                            extra={"correlation_id": correlation_id, **result},
                        )
                    else:
                        LOGGER.info(
                            "No evidence found for scheduled query",
                            extra={"correlation_id": correlation_id, "job_id": job_id, "query": query},
                        )
            except Exception as exc:
                LOGGER.exception(
                    "Scheduled verification failed",
                    extra={"correlation_id": correlation_id, "job_id": job_id, "query": query},
                )

        # Parse schedule
        trigger = None
        if isinstance(schedule, str):
            # Cron expression
            trigger = CronTrigger.from_crontab(schedule)
        elif isinstance(schedule, dict):
            # Interval schedule
            trigger = IntervalTrigger(**schedule)
        else:
            raise ValueError("Schedule must be cron string or interval dict")

        # Add job to scheduler
        self.scheduler.add_job(
            run_verification,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            **kwargs,
        )

        self.jobs[job_id] = {
            "query": query,
            "schedule": schedule,
            "callback": callback,
            "next_run": None,
        }

        LOGGER.info(
            "Added monitoring job",
            extra={"job_id": job_id, "query": query, "schedule": schedule},
        )
        return job_id

    def remove_job(self, job_id: str) -> bool:
        """Remove a monitoring job."""
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self.jobs:
                del self.jobs[job_id]
            LOGGER.info("Removed monitoring job", extra={"job_id": job_id})
            return True
        except Exception:
            LOGGER.exception("Failed to remove job", extra={"job_id": job_id})
            return False

    def get_jobs(self) -> list[dict[str, Any]]:
        """Get all scheduled jobs with their status."""
        jobs_info = []
        for job in self.scheduler.get_jobs():
            job_info = {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            if job.id in self.jobs:
                job_info.update(self.jobs[job.id])
            jobs_info.append(job_info)
        return jobs_info

    def pause_job(self, job_id: str) -> bool:
        """Pause a monitoring job."""
        try:
            self.scheduler.pause_job(job_id)
            LOGGER.info("Paused monitoring job", extra={"job_id": job_id})
            return True
        except Exception:
            LOGGER.exception("Failed to pause job", extra={"job_id": job_id})
            return False

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused monitoring job."""
        try:
            self.scheduler.resume_job(job_id)
            LOGGER.info("Resumed monitoring job", extra={"job_id": job_id})
            return True
        except Exception:
            LOGGER.exception("Failed to resume job", extra={"job_id": job_id})
            return False


def get_scheduler() -> BackgroundScheduler:
    """Get global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        settings = get_settings()
        _scheduler = BackgroundScheduler(
            timezone=settings.scheduler_timezone,
            daemon=True,
        )
    return _scheduler


def get_monitoring_service() -> MonitoringService:
    """Get global monitoring service instance."""
    global _app_instance
    if _app_instance is None:
        scheduler = get_scheduler()
        _app_instance = MonitoringService(scheduler=scheduler)
    return _app_instance


def init_monitoring(app_factory: Callable[[], Any] | None = None) -> MonitoringService:
    """Initialize and start monitoring service."""
    service = get_monitoring_service()
    if app_factory:
        service.app_factory = app_factory
    service.start()
    return service


def shutdown_monitoring() -> None:
    """Shutdown monitoring service."""
    global _scheduler, _app_instance
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=True)
        _scheduler = None
    _app_instance = None


# Example callback for alerting
def alert_callback(result: dict[str, Any]) -> None:
    """Example callback for high-confidence alerts."""
    verdict = result.get("verdict")
    confidence = result.get("confidence")

    if verdict in ("TRUE", "FALSE") and confidence and confidence >= 0.8:
        LOGGER.warning(
            "HIGH CONFIDENCE ALERT",
            extra={
                "query": result.get("query"),
                "verdict": verdict,
                "confidence": confidence,
                "timestamp": result.get("timestamp"),
            },
        )


__all__ = [
    "MonitoringService",
    "get_scheduler",
    "get_monitoring_service",
    "init_monitoring",
    "shutdown_monitoring",
    "alert_callback",
]