from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    brawl_stars_tag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )

    registrations: Mapped[list[Registration]] = relationship(back_populates="user")
    created_tournaments: Mapped[list[Tournament]] = relationship(back_populates="creator")


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    game_mode: Mapped[str] = mapped_column(String(100), nullable=False, default="Gem Grab")
    tournament_type: Mapped[str] = mapped_column(String(50), nullable=False, default="1v1")
    bracket_type: Mapped[str] = mapped_column(String(50), nullable=False, default="single_elimination")
    prize_1st: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prize_2nd: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prize_3rd: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    max_participants: Mapped[int] = mapped_column(Integer, nullable=False, default=16)
    start_date: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    registration_deadline: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True,
    )
    image_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    creator: Mapped[User | None] = relationship(back_populates="created_tournaments")
    registrations: Mapped[list[Registration]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan",
    )
    bracket_matches: Mapped[list[BracketMatch]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan",
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="tournament", cascade="all, delete-orphan",
    )


class Registration(Base):
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tournaments.id"), nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False,
    )
    registered_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="registered")

    tournament: Mapped[Tournament] = relationship(back_populates="registrations")
    user: Mapped[User] = relationship(back_populates="registrations")


class BracketMatch(Base):
    __tablename__ = "bracket_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tournaments.id"), nullable=False,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    match_number: Mapped[int] = mapped_column(Integer, nullable=False)
    player1_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True,
    )
    player2_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True,
    )
    winner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True,
    )
    score: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    next_match_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("bracket_matches.id"), nullable=True,
    )

    tournament: Mapped[Tournament] = relationship(back_populates="bracket_matches")
    player1: Mapped[User | None] = relationship(foreign_keys=[player1_id])
    player2: Mapped[User | None] = relationship(foreign_keys=[player2_id])
    winner: Mapped[User | None] = relationship(foreign_keys=[winner_id])
    next_match: Mapped[BracketMatch | None] = relationship(
        remote_side=[id], foreign_keys=[next_match_id],
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tournaments.id"), nullable=False,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )

    tournament: Mapped[Tournament] = relationship(back_populates="notifications")


class SystemConfig(Base):
    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)

