from __future__ import annotations

import os
import datetime as dt
from aiogram import F, Router, types
from aiogram.types import FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from config import settings
from database.db import async_session
from database.models import BracketMatch, Registration, Tournament, User
from services.config import get_config_value, set_config_value
from bot.keyboards.inline import (
    get_back_keyboard,
    get_profile_keyboard,
    get_start_keyboard,
    get_tournament_detail_keyboard,
    get_tournaments_keyboard,
    get_schedule_keyboard,
)

router = Router(name="menu")


class ProfileStates(StatesGroup):
    waiting_for_tag = State()


# ==================== MAIN MENU NAVIGATION ====================

async def prepare_section_view(state: FSMContext, bot, chat_id: int) -> None:
    """Kept for backward compatibility with FSM text-input handlers that
    still need to clean up a transient prompt message (not used for
    section-to-section navigation anymore)."""
    data = await state.get_data()
    last_section_id = data.get("last_section_message_id")
    if last_section_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=last_section_id)
        except Exception:
            pass
        await state.update_data(last_section_message_id=None)


@router.callback_query(F.data == "menu_main")
async def cb_main_menu(call: types.CallbackQuery, state: FSMContext) -> None:
    """Return to the main menu screen by editing the current message in place."""
    await state.clear()

    is_admin = call.from_user.id in settings.admin_ids_list

    async with async_session() as session:
        welcome_title = await get_config_value(
            session, "welcome_title", "👋 Добро пожаловать на площадку <b>DC Tournaments</b>!"
        )
        welcome_subtitle = await get_config_value(
            session, "welcome_subtitle", "Для начала игр перейдите ниже в расписание. ⚔️"
        )

    welcome_text = f"{welcome_title}\n\n{welcome_subtitle}"
    text_to_send = welcome_text + ("\n\n<i>Вы зашли как администратор.</i>" if is_admin else "")
    reply_markup = get_start_keyboard(is_admin=is_admin)

    if not call.message.photo:
        try:
            await call.message.edit_text(text=text_to_send, reply_markup=reply_markup, parse_mode="HTML")
            await state.update_data(main_menu_message_id=call.message.message_id)
            await call.answer()
            return
        except Exception:
            pass

    sent_msg = await call.message.answer(text=text_to_send, reply_markup=reply_markup, parse_mode="HTML")
    try:
        await call.message.delete()
    except Exception:
        pass
    await state.update_data(main_menu_message_id=sent_msg.message_id)
    await call.answer()


@router.callback_query(F.data == "menu_brackets_list")
async def cb_brackets_list(call: types.CallbackQuery, state: FSMContext) -> None:
    """Display all tournaments with brackets (active or completed)."""
    async with async_session() as session:
        stmt = select(Tournament).where(Tournament.status.in_(["active", "completed"])).order_by(Tournament.created_at.desc())
        result = await session.execute(stmt)
        tournaments = list(result.scalars().all())

        tour_list = []
        for t in tournaments:
            count_stmt = select(func.count(Registration.id)).where(Registration.tournament_id == t.id)
            count_res = await session.execute(count_stmt)
            count = count_res.scalar() or 0
            tour_list.append({
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "max_participants": t.max_participants,
                "participant_count": count
            })

    if not tour_list:
        text = (
            "📊 <b>Сетки турниров</b>\n\n"
            "На данный момент активных или завершенных сеток нет."
        )
        reply_markup = get_back_keyboard("menu_main")
    else:
        text = (
            "📊 <b>Сетки турниров</b>\n\n"
            "Выберите турнир ниже, чтобы посмотреть сетку:"
        )
        reply_markup = get_tournaments_keyboard(tour_list)

    async with async_session() as session:
        msg = await send_dynamic_view(call, session, "brackets", text, reply_markup)
        await state.update_data(last_section_message_id=msg.message_id)
    await call.answer()


@router.callback_query(F.data == "menu_rules")
async def cb_rules(call: types.CallbackQuery, state: FSMContext) -> None:
    """Display regulations/rules."""
    default_rules = (
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
    )
    async with async_session() as session:
        rules_text = await get_config_value(session, "rules", default_rules)
        msg = await send_dynamic_view(call, session, "rules", rules_text, get_back_keyboard("menu_main"))
        await state.update_data(last_section_message_id=msg.message_id)
    await call.answer()


@router.callback_query(F.data == "menu_about")
async def cb_about(call: types.CallbackQuery, state: FSMContext) -> None:
    """Display about Deadly Crew text."""
    default_about = (
        "💀 <b>О Deadly Crew</b>\n\n"
        "Мы — амбициозное игровое сообщество <b>Deadly Crew</b> по Brawl Stars. "
        "Наш клуб объединяет active игроков, стремящихся к развитию навыков и победам.\n\n"
        "Эта платформа создана специально для наших участников, чтобы проводить регулярные праки "
        "(тренировочные матчи), отборочные игры и клубные чемпионаты с ценными призами.\n\n"
        "Присоединяйся, тренируйся с лучшими и докажи, что ты достоин быть в топе!\n\n"
        "💬 Наш Telegram: @DeadlyCrew"
    )
    async with async_session() as session:
        about_text = await get_config_value(session, "about", default_about)
        msg = await send_dynamic_view(call, session, "about", about_text, get_back_keyboard("menu_main"))
        await state.update_data(last_section_message_id=msg.message_id)
    await call.answer()



async def get_schedule_photo(session) -> FSInputFile | str | None:
    """Retrieve schedule image file ID from database or local assets folder."""
    file_id = await get_config_value(session, "schedule_image", "")
    if file_id:
        return file_id
    
    local_path = "assets/schedule_banner.jpg"
    if os.path.exists(local_path):
        return FSInputFile(local_path)
    return None


async def send_dynamic_view(call_or_msg, session, key, text, reply_markup) -> types.Message:
    """Render a section either by editing the current message in place
    (when triggered by a button press) or by sending a fresh message
    (when triggered by a typed command). Never deletes-then-sends for
    button navigation, so the chat doesn't flicker."""
    image_key = f"{key}_image"
    file_id = await get_config_value(session, image_key, "")

    is_callback = isinstance(call_or_msg, types.CallbackQuery)

    if not is_callback:
        # Triggered by a typed command (e.g. /rules) — always send fresh,
        # since there is no "current" bot message to edit.
        message = call_or_msg
        if file_id:
            return await message.answer_photo(
                photo=file_id, caption=text, reply_markup=reply_markup, parse_mode="HTML"
            )
        return await message.answer(text=text, reply_markup=reply_markup, parse_mode="HTML")

    call = call_or_msg
    current = call.message
    wants_photo = bool(file_id)
    has_photo = bool(current.photo)

    try:
        if wants_photo and has_photo:
            # Photo -> photo: swap the image/caption in place.
            await current.edit_media(
                media=types.InputMediaPhoto(media=file_id, caption=text, parse_mode="HTML"),
                reply_markup=reply_markup,
            )
            return current
        if not wants_photo and not has_photo:
            # Text -> text: edit text in place.
            if current.text == text and current.reply_markup == reply_markup:
                return current
            await current.edit_text(text=text, reply_markup=reply_markup, parse_mode="HTML")
            return current
    except Exception:
        # Fall through to the rebuild path below (e.g. "message not modified"
        # or the message is too old to edit).
        pass

    # Type changed (text <-> photo) or edit failed: we must replace the
    # message. Send the new one first, then remove the old one, so users
    # never see an empty gap between the two.
    if wants_photo:
        new_msg = await current.answer_photo(
            photo=file_id, caption=text, reply_markup=reply_markup, parse_mode="HTML"
        )
    else:
        new_msg = await current.answer(text=text, reply_markup=reply_markup, parse_mode="HTML")

    try:
        await current.delete()
    except Exception:
        pass

    return new_msg


# ==================== TOURNAMENTS LIST & DETAILS ====================

@router.callback_query(F.data == "menu_tournaments")
async def cb_tournaments_list(call: types.CallbackQuery, state: FSMContext) -> None:
    """Display all active/upcoming tournaments."""
    async with async_session() as session:
        stmt = select(Tournament).where(Tournament.status != "completed").order_by(Tournament.created_at.desc())
        result = await session.execute(stmt)
        tournaments = list(result.scalars().all())

        tournaments_on_dates = {}
        for t in tournaments:
            if t.start_date:
                t_date = t.start_date.date().strftime("%Y-%m-%d")
                tournaments_on_dates[t_date] = tournaments_on_dates.get(t_date, 0) + 1

        tour_list = []
        for t in tournaments:
            count_stmt = select(func.count(Registration.id)).where(Registration.tournament_id == t.id)
            count_res = await session.execute(count_stmt)
            count = count_res.scalar() or 0
            tour_list.append({
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "max_participants": t.max_participants,
                "participant_count": count
            })

        photo = await get_schedule_photo(session)

    caption = "📅 <b>Расписание: Все игры</b>\n\nВыберите игру ниже для подробной информации:"
    reply_markup = get_schedule_keyboard(tour_list, tournaments_on_dates, "all")

    if photo:
        sent_msg = await call.message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        
        # Save file_id locally to database configs to prevent uploading it again
        if isinstance(photo, FSInputFile) and sent_msg.photo:
            async with async_session() as session:
                await set_config_value(session, "schedule_image", sent_msg.photo[-1].file_id)
    else:
        sent_msg = await call.message.answer(
            text=caption,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    await state.update_data(last_section_message_id=sent_msg.message_id)
    await call.answer()


@router.callback_query(F.data.startswith("tour_detail_"))
async def cb_tournament_detail(call: types.CallbackQuery, state: FSMContext) -> None:
    """Display full details of a specific tournament."""
    tour_id = int(call.data.replace("tour_detail_", ""))
    tg_id = call.from_user.id

    async with async_session() as session:
        stmt = select(Tournament).where(Tournament.id == tour_id)
        result = await session.execute(stmt)
        t = result.scalar_one_or_none()
        
        if not t:
            await call.answer("❌ Турнир не найден", show_alert=True)
            return

        # Check user registration status
        user_stmt = select(User).where(User.telegram_id == tg_id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        
        is_registered = False
        if user:
            reg_stmt = select(Registration).where(
                Registration.tournament_id == tour_id,
                Registration.user_id == user.id
            )
            reg_res = await session.execute(reg_stmt)
            is_registered = reg_res.scalar_one_or_none() is not None

        # Fetch participant count
        count_stmt = select(func.count(Registration.id)).where(Registration.tournament_id == tour_id)
        count_res = await session.execute(count_stmt)
        participant_count = count_res.scalar() or 0

        # Check if bracket exists (at least one match)
        bracket_stmt = select(BracketMatch).where(BracketMatch.tournament_id == tour_id)
        bracket_res = await session.execute(bracket_stmt)
        has_bracket = bracket_res.first() is not None

    status_str = "Регистрация открыта" if t.status == "registration" else "Идет турнир" if t.status == "active" else "Черновик"
    
    details = (
        f"🏆 <b>Турнир: {t.title}</b>\n\n"
        f"📝 Статус: {status_str}\n"
        f"🎮 Режим: {t.game_mode} ({t.tournament_type})\n"
        f"👥 Участники: {participant_count} / {t.max_participants}\n\n"
        f"🎁 <b>Призы:</b>\n"
        f"🥇 1-е место: {t.prize_1st or 'не указан'}\n"
        f"🥈 2-е место: {t.prize_2nd or 'не указан'}\n"
        f"🥉 3-е место: {t.prize_3rd or 'не указан'}\n\n"
        f"📖 <i>Описание:</i> {t.description or 'описание отсутствует.'}"
    )

    reply_markup = get_tournament_detail_keyboard(tour_id, is_registered, has_bracket)

    if not call.message.photo:
        # Already a plain text message (list view, another tournament's
        # detail view, etc.) — edit it in place.
        try:
            await call.message.edit_text(details, reply_markup=reply_markup, parse_mode="HTML")
            await call.answer()
            return
        except Exception:
            pass

    # Coming from a photo message (e.g. the schedule banner) — Telegram
    # can't turn a photo message into a text-only one, so send the new
    # message first, then remove the old one to avoid an empty gap.
    sent_msg = await call.message.answer(details, reply_markup=reply_markup, parse_mode="HTML")
    try:
        await call.message.delete()
    except Exception:
        pass
    await state.update_data(last_section_message_id=sent_msg.message_id)
    await call.answer()


# ==================== REGISTRATION & UNREGISTRATION ====================

@router.callback_query(F.data.startswith("tour_reg_"))
async def cb_register_tournament(call: types.CallbackQuery, state: FSMContext) -> None:
    """Register user for tournament."""
    tour_id = int(call.data.replace("tour_reg_", ""))
    tg_id = call.from_user.id

    async with async_session() as session:
        # Check user BS tag
        user_stmt = select(User).where(User.telegram_id == tg_id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()

        if not user or not user.brawl_stars_tag:
            await call.answer(
                "⚠️ Сначала укажите ваш Brawl Stars Tag в профиле!",
                show_alert=True
            )
            return

        # Check tournament
        stmt = select(Tournament).where(Tournament.id == tour_id)
        result = await session.execute(stmt)
        t = result.scalar_one_or_none()
        if not t:
            await call.answer("❌ Турнир не найден", show_alert=True)
            return

        if t.status not in ("registration", "draft"):
            await call.answer("❌ Регистрация на этот турнир уже закрыта!", show_alert=True)
            return

        # Check if already registered
        reg_stmt = select(Registration).where(
            Registration.tournament_id == tour_id,
            Registration.user_id == user.id
        )
        reg_res = await session.execute(reg_stmt)
        if reg_res.scalar_one_or_none():
            await call.answer("Вы уже зарегистрированы!", show_alert=True)
            return

        # Check capacity
        count_stmt = select(func.count(Registration.id)).where(Registration.tournament_id == tour_id)
        count_res = await session.execute(count_stmt)
        current_count = count_res.scalar() or 0
        if current_count >= t.max_participants:
            await call.answer("❌ Свободных мест больше нет!", show_alert=True)
            return

        # Register
        reg = Registration(tournament_id=tour_id, user_id=user.id, status="registered")
        session.add(reg)
        await session.commit()

    await call.answer("✅ Вы успешно зарегистрированы на турнир!", show_alert=True)
    # Re-render details
    call.data = f"tour_detail_{tour_id}"
    await cb_tournament_detail(call, state)


@router.callback_query(F.data.startswith("tour_unreg_"))
async def cb_unregister_tournament(call: types.CallbackQuery, state: FSMContext) -> None:
    """Unregister user from tournament."""
    tour_id = int(call.data.replace("tour_unreg_", ""))
    tg_id = call.from_user.id

    async with async_session() as session:
        user_stmt = select(User).where(User.telegram_id == tg_id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        
        if not user:
            await call.answer("Пользователь не найден", show_alert=True)
            return

        t_stmt = select(Tournament).where(Tournament.id == tour_id)
        t_res = await session.execute(t_stmt)
        t = t_res.scalar_one_or_none()
        if t and t.status not in ("registration", "draft"):
            await call.answer("❌ Нельзя отменить регистрацию, так как турнир уже начался!", show_alert=True)
            return

        reg_stmt = select(Registration).where(
            Registration.tournament_id == tour_id,
            Registration.user_id == user.id
        )
        reg_res = await session.execute(reg_stmt)
        reg = reg_res.scalar_one_or_none()
        if reg:
            await session.delete(reg)
            await session.commit()

    await call.answer("❌ Регистрация отменена", show_alert=True)
    # Re-render details
    call.data = f"tour_detail_{tour_id}"
    await cb_tournament_detail(call, state)


# ==================== BRACKET VIEWER IN CHAT ====================

@router.callback_query(F.data.startswith("tour_bracket_"))
async def cb_show_bracket(call: types.CallbackQuery, state: FSMContext) -> None:
    """Format and send the tournament bracket directly as a text list."""
    tour_id = int(call.data.replace("tour_bracket_", ""))
    
    async with async_session() as session:
        stmt = (
            select(BracketMatch)
            .where(BracketMatch.tournament_id == tour_id)
            .options(
                selectinload(BracketMatch.player1),
                selectinload(BracketMatch.player2),
                selectinload(BracketMatch.winner),
            )
            .order_by(BracketMatch.round_number, BracketMatch.match_number)
        )
        result = await session.execute(stmt)
        matches = list(result.scalars().all())

    if not matches:
        await call.answer("Сетка еще не сгенерирована", show_alert=True)
        return

    # Group matches by round
    rounds = {}
    for m in matches:
        if m.round_number not in rounds:
            rounds[m.round_number] = []
        rounds[m.round_number].append(m)

    lines = ["📊 <b>Турнирная сетка:</b>\n"]
    
    for round_num in sorted(rounds.keys()):
        round_matches = rounds[round_num]
        
        # Round name helper
        total_rounds = len(rounds)
        if round_num == total_rounds:
            r_name = "Финал"
        elif round_num == total_rounds - 1:
            r_name = "Полуфинал"
        else:
            r_name = f"Раунд {round_num}"
            
        lines.append(f"🟢 <b>{r_name}:</b>")
        
        for m in round_matches:
            p1_name = m.player1.display_name if m.player1 else "Ожидание..."
            p2_name = m.player2.display_name if m.player2 else "Ожидание..."
            
            # Highlight winner
            if m.winner_id:
                if m.winner_id == m.player1_id:
                    p1_name = f"🏆 <u>{p1_name}</u>"
                else:
                    p2_name = f"🏆 <u>{p2_name}</u>"
                    
            score_str = f"({m.score})" if m.score else "(pending)"
            lines.append(f" • Match {m.match_number}: {p1_name} vs {p2_name} {score_str}")
        lines.append("")

    bracket_text = "\n".join(lines)
    reply_markup = get_back_keyboard(f"tour_detail_{tour_id}")

    if not call.message.photo:
        try:
            await call.message.edit_text(bracket_text, reply_markup=reply_markup, parse_mode="HTML")
            await call.answer()
            return
        except Exception:
            pass

    sent_msg = await call.message.answer(bracket_text, reply_markup=reply_markup, parse_mode="HTML")
    try:
        await call.message.delete()
    except Exception:
        pass
    await state.update_data(last_section_message_id=sent_msg.message_id)
    await call.answer()


# ==================== PROFILE MANAGEMENT ====================

@router.callback_query(F.data == "menu_profile")
async def cb_user_profile(call: types.CallbackQuery, state: FSMContext) -> None:
    """Display user profile info and stats."""
    tg_id = call.from_user.id
    
    async with async_session() as session:
        user_stmt = select(User).where(User.telegram_id == tg_id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        
        if not user:
            await call.answer("Профиль не найден. Нажмите /start сначала.", show_alert=True)
            return

        # Count wins from leaderboard (matches won)
        wins_stmt = select(func.count(BracketMatch.id)).where(BracketMatch.winner_id == user.id)
        wins_res = await session.execute(wins_stmt)
        wins = wins_res.scalar() or 0

        # Count registrations
        regs_stmt = select(func.count(Registration.id)).where(Registration.user_id == user.id)
        regs_res = await session.execute(regs_stmt)
        tournaments_played = regs_res.scalar() or 0

    role = "Администратор" if user.is_admin else "Игрок"
    brawl_tag = f"#{user.brawl_stars_tag}" if user.brawl_stars_tag else "<i>Не установлен</i>"

    profile_text = (
        f"👤 <b>Ваш профиль:</b>\n\n"
        f"📝 Имя: <b>{user.display_name}</b>\n"
        f"🆔 Юзернейм: @{user.username or '—'}\n"
        f"🏷️ Brawl Stars Tag: {brawl_tag}\n"
        f"⚙️ Роль: <b>{role}</b>\n\n"
        f"📊 <b>Ваша статистика в Deadly Crew:</b>\n"
        f"🏆 Участий в турнирах: {tournaments_played}\n"
        f"🥇 Побед в матчах: {wins}\n\n"
        f"<i>Вы можете сменить ваш Brawl Stars Tag кнопкой ниже или отправив команду /set_tag [ваш_тег] в чат.</i>"
    )

    async with async_session() as session:
        msg = await send_dynamic_view(call, session, "profile", profile_text, get_profile_keyboard())
        await state.update_data(last_section_message_id=msg.message_id)
    await call.answer()


@router.callback_query(F.data == "profile_edit_tag")
async def cb_edit_tag_start(call: types.CallbackQuery, state: FSMContext) -> None:
    """Prompt user to change their Brawl Stars Tag."""
    await state.set_state(ProfileStates.waiting_for_tag)
    await call.message.edit_text(
        "📝 <b>Редактирование Brawl Stars Tag</b>\n\n"
        "Отправьте ваш уникальный тег игрока (без знака #) следующим сообщением.\n\n"
        "Пример: <code>YV8L0G</code>",
        reply_markup=get_back_keyboard("menu_profile"),
        parse_mode="HTML"
    )
    await call.answer()


@router.message(ProfileStates.waiting_for_tag)
async def process_profile_tag_message(message: types.Message, state: FSMContext) -> None:
    """FSM handler to capture and save the Brawl Stars Tag."""
    tag = message.text.strip().upper().replace("#", "")
    
    data = await state.get_data()
    main_menu_id = data.get("main_menu_message_id")
    last_section_id = data.get("last_section_message_id")
    
    await state.clear()
    
    if main_menu_id:
        await state.update_data(main_menu_message_id=main_menu_id)

    if last_section_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_section_id)
        except Exception:
            pass

    if not tag or len(tag) < 3 or len(tag) > 15:
        sent_msg = await message.answer(
            "❌ Некорректный тег. Попробуйте еще раз с помощью команды: `/set_tag [ваш_тег]`",
            parse_mode="HTML"
        )
        await state.update_data(last_section_message_id=sent_msg.message_id)
        return

    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            user.brawl_stars_tag = tag
            await session.commit()
            
            sent_msg = await message.answer(
                f"✅ Brawl Stars Tag изменен на <b>#{tag}</b>!\n\n"
                f"Вы можете проверить информацию в меню /start -> 👤 Мой профиль.",
                parse_mode="HTML",
                reply_markup=get_start_keyboard(is_admin=user.is_admin)
            )
            
            if main_menu_id:
                try:
                    await message.bot.delete_message(chat_id=message.chat.id, message_id=main_menu_id)
                except Exception:
                    pass
            await state.update_data(main_menu_message_id=sent_msg.message_id)
        else:
            await message.answer("Ошибка: пользователь не найден. Введите команду /start")


@router.message(Command("set_tag"))
async def cmd_set_tag(message: types.Message, state: FSMContext) -> None:
    """Fast command to set/change Brawl Stars Tag directly."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: `/set_tag YV8L0G` (укажите ваш тег)", parse_mode="HTML")
        return
        
    tag = parts[1].strip().upper().replace("#", "")
    if len(tag) < 3 or len(tag) > 15:
         await message.answer("❌ Недопустимая длина тега (должна быть от 3 до 15 символов).")
         return

    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            user.brawl_stars_tag = tag
            await session.commit()
            
            data = await state.get_data()
            main_menu_id = data.get("main_menu_message_id")
            last_section_id = data.get("last_section_message_id")
            if main_menu_id:
                try:
                    await message.bot.delete_message(chat_id=message.chat.id, message_id=main_menu_id)
                except Exception:
                    pass
            if last_section_id:
                try:
                    await message.bot.delete_message(chat_id=message.chat.id, message_id=last_section_id)
                except Exception:
                    pass
            
            await state.clear()
            
            sent_msg = await message.answer(
                f"✅ Brawl Stars Tag успешно изменен на <b>#{tag}</b>!",
                parse_mode="HTML",
                reply_markup=get_start_keyboard(is_admin=user.is_admin)
            )
            await state.update_data(main_menu_message_id=sent_msg.message_id)
        else:
             await message.answer("Введите команду /start, чтобы зарегистрироваться в системе.")


# ==================== LEADERBOARD ====================

@router.callback_query(F.data == "menu_leaderboard")
async def cb_leaderboard(call: types.CallbackQuery, state: FSMContext) -> None:
    """Display the top players sorted by wins directly in the chat."""
    async with async_session() as session:
        leaderboard_title = await get_config_value(
            session, "leaderboard_title", "🥇 <b>Зал Славы Deadly Crew (Топ-10):</b>"
        )
        # Query top players by win counts
        stmt = (
            select(
                User,
                func.count(BracketMatch.id).label("wins"),
            )
            .join(BracketMatch, BracketMatch.winner_id == User.id)
            .group_by(User.id)
            .order_by(func.count(BracketMatch.id).desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        rows = result.all()

    lines = [f"{leaderboard_title}\n"]
    if not rows:
        lines.append("Таблица лидеров пуста. Сыграйте в турнирах, чтобы попасть сюда!")
    else:
        for idx, (user, wins) in enumerate(rows):
            rank = idx + 1
            emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
            lines.append(f"{emoji} {user.display_name} — <b>{wins} W</b> (Tag: #{user.brawl_stars_tag or '—'})")

    text = "\n".join(lines)
    async with async_session() as session:
        msg = await send_dynamic_view(call, session, "leaderboard", text, get_back_keyboard("menu_main"))
        await state.update_data(last_section_message_id=msg.message_id)
    await call.answer()


# ==================== TEXT COMMAND HANDLERS ====================

@router.message(Command("tournaments"))
@router.message(Command("schedule"))
async def cmd_tournaments(message: types.Message, state: FSMContext) -> None:
    """Handle /tournaments (or /schedule) command (displays active/upcoming tournaments)."""
    await prepare_section_view(state, message.bot, message.chat.id)
    async with async_session() as session:
        stmt = select(Tournament).where(Tournament.status != "completed").order_by(Tournament.created_at.desc())
        result = await session.execute(stmt)
        tournaments = list(result.scalars().all())

        tournaments_on_dates = {}
        for t in tournaments:
            if t.start_date:
                t_date = t.start_date.date().strftime("%Y-%m-%d")
                tournaments_on_dates[t_date] = tournaments_on_dates.get(t_date, 0) + 1

        tour_list = []
        for t in tournaments:
            count_stmt = select(func.count(Registration.id)).where(Registration.tournament_id == t.id)
            count_res = await session.execute(count_stmt)
            count = count_res.scalar() or 0
            tour_list.append({
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "max_participants": t.max_participants,
                "participant_count": count
            })

        photo = await get_schedule_photo(session)

    caption = "📅 <b>Расписание: Все игры</b>\n\nВыберите игру ниже для подробной информации:"
    reply_markup = get_schedule_keyboard(tour_list, tournaments_on_dates, "all")

    if photo:
        sent_msg = await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        # Save file_id locally to database configs to prevent uploading it again
        if isinstance(photo, FSInputFile) and sent_msg.photo:
            async with async_session() as session:
                await set_config_value(session, "schedule_image", sent_msg.photo[-1].file_id)
    else:
        sent_msg = await message.answer(
            text=caption,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    await state.update_data(last_section_message_id=sent_msg.message_id)


@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: types.Message, state: FSMContext) -> None:
    """Handle /leaderboard command (shows top players list)."""
    await prepare_section_view(state, message.bot, message.chat.id)
    async with async_session() as session:
        leaderboard_title = await get_config_value(
            session, "leaderboard_title", "🥇 <b>Зал Славы Deadly Crew (Топ-10):</b>"
        )
        stmt = (
            select(User, func.count(BracketMatch.id).label("wins"))
            .join(BracketMatch, BracketMatch.winner_id == User.id)
            .group_by(User.id)
            .order_by(func.count(BracketMatch.id).desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        rows = result.all()

    lines = [f"{leaderboard_title}\n"]
    if not rows:
        lines.append("Таблица лидеров пуста. Сыграйте в турнирах, чтобы попасть сюда!")
    else:
        for idx, (user, wins) in enumerate(rows):
            rank = idx + 1
            emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
            lines.append(f"{emoji} {user.display_name} — <b>{wins} W</b> (Tag: #{user.brawl_stars_tag or '—'})")

    text = "\n".join(lines)
    async with async_session() as session:
        msg = await send_dynamic_view(message, session, "leaderboard", text, get_back_keyboard("menu_main"))
        await state.update_data(last_section_message_id=msg.message_id)


@router.message(Command("profile"))
async def cmd_profile(message: types.Message, state: FSMContext) -> None:
    """Handle /profile command (shows user profile)."""
    await prepare_section_view(state, message.bot, message.chat.id)
    tg_id = message.from_user.id
    async with async_session() as session:
        user_stmt = select(User).where(User.telegram_id == tg_id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        
        if not user:
            await message.answer("Профиль не найден. Нажмите /start сначала.")
            return

        wins_stmt = select(func.count(BracketMatch.id)).where(BracketMatch.winner_id == user.id)
        wins_res = await session.execute(wins_stmt)
        wins = wins_res.scalar() or 0

        regs_stmt = select(func.count(Registration.id)).where(Registration.user_id == user.id)
        regs_res = await session.execute(regs_stmt)
        tournaments_played = regs_res.scalar() or 0

    role = "Администратор" if user.is_admin else "Игрок"
    brawl_tag = f"#{user.brawl_stars_tag}" if user.brawl_stars_tag else "<i>Не установлен</i>"

    profile_text = (
        f"👤 <b>Ваш профиль:</b>\n\n"
        f"📝 Имя: <b>{user.display_name}</b>\n"
        f"🆔 Юзернейм: @{user.username or '—'}\n"
        f"🏷️ Brawl Stars Tag: {brawl_tag}\n"
        f"⚙️ Роль: <b>{role}</b>\n\n"
        f"📊 <b>Ваша статистика в Deadly Crew:</b>\n"
        f"🏆 Участий в турнирах: {tournaments_played}\n"
        f"🥇 Побед в матчах: {wins}\n\n"
        f"<i>Вы можете сменить ваш Brawl Stars Tag кнопкой ниже или отправив команду /set_tag [ваш_тег] в чат.</i>"
    )
    async with async_session() as session:
        msg = await send_dynamic_view(message, session, "profile", profile_text, get_profile_keyboard())
        await state.update_data(last_section_message_id=msg.message_id)


@router.message(Command("rules"))
@router.message(Command("bell"))
async def cmd_rules(message: types.Message, state: FSMContext) -> None:
    """Handle /rules (or /bell) command (displays rules/regulations)."""
    await prepare_section_view(state, message.bot, message.chat.id)
    default_rules = (
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
    )
    async with async_session() as session:
        rules_text = await get_config_value(session, "rules", default_rules)
        msg = await send_dynamic_view(message, session, "rules", rules_text, get_back_keyboard("menu_main"))
        await state.update_data(last_section_message_id=msg.message_id)


@router.callback_query(F.data.startswith("sched_date_"))
async def cb_sched_date_filter(call: types.CallbackQuery, state: FSMContext) -> None:
    """Filter the displayed tournament schedule by a selected date."""
    active_date_str = call.data.replace("sched_date_", "")
    
    async with async_session() as session:
        # Load all active tournaments
        stmt = select(Tournament).where(Tournament.status != "completed").order_by(Tournament.created_at.desc())
        result = await session.execute(stmt)
        tournaments = list(result.scalars().all())

        # Build tournaments count per date
        tournaments_on_dates = {}
        for t in tournaments:
            if t.start_date:
                t_date = t.start_date.date().strftime("%Y-%m-%d")
                tournaments_on_dates[t_date] = tournaments_on_dates.get(t_date, 0) + 1

        # Format details list
        tour_list = []
        for t in tournaments:
            # Check date filter
            if active_date_str != "all" and t.start_date:
                if t.start_date.date().strftime("%Y-%m-%d") != active_date_str:
                    continue
                    
            count_stmt = select(func.count(Registration.id)).where(Registration.tournament_id == t.id)
            count_res = await session.execute(count_stmt)
            count = count_res.scalar() or 0
            
            tour_list.append({
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "max_participants": t.max_participants,
                "participant_count": count
            })

        photo = await get_schedule_photo(session)

    if active_date_str == "all":
        caption = "📅 <b>Расписание: Все игры</b>\n\nВыберите игру ниже для подробной информации:"
    else:
        # format date prettily
        selected_date = dt.datetime.strptime(active_date_str, "%Y-%m-%d").date()
        date_pretty = selected_date.strftime("%d.%m")
        if not tour_list:
            caption = f"📅 <b>Расписание на {date_pretty}</b>\n\nНа этот день игр не запланировано. Отдыхаем! 😴"
        else:
            caption = f"📅 <b>Расписание на {date_pretty}</b>\n\nВыберите игру ниже для подробной информации:"

    reply_markup = get_schedule_keyboard(tour_list, tournaments_on_dates, active_date_str)
    
    if call.message.photo and photo:
        media_src = photo if isinstance(photo, str) else photo.file
        await call.message.edit_media(
            media=types.InputMediaPhoto(media=media_src, caption=caption, parse_mode="HTML"),
            reply_markup=reply_markup
        )
    else:
        # If no photo is loaded or it wasn't a photo message, edit/send text
        if call.message.photo or call.message.document:
            try:
                await call.message.delete()
            except Exception:
                pass
            sent_msg = await call.message.answer(
                text=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            await state.update_data(last_section_message_id=sent_msg.message_id)
        else:
            await call.message.edit_text(
                text=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
    await call.answer()


