from __future__ import annotations

from aiogram import Router

from bot.handlers.start import router as start_router
from bot.handlers.admin import router as admin_router
from bot.handlers.menu import router as menu_router

bot_router = Router(name="bot_main")
bot_router.include_routers(start_router, admin_router, menu_router)
