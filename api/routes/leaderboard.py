"""Leaderboard endpoint (public, authenticated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.telegram import get_current_user
from api.models.user import UserLeaderboard
from database.db import get_session
from database.models import User
from services.tournament import get_leaderboard

router = APIRouter(prefix="/api", tags=["leaderboard"])


@router.get("/leaderboard", response_model=list[UserLeaderboard])
async def leaderboard(
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Return top players ranked by total match wins."""
    return await get_leaderboard(session, limit=limit)
