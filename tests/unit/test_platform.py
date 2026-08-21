"""Tests for platform base behavior."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.manager import PlatformManager
from astrbot.core.platform.platform import Platform
from astrbot.core.platform.platform_metadata import PlatformMetadata
from astrbot.core.platform.register import platform_cls_map


class DummyPlatform(Platform):
    """Minimal platform implementation for base class tests."""

    def __init__(
        self,
        config: dict,
        settings_or_event_queue,
        event_queue: asyncio.Queue | None = None,
    ) -> None:
        """Initialize the dummy platform.

        Args:
            config: Platform config.
            settings_or_event_queue: Platform settings or event queue.
            event_queue: Optional event queue when settings are provided.
        """
        super().__init__(config, event_queue or settings_or_event_queue)

    async def run(self) -> None:
        """Run the dummy platform."""

    def meta(self) -> PlatformMetadata:
        """Return dummy platform metadata.

        Returns:
            Dummy platform metadata.
        """
        return PlatformMetadata(
            name="dummy",
            description="Dummy platform",
            id=self.config.get("id", "dummy"),
        )


class FakeConfig(dict):
    """Minimal config object for platform manager tests."""

    def save_config(self) -> None:
        """Save config."""


def test_commit_event_skips_disabled_platform() -> None:
    """Verify disabled platforms do not enqueue new events."""
    queue = asyncio.Queue()
    platform = DummyPlatform({"id": "dummy", "enable": False}, queue)

    platform.commit_event(MagicMock())

    assert queue.empty()


@pytest.mark.asyncio
async def test_commit_event_replies_to_expired_platform() -> None:
    """Verify expired platforms reply without enqueueing events."""
    queue = asyncio.Queue()
    event = MagicMock()
    event.send = AsyncMock()
    platform = DummyPlatform(
        {
            "id": "dummy",
            "enable": False,
            "expires_at": (datetime.now() - timedelta(minutes=1)).isoformat(),
        },
        queue,
    )

    platform.commit_event(event)
    await asyncio.sleep(0)

    assert queue.empty()
    event.send.assert_awaited_once()
    message = event.send.await_args.args[0]
    assert isinstance(message, MessageChain)
    assert message.get_plain_text() == "试用已到期，请联系管理员续期。"


def test_commit_event_enqueues_active_platform() -> None:
    """Verify active platforms still enqueue events."""
    queue = asyncio.Queue()
    event = MagicMock()
    platform = DummyPlatform({"id": "dummy", "enable": True}, queue)

    platform.commit_event(event)

    assert queue.get_nowait() is event


@pytest.mark.asyncio
async def test_manager_loads_expired_platform_for_expiration_reply(monkeypatch) -> None:
    """Verify expired platforms are loaded for expiration replies."""
    expires_at = (datetime.now() - timedelta(minutes=1)).isoformat()
    config = FakeConfig(
        {
            "platform": [
                {
                    "id": "expired-dummy",
                    "type": "dummy",
                    "enable": False,
                    "expires_at": expires_at,
                }
            ],
            "platform_settings": {},
        }
    )
    monkeypatch.setitem(platform_cls_map, "dummy", DummyPlatform)
    manager = PlatformManager(config, asyncio.Queue())

    await manager.load_platform(config["platform"][0])
    try:
        assert len(manager.platform_insts) == 1
        event = MagicMock()
        event.send = AsyncMock()

        manager.platform_insts[0].commit_event(event)
        await asyncio.sleep(0)

        assert manager.event_queue.empty()
        event.send.assert_awaited_once()
    finally:
        await manager.terminate()
