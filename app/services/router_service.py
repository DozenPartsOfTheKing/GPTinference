"""Utilities for LLM intent routing."""

from typing import Any, Dict, Optional

from ..models.ollama import OllamaRequest
from ..services.ollama_manager import OllamaManager


def build_router_system_prompt(schema: Dict[str, Any], system_message_override: Optional[str]) -> str:
    if system_message_override:
        base = system_message_override
    else:
        base = (
            "Ты маршрутизатор намерений. Твоя задача — выбрать один класс из списка и вернуть JSON. "
            "Отвечай строго JSON без лишнего текста. Если класс не подходит, верни пустой объект."
        )
    classes = schema.get("classes", [])
    examples = schema.get("examples", [])
    class_lines = [f"- {c.get('name')}: {c.get('description')}" for c in classes]
    examples_lines = []
    for ex in examples:
        examples_lines.append(f"запрос: \"{ex.get('query')}\"")
        examples_lines.append(f"{ex.get('expected')}")
        examples_lines.append("")
    return (
        base
        + "\n\nДоступные классы:"
        + ("\n" + "\n".join(class_lines) if class_lines else "\n- ")
        + "\n\nПримеры формата ответа:"
        + ("\n" + "\n".join(examples_lines) if examples_lines else "\n")
        + "\nВерни только JSON."
    )


def build_router_user_prompt(user_query: str, schema: Dict[str, Any]) -> str:
    class_names = ", ".join([c.get("name") for c in schema.get("classes", [])])
    return (
        f"Тебе приходит вопрос. Доступно классов: {len(schema.get('classes', []))}. "
        f"Названия классов: {class_names}. "
        f"Верни ответ строго в JSON с выбранным классом и аргументами.\n\nВопрос: {user_query}"
    )


async def run_router(
    ollama_manager: OllamaManager,
    schema: Dict[str, Any],
    query: str,
    model: str = "llama3.2:3b",
    system_message_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute routing and return parsed result with fallbacks."""
    sys_prompt = build_router_system_prompt(schema, system_message_override)
    user_prompt = build_router_user_prompt(query, schema)

    # Validate model outside to reuse caller's check when possible
    req = OllamaRequest(
        model=model,
        prompt=f"<|system|>\n{sys_prompt}\n\n<|user|>\n{user_prompt}\n",
        stream=False,
    )
    resp = await ollama_manager.generate(req)
    raw_text = getattr(resp, 'response', None) or getattr(resp, 'text', None) or str(resp)

    selected_class = None
    arguments: Optional[Dict[str, Any]] = None
    by_class_key: Optional[Dict[str, Any]] = None
    try:
        import json as _json
        parsed = _json.loads(raw_text)
        if isinstance(parsed, dict):
            if "class" in parsed:
                selected_class = parsed.get("class")
                arguments = parsed.get("arguments") if isinstance(parsed.get("arguments"), dict) else None
            else:
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

    return {
        "selected_class": selected_class,
        "arguments": arguments,
        "by_class_key": by_class_key,
        "raw": raw_text,
    }


