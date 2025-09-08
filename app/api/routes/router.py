"""Router schemas CRUD and routing endpoints."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ...utils.loguru_config import get_logger
from ...api.dependencies import check_user_rate_limit
from ...services.hybrid_memory_manager import get_hybrid_memory_manager
from ...services.ollama_manager import get_ollama_manager, OllamaManager
from ...models.ollama import OllamaRequest
from ...services.router_service import build_router_system_prompt, build_router_user_prompt
from ...models.router import RouterCreateRequest, RouteRequest, RouteResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/router", tags=["router"])


@router.get("/schemas", response_model=List[Dict[str, Any]])
async def list_router_schemas(
    user_id: str = Depends(check_user_rate_limit),
    memory_manager = Depends(get_hybrid_memory_manager),
):
    try:
        return await memory_manager.list_router_schemas()
    except Exception as e:
        logger.error(f"Failed to list router schemas: {e}")
        raise HTTPException(status_code=500, detail="Failed to list router schemas")


@router.post("/schemas", status_code=status.HTTP_201_CREATED)
async def create_router_schema(
    request: RouterCreateRequest,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager = Depends(get_hybrid_memory_manager),
):
    try:
        value = {
            "title": request.title or request.key,
            "description": request.description,
            "schema": {
                "classes": [c.dict() for c in request.classes],
                "examples": [e.dict() for e in request.examples],
            },
            "created_by": user_id,
        }
        success = await memory_manager.save_router_schema(
            key=request.key,
            schema_value=value["schema"],
            title=value["title"],
            description=value["description"],
            created_by=user_id,
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save router schema")
        return {"success": True, "key": request.key}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create router schema: {e}")
        raise HTTPException(status_code=500, detail="Failed to create router schema")


@router.delete("/schemas/{key}")
async def delete_router_schema(
    key: str,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager = Depends(get_hybrid_memory_manager),
):
    try:
        success = await memory_manager.delete_router_schema(key)
        if not success:
            raise HTTPException(status_code=404, detail="Schema not found")
        # If active, unset
        active = await memory_manager.get_active_router_schema()
        if active and active.get("key") == key:
            await memory_manager.set_system_memory(key='router_active', value=None, memory_type='preferences')
        return {"success": True, "key": key}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete router schema {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete router schema")


@router.put("/schemas/{key}/activate")
async def activate_router_schema(
    key: str,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager = Depends(get_hybrid_memory_manager),
):
    try:
        success = await memory_manager.set_active_router_schema(key)
        if not success:
            raise HTTPException(status_code=404, detail="Schema not found")
        return {"success": True, "key": key}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate router schema {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to activate router schema")


@router.get("/schemas/active")
async def get_active_router_schema(
    user_id: str = Depends(check_user_rate_limit),
    memory_manager = Depends(get_hybrid_memory_manager),
):
    try:
        active = await memory_manager.get_active_router_schema()
        return {"active": active}
    except Exception as e:
        logger.error(f"Failed to get active router schema: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active router schema")


def _build_router_system_prompt(schema: Dict[str, Any], system_message_override: Optional[str]) -> str:
    return build_router_system_prompt(schema, system_message_override)


def _build_router_prompt(user_query: str, schema: Dict[str, Any]) -> str:
    return build_router_user_prompt(user_query, schema)


@router.post("/route", response_model=RouteResponse)
async def route_query(
    request: RouteRequest,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager = Depends(get_hybrid_memory_manager),
    ollama_manager: OllamaManager = Depends(get_ollama_manager),
):
    try:
        # Get schema
        schema_record: Optional[Dict[str, Any]] = None
        if request.schema_key:
            value = await memory_manager.get_system_memory(request.schema_key)
            if value is None:
                raise HTTPException(status_code=404, detail="Schema not found")
            schema_record = {"key": request.schema_key, **(value if isinstance(value, dict) else {"schema": value})}
        else:
            active = await memory_manager.get_active_router_schema()
            if not active:
                raise HTTPException(status_code=400, detail="Active router schema not set")
            schema_record = active

        schema = schema_record.get("schema") or {}
        system_prompt = _build_router_system_prompt(schema, request.system_message)
        user_prompt = _build_router_prompt(request.query, schema)

        # Validate model availability
        from fastapi import status as _status
        if not await ollama_manager.is_model_available(request.model):
            raise HTTPException(
                status_code=_status.HTTP_400_BAD_REQUEST,
                detail=f"Model '{request.model}' is not available"
            )

        # Call LLM
        ollama_req = OllamaRequest(
            model=request.model,
            prompt=f"<|system|>\n{system_prompt}\n\n<|user|>\n{user_prompt}\n",
            stream=False,
        )
        resp = await ollama_manager.generate(ollama_req)
        raw_text = getattr(resp, 'response', None) or getattr(resp, 'text', None) or str(resp)

        # Try to parse JSON
        selected_class = None
        arguments: Optional[Dict[str, Any]] = None
        by_class_key: Optional[Dict[str, Any]] = None
        try:
            import json as _json
            parsed = _json.loads(raw_text)
            if isinstance(parsed, dict):
                # Common patterns:
                # {"class": "internet_search", "arguments": {"query": "..."}}
                # {"internet_search": "билеты москва рязань"}
                if "class" in parsed:
                    selected_class = parsed.get("class")
                    arguments = parsed.get("arguments") if isinstance(parsed.get("arguments"), dict) else None
                else:
                    # Pick first key
                    if len(parsed.keys()) > 0:
                        selected_class = next(iter(parsed.keys()))
                        val = parsed[selected_class]
                        if isinstance(val, dict):
                            arguments = val
                        else:
                            arguments = {"value": val}
                by_class_key = parsed
        except Exception:
            pass

        return RouteResponse(
            selected_class=selected_class,
            arguments=arguments,
            by_class_key=by_class_key,
            raw=raw_text,
            schema_key=schema_record.get("key"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to route query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Routing failed")


