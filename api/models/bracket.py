"""Pydantic schemas for Bracket / Match."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class PlayerInfo(BaseModel):
    id: int
    telegram_id: int
    display_name: str
    username: Optional[str] = None
    brawl_stars_tag: Optional[str] = None

    model_config = {"from_attributes": True}


class BracketMatchRead(BaseModel):
    id: int
    tournament_id: int
    round_number: int
    match_number: int
    player1: Optional[PlayerInfo] = None
    player2: Optional[PlayerInfo] = None
    winner: Optional[PlayerInfo] = None
    score: Optional[str] = None
    status: str
    next_match_id: Optional[int] = None

    model_config = {"from_attributes": True}


class MatchResultUpdate(BaseModel):
    winner_id: int
    score: Optional[str] = None
