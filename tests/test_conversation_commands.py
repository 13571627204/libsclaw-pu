from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.builtin_stars.builtin_commands.commands import (
    conversation as conversation_module,
)
from astrbot.core.star.filter.regex import RegexFilter
from astrbot.core.star.star_handler import star_handlers_registry


def make_command_event() -> SimpleNamespace:
    return SimpleNamespace(
        unified_msg_origin="platform:private:user",
        get_platform_id=lambda: "platform",
        set_extra=MagicMock(),
        set_result=MagicMock(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stopped_count", "expected_message"),
    [
        (2, "✅ 已请求停止 2 个运行中的任务。"),
        (0, "✅ 当前会话没有正在运行的任务。"),
    ],
)
async def test_stop_command_replies_in_chinese(
    monkeypatch: pytest.MonkeyPatch,
    stopped_count: int,
    expected_message: str,
):
    event = make_command_event()
    context = SimpleNamespace(
        get_config=lambda **kwargs: {
            "provider_settings": {"agent_runner_type": "internal"}
        }
    )
    request_stop = MagicMock(return_value=stopped_count)
    monkeypatch.setattr(
        conversation_module.active_event_registry,
        "request_agent_stop_all",
        request_stop,
    )

    await conversation_module.ConversationCommands(context).stop(event)

    request_stop.assert_called_once_with(
        event.unified_msg_origin,
        exclude=event,
    )
    result = event.set_result.call_args.args[0]
    assert result.chain[0].text == expected_message


@pytest.mark.asyncio
async def test_new_command_replies_in_chinese(monkeypatch: pytest.MonkeyPatch):
    event = make_command_event()
    conversation_manager = SimpleNamespace(
        get_curr_conversation_id=AsyncMock(return_value=None),
        new_conversation=AsyncMock(return_value="12e5abcd"),
    )
    context = SimpleNamespace(
        conversation_manager=conversation_manager,
        get_config=lambda **kwargs: {
            "provider_settings": {"agent_runner_type": "internal"}
        },
    )
    monkeypatch.setattr(
        conversation_module.active_event_registry,
        "stop_all",
        MagicMock(return_value=0),
    )

    await conversation_module.ConversationCommands(context).new_conv(event)

    result = event.set_result.call_args.args[0]
    assert result.chain[0].text == "✅ 已切换到新对话：12e5。"


@pytest.mark.asyncio
async def test_new_command_replies_in_chinese_for_third_party_runner(
    monkeypatch: pytest.MonkeyPatch,
):
    event = make_command_event()
    context = SimpleNamespace(
        get_config=lambda **kwargs: {"provider_settings": {"agent_runner_type": "dify"}}
    )
    monkeypatch.setattr(
        conversation_module.active_event_registry,
        "stop_all",
        MagicMock(return_value=0),
    )
    cleanup_state = AsyncMock()
    monkeypatch.setattr(
        conversation_module,
        "_clear_third_party_agent_runner_state",
        cleanup_state,
    )

    await conversation_module.ConversationCommands(context).new_conv(event)

    cleanup_state.assert_awaited_once_with(
        context,
        event.unified_msg_origin,
        "dify",
    )
    result = event.set_result.call_args.args[0]
    assert result.chain[0].text == "✅ 已创建新对话。"


@pytest.mark.asyncio
async def test_chinese_stop_command_matches_only_standalone_message():
    from astrbot.builtin_stars.builtin_commands.main import Main

    handler = star_handlers_registry.get_handler_by_full_name(
        f"{Main.stop_cn.__module__}_{Main.stop_cn.__name__}"
    )

    assert handler is not None
    regex_filter = next(
        filter_ for filter_ in handler.event_filters if isinstance(filter_, RegexFilter)
    )
    assert regex_filter.filter(
        SimpleNamespace(get_message_str=lambda: "停止"),
        {},
    )
    assert not regex_filter.filter(
        SimpleNamespace(get_message_str=lambda: "请停止"),
        {},
    )
    assert not regex_filter.filter(
        SimpleNamespace(get_message_str=lambda: "停止任务"),
        {},
    )
    assert not regex_filter.filter(
        SimpleNamespace(get_message_str=lambda: "停止一下"),
        {},
    )
    assert not regex_filter.filter(
        SimpleNamespace(get_message_str=lambda: "停止 任务"),
        {},
    )

    main = Main(SimpleNamespace())
    main.conversation_c.stop = AsyncMock()
    event = make_command_event()

    await main.stop_cn(event)

    main.conversation_c.stop.assert_awaited_once_with(event)


@pytest.mark.asyncio
async def test_clear_third_party_agent_runner_state_deletes_deerflow_thread_before_local_state(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[object] = []

    class FakeClient:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        async def delete_thread(self, thread_id: str, timeout: float = 20):
            calls.append(("delete", thread_id, timeout))

        async def close(self):
            calls.append(("close",))

    async def fake_get_async(*args, **kwargs):
        _ = args, kwargs
        return "thread-123"

    async def fake_remove_async(*args, **kwargs):
        calls.append(("remove", kwargs["scope"], kwargs["scope_id"], kwargs["key"]))

    context = SimpleNamespace(
        get_config=lambda **kwargs: {
            "provider_settings": {
                "deerflow_agent_runner_provider_id": "deerflow-runner"
            }
        },
        provider_manager=SimpleNamespace(
            get_provider_config_by_id=lambda provider_id, merged=False: (
                {
                    "id": provider_id,
                    "deerflow_api_base": "http://127.0.0.1:2026",
                    "deerflow_api_key": "token",
                    "deerflow_auth_header": "",
                    "proxy": "",
                }
                if merged
                else {"id": provider_id}
            ),
        ),
    )

    monkeypatch.setattr(conversation_module, "DeerFlowAPIClient", FakeClient)
    monkeypatch.setattr(conversation_module.sp, "get_async", fake_get_async)
    monkeypatch.setattr(conversation_module.sp, "remove_async", fake_remove_async)

    await conversation_module._clear_third_party_agent_runner_state(
        context,
        "umo-1",
        conversation_module.DEERFLOW_PROVIDER_TYPE,
    )

    assert ("delete", "thread-123", 20) in calls
    assert (
        "remove",
        "umo",
        "umo-1",
        conversation_module.DEERFLOW_THREAD_ID_KEY,
    ) in calls
    assert calls.index(("delete", "thread-123", 20)) < calls.index(
        ("remove", "umo", "umo-1", conversation_module.DEERFLOW_THREAD_ID_KEY)
    )


@pytest.mark.asyncio
async def test_clear_third_party_agent_runner_state_removes_local_state_when_deerflow_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[object] = []

    class FakeClient:
        def __init__(self, **kwargs):
            _ = kwargs

        async def delete_thread(self, thread_id: str, timeout: float = 20):
            _ = thread_id, timeout
            raise RuntimeError("gateway down")

        async def close(self):
            calls.append(("close",))

    async def fake_get_async(*args, **kwargs):
        _ = args, kwargs
        return "thread-456"

    async def fake_remove_async(*args, **kwargs):
        calls.append(("remove", kwargs["scope"], kwargs["scope_id"], kwargs["key"]))

    context = SimpleNamespace(
        get_config=lambda **kwargs: {
            "provider_settings": {
                "deerflow_agent_runner_provider_id": "deerflow-runner"
            }
        },
        provider_manager=SimpleNamespace(
            get_provider_config_by_id=lambda provider_id, merged=False: (
                {
                    "id": provider_id,
                    "deerflow_api_base": "http://127.0.0.1:2026",
                    "deerflow_api_key": "",
                    "deerflow_auth_header": "",
                    "proxy": "",
                }
                if merged
                else {"id": provider_id}
            ),
        ),
    )

    monkeypatch.setattr(conversation_module, "DeerFlowAPIClient", FakeClient)
    monkeypatch.setattr(conversation_module.sp, "get_async", fake_get_async)
    monkeypatch.setattr(conversation_module.sp, "remove_async", fake_remove_async)

    await conversation_module._clear_third_party_agent_runner_state(
        context,
        "umo-2",
        conversation_module.DEERFLOW_PROVIDER_TYPE,
    )

    assert (
        "remove",
        "umo",
        "umo-2",
        conversation_module.DEERFLOW_THREAD_ID_KEY,
    ) in calls


@pytest.mark.asyncio
async def test_clear_third_party_agent_runner_state_removes_local_state_when_deerflow_client_init_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[object] = []

    class FakeClient:
        def __init__(self, **kwargs):
            _ = kwargs
            raise RuntimeError("invalid deerflow config")

    async def fake_get_async(*args, **kwargs):
        _ = args, kwargs
        return "thread-789"

    async def fake_remove_async(*args, **kwargs):
        calls.append(("remove", kwargs["scope"], kwargs["scope_id"], kwargs["key"]))

    context = SimpleNamespace(
        get_config=lambda **kwargs: {
            "provider_settings": {
                "deerflow_agent_runner_provider_id": "deerflow-runner"
            }
        },
        provider_manager=SimpleNamespace(
            get_provider_config_by_id=lambda provider_id, merged=False: (
                {
                    "id": provider_id,
                    "deerflow_api_base": "http://127.0.0.1:2026",
                    "deerflow_api_key": "",
                    "deerflow_auth_header": "",
                    "proxy": "",
                }
                if merged
                else {"id": provider_id}
            ),
        ),
    )

    monkeypatch.setattr(conversation_module, "DeerFlowAPIClient", FakeClient)
    monkeypatch.setattr(conversation_module.sp, "get_async", fake_get_async)
    monkeypatch.setattr(conversation_module.sp, "remove_async", fake_remove_async)

    await conversation_module._clear_third_party_agent_runner_state(
        context,
        "umo-3",
        conversation_module.DEERFLOW_PROVIDER_TYPE,
    )

    assert (
        "remove",
        "umo",
        "umo-3",
        conversation_module.DEERFLOW_THREAD_ID_KEY,
    ) in calls
