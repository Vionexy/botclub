"""Telegram WebApp initData validation via HMAC-SHA256."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs, unquote

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.db import get_session
from database.models import User


def _validate_init_data(init_data: str, bot_token: str) -> dict:
    """Validate Telegram WebApp initData and return parsed user dict.

    Algorithm:
    1. Parse the query-string.
    2. Sort all key-value pairs except `hash` alphabetically.
    3. Build data_check_string (key=value joined with \\n).
    4. secret_key = HMAC-SHA256("WebAppData", bot_token).
    5. Calculated hash = HMAC-SHA256(secret_key, data_check_string).
    6. Compare with received hash.
    """
    parsed = parse_qs(init_data, keep_blank_values=True)
    received_hash = parsed.get("hash", [None])[0]
    if not received_hash:
        raise ValueError("hash is missing from initData")

    # Build data-check-string
    data_pairs: list[str] = []
    for key, values in parsed.items():
        if key == "hash":
            continue
        data_pairs.append(f"{key}={values[0]}")
    data_pairs.sort()
    data_check_string = "\n".join(data_pairs)

    # Compute HMAC
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256,
    ).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise ValueError("initData signature mismatch")

    # Optionally check auth_date freshness (allow 24 h)
    auth_date_str = parsed.get("auth_date", ["0"])[0]
    auth_date = int(auth_date_str)
    if time.time() - auth_date > 86400:
        raise ValueError("initData is too old")

    # Parse user JSON
    user_raw = parsed.get("user", [None])[0]
    if not user_raw:
        raise ValueError("user field missing from initData")

    return json.loads(unquote(user_raw))


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    authorization: str = Header(..., alias="Authorization"),
) -> User:
    """FastAPI dependency: validate Telegram initData header, return or create User."""
    # Header format: "tma <initData>"
    parts = authorization.split(" ", maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "tma":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected: tma <initData>",
        )

    init_data = parts[1]

    try:
        tg_user = _validate_init_data(init_data, settings.BOT_TOKEN)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"initData validation failed: {exc}",
        )

    telegram_id: int = tg_user["id"]

    # Lookup existing user
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        # Auto-create user on first visit
        is_admin = telegram_id in settings.admin_ids_list
        user = User(
            telegram_id=telegram_id,
            username=tg_user.get("username"),
            display_name=tg_user.get("first_name", "")
            + (" " + tg_user["last_name"] if tg_user.get("last_name") else ""),
            is_admin=is_admin,
        )
        session.add(user)
        await session.flush()
    else:
        # Update display info on each visit
        user.username = tg_user.get("username")
        user.display_name = (
            tg_user.get("first_name", "")
            + (" " + tg_user["last_name"] if tg_user.get("last_name") else "")
        )

    return user


async def get_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    """FastAPI dependency: ensures the current user is an admin."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
