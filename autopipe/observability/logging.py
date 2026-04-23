"""Structured logging configuration for AutoPipe."""
import logging
import sys
from pathlib import Path
from typing import Optional

import structlog
from structlog.types import Processor


def configure_logging(
    level: str = "INFO",
    format: str = "text",
    output: str = "stdout",
    file_path: Optional[str] = None,
    rotate: bool = False,
    max_bytes: int = 10485760,
    backup_count: int = 5,
) -> None:
    """Configure structured logging for AutoPipe.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Output format (text or json)
        output: Output destination (stdout, stderr, or file)
        file_path: Log file path if output is "file"
        rotate: Whether to rotate log files
        max_bytes: Max bytes before rotation
        backup_count: Number of backup files
    """
    # Configure standard logging
    log_level = getattr(logging, level.upper())

    if output == "file" and file_path:
        handler: logging.Handler
        if rotate:
            from logging.handlers import RotatingFileHandler
            handler = RotatingFileHandler(
                file_path, maxBytes=max_bytes, backupCount=backup_count
            )
        else:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(file_path)
    elif output == "stderr":
        handler = logging.StreamHandler(sys.stderr)
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setLevel(log_level)

    # Configure structlog processors
    shared_processors: list[Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if format == "json":
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)
