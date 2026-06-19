"""User profile endpoints (public, authenticated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.telegram import get_current_user
from api.models.user import UserRead, UserUpdate
from database.db import get_session
from database.models import User

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(
    user: User = Depends(get_current_user),
) -> User:
    """Return the authenticated user's profile."""
    return user


@router.put("/me", response_model=UserRead)
async def update_me(
    body: UserUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> User:
    """Update the authenticated user's profile (brawl_stars_tag, display_name)."""
    if body.brawl_stars_tag is not None:
        user.brawl_stars_tag = body.brawl_stars_tag
    if body.display_name is not None:
        user.display_name = body.display_name
    await session.flush()
    return user
