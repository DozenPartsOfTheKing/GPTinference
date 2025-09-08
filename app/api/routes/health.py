"""Health check endpoints."""

from ...utils.loguru_config import get_logger
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends

from ...services.ollama_manager import get_ollama_manager, OllamaManager
from ...services.rate_limiter import get_rate_limiter, RateLimiter
from ...core.config import settings

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check() -> Dict[str, str]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/detailed")
async def detailed_health_check(
    ollama_manager: OllamaManager = Depends(get_ollama_manager),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> Dict[str, Any]:
    """Detailed health check with service dependencies."""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": settings.app_name,
        "version": settings.app_version,
        "components": {},
    }
    
    # Check Ollama service
    try:
        ollama_healthy = await ollama_manager.health_check()
        health_status["components"]["ollama"] = {
            "status": "healthy" if ollama_healthy else "unhealthy",
            "url": settings.ollama_base_url,
        }
        
        if ollama_healthy:
            # Get available models
            try:
                models_response = await ollama_manager.list_models()
                health_status["components"]["ollama"]["models_count"] = len(models_response.models)
                health_status["components"]["ollama"]["models"] = [
                    model.name for model in models_response.models
                ]
            except Exception as e:
                logger.warning(f"Failed to get models in health check: {e}")
                health_status["components"]["ollama"]["models_error"] = str(e)
        
    except Exception as e:
        logger.error(f"Ollama health check failed: {e}")
        health_status["components"]["ollama"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_status["status"] = "degraded"
    
    # Check Redis (via rate limiter)
    try:
        # Try to perform a simple rate limit check
        test_result = await rate_limiter.get_rate_limit_status(
            "health_check_test",
            limit=1000,
            window_seconds=60,
        )
        health_status["components"]["redis"] = {
            "status": "healthy",
            "url": settings.redis_url.replace(settings.redis_password or "", "***") if settings.redis_password else settings.redis_url,
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        health_status["components"]["redis"] = {
            "status": "unhealthy", 
            "error": str(e),
        }
        health_status["status"] = "degraded"
    
    return health_status


@router.get("/ready")
async def readiness_check(
    ollama_manager: OllamaManager = Depends(get_ollama_manager),
) -> Dict[str, str]:
    """Readiness check for Kubernetes/Docker."""
    
    # Check if Ollama is ready
    ollama_ready = await ollama_manager.health_check()
    
    if not ollama_ready:
        return {
            "status": "not_ready",
            "reason": "Ollama service not available",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/live")
async def liveness_check() -> Dict[str, str]:
    """Liveness check for Kubernetes/Docker."""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }
