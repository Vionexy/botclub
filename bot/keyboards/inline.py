from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import settings


def get_start_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Return inline keyboard for the main welcome menu."""
    buttons = [
        [
            InlineKeyboardButton(text="Расписание", callback_data="menu_tournaments", icon_custom_emoji_id="5298883066415043645"),
            InlineKeyboardButton(text="Сетки", callback_data="menu_brackets_list", icon_custom_emoji_id="5298621889453776438"),
        ],
        [
            InlineKeyboardButton(text="Регламент", callback_data="menu_rules", icon_custom_emoji_id="5296471369263897453"),
            InlineKeyboardButton(text="О Deadly Crew", callback_data="menu_about", icon_custom_emoji_id="5267346053568419740"),
        ],
        [
            InlineKeyboardButton(text="Мой профиль", callback_data="menu_profile", icon_custom_emoji_id="5296511102006352211"),
            InlineKeyboardButton(text="Лидеры", callback_data="menu_leaderboard", icon_custom_emoji_id="5296793594890313365"),
        ]
    ]
    if is_admin:
        buttons.append([
            InlineKeyboardButton(text="Создать турнир", callback_data="admin_create_start", icon_custom_emoji_id="5296793594890313365"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tournaments_keyboard(tournaments: list[dict]) -> InlineKeyboardMarkup:
    """Return keyboard listing all active tournaments."""
    buttons = []
    for t in tournaments:
        status_emoji = "🟢" if t["status"] == "registration" else "🔵" if t["status"] == "active" else "🟡"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_emoji} {t['title']} ({t['participant_count']}/{t['max_participants']})",
                callback_data=f"tour_detail_{t['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tournament_detail_keyboard(
    tournament_id: int, 
    is_registered: bool, 
    has_bracket: bool
) -> InlineKeyboardMarkup:
    """Return actions for a specific tournament detail view."""
    buttons = []
    
    # Registration actions
    if not is_registered:
        buttons.append([InlineKeyboardButton(text="📝 Зарегистрироваться", callback_data=f"tour_reg_{tournament_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="❌ Отменить регистрацию", callback_data=f"tour_unreg_{tournament_id}")])
        
    # Bracket action
    if has_bracket:
        buttons.append([InlineKeyboardButton(text="📊 Показать сетку в чате", callback_data=f"tour_bracket_{tournament_id}")])
        
    buttons.append([
        InlineKeyboardButton(text="↩️ К списку турниров", callback_data="menu_tournaments")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Return actions for the user profile view."""
    buttons = [
        [InlineKeyboardButton(text="✏️ Изменить Brawl Stars Tag", callback_data="profile_edit_tag")],
        [InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_keyboard(back_callback: str) -> InlineKeyboardMarkup:
    """Return a single 'Back' button keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="↩️ Назад", callback_data=back_callback)]]
    )


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Return inline keyboard for the admin dashboard."""
    buttons = [
        [
            InlineKeyboardButton(text="➕ Создать турнир", callback_data="admin_create_start"),
        ],
        [
            InlineKeyboardButton(text="📝 Регламент", callback_data="admin_edit_rules"),
            InlineKeyboardButton(text="📝 О клубе", callback_data="admin_edit_about"),
        ],
        [
            InlineKeyboardButton(text="📝 Заголовок", callback_data="admin_edit_welcome_title"),
            InlineKeyboardButton(text="📝 Подзаголовок", callback_data="admin_edit_welcome_subtitle"),
        ],
        [
            InlineKeyboardButton(text="📝 Заголовок лидеров", callback_data="admin_edit_leaderboard_title"),
        ],
        [
            InlineKeyboardButton(text="🖼️ Картинки разделов (баннеры)", callback_data="admin_banners_menu"),
        ],
        [
            InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu_main"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_banners_menu_keyboard() -> InlineKeyboardMarkup:
    """Return inline keyboard for the admin banner management submenu."""
    buttons = [
        [
            InlineKeyboardButton(text="Расписание", callback_data="admin_edit_schedule_banner", icon_custom_emoji_id="5298883066415043645"),
            InlineKeyboardButton(text="Регламент", callback_data="admin_edit_rules_banner", icon_custom_emoji_id="5298621889453776438"),
        ],
        [
            InlineKeyboardButton(text="О Deadly Crew", callback_data="admin_edit_about_banner", icon_custom_emoji_id="5296471369263897453"),
            InlineKeyboardButton(text="Сетки", callback_data="admin_edit_brackets_banner", icon_custom_emoji_id="5298621889453776438"),
        ],
        [
            InlineKeyboardButton(text="Мой профиль", callback_data="admin_edit_profile_banner", icon_custom_emoji_id="5267346053568419740"),
            InlineKeyboardButton(text="Лидерборд", callback_data="admin_edit_leaderboard_banner", icon_custom_emoji_id="5296511102006352211"),
        ],
        [
            InlineKeyboardButton(text="↩️ Назад в админку", callback_data="admin_back_to_dashboard"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


import datetime as dt

def get_schedule_keyboard(
    tournaments: list[dict],
    tournaments_on_dates: dict[str, int],
    active_date_str: str = "all"
) -> InlineKeyboardMarkup:
    """Generate inline keyboard containing date picker and tournament list."""
    buttons = []
    
    # 1. Date Slider Buttons
    today = dt.date.today()
    weekdays_ru = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
    
    # Row for "All games"
    all_text = "⭐ Все игры" if active_date_str == "all" else "Все игры"
    buttons.append([InlineKeyboardButton(text=all_text, callback_data="sched_date_all")])
    
    # Rows for the next 6 days (3 rows of 2 columns)
    row = []
    for i in range(6):
        date_val = today + dt.timedelta(days=i)
        date_str = date_val.strftime("%Y-%m-%d")
        
        # Weekday and day
        wday_idx = int(date_val.strftime("%w"))
        wday_name = weekdays_ru[wday_idx]
        day_num = date_val.strftime("%d.%m")
        
        is_active = (date_str == active_date_str)
        has_games = tournaments_on_dates.get(date_str, 0) > 0
        dot = " 🟢" if has_games else ""
        
        btn_text = f"🔹 {wday_name} ({day_num}){dot}" if is_active else f"{wday_name} ({day_num}){dot}"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"sched_date_{date_str}"))
        
        if len(row) == 2:
            buttons.append(row)
            row = []
            
    # 2. Tournament List Buttons
    if tournaments:
        buttons.append([InlineKeyboardButton(text="— Игры на выбранную дату —", callback_data="noop")])
        for t in tournaments:
            status_emoji = "🟢" if t["status"] == "registration" else "🔵" if t["status"] == "active" else "🟡"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status_emoji} {t['title']} ({t['participant_count']}/{t['max_participants']})",
                    callback_data=f"tour_detail_{t['id']}"
                )
            ])
            
    # 3. Footer Back Navigation
    buttons.append([InlineKeyboardButton(text="↩️ В главное меню", callback_data="menu_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
