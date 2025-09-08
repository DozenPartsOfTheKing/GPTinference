"""Models for LLM intent router schemas and routing requests."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RouterClass(BaseModel):
    """A single intent/class definition for the router."""
    name: str = Field(..., min_length=1, max_length=128, description="Unique class key (e.g., internet_search)")
    description: str = Field(..., min_length=1, description="What this class means and when to choose it")


class RouterExample(BaseModel):
    """Few-shot example used to guide the router."""
    query: str = Field(..., min_length=1, description="User query example")
    expected: Dict[str, Any] = Field(
        ..., description="Expected JSON output for the example (e.g., {\"internet_search\": \"билеты ...\"})"
    )


class RouterSchema(BaseModel):
    """Router schema stored in system memory."""
    key: str = Field(..., min_length=1, max_length=255, description="Unique key for the router schema")
    title: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    classes: List[RouterClass] = Field(default_factory=list)
    examples: List[RouterExample] = Field(default_factory=list, description="Up to ~10 examples recommended")


class RouterCreateRequest(BaseModel):
    """Create or update router schema request."""
    key: str
    title: Optional[str] = None
    description: Optional[str] = None
    classes: List[RouterClass] = Field(default_factory=list)
    examples: List[RouterExample] = Field(default_factory=list)


class RouteRequest(BaseModel):
    """Route a user query using a router schema and LLM."""
    query: str = Field(..., min_length=1)
    schema_key: Optional[str] = Field(default=None, description="Use this schema; if omitted, active schema is used")
    system_message: Optional[str] = Field(default=None, description="Override default router system prompt")
    model: str = Field(default="llama3.2:3b", description="Model used for intent routing")


class RouteResponse(BaseModel):
    """Router result."""
    selected_class: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    by_class_key: Optional[Dict[str, Any]] = None
    raw: Optional[str] = None
    schema_key: Optional[str] = None


