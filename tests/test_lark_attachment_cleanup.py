from astrbot.api.message_components import File, Reply
from astrbot.api.platform import (
    AstrBotMessage,
    MessageMember,
    MessageType,
    PlatformMetadata,
)
from astrbot.core.platform.sources.lark import lark_adapter
from astrbot.core.platform.sources.lark.lark_adapter import LarkPlatformAdapter


def test_lark_event_tracks_current_and_quoted_temp_files(tmp_path, monkeypatch):
    """Clean Lark file downloads even when the pipeline stops before preprocessing."""
    current_file = tmp_path / "current.zip"
    quoted_file = tmp_path / "quoted.md"
    outside_file = tmp_path.parent / f"{tmp_path.name}-outside.md"
    current_file.write_bytes(b"zip fixture")
    quoted_file.write_text("# Quoted", encoding="utf-8")
    outside_file.write_text("# Outside", encoding="utf-8")
    monkeypatch.setattr(
        lark_adapter,
        "get_astrbot_temp_path",
        lambda: str(tmp_path),
    )

    message = AstrBotMessage()
    message.type = MessageType.FRIEND_MESSAGE
    message.session_id = "user-1"
    message.sender = MessageMember(user_id="user-1", nickname="User")
    message.message_str = "import attachment"
    message.message = [
        File(name=current_file.name, file=str(current_file)),
        File(name=outside_file.name, file=str(outside_file)),
        Reply(
            id="reply-1",
            chain=[File(name=quoted_file.name, file=str(quoted_file))],
            message_str="quoted",
        ),
    ]

    adapter = LarkPlatformAdapter.__new__(LarkPlatformAdapter)
    adapter.lark_api = object()
    adapter.meta = lambda: PlatformMetadata(
        id="lark-test",
        name="lark",
        description="Lark test adapter",
    )

    event = adapter.create_event(message)
    event.cleanup_temporary_local_files()

    assert not current_file.exists()
    assert not quoted_file.exists()
    assert outside_file.exists()
