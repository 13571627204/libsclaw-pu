import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from astrbot.core.agent.mcp_client import (
    MCPClient,
    MCPTool,
    _normalize_mcp_input_schema,
)


class TestNormalizeMcpInputSchema:
    def test_lifts_property_level_required_booleans_to_parent_required_array(self):
        schema = {
            "type": "object",
            "properties": {
                "stock_code": {"type": "string", "required": True},
                "market": {"type": "string", "required": False},
            },
        }

        normalized = _normalize_mcp_input_schema(schema)

        assert normalized["required"] == ["stock_code"]
        assert "required" not in normalized["properties"]["stock_code"]
        assert "required" not in normalized["properties"]["market"]
        assert schema["properties"]["stock_code"]["required"] is True

    def test_preserves_existing_required_arrays_while_fixing_nested_objects(self):
        schema = {
            "type": "object",
            "required": ["server"],
            "properties": {
                "server": {
                    "type": "object",
                    "required": ["transport"],
                    "properties": {
                        "transport": {"type": "string"},
                        "stock_code": {"type": "string", "required": True},
                        "market": {"type": "string", "required": False},
                    },
                }
            },
        }

        normalized = _normalize_mcp_input_schema(schema)

        assert normalized["required"] == ["server"]
        assert normalized["properties"]["server"]["required"] == [
            "transport",
            "stock_code",
        ]
        assert (
            "required"
            not in normalized["properties"]["server"]["properties"]["stock_code"]
        )
        assert (
            "required" not in normalized["properties"]["server"]["properties"]["market"]
        )

    def test_preserves_parent_required_flag_for_nested_object_properties(self):
        schema = {
            "type": "object",
            "properties": {
                "server": {
                    "type": "object",
                    "required": True,
                    "properties": {
                        "transport": {"type": "string", "required": True},
                    },
                }
            },
        }

        normalized = _normalize_mcp_input_schema(schema)

        assert normalized["required"] == ["server"]
        assert normalized["properties"]["server"]["required"] == ["transport"]
        assert (
            "required"
            not in normalized["properties"]["server"]["properties"]["transport"]
        )

    def test_ignores_non_boolean_required_values_and_non_dict_properties(self):
        schema = {
            "type": "object",
            "properties": {
                "server": "invalid-property-schema",
                "market": {"type": "string", "required": "yes"},
                "stock_code": {"type": "string", "required": True},
            },
        }

        normalized = _normalize_mcp_input_schema(schema)

        assert normalized["required"] == ["stock_code"]
        assert normalized["properties"]["server"] == "invalid-property-schema"
        assert normalized["properties"]["market"]["required"] == "yes"
        assert "required" not in normalized["properties"]["stock_code"]
        assert schema["properties"]["server"] == "invalid-property-schema"
        assert schema["properties"]["market"]["required"] == "yes"


class TestMCPClientConnectionTaskCleanup:
    @pytest.mark.asyncio
    async def test_connect_consumes_initialization_task_exception(self, monkeypatch):
        client = MCPClient()
        finally_completed = asyncio.Event()
        connection_tasks = []
        create_task = asyncio.create_task

        def capture_task(coro, *, name=None):
            task = create_task(coro, name=name)
            connection_tasks.append(task)
            return task

        async def fail_connect(_config, _name):
            try:
                raise RuntimeError("initialize failed")
            finally:
                await asyncio.sleep(0)
                finally_completed.set()

        monkeypatch.setattr(asyncio, "create_task", capture_task)
        monkeypatch.setattr(client, "_do_connect", fail_connect)

        with pytest.raises(RuntimeError, match="initialize failed"):
            await client.connect_to_server({}, "broken")

        assert finally_completed.is_set()
        assert connection_tasks[0].done()
        assert connection_tasks[0]._log_traceback is False
        assert client._connection_task is None

    @pytest.mark.asyncio
    async def test_cleanup_consumes_completed_old_task_exception(self):
        client = MCPClient()

        async def fail():
            raise RuntimeError("old connection failed")

        old_task = asyncio.create_task(fail())
        await asyncio.sleep(0)
        assert old_task.done()
        client._old_connection_tasks.append(old_task)

        await client.cleanup()

        assert old_task._log_traceback is False
        assert client._old_connection_tasks == []


class TestMCPToolSchemaNormalization:
    def test_mcp_tool_accepts_property_level_required_booleans(self):
        mcp_tool = SimpleNamespace(
            name="quote_lookup",
            description="Lookup a quote",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_code": {"type": "string", "required": True},
                    "market": {"type": "string", "required": False},
                },
            },
        )

        tool = MCPTool(mcp_tool, MagicMock(), "gf-securities")

        assert tool.parameters["required"] == ["stock_code"]
        assert "required" not in tool.parameters["properties"]["stock_code"]
        assert "required" not in tool.parameters["properties"]["market"]
