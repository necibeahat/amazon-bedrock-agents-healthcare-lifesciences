"""
Logging utilities for the pharmaceutical pipeline system.

This module provides centralized logging configuration and utilities
for all components of the multi-agent system.
"""

import logging
import sys
from typing import Optional


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        level: Optional logging level override
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Set level if provided
    if level:
        logger.setLevel(getattr(logging, level.upper()))
    elif not logger.handlers:
        # Set default level if no handlers exist
        logger.setLevel(logging.INFO)
    
    # Add handler if none exists
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


def configure_logging(level: str = "INFO", format_string: Optional[str] = None) -> None:
    """
    Configure global logging settings.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Optional custom format string
    """
    format_string = format_string or '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        handlers=[logging.StreamHandler(sys.stdout)]
    )