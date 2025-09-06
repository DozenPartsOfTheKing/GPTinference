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
    Enhanced user identification with session tracking.
    """
    
    # Get client info for better identification
    client_info = await get_client_info(request)
    client_ip = client_info["ip"]
    user_agent = client_info["user_agent"]
    
    # If credentials provided, try to extract user ID
    if credentials:
        try:
            token = credentials.credentials
            
            # Check for simple user ID format
            if token.startswith("user_"):
                logger.debug(f"Authenticated user: {token}")
                return token
            
            # Check for session token format
            if token.startswith("session_"):
                logger.debug(f"Session user: {token}")
                return token
            
            # TODO: Implement proper JWT validation here
            # For now, treat as session token
            session_id = f"session_{hash(token) % 100000}"
            logger.debug(f"Token-based session: {session_id}")
            return session_id
            
        except Exception as e:
            logger.warning(f"Invalid token: {e}")
    
    # Generate consistent anonymous user ID based on IP and User-Agent
    # This helps maintain session continuity for the same browser/IP
    user_fingerprint = f"{client_ip}_{hash(user_agent) % 10000}"
    anonymous_id = f"anon_{user_fingerprint}"
    
    logger.debug(f"Anonymous user: {anonymous_id} (IP: {client_ip})")
    return anonymous_id


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
