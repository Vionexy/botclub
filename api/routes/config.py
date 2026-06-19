"""System configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.telegram import get_current_user
from database.db import get_session
from database.models import User
from services.config import get_config_value

router = APIRouter(prefix="/api/config", tags=["config"])


DEFAULT_CONFIGS = {
    "rules": (
        "📜 <b>Регламент турниров Deadly Crew</b>\n\n"
        "<b>1. Регистрация и участие:</b>\n"
        "• Каждый участник обязан указать свой корректный Brawl Stars Tag в профиле.\n"
        "• Никнейм в игре должен быть похож на никнейм в Telegram.\n\n"
        "<b>2. Проведение матчей:</b>\n"
        "• Игры проводятся в режиме Дружеского боя (Friendly Battle).\n"
        "• Время ожидания соперника — 10 минут. Неявка = техническое поражение (ТП).\n"
        "• После матча скриншот с результатом отправляется администратору.\n\n"
        "<b>3. Запреты:</b>\n"
        "• Использование читов, макросов, модов запрещено.\n"
        "• Оскорбления соперников и судей караются дисквалификацией.\n\n"
        "<i>Любые спорные ситуации решаются главным судьей турнира.</i>"
    ),
    "about": (
        "💀 <b>О Deadly Crew</b>\n\n"
        "Мы — амбициозное игровое сообщество <b>Deadly Crew</b> по Brawl Stars. "
        "Наш клуб объединяет активных игроков, стремящихся к развитию навыков и победам.\n\n"
        "Эта платформа создана специально для наших участников, чтобы проводить регулярные праки "
        "(тренировочные матчи), отборочные игры и клубные чемпионаты с ценными призами.\n\n"
        "Присоединяйся, тренируйся с лучшими и докажи, что ты достоин быть в топе!\n\n"
        "💬 Наш Telegram: @DeadlyCrew"
    ),
    "welcome_title": "Добро пожаловать на площадку DC Tournaments",
    "welcome_subtitle": "Для начала игр перейдите ниже в расписание"
}


@router.get("/{key}")
async def get_config(
    key: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Retrieve configuration value by key."""
    default = DEFAULT_CONFIGS.get(key, "")
    val = await get_config_value(session, key, default)
    return {"key": key, "value": val}
