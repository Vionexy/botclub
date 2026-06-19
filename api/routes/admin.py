"""Admin endpoints (admin authorized)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth.telegram import get_admin_user
from api.models.bracket import BracketMatchRead, MatchResultUpdate, PlayerInfo
from api.models.tournament import TournamentCreate, TournamentRead, TournamentUpdate
from database.db import get_session
from database.models import BracketMatch, Registration, Tournament, User
from services.bracket import generate_single_elimination, set_match_result
from services.notification import send_bracket_published, send_results_published

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/check")
async def check_admin(user: User = Depends(get_admin_user)) -> dict:
    """Check if the user is an admin."""
    return {"is_admin": True, "display_name": user.display_name}


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
) -> dict:
    """Get admin dashboard stats."""
    tournaments_stmt = select(func.count(Tournament.id)).where(Tournament.status != "completed")
    tournaments_result = await session.execute(tournaments_stmt)
    active_tournaments = tournaments_result.scalar() or 0

    users_stmt = select(func.count(User.id))
    users_result = await session.execute(users_stmt)
    total_users = users_result.scalar() or 0

    return {
        "active_tournaments": active_tournaments,
        "total_users": total_users,
    }


@router.get("/users", response_model=list[PlayerInfo])
async def list_users(
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
) -> list[User]:
    """List all registered users."""
    stmt = select(User).order_by(User.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("/tournaments", response_model=TournamentRead)
async def create_tournament(
    payload: TournamentCreate,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
) -> Tournament:
    """Create a new tournament."""
    t = Tournament(
        title=payload.title,
        description=payload.description,
        game_mode=payload.game_mode,
        tournament_type=payload.tournament_type,
        bracket_type=payload.bracket_type,
        prize_1st=payload.prize_1st,
        prize_2nd=payload.prize_2nd,
        prize_3rd=payload.prize_3rd,
        status=payload.status,
        max_participants=payload.max_participants,
        start_date=payload.start_date,
        registration_deadline=payload.registration_deadline,
        created_by=admin.id,
    )
    session.add(t)
    await session.commit()
    return t


@router.put("/tournaments/{tournament_id}", response_model=TournamentRead)
async def update_tournament(
    tournament_id: int,
    payload: TournamentUpdate,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
) -> Tournament:
    """Update tournament fields."""
    stmt = select(Tournament).where(Tournament.id == tournament_id)
    result = await session.execute(stmt)
    t = result.scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(t, field, value)

    await session.commit()
    return t


@router.delete("/tournaments/{tournament_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_tournament(
    tournament_id: int,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Delete a tournament."""
    stmt = select(Tournament).where(Tournament.id == tournament_id)
    result = await session.execute(stmt)
    t = result.scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    await session.delete(t)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tournaments/{tournament_id}/generate-bracket", response_model=list[BracketMatchRead])
async def generate_tournament_bracket(
    tournament_id: int,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
) -> list[BracketMatchRead]:
    """Generate the bracket for a tournament."""
    stmt = select(Tournament).where(Tournament.id == tournament_id)
    result = await session.execute(stmt)
    t = result.scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    try:
        matches = await generate_single_elimination(session, tournament_id, shuffle=True)
        t.status = "active"  # Automatically set status to active when bracket generated
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Re-fetch matches with player relationships loaded
    stmt_refetch = (
        select(BracketMatch)
        .where(BracketMatch.tournament_id == tournament_id)
        .options(
            selectinload(BracketMatch.player1),
            selectinload(BracketMatch.player2),
            selectinload(BracketMatch.winner),
        )
        .order_by(BracketMatch.round_number, BracketMatch.match_number)
    )
    result_refetch = await session.execute(stmt_refetch)
    matches_loaded = result_refetch.scalars().all()

    output = []
    for m in matches_loaded:
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


@router.put("/brackets/{match_id}/result", response_model=BracketMatchRead)
async def update_bracket_match_result(
    match_id: int,
    payload: MatchResultUpdate,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
) -> BracketMatchRead:
    """Set match result (winner and score) and advance the bracket."""
    try:
        updated_match = await set_match_result(
            session, match_id, payload.winner_id, payload.score
        )
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Re-fetch match with player relationships
    stmt = (
        select(BracketMatch)
        .where(BracketMatch.id == match_id)
        .options(
            selectinload(BracketMatch.player1),
            selectinload(BracketMatch.player2),
            selectinload(BracketMatch.winner),
        )
    )
    result = await session.execute(stmt)
    m = result.scalar_one_or_none()
    if not m:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    return BracketMatchRead(
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


@router.post("/tournaments/{tournament_id}/notify")
async def notify_users(
    tournament_id: int,
    request: Request,
    type: str = Query("bracket", alias="type"),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
) -> dict:
    """Send bracket or results update notification to registered tournament participants."""
    bot = getattr(request.app.state, "bot", None)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Telegram bot is not initialized in the API backend",
        )

    stmt = select(Tournament).where(Tournament.id == tournament_id)
    result = await session.execute(stmt)
    t = result.scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    sent_count = 0
    if type == "bracket":
        sent_count = await send_bracket_published(
            bot, session, tournament_id, t.title, t.game_mode
        )
    else:
        sent_count = await send_results_published(
            bot, session, tournament_id, t.title, t.game_mode
        )

    await session.commit()
    return {"sent_count": sent_count}


def _player_info(user: User) -> PlayerInfo:
    return PlayerInfo(
        id=user.id,
        telegram_id=user.telegram_id,
        display_name=user.display_name,
        username=user.username,
        brawl_stars_tag=user.brawl_stars_tag,
    )
