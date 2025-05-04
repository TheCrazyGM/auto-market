"""
Logging configuration for Hive market trading scripts.
Provides consistent logging setup across all modules.
"""

import logging
import sys
from typing import Optional


def setup_logging(level: Optional[int] = None) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        level: Optional logging level to set. If None, defaults to INFO.

    Returns:
        The configured logger instance.
    """
    # Get the root logger
    logger = logging.getLogger()

    # Clear any existing handlers
    for handler in logger.handlers:
        logger.removeHandler(handler)

    # Set up basic configuration
    logging.basicConfig(
        level=level or logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
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
