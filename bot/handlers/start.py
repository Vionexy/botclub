from __future__ import annotations

from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from config import settings
from database.db import async_session
from database.models import User
from bot.keyboards.inline import get_start_keyboard
from bot.handlers.menu import prepare_section_view

router = Router(name="start")


@router.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext) -> None:
    """Handle /start command, register user in DB, and send welcome message."""
    if not message.from_user:
        return

    # Cleanup previous views to avoid duplication
    data = await state.get_data()
    main_menu_id = data.get("main_menu_message_id")
    await prepare_section_view(state, message.bot, message.chat.id)
    if main_menu_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=main_menu_id)
        except Exception:
            pass

    await state.clear()

    tg_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name or ""
    display_name = f"{first_name} {last_name}".strip()

    is_admin = tg_id in settings.admin_ids_list

    async with async_session() as session:
        # Check if user already exists
        stmt = select(User).where(User.telegram_id == tg_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # Register user
            user = User(
                telegram_id=tg_id,
                username=username,
                display_name=display_name,
                is_admin=is_admin,
            )
            session.add(user)
            await session.commit()
            welcome_suffix = "\n\nВы были успешно зарегистрированы в турнирной системе!"
        else:
            # Update user info in case it changed
            user.username = username
            user.display_name = display_name
            # If their admin status changed in settings, update it
            user.is_admin = is_admin
            await session.commit()
            welcome_suffix = ""

    async with async_session() as session:
        from services.config import get_config_value
        welcome_title = await get_config_value(
            session, "welcome_title", "👋 Добро пожаловать на площадку <b>DC Tournaments</b>!"
        )
        welcome_subtitle = await get_config_value(
            session, "welcome_subtitle", "Для начала игр перейдите ниже в расписание. ⚔️"
        )

    welcome_text = f"{welcome_title}\n\n{welcome_subtitle}{welcome_suffix}"

    sent_msg = await message.answer(
        welcome_text + ("\n\n<i>Вы зашли как администратор.</i>" if is_admin else ""),
        reply_markup=get_start_keyboard(is_admin=is_admin),
        parse_mode="HTML",
    )
    await state.update_data(main_menu_message_id=sent_msg.message_id)
