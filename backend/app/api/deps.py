"""Auth dependencies shared across routers."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip()


async def get_current_user_optional(request: Request, session: AsyncSession = Depends(get_db)) -> User | None:
    token = _extract_token(request)
    if not token:
        return None
    user_id = decode_access_token(token)
    if not user_id:
        return None
    return (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()


async def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
