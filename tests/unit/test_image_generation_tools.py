import base64
import json
from pathlib import Path

import pytest
from mcp.types import CallToolResult, ImageContent, TextContent

from astrbot.core.config.default import (
    CONFIG_METADATA_2,
    CONFIG_METADATA_3,
    DEFAULT_CONFIG,
)
from astrbot.core.tools.image_generation_tools import ImageGenerationTool
from astrbot.core.tools.registry import get_builtin_tool_config_statuses
from astrbot.core.utils.media_utils import ResolvedMediaData


@pytest.fixture
def image_tool_context():
    """Build a tool context with configured GPT-Image-2 credentials."""

    class FakeConfig:
        def get_config(self, umo):
            return {
                "provider_settings": {
                    "gpt_image_base_url": "https://api.apiyi.com/v1/",
                    "gpt_image_api_key": "test-key",
                }
            }

    class FakeEvent:
        unified_msg_origin = "webchat:FriendMessage:test"

    class FakeAstrContext:
        context = FakeConfig()
        event = FakeEvent()

    class FakeWrapper:
        context = FakeAstrContext()

    return FakeWrapper()


def test_image_generation_tool_requires_base_url_and_key():
    config_entries = [
        {
            "conf_id": "base-only",
            "conf_name": "base-only",
            "config": {
                "provider_settings": {
                    "gpt_image_base_url": "https://api.apiyi.com/v1",
                    "gpt_image_api_key": "",
                }
            },
        },
        {
            "conf_id": "key-only",
            "conf_name": "key-only",
            "config": {
                "provider_settings": {
                    "gpt_image_base_url": "",
                    "gpt_image_api_key": "test-key",
                }
            },
        },
        {
            "conf_id": "configured",
            "conf_name": "configured",
            "config": {
                "provider_settings": {
                    "gpt_image_base_url": "https://api.apiyi.com/v1",
                    "gpt_image_api_key": "test-key",
                }
            },
        },
    ]

    statuses = get_builtin_tool_config_statuses("generate_image", config_entries)

    assert [status["enabled"] for status in statuses] == [False, False, True]


def test_image_generation_config_is_exposed_in_model_settings():
    provider_settings = DEFAULT_CONFIG["provider_settings"]
    schema_items = CONFIG_METADATA_2["provider_group"]["metadata"]["provider_settings"][
        "items"
    ]
    model_items = CONFIG_METADATA_3["ai_group"]["metadata"]["ai"]["items"]

    assert provider_settings["gpt_image_base_url"] == "https://api.apiyi.com/v1"
    assert provider_settings["gpt_image_api_key"] == ""
    assert schema_items["gpt_image_base_url"]["type"] == "string"
    assert schema_items["gpt_image_api_key"]["type"] == "string"
    assert (
        model_items["provider_settings.gpt_image_base_url"].get("invisible") is not True
    )
    assert (
        model_items["provider_settings.gpt_image_api_key"].get("invisible") is not True
    )


@pytest.mark.parametrize("locale", ["zh-CN", "en-US", "ru-RU"])
def test_image_generation_config_has_translations(locale):
    locale_path = (
        Path(__file__).parents[2]
        / "dashboard/src/i18n/locales"
        / locale
        / "features/config-metadata.json"
    )

    with locale_path.open(encoding="utf-8") as locale_file:
        provider_settings = json.load(locale_file)["ai_group"]["ai"][
            "provider_settings"
        ]

    assert provider_settings["gpt_image_base_url"]["description"]
    assert provider_settings["gpt_image_base_url"]["hint"]
    assert provider_settings["gpt_image_api_key"]["description"]
    assert provider_settings["gpt_image_api_key"]["hint"]


@pytest.mark.asyncio
async def test_text_to_image_posts_json_and_returns_image(
    monkeypatch, image_tool_context
):
    from astrbot.core.tools import image_generation_tools

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [{"b64_json": base64.b64encode(b"png-data").decode()}],
                "usage": {"input_tokens": 12, "output_tokens": 34, "total_tokens": 46},
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["request"] = kwargs
            return FakeResponse()

    monkeypatch.setattr(image_generation_tools.httpx, "AsyncClient", FakeAsyncClient)

    result = await ImageGenerationTool().call(
        image_tool_context,
        prompt="A lighthouse at sunset",
        size="2048x1152",
        quality="high",
        output_format="png",
        moderation="low",
    )

    assert isinstance(result, CallToolResult)
    assert captured["client"]["timeout"] == 360
    assert captured["url"] == "https://api.apiyi.com/v1/images/generations"
    assert captured["request"]["headers"]["Authorization"] == "Bearer test-key"
    assert captured["request"]["json"] == {
        "model": "gpt-image-2",
        "prompt": "A lighthouse at sunset",
        "size": "2048x1152",
        "quality": "high",
        "output_format": "png",
        "background": "auto",
        "moderation": "low",
        "n": 1,
    }
    assert isinstance(result.content[0], TextContent)
    assert "total_tokens=46" in result.content[0].text
    assert isinstance(result.content[1], ImageContent)
    assert result.content[1].data == base64.b64encode(b"png-data").decode()
    assert result.content[1].mimeType == "image/png"


@pytest.mark.asyncio
async def test_image_to_image_posts_multipart_and_returns_selected_format(
    monkeypatch, image_tool_context
):
    from astrbot.core.tools import image_generation_tools

    captured = {}

    async def fake_resolve_image(image_ref, *, media_type, strict):
        assert media_type == "image"
        assert strict is True
        image_name = Path(image_ref).name
        return ResolvedMediaData(
            base64_data=base64.b64encode(image_name.encode()).decode(),
            mime_type="image/png",
            format="png",
        )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [{"b64_json": base64.b64encode(b"jpeg-data").decode()}],
                "usage": {"total_tokens": 99},
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["request"] = kwargs
            return FakeResponse()

    monkeypatch.setattr(
        image_generation_tools,
        "resolve_media_ref_to_base64_data",
        fake_resolve_image,
    )
    monkeypatch.setattr(image_generation_tools.httpx, "AsyncClient", FakeAsyncClient)

    result = await ImageGenerationTool().call(
        image_tool_context,
        prompt="Merge figure 1 into scene 2",
        image_refs=["figure.png", "scene.png"],
        output_format="jpeg",
        output_compression=85,
    )

    assert isinstance(result, CallToolResult)
    assert captured["url"] == "https://api.apiyi.com/v1/images/edits"
    assert captured["request"]["data"] == {
        "model": "gpt-image-2",
        "prompt": "Merge figure 1 into scene 2",
        "size": "auto",
        "quality": "auto",
        "output_format": "jpeg",
        "output_compression": "85",
        "background": "auto",
    }
    assert [item[0] for item in captured["request"]["files"]] == [
        "image[]",
        "image[]",
    ]
    assert captured["request"]["files"][0][1] == (
        "image-1.png",
        b"figure.png",
        "image/png",
    )
    assert captured["request"]["files"][1][1] == (
        "image-2.png",
        b"scene.png",
        "image/png",
    )
    assert isinstance(result.content[1], ImageContent)
    assert result.content[1].mimeType == "image/jpeg"


@pytest.mark.asyncio
async def test_image_generation_rejects_local_files_outside_allowed_roots(
    image_tool_context,
):
    result = await ImageGenerationTool().call(
        image_tool_context,
        prompt="Edit this file",
        image_refs=["/etc/passwd"],
    )

    assert result == (
        "error: image_refs[0] is outside the allowed workspace and temporary "
        "directories."
    )


@pytest.mark.asyncio
async def test_image_generation_rejects_more_than_sixteen_references(
    image_tool_context,
):
    result = await ImageGenerationTool().call(
        image_tool_context,
        prompt="Combine the references",
        image_refs=[f"image-{index}.png" for index in range(17)],
    )

    assert result == "error: image_refs supports at most 16 images."
