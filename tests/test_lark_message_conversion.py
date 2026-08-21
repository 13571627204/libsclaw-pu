import contextlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import astrbot.core.platform.sources.lark.lark_event as lark_event
from astrbot.api.message_components import At, Plain
from astrbot.api.message_components import Image as AstrBotImage
from astrbot.core.platform.sources.lark.lark_event import LarkMessageEvent


class FakeLarkResponse:
    def __init__(self, success: bool = True, data=None) -> None:
        self.code = 0
        self.msg = "ok"
        self.data = data
        self._success = success

    def success(self) -> bool:
        return self._success


class FakeImageResource:
    def __init__(self) -> None:
        self.upload_count = 0

    async def acreate(self, request):
        self.upload_count += 1
        return FakeLarkResponse(
            data=SimpleNamespace(image_key=f"img-key-{self.upload_count}"),
        )


class FakeLarkClient:
    def __init__(self) -> None:
        self.image_resource = FakeImageResource()
        self.im = SimpleNamespace(v1=SimpleNamespace(image=self.image_resource))


class FakeMessageChain:
    def __init__(self, chain) -> None:
        self.chain = chain


@pytest.fixture
def fake_image(tmp_path, monkeypatch) -> Path:
    """Provide a local image file and stub MediaResolver to resolve to it."""
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)

    class StubResolver:
        def __init__(self, *args, **kwargs) -> None:
            pass

        @contextlib.asynccontextmanager
        async def as_path(self):
            yield image_path

    monkeypatch.setattr(lark_event, "MediaResolver", StubResolver)
    return image_path


@pytest.mark.asyncio
async def test_convert_keeps_text_preceding_image(fake_image):
    """Text queued before an image must survive the image flush."""
    chain = FakeMessageChain([Plain("图片说明文字"), AstrBotImage(file=str(fake_image))])

    result = await LarkMessageEvent._convert_to_lark(chain, FakeLarkClient())

    assert result == [
        [{"tag": "md", "text": "图片说明文字"}],
        [{"tag": "img", "image_key": "img-key-1"}],
    ]


@pytest.mark.asyncio
async def test_convert_keeps_text_between_and_after_images(fake_image):
    """Each text segment stays attached to its own position in the chain."""
    chain = FakeMessageChain(
        [
            Plain("第一段"),
            AstrBotImage(file=str(fake_image)),
            Plain("第二段"),
            AstrBotImage(file=str(fake_image)),
            Plain("第三段"),
        ],
    )

    result = await LarkMessageEvent._convert_to_lark(chain, FakeLarkClient())

    assert result == [
        [{"tag": "md", "text": "第一段"}],
        [{"tag": "img", "image_key": "img-key-1"}],
        [{"tag": "md", "text": "第二段"}],
        [{"tag": "img", "image_key": "img-key-2"}],
        [{"tag": "md", "text": "第三段"}],
    ]


@pytest.mark.asyncio
async def test_convert_leading_image_emits_no_empty_segment(fake_image):
    """An image at the very start must not produce an empty leading segment."""
    chain = FakeMessageChain([AstrBotImage(file=str(fake_image)), Plain("图注")])

    result = await LarkMessageEvent._convert_to_lark(chain, FakeLarkClient())

    assert result == [
        [{"tag": "img", "image_key": "img-key-1"}],
        [{"tag": "md", "text": "图注"}],
    ]


@pytest.mark.asyncio
async def test_convert_keeps_mention_preceding_image(fake_image):
    """Mentions share the staging buffer with text and must survive too."""
    chain = FakeMessageChain(
        [At(qq="ou_1", name="张三"), AstrBotImage(file=str(fake_image))],
    )

    result = await LarkMessageEvent._convert_to_lark(chain, FakeLarkClient())

    assert result == [
        [{"tag": "at", "user_id": "ou_1", "style": []}],
        [{"tag": "img", "image_key": "img-key-1"}],
    ]
