"""Pydantic schemas for User."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field


class UserRead(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str] = None
    display_name: str
    brawl_stars_tag: Optional[str] = None
    is_admin: bool = False
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    brawl_stars_tag: Optional[str] = Field(None, max_length=50)
    display_name: Optional[str] = Field(None, max_length=255)


class UserLeaderboard(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str] = None
    display_name: str
    brawl_stars_tag: Optional[str] = None
    wins: int = 0

    model_config = {"from_attributes": True}
