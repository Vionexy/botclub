"""Notification service – send Telegram messages to registered users via the bot."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Notification, Registration, User

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)


async def notify_tournament_users(
    bot: Bot,
    session: AsyncSession,
    tournament_id: int,
    title: str,
    message_text: str,
    notification_type: str = "bracket",
) -> int:
    """Send a message to every user registered for the given tournament.

    Returns the number of messages successfully sent.
    """
    # Get all registered user telegram_ids
    stmt = (
        select(User.telegram_id)
        .join(Registration, Registration.user_id == User.id)
        .where(Registration.tournament_id == tournament_id)
    )
    result = await session.execute(stmt)
    telegram_ids = [row[0] for row in result.all()]

    if not telegram_ids:
        return 0

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎮 Открыть Mini App",
                    web_app=WebAppInfo(url=settings.MINI_APP_URL),
                ),
            ]
        ]
    )

    sent = 0
    for tg_id in telegram_ids:
        try:
            await bot.send_message(
                chat_id=tg_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            logger.warning("Failed to send notification to %s", tg_id, exc_info=True)

    # Save notification record
    notification = Notification(
        tournament_id=tournament_id,
        type=notification_type,
        message=message_text,
    )
    session.add(notification)
    await session.flush()

    return sent


async def send_bracket_published(
    bot: Bot,
    session: AsyncSession,
    tournament_id: int,
    title: str,
    game_mode: str,
) -> int:
    """Notify all registered users that the bracket has been published."""
    text = (
        "🏆 <b>Турнирная сетка опубликована!</b>\n\n"
        f"Турнир: <b>{title}</b>\n"
        f"Режим: <b>{game_mode}</b>\n\n"
        "Открой Mini App чтобы посмотреть сетку!"
    )
    return await notify_tournament_users(
        bot, session, tournament_id, title, text, notification_type="bracket_published",
    )


async def send_results_published(
    bot: Bot,
    session: AsyncSession,
    tournament_id: int,
    title: str,
    game_mode: str,
) -> int:
    """Notify all registered users about new match results."""
    text = (
        "📊 <b>Результаты обновлены!</b>\n\n"
        f"Турнир: <b>{title}</b>\n"
        f"Режим: <b>{game_mode}</b>\n\n"
        "Открой Mini App чтобы посмотреть результаты!"
    )
    return await notify_tournament_users(
        bot, session, tournament_id, title, text, notification_type="results_updated",
    )
