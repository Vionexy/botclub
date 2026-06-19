from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database.db import init_db
from bot.handlers import bot_router
from api.routes.tournaments import router as tournaments_router
from api.routes.registrations import router as registrations_router
from api.routes.brackets import router as brackets_router
from api.routes.leaderboard import router as leaderboard_router
from api.routes.users import router as users_router
from api.routes.admin import router as admin_router
from api.routes.config import router as config_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("main")

# Initialize Bot and Dispatcher
if settings.PROXY:
    from aiogram.client.session.aiohttp import AiohttpSession
    session = AiohttpSession(proxy=settings.PROXY)
    bot = Bot(token=settings.BOT_TOKEN, session=session)
else:
    bot = Bot(token=settings.BOT_TOKEN)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)
dp.include_router(bot_router)

# background polling task reference
bot_polling_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for FastAPI."""
    global bot_polling_task

    # Startup logic
    logger.info("Initializing database...")
    await init_db()

    logger.info("Starting Telegram bot polling...")
    # Store bot in app state so routes can access it
    app.state.bot = bot
    app.state.dp = dp

    # Delete webhook to ensure polling works
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.warning(f"Could not delete webhook on startup: {e}. If your internet blocks Telegram, check your network/VPN.")

    # Set bot commands menu
    from aiogram.types import BotCommand
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="🚀 Главное меню"),
            BotCommand(command="tournaments", description="📅 Расписание"),
            BotCommand(command="leaderboard", description="🥇 Лидерборд"),
            BotCommand(command="profile", description="👤 Профиль"),
            BotCommand(command="rules", description="📜 Регламент"),
            BotCommand(command="admin", description="🔧 Админ-панель (админ)"),
        ])
        logger.info("Bot commands menu set successfully.")
    except Exception as e:
        logger.warning(f"Could not set bot commands: {e}")

    # Start polling task
    bot_polling_task = asyncio.create_task(dp.start_polling(bot))

    yield

    # Shutdown logic
    logger.info("Stopping Telegram bot polling...")
    if bot_polling_task:
        bot_polling_task.cancel()
        try:
            await bot_polling_task
        except asyncio.CancelledError:
            pass

    await bot.session.close()
    logger.info("Shutdown completed.")


# Create FastAPI application
app = FastAPI(
    title="Brawl Stars Tournaments API",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup CORS middleware to allow requests from GitHub Pages and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "https://vionexy.github.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(tournaments_router)
app.include_router(registrations_router)
app.include_router(brackets_router)
app.include_router(leaderboard_router)
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(config_router)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
    )
