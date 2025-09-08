"""Rate limiting service using Redis."""

from ..utils.loguru_config import get_logger
import time
from functools import lru_cache
from typing import Optional

import redis.asyncio as redis

from ..core.config import settings

logger = get_logger(__name__)


class RateLimitExceeded(Exception):
    """Rate limit exceeded exception."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class RateLimiter:
    """Redis-based rate limiter with sliding window."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or self._create_redis_client()
        
    def _create_redis_client(self) -> redis.Redis:
        """Create Redis client."""
        return redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        cost: int = 1,
    ) -> bool:
        """
        Check if request is within rate limit using sliding window.
        
        Args:
            key: Unique identifier for the rate limit (e.g., user_id, ip_address)
            limit: Maximum number of requests allowed
            window_seconds: Time window in seconds
            cost: Cost of this request (default: 1)
            
        Returns:
            True if request is allowed, False otherwise
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        try:
            current_time = time.time()
            window_start = current_time - window_seconds
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1]
            
            # Check if adding this request would exceed limit
            if current_count + cost > limit:
                # Calculate retry after time
                oldest_request = await self.redis_client.zrange(key, 0, 0, withscores=True)
                if oldest_request:
                    retry_after = int(oldest_request[0][1] + window_seconds - current_time)
                    retry_after = max(1, retry_after)
                else:
                    retry_after = window_seconds
                    
                raise RateLimitExceeded(
                    f"Rate limit exceeded. Limit: {limit}/{window_seconds}s",
                    retry_after=retry_after
                )
            
            # Add current request to window
            pipe = self.redis_client.pipeline()
            for _ in range(cost):
                pipe.zadd(key, {f"{current_time}_{time.time_ns()}": current_time})
            
            # Set expiration for cleanup
            pipe.expire(key, window_seconds + 1)
            
            await pipe.execute()
            
            return True
            
        except RateLimitExceeded:
            raise
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # Fail open - allow request if Redis is down
            return True
    
    async def get_rate_limit_status(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> dict:
        """Get current rate limit status."""
        try:
            current_time = time.time()
            window_start = current_time - window_seconds
            
            # Clean up expired entries and count current
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.ttl(key)
            
            results = await pipe.execute()
            current_count = results[1]
            ttl = results[2]
            
            # Calculate reset time
            if ttl > 0:
                reset_time = int(current_time + ttl)
            else:
                reset_time = int(current_time + window_seconds)
            
            return {
                "limit": limit,
                "remaining": max(0, limit - current_count),
                "reset_time": reset_time,
                "window_seconds": window_seconds,
            }
            
        except Exception as e:
            logger.error(f"Error getting rate limit status: {e}")
            return {
                "limit": limit,
                "remaining": limit,
                "reset_time": int(time.time() + window_seconds),
                "window_seconds": window_seconds,
            }
    
    async def reset_rate_limit(self, key: str) -> bool:
        """Reset rate limit for a key."""
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")
            return False
    
    async def check_user_rate_limit(
        self,
        user_id: str,
        cost: int = 1,
    ) -> bool:
        """Check user-specific rate limits."""
        
        # Check per-minute limit
        minute_key = f"rate_limit:user:{user_id}:minute"
        await self.check_rate_limit(
            minute_key,
            settings.rate_limit_per_minute,
            60,
            cost
        )
        
        # Check per-hour limit
        hour_key = f"rate_limit:user:{user_id}:hour"
        await self.check_rate_limit(
            hour_key,
            settings.rate_limit_per_hour,
            3600,
            cost
        )
        
        return True
    
    async def check_global_rate_limit(self, cost: int = 1) -> bool:
        """Check global system rate limits."""
        
        # Global per-minute limit (prevent system overload)
        global_key = "rate_limit:global:minute"
        global_limit = settings.rate_limit_per_minute * 50  # Assume max 50 users
        
        await self.check_rate_limit(
            global_key,
            global_limit,
            60,
            cost
        )
        
        return True
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()


# Global instance
_rate_limiter: Optional[RateLimiter] = None


@lru_cache()
def get_rate_limiter() -> RateLimiter:
    """Get singleton rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
