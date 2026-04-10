"""
IncidentOps - Shared Auth Dependencies

Contains JWT config, token creation, and user extraction.
Shared by main.py and route modules to avoid circular imports.
"""
import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.repositories import UserRepository
from app.db.schemas import UserResponse

# === JWT Config ===
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # 1 week


def create_access_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserResponse | None:
    """Extract user from JWT Bearer token or API key"""
    auth_header = request.headers.get("Authorization", "")
    api_key = request.headers.get("X-API-Key", "")

    user_repo = UserRepository(db)

    # Try Bearer token
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = int(payload.get("sub", 0))
            user = await user_repo.get_by_id(user_id)
            if user and user.is_active:
                return UserResponse.model_validate(user)
        except JWTError:
            pass

    # Try API key
    if api_key:
        user = await user_repo.get_by_api_key(api_key)
        if user and user.is_active:
            return UserResponse.model_validate(user)

    return None
