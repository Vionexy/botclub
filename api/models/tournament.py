"""Pydantic schemas for Tournament."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field


class TournamentCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    game_mode: str = Field(default="Gem Grab", max_length=100)
    tournament_type: str = Field(default="1v1", max_length=50)
    bracket_type: str = Field(default="single_elimination", max_length=50)
    prize_1st: Optional[str] = None
    prize_2nd: Optional[str] = None
    prize_3rd: Optional[str] = None
    status: str = Field(default="draft", max_length=20)
    max_participants: int = Field(default=16, ge=2, le=256)
    start_date: Optional[dt.datetime] = None
    registration_deadline: Optional[dt.datetime] = None
    image_id: Optional[str] = None


class TournamentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    game_mode: Optional[str] = Field(None, max_length=100)
    tournament_type: Optional[str] = Field(None, max_length=50)
    bracket_type: Optional[str] = Field(None, max_length=50)
    prize_1st: Optional[str] = None
    prize_2nd: Optional[str] = None
    prize_3rd: Optional[str] = None
    status: Optional[str] = Field(None, max_length=20)
    max_participants: Optional[int] = Field(None, ge=2, le=256)
    start_date: Optional[dt.datetime] = None
    registration_deadline: Optional[dt.datetime] = None
    image_id: Optional[str] = None


class TournamentRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    game_mode: str
    tournament_type: str
    bracket_type: str
    prize_1st: Optional[str] = None
    prize_2nd: Optional[str] = None
    prize_3rd: Optional[str] = None
    status: str
    max_participants: int
    start_date: Optional[dt.datetime] = None
    registration_deadline: Optional[dt.datetime] = None
    created_at: dt.datetime
    created_by: Optional[int] = None
    participant_count: int = 0
    is_registered: bool = False
    image_id: Optional[str] = None

    model_config = {"from_attributes": True}


class RegistrationRead(BaseModel):
    id: int
    tournament_id: int
    user_id: int
    registered_at: dt.datetime
    status: str

    model_config = {"from_attributes": True}


class NotifyRequest(BaseModel):
    message: str
