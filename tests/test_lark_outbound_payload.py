import json
from types import SimpleNamespace

import pytest

from astrbot.api.message_components import File, Plain
from astrbot.core.platform.sources.lark.lark_event import LarkMessageEvent


class FakeLarkResponse:
    def __init__(self, success: bool = True, data=None) -> None:
        self.code = 0
        self.msg = "ok"
        self.data = data
        self._success = success

    def success(self) -> bool:
        return self._success


class RecordingClient:
    """Records outbound Lark API calls so assertions can inspect them."""

    def __init__(self) -> None:
        self.uploaded_paths: list[str] = []
        self.sent: list[dict] = []
        client = self

        class FileResource:
            async def acreate(self, request):
                client.uploaded_paths.append(request.request_body.file_name)
                return FakeLarkResponse(
                    data=SimpleNamespace(file_key=f"key-{len(client.uploaded_paths)}"),
                )

        class MessageResource:
            async def areply(self, request):
                body = request.request_body
                client.sent.append(
                    {"msg_type": body.msg_type, "content": body.content},
                )
                return FakeLarkResponse()

        self.im = SimpleNamespace(
            v1=SimpleNamespace(file=FileResource(), message=MessageResource()),
        )
        self.cardkit = None

    def post_texts(self) -> list[str]:
        """Return the text of every md fragment across all sent post messages."""
        texts = []
        for message in self.sent:
            if message["msg_type"] != "post":
                continue
            payload = json.loads(message["content"])
            for segment in payload["zh_cn"]["content"]:
                for item in segment:
                    if item.get("tag") == "md":
                        texts.append(item["text"])
        return texts


class FakeMessageChain:
    def __init__(self, chain) -> None:
        self.chain = chain


@pytest.mark.asyncio
async def test_send_file_downloads_url_only_component(tmp_path, monkeypatch):
    """A File carrying only a url must be downloaded instead of silently dropped."""
    downloaded = tmp_path / "remote.csv"
    downloaded.write_text("a,b\n1,2\n", encoding="utf-8")

    file_comp = File(name="remote.csv", url="https://example.com/remote.csv")

    async def fake_get_file(self, allow_return_url: bool = False) -> str:
        return str(downloaded)

    monkeypatch.setattr(File, "get_file", fake_get_file)

    client = RecordingClient()
    await LarkMessageEvent._send_file_message(
        file_comp, client, reply_message_id="om_1"
    )

    assert client.uploaded_paths == ["remote.csv"]
    assert [m["msg_type"] for m in client.sent] == ["file"]


@pytest.mark.asyncio
async def test_send_file_reports_unresolvable_component(monkeypatch):
    """An unresolvable file must not produce a file message."""
    file_comp = File(name="missing.csv", url="https://example.com/missing.csv")

    async def fake_get_file(self, allow_return_url: bool = False) -> str:
        return ""

    monkeypatch.setattr(File, "get_file", fake_get_file)

    client = RecordingClient()
    await LarkMessageEvent._send_file_message(
        file_comp, client, reply_message_id="om_2"
    )

    assert client.uploaded_paths == []
    assert client.sent == []


@pytest.mark.asyncio
async def test_send_file_survives_download_failure(monkeypatch):
    """A download raising must be caught rather than aborting the send."""
    file_comp = File(name="boom.csv", url="https://example.com/boom.csv")

    async def failing_get_file(self, allow_return_url: bool = False) -> str:
        raise RuntimeError("network down")

    monkeypatch.setattr(File, "get_file", failing_get_file)

    client = RecordingClient()
    await LarkMessageEvent._send_file_message(
        file_comp, client, reply_message_id="om_3"
    )

    assert client.sent == []


def test_split_text_keeps_short_text_intact():
    assert LarkMessageEvent._split_text_by_bytes("短文本") == ["短文本"]


def test_split_text_respects_byte_budget():
    """Every chunk must fit the byte budget, including multi-byte text."""
    text = "这是一段中文分析结论。" * 4000

    chunks = LarkMessageEvent._split_text_by_bytes(text)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.encode("utf-8")) <= LarkMessageEvent.MAX_TEXT_BYTES


def test_split_text_never_breaks_multibyte_characters():
    """Rejoined chunks must decode cleanly, proving no character was cut."""
    text = "汉字测试" * 9000

    chunks = LarkMessageEvent._split_text_by_bytes(text)

    for chunk in chunks:
        chunk.encode("utf-8").decode("utf-8")
    assert "".join(chunks) == text


def test_split_text_prefers_newline_boundaries():
    line = "x" * 500
    text = "\n".join([line] * 200)

    chunks = LarkMessageEvent._split_text_by_bytes(text)

    assert len(chunks) > 1
    # No chunk should start mid-line when newlines are available as breaks.
    for chunk in chunks[1:]:
        assert not chunk.startswith("x" * 501)


def test_split_text_returns_empty_list_for_empty_input():
    assert LarkMessageEvent._split_text_by_bytes("") == []


@pytest.mark.parametrize(
    ("label", "text"),
    [
        # Whitespace at a chunk boundary is syntactically meaningful in these
        # formats, so the split must not consume or reflow it.
        ("indented_code", "def f():\n    return 1\n" * 3000),
        ("nested_list", "- top\n  - nested item with some text here\n" * 3000),
        ("markdown_table", "| col a  | col b  | col c  |\n" * 4000),
        ("blank_lines", ("x" * 100 + "\n\n\n\n") * 3000),
        ("no_separators", "字" * 40000),
        ("emoji", "🎉" * 20000),
        ("zwj_emoji", "👨‍👩‍👧‍👦" * 5000),
        ("mixed_scripts", "中文abc🎉テスト한글" * 3000),
    ],
)
def test_split_text_is_lossless(label, text):
    """Rejoining the chunks must reproduce the input byte for byte."""
    chunks = LarkMessageEvent._split_text_by_bytes(text)

    assert "".join(chunks) == text, f"{label} lost content"
    for chunk in chunks:
        assert len(chunk.encode("utf-8")) <= LarkMessageEvent.MAX_TEXT_BYTES


@pytest.mark.parametrize("delta", [-2, -1, 0, 1, 2])
def test_split_text_boundary_sizes(delta):
    """Sizes straddling the limit must split exactly when they exceed it."""
    text = "a" * (LarkMessageEvent.MAX_TEXT_BYTES + delta)

    chunks = LarkMessageEvent._split_text_by_bytes(text)

    assert "".join(chunks) == text
    assert (len(chunks) == 1) is (delta <= 0)


@pytest.mark.asyncio
async def test_oversized_text_is_split_across_messages():
    """Oversized text must go out as several posts instead of one rejected blob."""
    long_text = "这是一段很长的分析结论。" * 3000
    chain = FakeMessageChain([Plain(long_text)])

    client = RecordingClient()
    await LarkMessageEvent.send_message_chain(chain, client, reply_message_id="om_4")

    assert len(client.sent) > 1
    for message in client.sent:
        assert len(message["content"].encode("utf-8")) <= 30 * 1024
    assert "".join(client.post_texts()) == long_text


@pytest.mark.asyncio
async def test_normal_text_still_sends_as_single_message():
    """Text under the limit must not be fragmented."""
    chain = FakeMessageChain([Plain("## 结果\n\n销量上升 **12%**。")])

    client = RecordingClient()
    await LarkMessageEvent.send_message_chain(chain, client, reply_message_id="om_5")

    assert len(client.sent) == 1
    assert client.post_texts() == ["## 结果\n\n销量上升 **12%**。"]
