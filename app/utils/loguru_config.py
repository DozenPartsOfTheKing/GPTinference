"""Centralized logging configuration with loguru."""

import sys
from pathlib import Path
from typing import Dict, Any

from loguru import logger

from ..core.config import get_settings

settings = get_settings()


def setup_loguru() -> None:
    """Setup loguru logging with comprehensive configuration."""
    
    # Remove default handler
    logger.remove()
    
    # Create logs directory
    logs_dir = Path("/app/logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Console logging with colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level="DEBUG" if settings.debug else "INFO",
        colorize=True,
        backtrace=True,
        diagnose=True,
    )
    
    # File logging - General application log
    logger.add(
        logs_dir / "app.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="100 MB",
        retention="30 days",
        compression="gz",
        backtrace=True,
        diagnose=True,
    )
    
    # File logging - Error log
    logger.add(
        logs_dir / "errors.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="ERROR",
        rotation="50 MB",
        retention="60 days",
        compression="gz",
        backtrace=True,
        diagnose=True,
    )
    
    # Memory operations log
    logger.add(
        logs_dir / "memory.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="50 MB",
        retention="14 days",
        compression="gz",
        filter=lambda record: "memory" in record["name"].lower() or "conversation" in record["message"].lower(),
    )
    
    # Chat operations log
    logger.add(
        logs_dir / "chat.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="100 MB",
        retention="7 days",
        compression="gz",
        filter=lambda record: "chat" in record["name"].lower() or "ollama" in record["name"].lower(),
    )
    
    # Database operations log
    logger.add(
        logs_dir / "database.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="50 MB",
        retention="14 days",
        compression="gz",
        filter=lambda record: "database" in record["name"].lower() or "postgres" in record["name"].lower() or "redis" in record["name"].lower(),
    )
    
    # API requests log
    logger.add(
        logs_dir / "api.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="INFO",
        rotation="100 MB",
        retention="7 days",
        compression="gz",
        filter=lambda record: "api" in record["name"].lower() or "fastapi" in record["name"].lower() or "uvicorn" in record["name"].lower(),
    )
    
    logger.info("🚀 Loguru logging system initialized")
    logger.info(f"📁 Logs directory: {logs_dir}")
    logger.info(f"🔧 Debug mode: {settings.debug}")
    logger.info(f"📊 Log level: {'DEBUG' if settings.debug else 'INFO'}")


def get_logger(name: str) -> Any:
    """Get logger instance with context."""
    return logger.bind(name=name)


def log_function_call(func_name: str, args: Dict[str, Any] = None, kwargs: Dict[str, Any] = None):
    """Decorator to log function calls."""
    def decorator(func):
        def wrapper(*args_inner, **kwargs_inner):
            logger.debug(f"🔄 Calling {func_name} with args={args_inner}, kwargs={kwargs_inner}")
            try:
                result = func(*args_inner, **kwargs_inner)
                logger.debug(f"✅ {func_name} completed successfully")
                return result
            except Exception as e:
                logger.error(f"❌ {func_name} failed: {e}")
                raise
        return wrapper
    return decorator


def log_async_function_call(func_name: str):
    """Decorator to log async function calls."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            logger.debug(f"🔄 Calling async {func_name} with args={args}, kwargs={kwargs}")
            try:
                result = await func(*args, **kwargs)
                logger.debug(f"✅ Async {func_name} completed successfully")
                return result
            except Exception as e:
                logger.error(f"❌ Async {func_name} failed: {e}")
                raise
        return wrapper
    return decorator


# Context managers for detailed logging
class LogContext:
    """Context manager for detailed operation logging."""
    
    def __init__(self, operation: str, **context):
        self.operation = operation
        self.context = context
        self.logger = logger.bind(operation=operation, **context)
    
    def __enter__(self):
        self.logger.info(f"🚀 Starting {self.operation}")
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(f"❌ {self.operation} failed: {exc_val}")
        else:
            self.logger.info(f"✅ {self.operation} completed successfully")


class MemoryLogContext(LogContext):
    """Specialized context for memory operations."""
    
    def __init__(self, operation: str, conversation_id: str = None, user_id: str = None, **context):
        super().__init__(
            operation=f"Memory: {operation}",
            conversation_id=conversation_id,
            user_id=user_id,
            **context
        )


class ChatLogContext(LogContext):
    """Specialized context for chat operations."""
    
    def __init__(self, operation: str, model: str = None, tokens: int = None, **context):
        super().__init__(
            operation=f"Chat: {operation}",
            model=model,
            tokens=tokens,
            **context
        )


class DatabaseLogContext(LogContext):
    """Specialized context for database operations."""
    
    def __init__(self, operation: str, table: str = None, query_type: str = None, **context):
        super().__init__(
            operation=f"Database: {operation}",
            table=table,
            query_type=query_type,
            **context
        )


# Export main logger instance
main_logger = logger
