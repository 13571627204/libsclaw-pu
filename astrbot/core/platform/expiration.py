from __future__ import annotations

from datetime import datetime


def parse_platform_expires_at(value: object) -> datetime | None:
    """Parse a platform expiration value.

    Args:
        value: Stored expiration datetime. Empty values mean no expiration.

    Returns:
        Parsed datetime when valid, otherwise None.
    """
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_platform_expired(
    platform_config: dict,
    *,
    now: datetime | None = None,
) -> bool:
    """Check whether a platform has reached its expiration time.

    Args:
        platform_config: Platform configuration dictionary.
        now: Optional current datetime for tests.

    Returns:
        True when the platform expiration time has passed.
    """
    expires_at = parse_platform_expires_at(platform_config.get("expires_at"))
    if expires_at is None:
        return False

    if now is None:
        now = datetime.now(expires_at.tzinfo) if expires_at.tzinfo else datetime.now()
    elif expires_at.tzinfo and not now.tzinfo:
        now = now.replace(tzinfo=expires_at.tzinfo)

    return expires_at <= now
