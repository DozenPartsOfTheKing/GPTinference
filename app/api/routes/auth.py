"""Basic authentication routes (env-based)."""

import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel

from ...core.config import settings
from ...utils.loguru_config import get_logger
from ..dependencies import get_client_info

logger = get_logger(__name__)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_in: int


router = APIRouter(prefix="/auth", tags=["auth"])


def _verify_credentials(username: str, password: str) -> bool:
    expected_user = settings.auth_username
    if not expected_user:
        return False
    if username != expected_user:
        return False
    # salted sha256(salt + password)
    salt = settings.auth_salt
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return hashed == settings.auth_password_hash


def _issue_token(username: str) -> str:
    # Very simple opaque token: session_<timestamp>_<hash>
    now = int(datetime.utcnow().timestamp())
    raw = f"{username}:{now}:{settings.secret_key}"
    sig = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"user_{username}_session_{now}_{sig}"


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, client: Dict[str, Any] = Depends(get_client_info)):
    if not _verify_credentials(payload.username, payload.password):
        logger.bind(ip=client.get("ip"), ua=client.get("user_agent")).info("Failed login attempt")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = _issue_token(payload.username)
    # 7 days expiry for simplicity (frontend stores token client-side)
    expires_in = int(timedelta(days=7).total_seconds())
    logger.bind(user=payload.username, ip=client.get("ip")).info("User logged in")
    return LoginResponse(token=token, expires_in=expires_in)


@router.get("/me")
async def me(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    token = auth.split(" ")[-1] if auth else ""
    is_authenticated = token.startswith("user_") or token.startswith("session_")
    user = None
    if token.startswith("user_"):
        # token format: user_<username>_session_...
        try:
            user = token.split("_")[1]
        except Exception:
            user = None
    return {"authenticated": is_authenticated, "user": user}


