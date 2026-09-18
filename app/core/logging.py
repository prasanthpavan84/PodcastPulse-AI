"""Structured logging configuration using structlog."""

import contextvars
import logging
import sys
from typing import Any, Dict

import structlog

from app.core.config import settings

# Correlation context variables
ctx_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
ctx_project_id: contextvars.ContextVar[str] = contextvars.ContextVar("project_id", default="")
ctx_job_id: contextvars.ContextVar[str] = contextvars.ContextVar("job_id", default="")
ctx_agent_run_id: contextvars.ContextVar[str] = contextvars.ContextVar("agent_run_id", default="")


def add_correlation_ids(logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Inject active correlation IDs into every log event."""
    req_id = ctx_request_id.get()
    if req_id:
        event_dict["request_id"] = req_id

    proj_id = ctx_project_id.get()
    if proj_id:
        event_dict["project_id"] = proj_id

    job_id = ctx_job_id.get()
    if job_id:
        event_dict["job_id"] = job_id

    agent_id = ctx_agent_run_id.get()
    if agent_id:
        event_dict["agent_run_id"] = agent_id

    return event_dict


def setup_logging() -> None:
    """Initialize structured logging for application and third-party libraries."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_correlation_ids,
    ]

    if settings.log_format == "json":
        formatter = structlog.processors.JSONRenderer()
    else:
        formatter = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=formatter,
            foreign_pre_chain=shared_processors,
        )
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Silence overly verbose external loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str = "podcastpulse"):
    """Return a configured structlog bound logger."""
    return structlog.get_logger(name)
