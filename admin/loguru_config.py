"""Loguru configuration for admin panel."""

import sys
from pathlib import Path
from loguru import logger


def setup_admin_loguru():
    """Setup loguru for admin panel."""
    
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
               "<cyan>ADMIN</cyan> | "
               "<level>{message}</level>",
        level="DEBUG",
        colorize=True,
    )
    
    # Admin panel log
    logger.add(
        logs_dir / "admin.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | ADMIN | {message}",
        level="DEBUG",
        rotation="50 MB",
        retention="14 days",
        compression="gz",
    )
    
    logger.info("🛠️ Admin panel loguru initialized")


def get_admin_logger():
    """Get admin logger."""
    return logger
