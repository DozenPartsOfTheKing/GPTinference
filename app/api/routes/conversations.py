"""Conversations endpoints tied to the current user."""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status

from ...services.hybrid_memory_manager import get_hybrid_memory_manager, HybridMemoryManager
from ...api.dependencies import check_user_rate_limit

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("/")
async def list_my_conversations(
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(check_user_rate_limit),
    memory: HybridMemoryManager = Depends(get_hybrid_memory_manager),
) -> Dict[str, Any]:
    try:
        rows = await memory.list_recent_conversations(limit=limit, offset=offset, user_id=user_id)
        return {"items": rows, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error(f"Failed to list conversations for {user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list conversations")


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(check_user_rate_limit),
    memory: HybridMemoryManager = Depends(get_hybrid_memory_manager),
) -> Dict[str, Any]:
    try:
        convo = await memory.get_conversation_memory(conversation_id)
        if not convo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        # Enforce ownership: only the owner can access
        if convo.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return {
            "conversation_id": convo.conversation_id,
            "user_id": convo.user_id,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.timestamp,
                    "model": m.model,
                } for m in (convo.messages or [])
            ],
            "updated_at": convo.updated_at,
            "created_at": convo.created_at,
            "message_count": convo.message_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation {conversation_id} for {user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch conversation")


