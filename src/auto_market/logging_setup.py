"""
Logging configuration for Hive market trading scripts.
Provides consistent logging setup across all modules.
"""

import logging
from typing import Optional

from rich.logging import RichHandler
from rich.traceback import install as install_rich_traceback


def setup_logging(level: Optional[int] = None) -> logging.Logger:
    """
    Configure logging for the application using Rich for colorful console output and enhanced tracebacks.

    Args:
        level: Optional logging level to set. If None, defaults to INFO.

    Returns:
        The configured logger instance.
    """
    # Enable rich traceback for nicer exception traces
    install_rich_traceback(show_locals=True)

    # Get the root logger and clear existing handlers
    logger = logging.getLogger()
    for handler in logger.handlers:
        logger.removeHandler(handler)

    # Configure logging to use RichHandler for colorful console output
    level = level or logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )

    return logger


def set_debug_logging(logger: logging.Logger) -> None:
    """
    Enable debug logging for the given logger.

    Args:
        logger: The logger to configure.
    """
    logger.setLevel(logging.DEBUG)
    logger.debug("Debug logging enabled.")
