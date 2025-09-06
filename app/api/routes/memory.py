"""Memory management endpoints."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from ...models.memory import (
    ConversationMessage,
    MemoryCreateRequest,
    MemoryQuery,
    MemoryResponse,
    MemoryStats,
    MemoryTypeEnum,
    MemoryUpdateRequest,
    SystemMemory,
    UserMemory,
)
from ...services.hybrid_memory_manager import get_hybrid_memory_manager
from ...api.dependencies import check_user_rate_limit, get_client_info

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("/conversation/{conversation_id}/message", response_model=MemoryResponse)
async def add_conversation_message(
    conversation_id: str,
    message: ConversationMessage,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager: MemoryManager = Depends(get_hybrid_memory_manager),
    ttl_hours: Optional[int] = None,
) -> MemoryResponse:
    """Add a message to conversation memory."""
    
    try:
        # Ensure message has an ID
        if not message.id:
            message.id = str(uuid.uuid4())
        
        success = await memory_manager.save_conversation_message(
            conversation_id=conversation_id,
            message=message,
            user_id=user_id,
            ttl_hours=ttl_hours
        )
        
        if success:
            logger.info(f"Added message to conversation {conversation_id}")
            return MemoryResponse(
                success=True,
                message="Message added to conversation memory",
                memory_id=conversation_id
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save conversation message"
            )
            
    except Exception as e:
        logger.error(f"Error adding conversation message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding message: {str(e)}"
        )


@router.get("/conversation/{conversation_id}")
async def get_conversation_memory(
    conversation_id: str,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager: MemoryManager = Depends(get_hybrid_memory_manager),
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Get conversation memory."""
    
    try:
        conversation = await memory_manager.get_conversation_memory(
            conversation_id=conversation_id,
            limit=limit
        )
        
        if conversation:
            # Check if user has access to this conversation
            if conversation.user_id and conversation.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this conversation"
                )
            
            return {
                "success": True,
                "data": conversation.dict(),
                "message": "Conversation memory retrieved"
            }
        else:
            return {
                "success": False,
                "data": None,
                "message": "Conversation not found"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving conversation: {str(e)}"
        )


@router.delete("/conversation/{conversation_id}", response_model=MemoryResponse)
async def delete_conversation_memory(
    conversation_id: str,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager: MemoryManager = Depends(get_hybrid_memory_manager),
) -> MemoryResponse:
    """Delete conversation memory."""
    
    try:
        # Check if user has access to this conversation
        conversation = await memory_manager.get_conversation_memory(conversation_id)
        if conversation and conversation.user_id and conversation.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this conversation"
            )
        
        success = await memory_manager.delete_conversation_memory(conversation_id)
        
        if success:
            return MemoryResponse(
                success=True,
                message="Conversation memory deleted",
                memory_id=conversation_id
            )
        else:
            return MemoryResponse(
                success=False,
                message="Conversation not found or already deleted",
                memory_id=conversation_id
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting conversation: {str(e)}"
        )


@router.get("/user/{target_user_id}")
async def get_user_memory(
    target_user_id: str,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager: MemoryManager = Depends(get_hybrid_memory_manager),
) -> Dict[str, Any]:
    """Get user memory."""
    
    try:
        # Users can only access their own memory
        if target_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to other user's memory"
            )
        
        user_memory = await memory_manager.get_user_memory(target_user_id)
        
        return {
            "success": True,
            "data": user_memory.dict() if user_memory else None,
            "message": "User memory retrieved"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user memory: {str(e)}"
        )


@router.put("/user/{target_user_id}/preferences")
async def update_user_preferences(
    target_user_id: str,
    preferences: Dict[str, Any],
    user_id: str = Depends(check_user_rate_limit),
    memory_manager: MemoryManager = Depends(get_hybrid_memory_manager),
) -> MemoryResponse:
    """Update user preferences."""
    
    try:
        # Users can only update their own preferences
        if target_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to other user's preferences"
            )
        
        success = await memory_manager.update_user_preferences(
            user_id=target_user_id,
            preferences=preferences
        )
        
        if success:
            return MemoryResponse(
                success=True,
                message="User preferences updated",
                memory_id=target_user_id
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user preferences"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user preferences: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating preferences: {str(e)}"
        )


@router.post("/user/{target_user_id}/fact")
async def add_user_fact(
    target_user_id: str,
    fact: str,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager: MemoryManager = Depends(get_hybrid_memory_manager),
) -> MemoryResponse:
    """Add a fact about the user."""
    
    try:
        # Users can only add facts about themselves
        if target_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to other user's facts"
            )
        
        success = await memory_manager.add_user_fact(
            user_id=target_user_id,
            fact=fact
        )
        
        if success:
            return MemoryResponse(
                success=True,
                message="User fact added",
                memory_id=target_user_id
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add user fact"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding user fact: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding fact: {str(e)}"
        )


@router.post("/system", response_model=MemoryResponse)
async def create_system_memory(
    request: MemoryCreateRequest,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager: MemoryManager = Depends(get_hybrid_memory_manager),
) -> MemoryResponse:
    """Create system memory (admin only)."""
    
    try:
        # TODO: Add admin role check
        # For now, allow all authenticated users
        
        system_memory = SystemMemory(
            key=request.data.get("key", str(uuid.uuid4())),
            value=request.data.get("value"),
            memory_type=request.memory_type,
            priority=request.priority,
            tags=request.tags
        )
        
        success = await memory_manager.save_system_memory(
            system_memory=system_memory,
            ttl_hours=request.ttl_hours
        )
        
        if success:
            return MemoryResponse(
                success=True,
                message="System memory created",
                memory_id=system_memory.key,
                expires_at=system_memory.expires_at
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create system memory"
            )
            
    except Exception as e:
        logger.error(f"Error creating system memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating system memory: {str(e)}"
        )


@router.get("/system/{key}")
async def get_system_memory(
    key: str,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager: MemoryManager = Depends(get_hybrid_memory_manager),
) -> Dict[str, Any]:
    """Get system memory."""
    
    try:
        system_memory = await memory_manager.get_system_memory(key)
        
        if system_memory:
            return {
                "success": True,
                "data": system_memory.dict(),
                "message": "System memory retrieved"
            }
        else:
            return {
                "success": False,
                "data": None,
                "message": "System memory not found"
            }
            
    except Exception as e:
        logger.error(f"Error getting system memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving system memory: {str(e)}"
        )


@router.put("/system/{key}")
async def update_system_memory(
    key: str,
    request: MemoryUpdateRequest,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager: MemoryManager = Depends(get_hybrid_memory_manager),
) -> MemoryResponse:
    """Update system memory (admin only)."""
    
    try:
        # TODO: Add admin role check
        
        # Get existing memory
        system_memory = await memory_manager.get_system_memory(key)
        if not system_memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="System memory not found"
            )
        
        # Update fields
        if request.data:
            if "value" in request.data:
                system_memory.value = request.data["value"]
        
        if request.priority:
            system_memory.priority = request.priority
        
        if request.tags is not None:
            system_memory.tags = request.tags
        
        success = await memory_manager.save_system_memory(
            system_memory=system_memory,
            ttl_hours=request.ttl_hours
        )
        
        if success:
            return MemoryResponse(
                success=True,
                message="System memory updated",
                memory_id=key,
                expires_at=system_memory.expires_at
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update system memory"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating system memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating system memory: {str(e)}"
        )


@router.delete("/system/{key}", response_model=MemoryResponse)
async def delete_system_memory(
    key: str,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager: MemoryManager = Depends(get_hybrid_memory_manager),
) -> MemoryResponse:
    """Delete system memory (admin only)."""
    
    try:
        # TODO: Add admin role check
        
        success = await memory_manager.delete_system_memory(key)
        
        if success:
            return MemoryResponse(
                success=True,
                message="System memory deleted",
                memory_id=key
            )
        else:
            return MemoryResponse(
                success=False,
                message="System memory not found or already deleted",
                memory_id=key
            )
            
    except Exception as e:
        logger.error(f"Error deleting system memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting system memory: {str(e)}"
        )


@router.post("/query")
async def query_memories(
    query: MemoryQuery,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager: MemoryManager = Depends(get_hybrid_memory_manager),
) -> Dict[str, Any]:
    """Query memories with filters."""
    
    try:
        # Restrict user queries to their own data
        if not query.user_id:
            query.user_id = user_id
        elif query.user_id != user_id:
            # TODO: Add admin role check to allow querying other users
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to other user's memories"
            )
        
        results = await memory_manager.query_memories(query)
        
        return {
            "success": True,
            "data": results,
            "message": f"Found {results['total_count']} memories"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying memories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error querying memories: {str(e)}"
        )


@router.get("/stats", response_model=MemoryStats)
async def get_memory_stats(
    user_id: str = Depends(check_user_rate_limit),
    memory_manager: MemoryManager = Depends(get_hybrid_memory_manager),
) -> MemoryStats:
    """Get memory statistics (admin only)."""
    
    try:
        # TODO: Add admin role check
        
        stats = await memory_manager.get_memory_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting memory statistics: {str(e)}"
        )


@router.get("/health")
async def memory_health_check(
    memory_manager: MemoryManager = Depends(get_hybrid_memory_manager),
) -> Dict[str, Any]:
    """Memory service health check."""
    
    try:
        # Test Redis connection
        redis_client = await memory_manager._get_redis()
        await redis_client.ping()
        
        return {
            "status": "healthy",
            "service": "memory",
            "timestamp": datetime.utcnow().isoformat(),
            "redis_connected": True
        }
        
    except Exception as e:
        logger.error(f"Memory health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "memory",
                "timestamp": datetime.utcnow().isoformat(),
                "redis_connected": False,
                "error": str(e)
            }
        )
