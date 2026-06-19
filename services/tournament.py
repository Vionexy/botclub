"""Tournament business logic."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import BracketMatch, Registration, Tournament, User


async def get_tournaments(
    session: AsyncSession,
    status_filter: str | None = None,
) -> list[dict]:
    """Return tournaments with participant counts."""
    stmt = select(Tournament).order_by(Tournament.created_at.desc())
    if status_filter:
        stmt = stmt.where(Tournament.status == status_filter)

    result = await session.execute(stmt)
    tournaments = result.scalars().all()

    output: list[dict] = []
    for t in tournaments:
        count_stmt = (
            select(func.count())
            .select_from(Registration)
            .where(Registration.tournament_id == t.id)
        )
        count_result = await session.execute(count_stmt)
        count = count_result.scalar() or 0
        data = {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "game_mode": t.game_mode,
            "tournament_type": t.tournament_type,
            "bracket_type": t.bracket_type,
            "prize_1st": t.prize_1st,
            "prize_2nd": t.prize_2nd,
            "prize_3rd": t.prize_3rd,
            "status": t.status,
            "max_participants": t.max_participants,
            "start_date": t.start_date,
            "registration_deadline": t.registration_deadline,
            "created_at": t.created_at,
            "created_by": t.created_by,
            "participant_count": count,
            "image_id": t.image_id,
        }
        output.append(data)
    return output


async def get_tournament_by_id(
    session: AsyncSession,
    tournament_id: int,
    user_id: int | None = None,
) -> dict | None:
    """Return a single tournament with participant count and user registration status."""
    stmt = select(Tournament).where(Tournament.id == tournament_id)
    result = await session.execute(stmt)
    t = result.scalar_one_or_none()
    if t is None:
        return None

    count_stmt = (
        select(func.count())
        .select_from(Registration)
        .where(Registration.tournament_id == t.id)
    )
    count_result = await session.execute(count_stmt)
    count = count_result.scalar() or 0

    is_registered = False
    if user_id:
        reg_stmt = select(Registration).where(
            Registration.tournament_id == t.id,
            Registration.user_id == user_id,
        )
        reg_result = await session.execute(reg_stmt)
        is_registered = reg_result.scalar_one_or_none() is not None

    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "game_mode": t.game_mode,
        "tournament_type": t.tournament_type,
        "bracket_type": t.bracket_type,
        "prize_1st": t.prize_1st,
        "prize_2nd": t.prize_2nd,
        "prize_3rd": t.prize_3rd,
        "status": t.status,
        "max_participants": t.max_participants,
        "start_date": t.start_date,
        "registration_deadline": t.registration_deadline,
        "created_at": t.created_at,
        "created_by": t.created_by,
        "participant_count": count,
        "is_registered": is_registered,
        "image_id": t.image_id,
    }


async def get_completed_tournaments(session: AsyncSession) -> list[dict]:
    """Return completed tournaments."""
    return await get_tournaments(session, status_filter="completed")


async def get_leaderboard(session: AsyncSession, limit: int = 50) -> list[dict]:
    """Top players ranked by total match wins across all tournaments."""
    stmt = (
        select(
            User,
            func.count(BracketMatch.id).label("wins"),
        )
        .join(BracketMatch, BracketMatch.winner_id == User.id)
        .group_by(User.id)
        .order_by(func.count(BracketMatch.id).desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()

    output: list[dict] = []
    for user, wins in rows:
        output.append(
            {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "display_name": user.display_name,
                "brawl_stars_tag": user.brawl_stars_tag,
                "wins": wins,
            }
        )
    return output
