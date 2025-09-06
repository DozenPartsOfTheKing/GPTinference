"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from .core.config import settings
from .utils.logging import setup_logging, LoggingMiddleware
from .utils.loguru_config import setup_loguru, get_logger
from .api.routes import chat, health, models, memory
from .services.ollama_manager import get_ollama_manager
from .services.rate_limiter import get_rate_limiter, RateLimitExceeded
from .services.hybrid_memory_manager import close_hybrid_memory_manager
from .services.database_manager import close_database_manager

# Setup logging
setup_logging()
setup_loguru()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    # Initialize services
    try:
        # Initialize Ollama manager
        ollama_manager = get_ollama_manager()
        await ollama_manager._get_session()
        
        # Check Ollama health
        if await ollama_manager.health_check():
            logger.info("Ollama service is healthy")
            
            # Load available models
            models_response = await ollama_manager.list_models()
            logger.info(f"Found {len(models_response.models)} available models")
            for model in models_response.models:
                logger.info(f"  - {model.name} ({model.size})")
        else:
            logger.warning("Ollama service is not healthy")
        
        # Initialize rate limiter
        rate_limiter = get_rate_limiter()
        logger.info("Rate limiter initialized")
        
        logger.info("Application startup completed")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        # Continue startup even if some services fail
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    
    try:
        # Close Ollama manager
        ollama_manager = get_ollama_manager()
        await ollama_manager.close()
        
        # Close rate limiter
        rate_limiter = get_rate_limiter()
        await rate_limiter.close()
        
        # Close memory manager
        await close_hybrid_memory_manager()
        
        logger.info("Application shutdown completed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Internal ChatGPT-like service powered by Ollama",
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.debug else ["localhost", "127.0.0.1"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Add Prometheus metrics if enabled
if settings.enable_metrics:
    instrumentator = Instrumentator()
    instrumentator.instrument(app)
    instrumentator.expose(app, endpoint="/metrics")
    logger.info(f"Metrics enabled at /metrics")

# Include routers
app.include_router(health.router)
app.include_router(models.router)
app.include_router(chat.router)
app.include_router(memory.router)


# Startup and shutdown events
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down application...")
    
    # Close memory managers
    await close_hybrid_memory_manager()
    await close_database_manager()
    
    logger.info("Application shutdown complete")


# Global exception handlers
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceptions."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": str(exc),
            "retry_after": getattr(exc, 'retry_after', 60),
        },
        headers={"Retry-After": str(getattr(exc, 'retry_after', 60))},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs" if settings.debug else "disabled",
        "health": "/health",
        "models": "/models",
        "chat": "/chat",
        "memory": "/memory",
    }


# Additional utility endpoints
@app.get("/info")
async def app_info():
    """Application information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "debug": settings.debug,
        "environment": "development" if settings.debug else "production",
        "ollama_url": settings.ollama_base_url,
        "features": {
            "async_processing": True,
            "streaming": True,
            "rate_limiting": True,
            "metrics": settings.enable_metrics,
        },
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.api_workers,
        log_level=settings.log_level.lower(),
        access_log=True,
    )
