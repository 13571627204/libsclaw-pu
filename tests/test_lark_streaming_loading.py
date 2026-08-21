import asyncio
import json
from types import SimpleNamespace

import pytest

from astrbot.core.platform.sources.lark.lark_event import LarkMessageEvent


class FakeLarkResponse:
    def __init__(self, success: bool = True, data=None) -> None:
        self.code = 0
        self.msg = "ok"
        self.data = data
        self._success = success

    def success(self) -> bool:
        return self._success


class FakeCardResource:
    def __init__(self) -> None:
        self.create_request = None
        self.settings_request = None

    async def acreate(self, request):
        self.create_request = request
        return FakeLarkResponse(data=SimpleNamespace(card_id="card-1"))

    async def asettings(self, request):
        self.settings_request = request
        return FakeLarkResponse()


class FakeCardElementResource:
    def __init__(self) -> None:
        self.delete_request = None

    async def adelete(self, request):
        self.delete_request = request
        return FakeLarkResponse()


class FakeMessageResource:
    def __init__(self) -> None:
        self.reply_request = None
        self.replied = asyncio.Event()

    async def areply(self, request):
        self.reply_request = request
        self.replied.set()
        return FakeLarkResponse()


def _make_event(
    card_resource=None,
    card_element_resource=None,
    message_resource=None,
) -> LarkMessageEvent:
    event = LarkMessageEvent.__new__(LarkMessageEvent)
    event.bot = SimpleNamespace(
        im=SimpleNamespace(v1=SimpleNamespace(message=message_resource)),
        cardkit=SimpleNamespace(
            v1=SimpleNamespace(
                card=card_resource or FakeCardResource(),
                card_element=card_element_resource or FakeCardElementResource(),
            )
        ),
    )
    event.message_obj = SimpleNamespace(message_id="message-1")
    event.platform_meta = SimpleNamespace(name="lark")
    event._has_send_oper = False
    return event


@pytest.mark.asyncio
async def test_create_streaming_card_includes_loading_element():
    """Streaming cards should show a temporary loading message under output."""
    card_resource = FakeCardResource()
    event = _make_event(card_resource=card_resource)

    card_id = await event._create_streaming_card()

    assert card_id == "card-1"
    card_json = json.loads(card_resource.create_request.body.data)
    elements = card_json["body"]["elements"]
    assert elements == [
        {
            "tag": "markdown",
            "content": "",
            "element_id": LarkMessageEvent.STREAMING_MARKDOWN_ELEMENT_ID,
        },
        {
            "tag": "markdown",
            "content": LarkMessageEvent.STREAMING_LOADING_TEXT,
            "element_id": LarkMessageEvent.STREAMING_LOADING_ELEMENT_ID,
        },
    ]


@pytest.mark.asyncio
async def test_delete_streaming_loading_targets_loading_element():
    """Closing a streaming card should remove the temporary loading element."""
    card_element_resource = FakeCardElementResource()
    event = _make_event(card_element_resource=card_element_resource)

    deleted = await event._delete_streaming_loading("card-1", 7)

    assert deleted is True
    request = card_element_resource.delete_request
    assert request.card_id == "card-1"
    assert request.element_id == LarkMessageEvent.STREAMING_LOADING_ELEMENT_ID
    assert request.body.sequence == 7


@pytest.mark.asyncio
async def test_send_streaming_sends_loading_card_before_first_content():
    """A loading card should be visible while waiting for the first content."""
    release_generator = asyncio.Event()
    card_resource = FakeCardResource()
    message_resource = FakeMessageResource()
    event = _make_event(
        card_resource=card_resource,
        message_resource=message_resource,
    )

    async def waiting_generator():
        await release_generator.wait()
        if False:
            yield

    task = asyncio.create_task(event.send_streaming(waiting_generator()))
    await asyncio.wait_for(message_resource.replied.wait(), timeout=1)

    assert card_resource.create_request is not None
    request_body = message_resource.reply_request.body
    assert request_body.msg_type == "interactive"
    assert json.loads(request_body.content) == {
        "type": "card",
        "data": {"card_id": "card-1"},
    }

    release_generator.set()
    await task
