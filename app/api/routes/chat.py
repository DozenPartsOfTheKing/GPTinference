"""Chat endpoints."""

import logging
import uuid
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse

from ...models.chat import ChatRequest, ChatResponse, TaskStatus, ChatTaskRequest
from ...utils.loguru_config import get_logger
from ...services.ollama_manager import get_ollama_manager, OllamaManager
from ...api.dependencies import check_user_rate_limit, get_client_info
from ...utils.celery_app import get_celery_app
from ...workers.chat_worker import process_chat_task, process_streaming_chat_task
from ...services.hybrid_memory_manager import get_hybrid_memory_manager
from ...services.router_service import run_router

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=Dict[str, Any])
async def create_chat_task(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(check_user_rate_limit),
    client_info: Dict[str, Any] = Depends(get_client_info),
    ollama_manager: OllamaManager = Depends(get_ollama_manager),
    memory_manager = Depends(get_hybrid_memory_manager),
) -> Dict[str, Any]:
    """
    Create a new chat task (async processing).
    Returns task ID for status checking.
    """
    
    try:
        logger.info(f"🚀 Creating chat task for user {user_id}, model: {request.model}")
        logger.debug(f"Request details: prompt_length={len(request.prompt)}, stream={request.stream}")
        
        # Validate model availability
        logger.info(f"🔍 Validating model availability: {request.model}")
        if not await ollama_manager.is_model_available(request.model):
            logger.warning(f"❌ Model not available: {request.model}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Model '{request.model}' is not available"
            )
        
        # Generate task ID and conversation ID
        task_id = str(uuid.uuid4())
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        # Update request with conversation ID
        request.conversation_id = conversation_id
        
        # Create task request
        task_request = ChatTaskRequest(
            task_id=task_id,
            user_id=user_id,
            chat_request=request,
            priority=5,  # Default priority
            retry_count=0,
        )
        
        # Optionally run routing first (no memory needed). If routing fails or inactive, proceed normally.
        routing_result = None
        try:
            active_router = await memory_manager.get_active_router_schema()
            if active_router:
                schema = active_router.get("schema") or {}
                # Ensure routing model is available; if not, skip routing
                routing_model = "llama3.2:3b"
                if await ollama_manager.is_model_available(routing_model):
                    routing_result = await run_router(ollama_manager, schema, request.prompt, model=routing_model)
        except Exception:
            routing_result = None

        # Submit task to Celery
        celery_app = get_celery_app()
        if request.stream:
            celery_task = process_streaming_chat_task.delay(
                task_request.dict()
            )
        else:
            celery_task = process_chat_task.delay(
                task_request.dict(), routing_result
            )
        
        logger.bind(task_id=task_id, celery_task_id=celery_task.id, user_id=user_id, model=request.model, stream=request.stream, client_ip=client_info.get("ip")).info(
            f"Created chat task {task_id} for user {user_id}"
        )
        
        return {
            "task_id": celery_task.id,
            "conversation_id": conversation_id,
            "status": "processing",
            "message": "Task created successfully",
            "estimated_time": "30-60 seconds",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create chat task for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create chat task: {str(e)}"
        )


@router.get("/task/{task_id}", response_model=Dict[str, Any])
async def get_task_status(
    task_id: str,
    user_id: str = Depends(check_user_rate_limit),
) -> Dict[str, Any]:
    """Get status of a chat task."""
    
    try:
        celery_app = get_celery_app()
        task = celery_app.AsyncResult(task_id)
        
        # Get task state and result
        task_state = task.state
        task_result = task.result
        
        logger.debug(f"Task {task_id} status check by user {user_id}: {task_state}")
        
        if task_state == "PENDING":
            return {
                "task_id": task_id,
                "status": "processing",
                "message": "Task is being processed",
            }
        
        elif task_state == "SUCCESS":
            # Task completed successfully
            if isinstance(task_result, dict) and task_result.get("error"):
                # Task completed but with error
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "error": task_result.get("message", "Unknown error"),
                }
            else:
                # Task completed successfully
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "result": task_result,
                }
        
        elif task_state == "FAILURE":
            # Task failed
            error_message = str(task_result) if task_result else "Unknown error"
            return {
                "task_id": task_id,
                "status": "failed",
                "error": error_message,
            }
        
        elif task_state == "RETRY":
            # Task is being retried
            return {
                "task_id": task_id,
                "status": "retrying",
                "message": "Task is being retried due to temporary failure",
            }
        
        else:
            # Unknown state
            return {
                "task_id": task_id,
                "status": task_state.lower(),
                "message": f"Task is in {task_state} state",
            }
            
    except Exception as e:
        logger.error(f"Error getting task status for {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )


@router.post("/sync", response_model=ChatResponse)
async def chat_sync(
    request: ChatRequest,
    user_id: str = Depends(check_user_rate_limit),
    client_info: Dict[str, Any] = Depends(get_client_info),
    ollama_manager: OllamaManager = Depends(get_ollama_manager),
    memory_manager = Depends(get_hybrid_memory_manager),
) -> ChatResponse:
    """
    Synchronous chat endpoint (direct processing).
    Use for quick responses or testing.
    """
    
    try:
        logger.info(f"🔄 Processing sync chat for user {user_id}, model: {request.model}")
        logger.debug(f"Sync request details: prompt_length={len(request.prompt)}, conversation_id={request.conversation_id}")
        
        # Validate model availability
        logger.info(f"🔍 Validating model availability: {request.model}")
        if not await ollama_manager.is_model_available(request.model):
            logger.warning(f"❌ Model not available: {request.model}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Model '{request.model}' is not available"
            )
        
        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        # Create task request for processing
        task_request = ChatTaskRequest(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            chat_request=request,
            priority=1,  # High priority for sync requests
            retry_count=0,
        )
        
        logger.bind(user_id=user_id, model=request.model, prompt_length=len(request.prompt), client_ip=client_info.get("ip")).info(
            f"Processing sync chat for user {user_id}"
        )
        
        # Import and use the async processing function directly
        from ...workers.chat_worker import _process_chat_async
        
        # Optional routing before processing (queues not used in sync, but logic consistent)
        routing_result = None
        try:
            active_router = await memory_manager.get_active_router_schema()
            if active_router:
                schema = active_router.get("schema") or {}
                routing_model = "llama3.2:3b"
                if await ollama_manager.is_model_available(routing_model):
                    routing_result = await run_router(ollama_manager, schema, request.prompt, model=routing_model)
        except Exception:
            routing_result = None

        result = await _process_chat_async(task_request, routing_result=routing_result)
        
        # Convert result to ChatResponse
        chat_response = ChatResponse(**result)
        
        logger.info(
            f"Sync chat completed for user {user_id}",
            extra={
                "user_id": user_id,
                "processing_time": chat_response.processing_time,
                "tokens_used": chat_response.tokens_used,
            }
        )
        
        return chat_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync chat failed for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}"
        )


@router.delete("/task/{task_id}")
async def cancel_task(
    task_id: str,
    user_id: str = Depends(check_user_rate_limit),
) -> Dict[str, str]:
    """Cancel a running chat task."""
    
    try:
        celery_app = get_celery_app()
        
        # Revoke the task
        celery_app.control.revoke(task_id, terminate=True)
        
        logger.info(f"Task {task_id} cancelled by user {user_id}")
        
        return {
            "task_id": task_id,
            "status": "cancelled",
            "message": "Task cancelled successfully",
        }
        
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}"
        )


@router.get("/history/{conversation_id}")
async def get_conversation_history(
    conversation_id: str,
    user_id: str = Depends(check_user_rate_limit),
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Get conversation history (placeholder for future implementation).
    This would typically query a database.
    """
    
    # TODO: Implement conversation history storage and retrieval
    logger.info(f"History requested for conversation {conversation_id} by user {user_id}")
    
    return {
        "conversation_id": conversation_id,
        "messages": [],
        "total_count": 0,
        "limit": limit,
        "offset": offset,
        "message": "Conversation history not implemented yet",
    }


@router.get("/stats")
async def get_chat_stats(
    user_id: str = Depends(check_user_rate_limit),
) -> Dict[str, Any]:
    """Get user chat statistics."""
    
    try:
        # TODO: Implement proper stats from database/cache
        # For now, return placeholder data
        
        return {
            "user_id": user_id,
            "total_chats": 0,
            "total_tokens": 0,
            "favorite_models": [],
            "avg_response_time": 0.0,
            "message": "Statistics not implemented yet",
        }
        
    except Exception as e:
        logger.error(f"Error getting stats for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )
