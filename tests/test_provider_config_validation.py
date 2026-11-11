from __future__ import annotations

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import astrbot.api  # noqa: F401 - initialize the existing API import graph first
import astrbot.core.provider.manager as provider_manager_module
from astrbot.core.provider.entities import ProviderType
from astrbot.core.provider.manager import (
    ProviderConfigurationError,
    ProviderManager,
)
from astrbot.core.provider.provider import Provider


class FakeConfig(dict):
    def __init__(self):
        super().__init__(
            provider=[],
            provider_sources=[
                {
                    "id": "active-source",
                    "type": "test_chat",
                    "provider_type": "chat_completion",
                }
            ],
            provider_settings={},
        )
        self.save_config = Mock()


class LocalProvider(Provider):
    def get_current_key(self):
        return ""

    def set_key(self, key):
        pass

    async def get_models(self):
        return []

    async def text_chat(self, **kwargs):
        raise AssertionError("No network requests are expected")


@pytest.fixture
def manager(monkeypatch):
    config = FakeConfig()
    instance = ProviderManager(
        SimpleNamespace(confs={"default": config}, default_conf=config),
        None,
        SimpleNamespace(default_persona=None),
    )
    instance.dynamic_import_provider = Mock()
    instance.llm_tools = SimpleNamespace(init_mcp_clients=AsyncMock())
    monkeypatch.setitem(
        provider_manager_module.provider_cls_map,
        "test_chat",
        SimpleNamespace(
            cls_type=LocalProvider, provider_type=ProviderType.CHAT_COMPLETION
        ),
    )
    monkeypatch.setattr(
        provider_manager_module.sp, "get_async", AsyncMock(return_value=None)
    )
    return instance


@pytest.mark.parametrize("placeholder", [None, "", "  "])
@pytest.mark.asyncio
async def test_load_inherits_source_type_despite_empty_model_placeholder(
    manager, placeholder
):
    model = {
        "id": "working-model",
        "provider_source_id": "active-source",
        "type": placeholder,
        "enable": True,
    }
    original = copy.deepcopy(model)

    await manager.load_provider(model)

    assert manager.inst_map["working-model"].provider_config["type"] == "test_chat"
    manager.dynamic_import_provider.assert_called_once_with("test_chat")
    assert model == original


@pytest.mark.asyncio
async def test_startup_skips_orphan_model_and_keeps_loading(manager, monkeypatch):
    manager.providers_config[:] = [
        {"id": "orphan", "provider_source_id": "deleted-source", "enable": True},
        {"id": "healthy", "provider_source_id": "active-source", "enable": True},
    ]
    log_warning = Mock()
    log_error = Mock()
    monkeypatch.setattr(provider_manager_module.logger, "warning", log_warning)
    monkeypatch.setattr(provider_manager_module.logger, "error", log_error)

    await manager.initialize()
    await manager._mcp_init_task

    assert set(manager.inst_map) == {"healthy"}
    assert manager.curr_provider_inst is manager.inst_map["healthy"]
    log_error.assert_not_called()
    assert "deleted-source" in str(log_warning.call_args.args[1])


@pytest.mark.asyncio
async def test_create_invalid_model_does_not_persist(manager):
    with pytest.raises(ProviderConfigurationError, match="missing-source"):
        await manager.create_provider(
            {"id": "new", "provider_source_id": "missing-source", "enable": True}
        )

    assert manager.acm.default_conf["provider"] == []
    manager.acm.default_conf.save_config.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_update_preserves_saved_config_and_running_instance(manager):
    original = {"id": "healthy", "provider_source_id": "active-source", "enable": True}
    manager.providers_config.append(original)
    manager.reload = AsyncMock()

    with pytest.raises(ProviderConfigurationError, match="type"):
        await manager.update_provider("healthy", {"id": "healthy", "enable": True})

    assert manager.acm.default_conf["provider"] == [original]
    manager.acm.default_conf.save_config.assert_not_called()
    manager.reload.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_reload_does_not_terminate_existing_model(manager):
    manager.terminate_provider = AsyncMock()
    with pytest.raises(ProviderConfigurationError, match="type"):
        await manager.reload({"id": "healthy", "enable": True})
    manager.terminate_provider.assert_not_called()


@pytest.mark.asyncio
async def test_disabled_orphan_can_still_be_loaded_without_an_error(manager):
    await manager.load_provider(
        {"id": "orphan", "provider_source_id": "deleted-source", "enable": False}
    )
    assert manager.inst_map == {}
    manager.dynamic_import_provider.assert_not_called()


@pytest.mark.asyncio
async def test_agent_runner_does_not_require_model_adapter_type(manager):
    await manager.load_provider(
        {"id": "runner", "provider_type": "agent_runner", "enable": True}
    )
    assert manager.inst_map == {}
    manager.dynamic_import_provider.assert_not_called()


def test_explicit_adapter_type_remains_authoritative(manager):
    merged = manager._validated_provider_config(
        {"id": "override", "provider_source_id": "active-source", "type": "custom_chat"}
    )
    assert merged["type"] == "custom_chat"


def test_missing_type_error_does_not_disclose_credentials(manager):
    with pytest.raises(ProviderConfigurationError, match="type") as exc:
        manager._validated_provider_config(
            {"id": "incomplete", "enable": True, "key": ["secret-value"]}
        )
    assert "secret-value" not in str(exc.value)
