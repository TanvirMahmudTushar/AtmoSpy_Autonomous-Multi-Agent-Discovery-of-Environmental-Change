import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limit import rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201, dependencies=[Depends(rate_limit(20, 60))])
async def signup(body: SignupRequest, session: AsyncSession = Depends(get_db)):
    existing = (await session.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        is_demo=False,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    await session.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit(20, 60))])
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)):
    user = (await session.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/guest", response_model=TokenResponse, status_code=201, dependencies=[Depends(rate_limit(20, 60))])
async def guest_login(session: AsyncSession = Depends(get_db)):
    """Creates a brand-new throwaway account and logs into it immediately —
    no form, no email. A fresh row every call, never a shared account
    (two guests sharing one row would see each other's watches/investigations
    history). The random password is generated only so it satisfies the
    schema's NOT NULL constraint; nothing needs to know it, since this
    account is only ever reached via the token this endpoint returns, never
    via a future /login call.

    is_demo=True is otherwise inert today (grep confirms nothing in the
    backend branches on it) — it's here so a guest row is honestly
    distinguishable from a real signup if that's ever needed later, not
    because it currently restricts anything. A guest gets the exact same
    user_id-backed access as any signed-up user, including Watches."""
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"guest-{suffix}@guest.local",
        password_hash=hash_password(secrets.token_urlsafe(32)),
        display_name=f"Guest-{suffix[:5]}",
        is_demo=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)
