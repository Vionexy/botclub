from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import SystemConfig


async def get_config_value(session: AsyncSession, key: str, default: str = "") -> str:
    """Retrieve a configuration value from database, fallback to default."""
    try:
        stmt = select(SystemConfig).where(SystemConfig.key == key)
        result = await session.execute(stmt)
        config = result.scalar_one_or_none()
        if config:
            return config.value
    except Exception:
        pass
    return default


async def set_config_value(session: AsyncSession, key: str, value: str) -> None:
    """Save or update a configuration key-value pair in database."""
    stmt = select(SystemConfig).where(SystemConfig.key == key)
    result = await session.execute(stmt)
    config = result.scalar_one_or_none()
    
    if config:
        config.value = value
    else:
        config = SystemConfig(key=key, value=value)
        session.add(config)
    await session.commit()
