"""Redis operations tracer with detailed logging."""

import json
from typing import Any, Dict, Optional
from functools import wraps

from .loguru_config import get_logger, DatabaseLogContext

logger = get_logger(__name__)


class RedisTracer:
    """Redis operations tracer for debugging cache behavior."""
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.operation_count = 0
    
    async def trace_get(self, key: str, description: str = "") -> Optional[Any]:
        """Trace Redis GET operation."""
        self.operation_count += 1
        
        with DatabaseLogContext(
            "Redis GET", 
            operation_id=self.operation_count,
            key=key,
            description=description
        ) as db_logger:
            
            db_logger.info(f"🔍 Redis GET: {key}")
            
            try:
                result = await self.redis_client.get(key)
                
                if result:
                    # Try to parse as JSON to get size info
                    try:
                        parsed = json.loads(result)
                        if isinstance(parsed, dict):
                            size_info = f"dict with {len(parsed)} keys"
                        elif isinstance(parsed, list):
                            size_info = f"list with {len(parsed)} items"
                        else:
                            size_info = f"value of type {type(parsed).__name__}"
                    except:
                        size_info = f"string of {len(result)} chars"
                    
                    db_logger.success(f"✅ Redis GET SUCCESS: {key} -> {size_info}")
                    return result
                else:
                    db_logger.warning(f"🔍 Redis GET MISS: {key} (not found)")
                    return None
                    
            except Exception as e:
                db_logger.error(f"❌ Redis GET ERROR: {key} -> {e}")
                return None
    
    async def trace_set(self, key: str, value: Any, ttl: Optional[int] = None, description: str = "") -> bool:
        """Trace Redis SET operation."""
        self.operation_count += 1
        
        with DatabaseLogContext(
            "Redis SET",
            operation_id=self.operation_count,
            key=key,
            ttl=ttl,
            description=description
        ) as db_logger:
            
            # Get value info
            if isinstance(value, str):
                value_info = f"string ({len(value)} chars)"
            elif isinstance(value, (dict, list)):
                try:
                    json_str = json.dumps(value) if not isinstance(value, str) else value
                    value_info = f"JSON ({len(json_str)} chars)"
                except:
                    value_info = f"{type(value).__name__}"
            else:
                value_info = f"{type(value).__name__}"
            
            db_logger.info(f"💾 Redis SET: {key} -> {value_info}" + (f" (TTL: {ttl}s)" if ttl else ""))
            
            try:
                if ttl:
                    result = await self.redis_client.setex(key, ttl, value)
                else:
                    result = await self.redis_client.set(key, value)
                
                if result:
                    db_logger.success(f"✅ Redis SET SUCCESS: {key}")
                    return True
                else:
                    db_logger.error(f"❌ Redis SET FAILED: {key}")
                    return False
                    
            except Exception as e:
                db_logger.error(f"❌ Redis SET ERROR: {key} -> {e}")
                return False
    
    async def trace_delete(self, key: str, description: str = "") -> bool:
        """Trace Redis DELETE operation."""
        self.operation_count += 1
        
        with DatabaseLogContext(
            "Redis DELETE",
            operation_id=self.operation_count,
            key=key,
            description=description
        ) as db_logger:
            
            db_logger.info(f"🗑️ Redis DELETE: {key}")
            
            try:
                result = await self.redis_client.delete(key)
                
                if result > 0:
                    db_logger.success(f"✅ Redis DELETE SUCCESS: {key} (deleted {result} keys)")
                    return True
                else:
                    db_logger.warning(f"🔍 Redis DELETE MISS: {key} (key not found)")
                    return False
                    
            except Exception as e:
                db_logger.error(f"❌ Redis DELETE ERROR: {key} -> {e}")
                return False
    
    async def trace_keys(self, pattern: str = "*", description: str = "") -> list:
        """Trace Redis KEYS operation."""
        self.operation_count += 1
        
        with DatabaseLogContext(
            "Redis KEYS",
            operation_id=self.operation_count,
            pattern=pattern,
            description=description
        ) as db_logger:
            
            db_logger.info(f"🔑 Redis KEYS: {pattern}")
            
            try:
                keys = await self.redis_client.keys(pattern)
                db_logger.success(f"✅ Redis KEYS SUCCESS: {pattern} -> {len(keys)} keys found")
                
                # Log first few keys for debugging
                if keys:
                    sample_keys = keys[:5]
                    db_logger.debug(f"📋 Sample keys: {sample_keys}")
                    if len(keys) > 5:
                        db_logger.debug(f"... and {len(keys) - 5} more keys")
                
                return keys
                
            except Exception as e:
                db_logger.error(f"❌ Redis KEYS ERROR: {pattern} -> {e}")
                return []
    
    async def trace_info(self, section: str = "all", description: str = "") -> dict:
        """Trace Redis INFO operation."""
        self.operation_count += 1
        
        with DatabaseLogContext(
            "Redis INFO",
            operation_id=self.operation_count,
            section=section,
            description=description
        ) as db_logger:
            
            db_logger.info(f"ℹ️ Redis INFO: {section}")
            
            try:
                info = await self.redis_client.info(section)
                
                # Log key metrics
                if section == "memory" or section == "all":
                    used_memory = info.get("used_memory_human", "unknown")
                    db_logger.info(f"📊 Redis memory usage: {used_memory}")
                
                if section == "keyspace" or section == "all":
                    keyspace_info = {k: v for k, v in info.items() if k.startswith("db")}
                    if keyspace_info:
                        db_logger.info(f"🔑 Redis keyspace: {keyspace_info}")
                    else:
                        db_logger.info("🔑 Redis keyspace: empty")
                
                db_logger.success(f"✅ Redis INFO SUCCESS: {section}")
                return info
                
            except Exception as e:
                db_logger.error(f"❌ Redis INFO ERROR: {section} -> {e}")
                return {}


def trace_redis_operations(redis_client):
    """Create a Redis tracer for the given client."""
    return RedisTracer(redis_client)
