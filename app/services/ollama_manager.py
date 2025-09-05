"""Ollama API manager with connection pooling and error handling."""

import asyncio
import logging
from functools import lru_cache
from typing import Dict, List, Optional

import aiohttp
from aiohttp import ClientTimeout

from ..core.config import settings
from ..models.ollama import (
    ModelInfo,
    ModelListResponse,
    OllamaRequest,
    OllamaResponse,
)

logger = logging.getLogger(__name__)


class OllamaConnectionError(Exception):
    """Ollama connection error."""
    pass


class OllamaModelNotFoundError(Exception):
    """Ollama model not found error."""
    pass


class OllamaManager:
    """Manages connections and requests to Ollama API."""
    
    def __init__(
        self,
        base_url: str = None,
        timeout: int = None,
        max_retries: int = None,
        connector_limit: int = 100,
    ):
        self.base_url = base_url or settings.ollama_base_url
        self.timeout = timeout or settings.ollama_timeout
        self.max_retries = max_retries or settings.ollama_max_retries
        self.connector_limit = connector_limit
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._available_models: Dict[str, ModelInfo] = {}
        self._models_last_updated: Optional[float] = None
        self._models_cache_ttl = 300  # 5 minutes
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with connection pooling."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.connector_limit,
                limit_per_host=20,
                ttl_dns_cache=300,
                use_dns_cache=True,
            )
            
            timeout = ClientTimeout(total=self.timeout)
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={"Content-Type": "application/json"},
            )
            
        return self._session
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def health_check(self) -> bool:
        """Check if Ollama service is healthy."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/tags") as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
    
    async def list_models(self, force_refresh: bool = False) -> ModelListResponse:
        """Get list of available models with caching."""
        import time
        
        current_time = time.time()
        
        # Check cache validity
        if (
            not force_refresh 
            and self._models_last_updated 
            and (current_time - self._models_last_updated) < self._models_cache_ttl
            and self._available_models
        ):
            return ModelListResponse(models=list(self._available_models.values()))
        
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/tags") as response:
                if response.status != 200:
                    raise OllamaConnectionError(f"Failed to fetch models: {response.status}")
                
                data = await response.json()
                models_data = data.get("models", [])
                
                # Parse and cache models
                self._available_models = {}
                for model_data in models_data:
                    try:
                        # Handle different response formats
                        model_info = ModelInfo(
                            name=model_data["name"],
                            size=model_data.get("size", "unknown"),
                            digest=model_data.get("digest", ""),
                            modified_at=model_data.get("modified_at", model_data.get("modified", "1970-01-01T00:00:00Z")),
                            details=model_data.get("details"),
                        )
                        self._available_models[model_info.name] = model_info
                    except Exception as e:
                        logger.warning(f"Failed to parse model data {model_data}: {e}")
                        continue
                
                self._models_last_updated = current_time
                
                return ModelListResponse(models=list(self._available_models.values()))
                
        except aiohttp.ClientError as e:
            raise OllamaConnectionError(f"Connection error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error listing models: {e}")
            raise
    
    async def is_model_available(self, model_name: str) -> bool:
        """Check if a specific model is available."""
        try:
            models_response = await self.list_models()
            return any(model.name == model_name for model in models_response.models)
        except Exception:
            return False
    
    async def generate(
        self,
        request: OllamaRequest,
        retry_count: int = 0,
    ) -> OllamaResponse:
        """Generate response using Ollama API with retry logic."""
        
        # Validate model availability
        if not await self.is_model_available(request.model):
            raise OllamaModelNotFoundError(f"Model '{request.model}' not found")
        
        session = await self._get_session()
        
        # Prepare request payload
        payload = request.dict(exclude_none=True)
        
        try:
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as response:
                
                if response.status == 404:
                    raise OllamaModelNotFoundError(f"Model '{request.model}' not found")
                elif response.status != 200:
                    error_text = await response.text()
                    raise OllamaConnectionError(
                        f"Ollama API error {response.status}: {error_text}"
                    )
                
                response_data = await response.json()
                return OllamaResponse(**response_data)
                
        except aiohttp.ClientError as e:
            if retry_count < self.max_retries:
                logger.warning(
                    f"Request failed (attempt {retry_count + 1}/{self.max_retries + 1}): {e}"
                )
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                return await self.generate(request, retry_count + 1)
            else:
                raise OllamaConnectionError(f"Max retries exceeded: {e}")
        
        except Exception as e:
            logger.error(f"Unexpected error during generation: {e}")
            raise
    
    async def generate_stream(
        self,
        request: OllamaRequest,
    ):
        """Generate streaming response using Ollama API."""
        
        # Validate model availability
        if not await self.is_model_available(request.model):
            raise OllamaModelNotFoundError(f"Model '{request.model}' not found")
        
        session = await self._get_session()
        
        # Force streaming mode
        request.stream = True
        payload = request.dict(exclude_none=True)
        
        try:
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as response:
                
                if response.status == 404:
                    raise OllamaModelNotFoundError(f"Model '{request.model}' not found")
                elif response.status != 200:
                    error_text = await response.text()
                    raise OllamaConnectionError(
                        f"Ollama API error {response.status}: {error_text}"
                    )
                
                async for line in response.content:
                    if line:
                        try:
                            import json
                            chunk_data = json.loads(line.decode('utf-8'))
                            yield OllamaResponse(**chunk_data)
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.warning(f"Failed to parse streaming chunk: {e}")
                            continue
                            
        except aiohttp.ClientError as e:
            raise OllamaConnectionError(f"Streaming connection error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during streaming: {e}")
            raise
    
    async def pull_model(self, model_name: str) -> bool:
        """Pull/download a model."""
        try:
            session = await self._get_session()
            payload = {"name": model_name}
            
            async with session.post(
                f"{self.base_url}/api/pull",
                json=payload
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to pull model {model_name}: {error_text}")
                    return False
                
                # Force refresh models cache
                await self.list_models(force_refresh=True)
                return True
                
        except Exception as e:
            logger.error(f"Error pulling model {model_name}: {e}")
            return False
    
    def __del__(self):
        """Cleanup on deletion."""
        if self._session and not self._session.closed:
            # Create a new event loop if needed for cleanup
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.close())
                else:
                    loop.run_until_complete(self.close())
            except Exception:
                pass


# Global instance
_ollama_manager: Optional[OllamaManager] = None


@lru_cache()
def get_ollama_manager() -> OllamaManager:
    """Get singleton Ollama manager instance."""
    global _ollama_manager
    if _ollama_manager is None:
        _ollama_manager = OllamaManager()
    return _ollama_manager
