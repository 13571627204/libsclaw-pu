import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from astrbot.core import astr_main_agent as _astr_main_agent  # noqa: F401
from astrbot.core.persona_mgr import PersonaManager
from astrbot.core.tools.persona_memory_tools import PersonaMemoryTool


def _tool_context(
    *,
    role: str,
    persona_id: str | None,
    manager,
    write_allowed: bool | None = None,
) -> SimpleNamespace:
    if write_allowed is None:
        write_allowed = True
    extras = {
        "selected_persona_id": persona_id,
        "persona_memory_write_allowed": write_allowed,
    }
    event = SimpleNamespace(
        role=role,
        get_extra=lambda key, default=None: extras.get(key, default),
    )
    agent_context = SimpleNamespace(
        event=event,
        context=SimpleNamespace(persona_manager=manager),
    )
    return SimpleNamespace(context=agent_context)


@pytest.mark.asyncio
async def test_persona_memory_tool_updates_active_allowed_persona():
    manager = SimpleNamespace(
        mutate_memory=AsyncMock(return_value=("User prefers concise replies.", True))
    )
    context = _tool_context(
        role="admin",
        persona_id="assistant",
        manager=manager,
    )

    result = await PersonaMemoryTool().call(
        context,
        action="add",
        content="User prefers concise replies.",
    )

    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["persona_id"] == "assistant"
    manager.mutate_memory.assert_awaited_once_with(
        persona_id="assistant",
        action="add",
        content="User prefers concise replies.",
        target="",
    )


@pytest.mark.asyncio
async def test_persona_memory_tool_allows_member_request():
    manager = SimpleNamespace(
        mutate_memory=AsyncMock(
            return_value=("User prefers being called Master.", True)
        )
    )
    context = _tool_context(
        role="member",
        persona_id="assistant",
        manager=manager,
        write_allowed=True,
    )

    result = await PersonaMemoryTool().call(
        context,
        action="add",
        content="User prefers being called Master.",
    )

    assert json.loads(result)["changed"] is True
    manager.mutate_memory.assert_awaited_once()


@pytest.mark.asyncio
async def test_persona_memory_tool_rejects_unauthorized_requests_and_secrets():
    manager = SimpleNamespace(mutate_memory=AsyncMock())
    member_context = _tool_context(
        role="member",
        persona_id="assistant",
        manager=manager,
        write_allowed=False,
    )
    admin_context = _tool_context(
        role="admin",
        persona_id="assistant",
        manager=manager,
    )

    member_result = await PersonaMemoryTool().call(
        member_context,
        action="add",
        content="User prefers concise replies.",
    )
    secret_result = await PersonaMemoryTool().call(
        admin_context,
        action="add",
        content="API key: sk-example-secret-token-123456",
    )

    assert "not allowed to update shared persona memory" in member_result
    assert "Refusing to store secrets" in secret_result
    manager.mutate_memory.assert_not_awaited()


@pytest.mark.asyncio
async def test_persona_memory_tool_database_failure_does_not_escape():
    manager = SimpleNamespace(
        mutate_memory=AsyncMock(side_effect=RuntimeError("database unavailable"))
    )
    context = _tool_context(
        role="admin",
        persona_id="assistant",
        manager=manager,
    )

    result = await PersonaMemoryTool().call(
        context,
        action="add",
        content="User prefers concise replies.",
    )

    assert "Continue the user reply" in result
    assert "database unavailable" not in result


@pytest.mark.asyncio
async def test_persona_manager_memory_mutation_adds_deduplicates_and_replaces():
    manager = PersonaManager.__new__(PersonaManager)
    manager._memory_lock = asyncio.Lock()
    persona = SimpleNamespace(memory="User prefers concise replies.")
    manager.get_persona = AsyncMock(return_value=persona)
    manager.update_persona = AsyncMock()

    unchanged, changed = await manager.mutate_memory(
        "assistant",
        "add",
        content="User prefers concise replies.",
    )
    updated, replaced = await manager.mutate_memory(
        "assistant",
        "replace",
        content="concise Chinese replies",
        target="concise replies",
    )

    assert unchanged == "User prefers concise replies."
    assert changed is False
    assert updated == "User prefers concise Chinese replies."
    assert replaced is True
    manager.update_persona.assert_awaited_once_with(
        persona_id="assistant",
        memory="User prefers concise Chinese replies.",
    )
