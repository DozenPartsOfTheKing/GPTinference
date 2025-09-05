"""FastAPI dependencies."""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..services.rate_limiter import RateLimiter, get_rate_limiter

logger = logging.getLogger(__name__)

# Security scheme for JWT tokens (optional)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    Get current user from JWT token or return anonymous user.
    For now, returns a simple user ID based on IP or token.
    """
    
    # If no credentials provided, use IP-based identification
    if not credentials:
        client_ip = request.client.host
        return f"anonymous_{client_ip}"
    
    # TODO: Implement proper JWT validation here
    # For now, just extract user ID from token
    try:
        # This is a placeholder - implement proper JWT decoding
        token = credentials.credentials
        if token.startswith("user_"):
            return token
        else:
            # Fallback to IP-based ID
            client_ip = request.client.host
            return f"token_{client_ip}"
    except Exception as e:
        logger.warning(f"Invalid token: {e}")
        client_ip = request.client.host
        return f"invalid_{client_ip}"


async def get_rate_limiter_dep() -> RateLimiter:
    """Dependency to get rate limiter instance."""
    return get_rate_limiter()


async def check_user_rate_limit(
    user_id: str = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
) -> str:
    """Check user rate limits before processing request."""
    
    try:
        await rate_limiter.check_user_rate_limit(user_id)
        await rate_limiter.check_global_rate_limit()
        return user_id
    except Exception as e:
        logger.warning(f"Rate limit exceeded for user {user_id}: {e}")
        
        # Extract retry_after if available
        retry_after = getattr(e, 'retry_after', 60)
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "message": str(e),
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


async def get_client_info(request: Request) -> dict:
    """Extract client information from request."""
    
    # Get real IP (considering proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    real_ip = request.headers.get("X-Real-IP")
    client_ip = request.client.host
    
    if forwarded_for:
        # Take the first IP from X-Forwarded-For
        client_ip = forwarded_for.split(",")[0].strip()
    elif real_ip:
        client_ip = real_ip
    
    return {
        "ip": client_ip,
        "user_agent": request.headers.get("User-Agent", ""),
        "referer": request.headers.get("Referer", ""),
        "host": request.headers.get("Host", ""),
    }
