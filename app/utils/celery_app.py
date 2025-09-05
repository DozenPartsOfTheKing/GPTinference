"""Celery application configuration."""

import logging
from functools import lru_cache

from celery import Celery

from ..core.config import settings

logger = logging.getLogger(__name__)


def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    
    celery_app = Celery(
        "gptinfernse_worker",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["app.workers.chat_worker"],
    )
    
    # Configure Celery
    celery_app.conf.update(
        # Serialization
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        
        # Timezone
        timezone="UTC",
        enable_utc=True,
        
        # Task routing
        task_routes={
            "app.workers.chat_worker.process_chat_task": {"queue": "chat_queue"},
            "app.workers.chat_worker.process_streaming_chat_task": {"queue": "chat_stream_queue"},
        },
        
        # Task annotations (rate limiting, etc.)
        task_annotations={
            "app.workers.chat_worker.process_chat_task": {
                "rate_limit": "10/s",
                "time_limit": 300,  # 5 minutes
                "soft_time_limit": 240,  # 4 minutes
            },
            "app.workers.chat_worker.process_streaming_chat_task": {
                "rate_limit": "5/s", 
                "time_limit": 600,  # 10 minutes
                "soft_time_limit": 540,  # 9 minutes
            },
        },
        
        # Result backend settings
        result_expires=3600,  # 1 hour
        result_backend_transport_options={
            "master_name": "mymaster",
            "visibility_timeout": 3600,
        },
        
        # Worker settings
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_max_tasks_per_child=1000,
        
        # Retry settings
        task_reject_on_worker_lost=True,
        task_default_retry_delay=60,
        task_max_retries=3,
        
        # Monitoring
        worker_send_task_events=True,
        task_send_sent_event=True,
        
        # Security
        task_always_eager=False,  # Set to True for testing
        task_eager_propagates=True,
    )
    
    return celery_app


# Create the Celery app instance
celery_app = create_celery_app()


@lru_cache()
def get_celery_app() -> Celery:
    """Get Celery app instance."""
    return celery_app


# Configure logging for Celery
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks."""
    # Add any periodic tasks here if needed
    pass


@celery_app.on_after_finalize.connect
def setup_celery_logging(sender, **kwargs):
    """Setup logging for Celery."""
    logger.info("Celery application configured successfully")


# Task failure handler
@celery_app.task(bind=True)
def task_failure_handler(self, task_id, error, traceback):
    """Handle task failures."""
    logger.error(f"Task {task_id} failed: {error}")
    logger.error(f"Traceback: {traceback}")


if __name__ == "__main__":
    # For running Celery worker directly
    celery_app.start()
