"""Loguru configuration for frontend."""

import sys
from pathlib import Path
from loguru import logger


def setup_frontend_loguru():
    """Setup loguru for frontend."""
    
    # Remove default handler
    logger.remove()
    
    # Create logs directory with proper permissions
    logs_dir = Path("/app/logs")
    logs_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
    
    # Console logging
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>FRONTEND</cyan> | "
               "<level>{message}</level>",
        level="DEBUG",
        colorize=True,
    )
    
    # Frontend log
    logger.add(
        logs_dir / "frontend.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | FRONTEND | {message}",
        level="DEBUG",
        rotation="50 MB",
        retention="14 days",
        compression="gz",
    )
    
    logger.info("🌐 Frontend loguru initialized")


def get_frontend_logger():
    """Get frontend logger."""
    return logger
