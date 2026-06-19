"""Tournament endpoints (public, authenticated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.telegram import get_current_user
from api.models.tournament import TournamentRead
from database.db import get_session
from database.models import User
from services.tournament import (
    get_completed_tournaments,
    get_tournament_by_id,
    get_tournaments,
)

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])


@router.get("", response_model=list[TournamentRead])
async def list_tournaments(
    status_filter: str | None = Query(None, alias="status"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """List tournaments, optionally filtered by status."""
    tournaments = await get_tournaments(session, status_filter=status_filter)
    # Enrich with is_registered flag for current user
    for t in tournaments:
        detail = await get_tournament_by_id(session, t["id"], user_id=user.id)
        if detail:
            t["is_registered"] = detail["is_registered"]
    return tournaments


@router.get("/history", response_model=list[TournamentRead])
async def tournament_history(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Return completed tournaments."""
    return await get_completed_tournaments(session)


@router.get("/{tournament_id}", response_model=TournamentRead)
async def get_tournament(
    tournament_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Get tournament details by ID."""
    data = await get_tournament_by_id(session, tournament_id, user_id=user.id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    return data


@router.get("/{tournament_id}/image")
async def get_tournament_image(
    tournament_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Securely proxy the tournament banner image from Telegram to the web client."""
    from database.models import Tournament
    from sqlalchemy import select
    import httpx
    from fastapi.responses import Response
    from config import settings

    stmt = select(Tournament).where(Tournament.id == tournament_id)
    result = await session.execute(stmt)
    t = result.scalar_one_or_none()
    if not t or not t.image_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    async with httpx.AsyncClient() as client:
        # Get file path
        url_file_info = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/getFile"
        res_info = await client.get(url_file_info, params={"file_id": t.image_id})
        if res_info.status_code != 200:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failed to fetch image info from Telegram")
        
        file_path = res_info.json().get("result", {}).get("file_path")
        if not file_path:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image path empty")

        # Download file content
        url_download = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file_path}"
        res_content = await client.get(url_download)
        if res_content.status_code != 200:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failed to download image from Telegram")

        return Response(content=res_content.content, media_type="image/jpeg")

