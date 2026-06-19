"""Registration endpoint (public, authenticated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.telegram import get_current_user
from api.models.tournament import RegistrationRead
from api.models.user import UserRead
from database.db import get_session
from database.models import Registration, Tournament, User

router = APIRouter(prefix="/api/tournaments", tags=["registrations"])


@router.post("/{tournament_id}/register", response_model=RegistrationRead, status_code=status.HTTP_201_CREATED)
async def register_for_tournament(
    tournament_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Registration:
    """Register the current user for a tournament."""
    # Check tournament exists and is open for registration
    stmt = select(Tournament).where(Tournament.id == tournament_id)
    result = await session.execute(stmt)
    tournament = result.scalar_one_or_none()
    if tournament is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Турнир не найден")

    if tournament.status not in ("registration", "draft"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Регистрация на турнир закрыта",
        )

    # Check if already registered
    existing_stmt = select(Registration).where(
        Registration.tournament_id == tournament_id,
        Registration.user_id == user.id,
    )
    existing_result = await session.execute(existing_stmt)
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Вы уже зарегистрированы на этот турнир",
        )

    # Check max participants
    count_stmt = (
        select(func.count())
        .select_from(Registration)
        .where(Registration.tournament_id == tournament_id)
    )
    count_result = await session.execute(count_stmt)
    current_count = count_result.scalar() or 0
    if current_count >= tournament.max_participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Достигнуто максимальное количество участников",
        )

    registration = Registration(
        tournament_id=tournament_id,
        user_id=user.id,
        status="registered",
    )
    session.add(registration)
    await session.flush()
    return registration


@router.delete("/{tournament_id}/register", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def unregister_from_tournament(
    tournament_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Unregister the current user from a tournament."""
    stmt = select(Registration).where(
        Registration.tournament_id == tournament_id,
        Registration.user_id == user.id,
    )
    result = await session.execute(stmt)
    registration = result.scalar_one_or_none()
    if registration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Вы не зарегистрированы на этот турнир",
        )

    # Check tournament status (only draft or registration)
    stmt_t = select(Tournament).where(Tournament.id == tournament_id)
    result_t = await session.execute(stmt_t)
    tournament = result_t.scalar_one_or_none()
    if tournament and tournament.status not in ("registration", "draft"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя отменить регистрацию, так как турнир уже начался",
        )

    await session.delete(registration)
    await session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{tournament_id}/participants", response_model=list[UserRead])
async def list_tournament_participants(
    tournament_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[User]:
    """Get list of users registered for a specific tournament."""
    stmt = (
        select(User)
        .join(Registration, Registration.user_id == User.id)
        .where(Registration.tournament_id == tournament_id)
        .order_by(Registration.registered_at.asc())
    )
    result = await session.execute(stmt)
    users = result.scalars().all()
    return list(users)


