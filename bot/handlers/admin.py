from __future__ import annotations

import datetime as dt
from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from sqlalchemy import select

from config import settings
from database.db import async_session
from database.models import Tournament, User
from bot.keyboards.inline import get_admin_keyboard, get_back_keyboard
from services.config import set_config_value
from bot.handlers.menu import prepare_section_view

router = Router(name="admin")


class CreateTournamentStates(StatesGroup):
    title = State()
    description = State()
    game_mode = State()
    tournament_type = State()
    max_participants = State()
    prizes = State()
    image = State()


class AdminConfigStates(StatesGroup):
    waiting_for_rules = State()
    waiting_for_about = State()
    waiting_for_welcome_title = State()
    waiting_for_welcome_subtitle = State()
    waiting_for_leaderboard_title = State()
    waiting_for_schedule_banner = State()
    waiting_for_rules_banner = State()
    waiting_for_about_banner = State()
    waiting_for_brackets_banner = State()
    waiting_for_profile_banner = State()
    waiting_for_leaderboard_banner = State()


# Helper keyboard for game modes
game_modes_kbd = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Gem Grab"), KeyboardButton(text="Brawl Ball")],
        [KeyboardButton(text="Knockout"), KeyboardButton(text="Showdown")],
        [KeyboardButton(text="Wipeout"), KeyboardButton(text="Heist")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

# Helper keyboard for tournament types
types_kbd = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="1v1 (Соло)"), KeyboardButton(text="2v2 (Дуо)")],
        [KeyboardButton(text="3v3")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)


@router.message(Command("admin"))
async def admin_cmd(message: types.Message, state: FSMContext) -> None:
    """Provide admin links if the user is an admin."""
    if not message.from_user:
        return

    tg_id = message.from_user.id
    if tg_id not in settings.admin_ids_list:
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return

    await prepare_section_view(state, message.bot, message.chat.id)
    sent_msg = await message.answer(
        "🔧 <b>Админ-панель управления Deadly Crew</b>\n\n"
        "Здесь вы можете изменять правила, регламент и описание клуба прямо из бота,\n"
        "а также создавать новые турниры и праки.",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )
    await state.update_data(last_section_message_id=sent_msg.message_id)


@router.callback_query(F.data == "admin_create_start")
async def cb_admin_create_start(call: types.CallbackQuery, state: FSMContext) -> None:
    """Start the FSM wizard from an inline button click."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer("❌ У вас нет прав для создания турниров.", show_alert=True)
        return

    await state.clear()
    await state.set_state(CreateTournamentStates.title)
    await call.message.answer(
        "🏆 <b>Запущен мастер создания турнира!</b>\n\n"
        "Введите НАЗВАНИЕ турнира (например, <i>Deadly Crew Cup #1</i>):",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await call.answer()


@router.message(Command("create", "create_tournament"))
async def start_creation_wizard(message: types.Message, state: FSMContext) -> None:
    """Start the FSM wizard for tournament creation."""
    if not message.from_user:
        return

    tg_id = message.from_user.id
    if tg_id not in settings.admin_ids_list:
        await message.answer("❌ У вас нет прав для создания турниров.")
        return

    await state.clear()
    await state.set_state(CreateTournamentStates.title)
    await message.answer(
        "🏆 <b>Запущен мастер создания турнира!</b>\n\n"
        "Введите НАЗВАНИЕ турнира (например, <i>Deadly Crew Cup #1</i>):",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(CreateTournamentStates.title)
async def process_title(message: types.Message, state: FSMContext) -> None:
    """Save title and ask for description."""
    title = message.text
    if not title:
        await message.answer("Пожалуйста, введите корректное название.")
        return

    await state.update_data(title=title)
    await state.set_state(CreateTournamentStates.description)
    await message.answer(
        "Введите ОПИСАНИЕ турнира или отправьте /skip чтобы пропустить:"
    )


@router.message(CreateTournamentStates.description)
async def process_description(message: types.Message, state: FSMContext) -> None:
    """Save description and ask for game mode."""
    desc = message.text
    if desc == "/skip":
        desc = None

    await state.update_data(description=desc)
    await state.set_state(CreateTournamentStates.game_mode)
    await message.answer(
        "Выберите или введите РЕЖИМ ИГРЫ:",
        reply_markup=game_modes_kbd,
    )


@router.message(CreateTournamentStates.game_mode)
async def process_game_mode(message: types.Message, state: FSMContext) -> None:
    """Save game mode and ask for tournament type."""
    mode = message.text
    if not mode:
        await message.answer("Выберите режим с клавиатуры или введите текстом.")
        return

    await state.update_data(game_mode=mode)
    await state.set_state(CreateTournamentStates.tournament_type)
    await message.answer(
        "Выберите ФОРМАТ матчей:",
        reply_markup=types_kbd,
    )


@router.message(CreateTournamentStates.tournament_type)
async def process_type(message: types.Message, state: FSMContext) -> None:
    """Save type and ask for max participants."""
    t_type = message.text
    if not t_type:
        await message.answer("Выберите тип с клавиатуры.")
        return

    # Normalize name (remove suffix)
    if "1v1" in t_type:
        t_type = "1v1"
    elif "2v2" in t_type:
        t_type = "2v2"

    await state.update_data(tournament_type=t_type)
    await state.set_state(CreateTournamentStates.max_participants)
    await message.answer(
        "Введите МАКСИМАЛЬНОЕ КОЛИЧЕСТВО УЧАСТНИКОВ (число, например: 16):",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(CreateTournamentStates.max_participants)
async def process_max_participants(message: types.Message, state: FSMContext) -> None:
    """Save max participants and ask for prizes."""
    try:
        max_p = int(message.text or "16")
        if max_p < 2 or max_p > 256:
            raise ValueError()
    except ValueError:
        await message.answer("Пожалуйста, введите число от 2 до 256.")
        return

    await state.update_data(max_participants=max_p)
    await state.set_state(CreateTournamentStates.prizes)
    await message.answer(
        "Введите ПРИЗЫ за 1, 2 и 3 места через запятую\n"
        "(например: <i>170 кристаллов, 80 кристаллов, 30 кристаллов</i>)\n"
        "Или отправьте /skip для пропуска:",
        parse_mode="HTML"
    )


@router.message(CreateTournamentStates.prizes)
async def process_prizes(message: types.Message, state: FSMContext) -> None:
    """Save prizes and ask for photo."""
    prizes_text = message.text
    prize1, prize2, prize3 = None, None, None

    if prizes_text != "/skip" and prizes_text:
        parts = [p.strip() for p in prizes_text.split(",", maxsplit=2)]
        if len(parts) >= 1:
            prize1 = parts[0]
        if len(parts) >= 2:
            prize2 = parts[1]
        if len(parts) >= 3:
            prize3 = parts[2]

    await state.update_data(prize_1st=prize1, prize_2nd=prize2, prize_3rd=prize3)
    await state.set_state(CreateTournamentStates.image)
    await message.answer(
        "Отправьте КАРТИНКУ (баннер) турнира, которая будет видна в Mini App,\n"
        "Или отправьте /skip чтобы завершить создание без картинки:"
    )


@router.message(CreateTournamentStates.image)
async def process_image(message: types.Message, state: FSMContext) -> None:
    """Save image, create tournament in database, and clear FSM state."""
    image_id = None
    if message.photo:
        image_id = message.photo[-1].file_id
    elif message.text != "/skip":
        await message.answer("Пожалуйста, отправьте картинку (как фото) или напишите /skip.")
        return

    data = await state.get_data()
    await state.clear()

    # Automatically set start date to tomorrow, and registration deadline to 2 hours before
    now = dt.datetime.now()
    start_date = now + dt.timedelta(days=1)
    deadline = start_date - dt.timedelta(hours=2)

    async with async_session() as session:
        # Get admin user ID
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        result = await session.execute(stmt)
        admin_user = result.scalar_one_or_none()
        creator_id = admin_user.id if admin_user else None

        # Create tournament model
        t = Tournament(
            title=data["title"],
            description=data["description"],
            game_mode=data["game_mode"],
            tournament_type=data["tournament_type"],
            bracket_type="single_elimination",
            max_participants=data["max_participants"],
            prize_1st=data.get("prize_1st"),
            prize_2nd=data.get("prize_2nd"),
            prize_3rd=data.get("prize_3rd"),
            status="registration",  # Instantly open for registrations
            start_date=start_date,
            registration_deadline=deadline,
            image_id=image_id,
            created_by=creator_id,
        )
        session.add(t)
        await session.commit()

    prizes_str = f"🥇 {t.prize_1st or '—'}\n🥈 {t.prize_2nd or '—'}\n🥉 {t.prize_3rd or '—'}"
    success_msg = (
        "🎉 <b>Турнир успешно создан и опубликован!</b>\n\n"
        f"🏆 Название: <b>{t.title}</b>\n"
        f"🎮 Режим: {t.game_mode} ({t.tournament_type})\n"
        f"👥 Макс. участников: {t.max_participants}\n"
        f"🎁 Призы:\n{prizes_str}\n\n"
        "Турнир уже отображается в Mini App, и игроки могут регистрироваться!"
    )

    sent_msg = await message.answer(
        success_msg,
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )
    await state.update_data(last_section_message_id=sent_msg.message_id)


# ==================== CONFIG EDITING HANDLERS ====================

@router.callback_query(F.data == "admin_edit_rules")
async def cb_admin_edit_rules(call: types.CallbackQuery, state: FSMContext) -> None:
    """Prompt admin to enter the new rules text."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer("❌ У вас нет прав для изменения регламента.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminConfigStates.waiting_for_rules)
    await call.message.answer(
        "📝 <b>Редактирование Регламента</b>\n\n"
        "Отправьте следующим сообщением новый текст регламента.\n"
        "Вы можете использовать HTML-разметку (например, &lt;b&gt;жирный&lt;/b&gt;, &lt;i&gt;курсив&lt;/i&gt;, списки).\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await call.answer()


@router.callback_query(F.data == "admin_edit_about")
async def cb_admin_edit_about(call: types.CallbackQuery, state: FSMContext) -> None:
    """Prompt admin to enter the new about info text."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer("❌ У вас нет прав для изменения информации о клубе.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminConfigStates.waiting_for_about)
    await call.message.answer(
        "📝 <b>Редактирование раздела 'О Deadly Crew'</b>\n\n"
        "Отправьте следующим сообщением новый текст описания вашего клуба.\n"
        "Вы можете использовать HTML-разметку.\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await call.answer()


@router.callback_query(F.data == "admin_edit_welcome_title")
async def cb_admin_edit_welcome_title(call: types.CallbackQuery, state: FSMContext) -> None:
    """Prompt admin to enter the new welcome title."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer("❌ У вас нет прав для изменения приветствия.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminConfigStates.waiting_for_welcome_title)
    await call.message.answer(
        "📝 <b>Редактирование Заголовка Приветствия</b>\n\n"
        "Отправьте следующим сообщением новый заголовок приветствия (например, <i>👋 Добро пожаловать на площадку DC Tournaments!</i>).\n"
        "Вы можете использовать HTML-разметку.\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await call.answer()


@router.callback_query(F.data == "admin_edit_welcome_subtitle")
async def cb_admin_edit_welcome_subtitle(call: types.CallbackQuery, state: FSMContext) -> None:
    """Prompt admin to enter the new welcome subtitle."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer("❌ У вас нет прав для изменения подтекста приветствия.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminConfigStates.waiting_for_welcome_subtitle)
    await call.message.answer(
        "📝 <b>Редактирование Подзаголовка Приветствия</b>\n\n"
        "Отправьте следующим сообщением новый подзаголовок приветствия (например, <i>Для начала игр перейдите ниже в расписание. ⚔️</i>).\n"
        "Вы можете использовать HTML-разметку.\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await call.answer()


@router.callback_query(F.data == "admin_edit_leaderboard_title")
async def cb_admin_edit_leaderboard_title(call: types.CallbackQuery, state: FSMContext) -> None:
    """Prompt admin to enter the new leaderboard title."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer("❌ У вас нет прав для изменения заголовка лидеров.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminConfigStates.waiting_for_leaderboard_title)
    await call.message.answer(
        "📝 <b>Редактирование Заголовка Лидерборда</b>\n\n"
        "Отправьте следующим сообщением новый заголовок раздела «Лидеры» (например, <i>🥇 Зал Славы Deadly Crew (Топ-10):</i>).\n"
        "Вы можете использовать HTML-разметку.\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await call.answer()


@router.callback_query(F.data == "admin_edit_schedule_banner")
async def cb_admin_edit_schedule_banner(call: types.CallbackQuery, state: FSMContext) -> None:
    """Prompt admin to send a new schedule banner photo."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer("❌ У вас нет прав для изменения баннера.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminConfigStates.waiting_for_schedule_banner)
    await call.message.answer(
        "🖼️ <b>Редактирование Баннера Расписания</b>\n\n"
        "Отправьте следующим сообщением картинку (фото), которая будет отображаться при открытии расписания в боте.\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await call.answer()


@router.callback_query(F.data == "admin_banners_menu")
async def cb_admin_banners_menu(call: types.CallbackQuery) -> None:
    """Show the submenu for banner management."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer("❌ У вас нет прав для управления баннерами.", show_alert=True)
        return

    from bot.keyboards.inline import get_banners_menu_keyboard
    await call.message.edit_text(
        "🖼️ <b>Управление баннерами и картинками разделов</b>\n\n"
        "Выберите раздел, для которого вы хотите загрузить или обновить изображение.\n"
        "Картинки будут отображаться пользователям в чате при открытии соответствующих разделов меню.",
        parse_mode="HTML",
        reply_markup=get_banners_menu_keyboard()
    )
    await call.answer()


@router.callback_query(F.data == "admin_back_to_dashboard")
async def cb_admin_back_to_dashboard(call: types.CallbackQuery) -> None:
    """Return to primary admin dashboard."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer()
        return

    await call.message.edit_text(
        "🔧 <b>Админ-панель управления Deadly Crew</b>\n\n"
        "Здесь вы можете изменять правила, регламент и описание клуба прямо из бота,\n"
        "а также создавать новые турниры и праки.",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await call.answer()


@router.callback_query(F.data == "admin_edit_rules_banner")
async def cb_admin_edit_rules_banner(call: types.CallbackQuery, state: FSMContext) -> None:
    """Prompt admin to send a new rules banner photo."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer("❌ У вас нет прав для изменения баннера.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminConfigStates.waiting_for_rules_banner)
    await call.message.answer(
        "🖼️ <b>Редактирование Баннера Регламента</b>\n\n"
        "Отправьте следующим сообщением картинку (фото), которая будет отображаться при открытии регламента в боте.\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await call.answer()


@router.callback_query(F.data == "admin_edit_about_banner")
async def cb_admin_edit_about_banner(call: types.CallbackQuery, state: FSMContext) -> None:
    """Prompt admin to send a new about banner photo."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer("❌ У вас нет прав для изменения баннера.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminConfigStates.waiting_for_about_banner)
    await call.message.answer(
        "🖼️ <b>Редактирование Баннера 'О Deadly Crew'</b>\n\n"
        "Отправьте следующим сообщением картинку (фото), которая будет отображаться при открытии 'О клубе' в боте.\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await call.answer()


@router.callback_query(F.data == "admin_edit_brackets_banner")
async def cb_admin_edit_brackets_banner(call: types.CallbackQuery, state: FSMContext) -> None:
    """Prompt admin to send a new brackets banner photo."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer("❌ У вас нет прав для изменения баннера.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminConfigStates.waiting_for_brackets_banner)
    await call.message.answer(
        "🖼️ <b>Редактирование Баннера Сеток</b>\n\n"
        "Отправьте следующим сообщением картинку (фото), которая будет отображаться при открытии сеток в боте.\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await call.answer()


@router.callback_query(F.data == "admin_edit_profile_banner")
async def cb_admin_edit_profile_banner(call: types.CallbackQuery, state: FSMContext) -> None:
    """Prompt admin to send a new profile banner photo."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer("❌ У вас нет прав для изменения баннера.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminConfigStates.waiting_for_profile_banner)
    await call.message.answer(
        "🖼️ <b>Редактирование Баннера Профиля</b>\n\n"
        "Отправьте следующим сообщением картинку (фото), которая будет отображаться при открытии профиля в боте.\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await call.answer()


@router.callback_query(F.data == "admin_edit_leaderboard_banner")
async def cb_admin_edit_leaderboard_banner(call: types.CallbackQuery, state: FSMContext) -> None:
    """Prompt admin to send a new leaderboard banner photo."""
    if call.from_user.id not in settings.admin_ids_list:
        await call.answer("❌ У вас нет прав для изменения баннера.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminConfigStates.waiting_for_leaderboard_banner)
    await call.message.answer(
        "🖼️ <b>Редактирование Баннера Лидерборда</b>\n\n"
        "Отправьте следующим сообщением картинку (фото), которая будет отображаться при открытии лидерборда в боте.\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await call.answer()


@router.message(Command("cancel"))
async def cmd_cancel_config(message: types.Message, state: FSMContext) -> None:
    """Cancel config editing and return to admin panel."""
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("❌ Редактирование отменено.", reply_markup=get_admin_keyboard())


@router.message(AdminConfigStates.waiting_for_rules)
async def process_new_rules(message: types.Message, state: FSMContext) -> None:
    """Save the new rules to database."""
    new_rules = message.text
    if not new_rules:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    await state.clear()
    async with async_session() as session:
        await set_config_value(session, "rules", new_rules)

    await message.answer(
        "✅ <b>Регламент успешно обновлен!</b>\n\n"
        "Изменения применились для бота и Mini App.",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )


@router.message(AdminConfigStates.waiting_for_about)
async def process_new_about(message: types.Message, state: FSMContext) -> None:
    """Save the new about text to database."""
    new_about = message.text
    if not new_about:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    await state.clear()
    async with async_session() as session:
        await set_config_value(session, "about", new_about)

    await message.answer(
        "✅ <b>Описание клуба успешно обновлено!</b>\n\n"
        "Изменения применились для бота и Mini App.",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )


@router.message(AdminConfigStates.waiting_for_welcome_title)
async def process_new_welcome_title(message: types.Message, state: FSMContext) -> None:
    """Save the new welcome title to database."""
    new_title = message.text
    if not new_title:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    await state.clear()
    async with async_session() as session:
        await set_config_value(session, "welcome_title", new_title)

    await message.answer(
        "✅ <b>Заголовок приветствия успешно обновлен!</b>\n\n"
        "Изменения применились для бота и Mini App.",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )


@router.message(AdminConfigStates.waiting_for_welcome_subtitle)
async def process_new_welcome_subtitle(message: types.Message, state: FSMContext) -> None:
    """Save the new welcome subtitle to database."""
    new_subtitle = message.text
    if not new_subtitle:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    await state.clear()
    async with async_session() as session:
        await set_config_value(session, "welcome_subtitle", new_subtitle)

    await message.answer(
        "✅ <b>Подзаголовок приветствия успешно обновлен!</b>\n\n"
        "Изменения применились для бота и Mini App.",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )


@router.message(AdminConfigStates.waiting_for_leaderboard_title)
async def process_new_leaderboard_title(message: types.Message, state: FSMContext) -> None:
    """Save the new leaderboard title to database."""
    new_title = message.text
    if not new_title:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    await state.clear()
    async with async_session() as session:
        await set_config_value(session, "leaderboard_title", new_title)

    await message.answer(
        "✅ <b>Заголовок лидерборда успешно обновлен!</b>\n\n"
        "Изменения применились для бота и Mini App.",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )


@router.message(AdminConfigStates.waiting_for_schedule_banner)
async def process_new_schedule_banner(message: types.Message, state: FSMContext) -> None:
    """Save the new schedule banner image file_id to database."""
    if not message.photo:
        await message.answer("Пожалуйста, отправьте картинку как фото (или напишите /cancel).")
        return

    # Telegram returns photos in a list of different sizes; take the highest resolution one
    file_id = message.photo[-1].file_id

    await state.clear()
    async with async_session() as session:
        await set_config_value(session, "schedule_image", file_id)

    await message.answer(
        "✅ <b>Баннер расписания успешно обновлен!</b>\n\n"
        "Теперь при открытии расписания в боте будет отображаться эта картинка.",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )


@router.message(AdminConfigStates.waiting_for_rules_banner)
async def process_new_rules_banner(message: types.Message, state: FSMContext) -> None:
    """Save the new rules banner image file_id to database."""
    if not message.photo:
        await message.answer("Пожалуйста, отправьте картинку как фото (или напишите /cancel).")
        return

    file_id = message.photo[-1].file_id
    await state.clear()
    async with async_session() as session:
        await set_config_value(session, "rules_image", file_id)

    await message.answer(
        "✅ <b>Баннер регламента успешно обновлен!</b>\n\n"
        "При открытии правил пользователям будет отправляться эта картинка.",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )


@router.message(AdminConfigStates.waiting_for_about_banner)
async def process_new_about_banner(message: types.Message, state: FSMContext) -> None:
    """Save the new about banner image file_id to database."""
    if not message.photo:
        await message.answer("Пожалуйста, отправьте картинку как фото (или напишите /cancel).")
        return

    file_id = message.photo[-1].file_id
    await state.clear()
    async with async_session() as session:
        await set_config_value(session, "about_image", file_id)

    await message.answer(
        "✅ <b>Баннер раздела 'О нас' успешно обновлен!</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )


@router.message(AdminConfigStates.waiting_for_brackets_banner)
async def process_new_brackets_banner(message: types.Message, state: FSMContext) -> None:
    """Save the new brackets banner image file_id to database."""
    if not message.photo:
        await message.answer("Пожалуйста, отправьте картинку как фото (или напишите /cancel).")
        return

    file_id = message.photo[-1].file_id
    await state.clear()
    async with async_session() as session:
        await set_config_value(session, "brackets_image", file_id)

    await message.answer(
        "✅ <b>Баннер раздела 'Сетки' успешно обновлен!</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )


@router.message(AdminConfigStates.waiting_for_profile_banner)
async def process_new_profile_banner(message: types.Message, state: FSMContext) -> None:
    """Save the new profile banner image file_id to database."""
    if not message.photo:
        await message.answer("Пожалуйста, отправьте картинку как фото (или напишите /cancel).")
        return

    file_id = message.photo[-1].file_id
    await state.clear()
    async with async_session() as session:
        await set_config_value(session, "profile_image", file_id)

    await message.answer(
        "✅ <b>Баннер раздела 'Профиль' успешно обновлен!</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )


@router.message(AdminConfigStates.waiting_for_leaderboard_banner)
async def process_new_leaderboard_banner(message: types.Message, state: FSMContext) -> None:
    """Save the new leaderboard banner image file_id to database."""
    if not message.photo:
        await message.answer("Пожалуйста, отправьте картинку как фото (или напишите /cancel).")
        return

    file_id = message.photo[-1].file_id
    await state.clear()
    async with async_session() as session:
        await set_config_value(session, "leaderboard_image", file_id)

    await message.answer(
        "✅ <b>Баннер раздела 'Лидерборд' успешно обновлен!</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )
