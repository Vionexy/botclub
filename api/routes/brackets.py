"""Bracket endpoints (public, authenticated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth.telegram import get_current_user
from api.models.bracket import BracketMatchRead, PlayerInfo
from database.db import get_session
from database.models import BracketMatch, User

router = APIRouter(prefix="/api/tournaments", tags=["brackets"])


@router.get("/{tournament_id}/bracket", response_model=list[BracketMatchRead])
async def get_bracket(
    tournament_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[BracketMatchRead]:
    """Return all bracket matches for a tournament."""
    stmt = (
        select(BracketMatch)
        .where(BracketMatch.tournament_id == tournament_id)
        .options(
            selectinload(BracketMatch.player1),
            selectinload(BracketMatch.player2),
            selectinload(BracketMatch.winner),
        )
        .order_by(BracketMatch.round_number, BracketMatch.match_number)
    )
    result = await session.execute(stmt)
    matches = result.scalars().all()

    output: list[BracketMatchRead] = []
    for m in matches:
        output.append(
            BracketMatchRead(
                id=m.id,
                tournament_id=m.tournament_id,
                round_number=m.round_number,
                match_number=m.match_number,
                player1=_player_info(m.player1) if m.player1 else None,
                player2=_player_info(m.player2) if m.player2 else None,
                winner=_player_info(m.winner) if m.winner else None,
                score=m.score,
                status=m.status,
                next_match_id=m.next_match_id,
            )
        )
    return output


def _player_info(user: User) -> PlayerInfo:
    return PlayerInfo(
        id=user.id,
        telegram_id=user.telegram_id,
        display_name=user.display_name,
        username=user.username,
        brawl_stars_tag=user.brawl_stars_tag,
    )
