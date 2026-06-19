"""Bracket generation – single elimination."""

from __future__ import annotations

import math
import random

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BracketMatch, Registration


async def generate_single_elimination(
    session: AsyncSession,
    tournament_id: int,
    *,
    shuffle: bool = True,
) -> list[BracketMatch]:
    """Generate a single-elimination bracket for a tournament.

    Steps:
    1. Fetch confirmed/registered players.
    2. Pad to the next power of 2 (byes).
    3. Create all match slots with next_match links.
    4. Seed players into round-1 matches.
    """
    # Fetch registered players
    stmt = (
        select(Registration)
        .where(
            Registration.tournament_id == tournament_id,
            Registration.status.in_(["registered", "confirmed"]),
        )
        .order_by(Registration.registered_at)
    )
    result = await session.execute(stmt)
    registrations = list(result.scalars().all())

    player_ids = [r.user_id for r in registrations]
    if len(player_ids) < 2:
        raise ValueError("Need at least 2 players to generate a bracket")

    if shuffle:
        random.shuffle(player_ids)

    # Pad to next power of 2
    n = len(player_ids)
    bracket_size = 2 ** math.ceil(math.log2(n))
    # Pad with None (byes)
    while len(player_ids) < bracket_size:
        player_ids.append(None)  # type: ignore[arg-type]

    total_rounds = int(math.log2(bracket_size))

    # Remove existing bracket for this tournament
    await session.execute(
        delete(BracketMatch).where(BracketMatch.tournament_id == tournament_id)
    )
    await session.flush()

    # Create all matches per round (bottom-up)
    matches_by_round: dict[int, list[BracketMatch]] = {}
    global_match_num = 0

    for rnd in range(1, total_rounds + 1):
        num_matches_in_round = bracket_size // (2**rnd)
        matches_by_round[rnd] = []
        for i in range(num_matches_in_round):
            global_match_num += 1
            m = BracketMatch(
                tournament_id=tournament_id,
                round_number=rnd,
                match_number=global_match_num,
                status="pending",
            )
            session.add(m)
            matches_by_round[rnd].append(m)

    await session.flush()  # assigns IDs

    # Link next_match: every pair of matches in round R feeds into one match in round R+1
    for rnd in range(1, total_rounds):
        current = matches_by_round[rnd]
        next_rnd = matches_by_round[rnd + 1]
        for idx, match in enumerate(current):
            match.next_match_id = next_rnd[idx // 2].id

    # Seed players into round 1
    round1 = matches_by_round[1]
    for idx, match in enumerate(round1):
        p1 = player_ids[idx * 2]
        p2 = player_ids[idx * 2 + 1]
        match.player1_id = p1
        match.player2_id = p2

        # Handle byes: auto-advance if one player is None
        if p1 is not None and p2 is None:
            match.winner_id = p1
            match.status = "completed"
            _advance_winner(match, p1, matches_by_round)
        elif p1 is None and p2 is not None:
            match.winner_id = p2
            match.status = "completed"
            _advance_winner(match, p2, matches_by_round)
        elif p1 is None and p2 is None:
            match.status = "completed"

    await session.flush()

    # Return all matches
    all_matches: list[BracketMatch] = []
    for rnd in range(1, total_rounds + 1):
        all_matches.extend(matches_by_round[rnd])
    return all_matches


def _advance_winner(
    match: BracketMatch,
    winner_id: int,
    matches_by_round: dict[int, list[BracketMatch]],
) -> None:
    """Place the winner into the correct slot of the next match."""
    if match.next_match_id is None:
        return
    # Find the next match object
    for rnd_matches in matches_by_round.values():
        for nm in rnd_matches:
            if nm.id == match.next_match_id:
                if nm.player1_id is None:
                    nm.player1_id = winner_id
                else:
                    nm.player2_id = winner_id
                return


async def set_match_result(
    session: AsyncSession,
    match_id: int,
    winner_id: int,
    score: str | None = None,
) -> BracketMatch:
    """Set the winner of a match and advance them in the bracket."""
    stmt = select(BracketMatch).where(BracketMatch.id == match_id)
    result = await session.execute(stmt)
    match = result.scalar_one_or_none()
    if match is None:
        raise ValueError("Match not found")

    if match.status == "completed":
        raise ValueError("Match is already completed")

    if winner_id not in (match.player1_id, match.player2_id):
        raise ValueError("Winner must be one of the match players")

    match.winner_id = winner_id
    match.score = score
    match.status = "completed"

    # Advance winner to next match
    if match.next_match_id:
        next_stmt = select(BracketMatch).where(BracketMatch.id == match.next_match_id)
        next_result = await session.execute(next_stmt)
        next_match = next_result.scalar_one_or_none()
        if next_match:
            if next_match.player1_id is None:
                next_match.player1_id = winner_id
            else:
                next_match.player2_id = winner_id

    # Mark loser as eliminated in registrations
    loser_id = (
        match.player2_id if winner_id == match.player1_id else match.player1_id
    )
    if loser_id:
        reg_stmt = select(Registration).where(
            Registration.tournament_id == match.tournament_id,
            Registration.user_id == loser_id,
        )
        reg_result = await session.execute(reg_stmt)
        reg = reg_result.scalar_one_or_none()
        if reg:
            reg.status = "eliminated"

    await session.flush()
    return match
