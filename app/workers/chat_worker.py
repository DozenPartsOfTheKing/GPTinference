"""Chat processing Celery worker."""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any

from celery import Task
from celery.exceptions import Retry

from ..utils.celery_app import celery_app
from ..services.ollama_manager import get_ollama_manager
from ..services.memory_manager import get_memory_manager
from ..models.chat import ChatRequest, ChatResponse, ChatTaskRequest
from ..models.ollama import OllamaRequest, OllamaGenerateOptions
from ..models.memory import ConversationMessage

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """Custom Celery task with callbacks."""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called on task success."""
        logger.info(f"Task {task_id} completed successfully")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called on task failure."""
        logger.error(f"Task {task_id} failed: {exc}")
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called on task retry."""
        logger.warning(f"Task {task_id} retrying: {exc}")


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name="app.workers.chat_worker.process_chat_task",
    max_retries=3,
    default_retry_delay=60,
)
def process_chat_task(
    self,
    task_request: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process chat request asynchronously.
    
    Args:
        task_request: Serialized ChatTaskRequest
        
    Returns:
        Serialized ChatResponse
    """
    
    try:
        # Parse task request
        task_req = ChatTaskRequest(**task_request)
        chat_req = task_req.chat_request
        
        logger.info(
            f"Processing chat task {task_req.task_id} for user {task_req.user_id}",
            extra={
                "task_id": task_req.task_id,
                "user_id": task_req.user_id,
                "model": chat_req.model,
                "prompt_length": len(chat_req.prompt),
            }
        )
        
        # Run async processing in new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _process_chat_async(task_req)
            )
            return result
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(
            f"Chat task {task_request.get('task_id', 'unknown')} failed: {exc}",
            exc_info=True
        )
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying task in {self.default_retry_delay} seconds")
            raise self.retry(exc=exc, countdown=self.default_retry_delay)
        
        # Max retries exceeded
        return {
            "error": True,
            "message": f"Task failed after {self.max_retries} retries: {str(exc)}",
            "task_id": task_request.get("task_id"),
        }


async def _process_chat_async(task_request: ChatTaskRequest) -> Dict[str, Any]:
    """Async chat processing logic with memory integration."""
    
    start_time = time.time()
    ollama_manager = get_ollama_manager()
    memory_manager = get_memory_manager()
    
    try:
        # Initialize services
        await ollama_manager._get_session()
        
        # Get or create conversation ID
        conversation_id = task_request.chat_request.conversation_id or str(uuid.uuid4())
        
        # Build context-aware prompt
        enhanced_prompt = await _build_context_prompt(
            memory_manager, 
            task_request.chat_request.prompt,
            conversation_id,
            task_request.user_id,
            task_request.chat_request.model
        )
        
        # Prepare Ollama request with enhanced prompt
        ollama_options = OllamaGenerateOptions(
            temperature=task_request.chat_request.temperature,
            top_p=task_request.chat_request.top_p,
            num_predict=task_request.chat_request.max_tokens,
        )
        
        ollama_request = OllamaRequest(
            model=task_request.chat_request.model,
            prompt=enhanced_prompt,
            stream=False,
            options=ollama_options,
        )
        
        # Generate response
        logger.info(f"Sending enhanced request to Ollama for task {task_request.task_id}")
        logger.debug(f"Enhanced prompt length: {len(enhanced_prompt)} chars")
        ollama_response = await ollama_manager.generate(ollama_request)
        
        processing_time = time.time() - start_time
        chat_response = ChatResponse(
            response=ollama_response.response,
            conversation_id=conversation_id,
            model=ollama_response.model,
            processing_time=processing_time,
            tokens_used=ollama_response.eval_count,
        )
        
        # Save to memory
        try:
            await _save_conversation_messages(
                memory_manager,
                conversation_id,
                task_request.user_id,
                task_request.chat_request.prompt,
                ollama_response.response,
                ollama_response.model,
                ollama_response.eval_count or 0
            )
        except Exception as e:
            logger.warning(f"Failed to save conversation to memory: {e}")
            # Don't fail the task if memory save fails
        
        logger.info(
            f"Chat task {task_request.task_id} completed successfully",
            extra={
                "task_id": task_request.task_id,
                "processing_time": processing_time,
                "tokens_used": ollama_response.eval_count,
                "response_length": len(ollama_response.response),
                "conversation_id": conversation_id,
            }
        )
        
        return chat_response.dict()
        
    except Exception as e:
        logger.error(f"Error in async chat processing: {e}", exc_info=True)
        raise
    
    finally:
        # Clean up
        try:
            await ollama_manager.close()
        except Exception as e:
            logger.warning(f"Error closing Ollama manager: {e}")


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name="app.workers.chat_worker.process_streaming_chat_task",
    max_retries=2,
    default_retry_delay=30,
)
def process_streaming_chat_task(
    self,
    task_request: Dict[str, Any],
    callback_url: str = None,
) -> Dict[str, Any]:
    """
    Process streaming chat request.
    
    Args:
        task_request: Serialized ChatTaskRequest
        callback_url: Optional URL to send streaming updates
        
    Returns:
        Task status
    """
    
    try:
        # Parse task request
        task_req = ChatTaskRequest(**task_request)
        
        logger.info(
            f"Processing streaming chat task {task_req.task_id}",
            extra={
                "task_id": task_req.task_id,
                "user_id": task_req.user_id,
                "callback_url": callback_url,
            }
        )
        
        # Run async streaming in new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _process_streaming_chat_async(task_req, callback_url)
            )
            return result
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(
            f"Streaming chat task {task_request.get('task_id', 'unknown')} failed: {exc}",
            exc_info=True
        )
        
        # Retry logic (fewer retries for streaming)
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying streaming task in {self.default_retry_delay} seconds")
            raise self.retry(exc=exc, countdown=self.default_retry_delay)
        
        return {
            "error": True,
            "message": f"Streaming task failed: {str(exc)}",
            "task_id": task_request.get("task_id"),
        }


async def _process_streaming_chat_async(
    task_request: ChatTaskRequest,
    callback_url: str = None,
) -> Dict[str, Any]:
    """Async streaming chat processing logic."""
    
    start_time = time.time()
    ollama_manager = get_ollama_manager()
    accumulated_response = ""
    
    try:
        # Initialize Ollama session
        await ollama_manager._get_session()
        
        # Prepare Ollama request for streaming
        ollama_options = OllamaGenerateOptions(
            temperature=task_request.chat_request.temperature,
            top_p=task_request.chat_request.top_p,
            num_predict=task_request.chat_request.max_tokens,
        )
        
        ollama_request = OllamaRequest(
            model=task_request.chat_request.model,
            prompt=task_request.chat_request.prompt,
            stream=True,  # Enable streaming
            options=ollama_options,
        )
        
        # Process streaming response
        logger.info(f"Starting streaming for task {task_request.task_id}")
        
        async for chunk in ollama_manager.generate_stream(ollama_request):
            accumulated_response += chunk.response
            
            # Send chunk to callback URL if provided
            if callback_url:
                await _send_streaming_chunk(
                    callback_url,
                    task_request.task_id,
                    chunk.response,
                    chunk.done
                )
            
            # Log progress
            if len(accumulated_response) % 100 == 0:  # Log every 100 characters
                logger.debug(f"Streaming progress for task {task_request.task_id}: {len(accumulated_response)} chars")
        
        processing_time = time.time() - start_time
        
        # Create final response
        chat_response = ChatResponse(
            response=accumulated_response,
            conversation_id=task_request.chat_request.conversation_id or str(uuid.uuid4()),
            model=task_request.chat_request.model,
            processing_time=processing_time,
            tokens_used=len(accumulated_response.split()),  # Rough token estimate
        )
        
        logger.info(
            f"Streaming chat task {task_request.task_id} completed",
            extra={
                "task_id": task_request.task_id,
                "processing_time": processing_time,
                "response_length": len(accumulated_response),
            }
        )
        
        return chat_response.dict()
        
    except Exception as e:
        logger.error(f"Error in streaming chat processing: {e}", exc_info=True)
        raise
    
    finally:
        # Clean up
        try:
            await ollama_manager.close()
        except Exception as e:
            logger.warning(f"Error closing Ollama manager: {e}")


async def _send_streaming_chunk(
    callback_url: str,
    task_id: str,
    chunk: str,
    is_done: bool,
) -> None:
    """Send streaming chunk to callback URL."""
    
    try:
        import aiohttp
        
        payload = {
            "task_id": task_id,
            "chunk": chunk,
            "done": is_done,
            "timestamp": time.time(),
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                callback_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status != 200:
                    logger.warning(f"Callback failed with status {response.status}")
                    
    except Exception as e:
        logger.warning(f"Failed to send streaming chunk: {e}")


async def _build_context_prompt(
    memory_manager,
    user_prompt: str,
    conversation_id: str,
    user_id: str,
    model: str
) -> str:
    """Build context-aware prompt with conversation history and user preferences."""
    
    try:
        # Get conversation history
        conversation = await memory_manager.get_conversation_memory(
            conversation_id, limit=10  # Last 10 messages for context
        )
        
        # Get user preferences and context
        user_memory = await memory_manager.get_user_memory(user_id) if user_id else None
        
        # Build system context
        system_context = []
        
        # Add model identity
        system_context.append(f"Ты - AI ассистент, работающий на модели {model}.")
        
        # Add user context if available
        if user_memory:
            if user_memory.preferences:
                prefs = []
                if user_memory.preferences.get('language'):
                    prefs.append(f"язык: {user_memory.preferences['language']}")
                if user_memory.preferences.get('temperature'):
                    prefs.append(f"стиль ответов: {'творческий' if user_memory.preferences['temperature'] > 0.7 else 'точный'}")
                
                if prefs:
                    system_context.append(f"Предпочтения пользователя: {', '.join(prefs)}.")
            
            if user_memory.facts:
                facts_text = "; ".join(user_memory.facts[-3:])  # Last 3 facts
                system_context.append(f"Известные факты о пользователе: {facts_text}.")
        
        # Build conversation context
        conversation_context = []
        if conversation and conversation.messages:
            conversation_context.append("История диалога:")
            
            # Add recent messages (skip system messages)
            recent_messages = [msg for msg in conversation.messages[-6:] if msg.role != "system"]
            for msg in recent_messages:
                role_name = "Пользователь" if msg.role == "user" else "Ассистент"
                conversation_context.append(f"{role_name}: {msg.content}")
        
        # Combine all context
        full_context = []
        
        if system_context:
            full_context.append("КОНТЕКСТ:")
            full_context.extend(system_context)
            full_context.append("")
        
        if conversation_context:
            full_context.extend(conversation_context)
            full_context.append("")
        
        full_context.append("ТЕКУЩИЙ ВОПРОС:")
        full_context.append(f"Пользователь: {user_prompt}")
        full_context.append("")
        full_context.append("Ассистент:")
        
        enhanced_prompt = "\n".join(full_context)
        
        logger.debug(f"Built context prompt with {len(system_context)} system items, "
                    f"{len(conversation_context)} conversation items")
        
        return enhanced_prompt
        
    except Exception as e:
        logger.warning(f"Failed to build context prompt: {e}")
        # Fallback to simple prompt
        return f"Пользователь: {user_prompt}\n\nАссистент:"


async def _save_conversation_messages(
    memory_manager,
    conversation_id: str,
    user_id: str,
    user_prompt: str,
    assistant_response: str,
    model: str,
    tokens_used: int
) -> None:
    """Save conversation messages to memory."""
    
    try:
        # Save user message
        user_message = ConversationMessage(
            id=str(uuid.uuid4()),
            role="user",
            content=user_prompt,
            tokens=len(user_prompt.split()),  # Approximate token count
            model=None
        )
        
        await memory_manager.save_conversation_message(
            conversation_id=conversation_id,
            message=user_message,
            user_id=user_id,
            ttl_hours=24 * 7  # Keep for 7 days
        )
        
        # Save assistant response
        assistant_message = ConversationMessage(
            id=str(uuid.uuid4()),
            role="assistant",
            content=assistant_response,
            tokens=tokens_used,
            model=model
        )
        
        await memory_manager.save_conversation_message(
            conversation_id=conversation_id,
            message=assistant_message,
            user_id=user_id,
            ttl_hours=24 * 7  # Keep for 7 days
        )
        
        # Update user facts based on conversation
        if user_id:
            await _extract_and_save_user_facts(
                memory_manager, user_id, user_prompt, assistant_response
            )
        
        logger.info(f"Saved conversation messages to memory for {conversation_id}")
        
    except Exception as e:
        logger.warning(f"Failed to save conversation to memory: {e}")


async def _extract_and_save_user_facts(
    memory_manager,
    user_id: str,
    user_prompt: str,
    assistant_response: str
) -> None:
    """Extract and save facts about user from conversation."""
    
    try:
        # Simple fact extraction based on keywords
        facts_to_add = []
        
        prompt_lower = user_prompt.lower()
        
        # Programming languages
        prog_langs = ['python', 'javascript', 'java', 'c++', 'go', 'rust', 'php', 'ruby']
        for lang in prog_langs:
            if lang in prompt_lower and f"программирует на {lang}" not in facts_to_add:
                facts_to_add.append(f"Интересуется программированием на {lang}")
        
        # Interests
        if any(word in prompt_lower for word in ['ai', 'машинное обучение', 'нейронные сети']):
            facts_to_add.append("Интересуется искусственным интеллектом")
        
        if any(word in prompt_lower for word in ['docker', 'kubernetes', 'devops']):
            facts_to_add.append("Работает с DevOps технологиями")
        
        # Language preference
        if any(word in prompt_lower for word in ['на русском', 'по-русски']):
            await memory_manager.update_user_preferences(user_id, {"language": "ru"})
        elif any(word in prompt_lower for word in ['in english', 'на английском']):
            await memory_manager.update_user_preferences(user_id, {"language": "en"})
        
        # Save extracted facts
        for fact in facts_to_add:
            await memory_manager.add_user_fact(user_id, fact)
            
    except Exception as e:
        logger.debug(f"Failed to extract user facts: {e}")


# Health check task
@celery_app.task(name="app.workers.chat_worker.health_check")
def health_check() -> Dict[str, Any]:
    """Worker health check task."""
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "worker_id": celery_app.control.inspect().active(),
    }
