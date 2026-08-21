import base64
import json
from dataclasses import field
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import mcp
from pydantic.dataclasses import dataclass

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.tools.computer_tools.util import workspace_root_for_context
from astrbot.core.tools.registry import builtin_tool
from astrbot.core.utils.astrbot_path import (
    get_astrbot_system_tmp_path,
    get_astrbot_temp_path,
)
from astrbot.core.utils.media_utils import (
    file_uri_to_path,
    is_file_uri,
    resolve_media_ref_to_base64_data,
)


@builtin_tool
@dataclass
class ImageGenerationTool(FunctionTool[AstrAgentContext]):
    """Generate or edit an image through the configured GPT-Image-2 API."""

    name: str = "generate_image"
    execution_timeout: int = 360
    description: str = (
        "Generate an image from a prompt, or edit/fuse up to 16 reference images "
        "with GPT-Image-2. Omit image_refs for text-to-image. The returned image "
        "can be reviewed and then sent with send_message_to_user."
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Text-to-image prompt or image editing instruction.",
                },
                "image_refs": {
                    "type": "array",
                    "description": (
                        "Optional reference images for editing or fusion. Each item may "
                        "be a local path, HTTP(S) URL, file URI, or base64/data URI. "
                        "Order maps to image 1, image 2, and so on in the prompt."
                    ),
                    "items": {"type": "string"},
                    "maxItems": 16,
                },
                "size": {
                    "type": "string",
                    "description": "Output size, such as auto, 1024x1024, or 2048x1152.",
                    "default": "auto",
                },
                "quality": {
                    "type": "string",
                    "description": "Output quality.",
                    "enum": ["auto", "low", "medium", "high"],
                    "default": "auto",
                },
                "output_format": {
                    "type": "string",
                    "description": "Generated image format.",
                    "enum": ["png", "jpeg", "webp"],
                    "default": "png",
                },
                "output_compression": {
                    "type": "integer",
                    "description": "Compression from 0 to 100 for JPEG or WebP output.",
                    "minimum": 0,
                    "maximum": 100,
                },
                "background": {
                    "type": "string",
                    "description": "Background mode. Transparent is not supported.",
                    "enum": ["auto", "opaque"],
                    "default": "auto",
                },
                "moderation": {
                    "type": "string",
                    "description": "Moderation strength for text-to-image requests.",
                    "enum": ["auto", "low"],
                    "default": "auto",
                },
            },
            "required": ["prompt"],
        }
    )

    async def call(
        self,
        context: ContextWrapper[AstrAgentContext],
        **kwargs,
    ) -> ToolExecResult:
        """Call GPT-Image-2 and return its image as MCP content.

        Args:
            context: Current agent context used to resolve profile configuration.
            **kwargs: Tool arguments defined by ``parameters``.

        Returns:
            An MCP result containing usage text and generated image content, or an
            error string when validation or the upstream request fails.
        """
        prompt = str(kwargs.get("prompt", "")).strip()
        if not prompt:
            return "error: prompt is required."

        image_refs = kwargs.get("image_refs") or []
        if not isinstance(image_refs, list) or any(
            not isinstance(image_ref, str) or not image_ref.strip()
            for image_ref in image_refs
        ):
            return "error: image_refs must be an array of non-empty strings."
        if len(image_refs) > 16:
            return "error: image_refs supports at most 16 images."

        size = str(kwargs.get("size", "auto")).strip() or "auto"
        quality = str(kwargs.get("quality", "auto")).strip() or "auto"
        output_format = str(kwargs.get("output_format", "png")).strip().lower() or "png"
        background = str(kwargs.get("background", "auto")).strip() or "auto"
        moderation = str(kwargs.get("moderation", "auto")).strip() or "auto"
        output_compression = kwargs.get("output_compression")

        if quality not in {"auto", "low", "medium", "high"}:
            return "error: quality must be auto, low, medium, or high."
        if output_format not in {"png", "jpeg", "webp"}:
            return "error: output_format must be png, jpeg, or webp."
        if background not in {"auto", "opaque"}:
            return "error: background must be auto or opaque."
        if moderation not in {"auto", "low"}:
            return "error: moderation must be auto or low."
        if output_compression is not None:
            if (
                not isinstance(output_compression, int)
                or isinstance(output_compression, bool)
                or not 0 <= output_compression <= 100
            ):
                return "error: output_compression must be an integer from 0 to 100."
            if output_format == "png":
                return "error: output_compression is only supported for jpeg or webp."

        cfg = context.context.context.get_config(
            umo=context.context.event.unified_msg_origin
        )
        provider_settings = cfg.get("provider_settings", {})
        base_url = str(provider_settings.get("gpt_image_base_url", "")).strip()
        api_key = str(provider_settings.get("gpt_image_api_key", "")).strip()
        if not base_url or not api_key:
            return (
                "error: GPT-Image-2 is not configured. Set its Base URL and API Key "
                "in AI settings."
            )

        headers = {"Authorization": f"Bearer {api_key}"}
        request_url = ""
        request_kwargs = {}
        if image_refs:
            request_url = f"{base_url.rstrip('/')}/images/edits"
            files = []
            workspace_path = await workspace_root_for_context(context)
            allowed_local_roots = (
                workspace_path.resolve(strict=False),
                Path(get_astrbot_temp_path()).resolve(strict=False),
                Path(get_astrbot_system_tmp_path()).resolve(strict=False),
            )
            for index, image_ref in enumerate(image_refs, start=1):
                normalized_ref = image_ref.strip()
                scheme = urlsplit(normalized_ref).scheme.lower()
                if (
                    is_file_uri(normalized_ref)
                    or not scheme
                    or Path(normalized_ref).is_absolute()
                ):
                    local_path = Path(file_uri_to_path(normalized_ref)).expanduser()
                    if not local_path.is_absolute():
                        local_path = workspace_path / local_path
                    local_path = local_path.resolve(strict=False)
                    if not any(
                        local_path == root or local_path.is_relative_to(root)
                        for root in allowed_local_roots
                    ):
                        return (
                            f"error: image_refs[{index - 1}] is outside the allowed "
                            "workspace and temporary directories."
                        )
                    normalized_ref = str(local_path)
                try:
                    image_data = await resolve_media_ref_to_base64_data(
                        normalized_ref,
                        media_type="image",
                        strict=True,
                    )
                except Exception as exc:
                    return f"error: failed to resolve image_refs[{index - 1}]: {exc}"
                if image_data is None:
                    return f"error: failed to resolve image_refs[{index - 1}]."
                if image_data.mime_type not in {
                    "image/jpeg",
                    "image/jpg",
                    "image/png",
                    "image/webp",
                }:
                    return f"error: image_refs[{index - 1}] must be PNG, JPEG, or WebP."
                extension = (
                    image_data.format
                    or {
                        "image/jpeg": "jpg",
                        "image/jpg": "jpg",
                        "image/png": "png",
                        "image/webp": "webp",
                    }[image_data.mime_type]
                )
                files.append(
                    (
                        "image[]",
                        (
                            f"image-{index}.{extension}",
                            image_data.to_bytes(),
                            image_data.mime_type,
                        ),
                    )
                )

            form_data = {
                "model": "gpt-image-2",
                "prompt": prompt,
                "size": size,
                "quality": quality,
                "output_format": output_format,
                "background": background,
            }
            if output_compression is not None:
                form_data["output_compression"] = str(output_compression)
            request_kwargs = {"data": form_data, "files": files}
        else:
            request_url = f"{base_url.rstrip('/')}/images/generations"
            payload = {
                "model": "gpt-image-2",
                "prompt": prompt,
                "size": size,
                "quality": quality,
                "output_format": output_format,
                "background": background,
                "moderation": moderation,
                "n": 1,
            }
            if output_compression is not None:
                payload["output_compression"] = output_compression
            request_kwargs = {"json": payload}

        try:
            async with httpx.AsyncClient(timeout=360) as client:
                response = await client.post(
                    request_url,
                    headers=headers,
                    **request_kwargs,
                )
                response.raise_for_status()
                response_data = response.json()
        except httpx.HTTPStatusError as exc:
            error_message = f"HTTP {exc.response.status_code}"
            try:
                error_data = exc.response.json()
                upstream_error = error_data.get("error", error_data)
                if isinstance(upstream_error, dict):
                    error_message = (
                        str(
                            upstream_error.get("message") or upstream_error.get("code")
                        ).strip()
                        or error_message
                    )
            except (json.JSONDecodeError, ValueError, AttributeError):
                pass
            return f"error: GPT-Image-2 request failed: {error_message}"
        except httpx.TimeoutException:
            return "error: GPT-Image-2 request timed out after 360 seconds."
        except httpx.RequestError as exc:
            return f"error: GPT-Image-2 request failed: {exc}"
        except (json.JSONDecodeError, ValueError) as exc:
            return f"error: GPT-Image-2 returned invalid JSON: {exc}"

        data = response_data.get("data") if isinstance(response_data, dict) else None
        image_payload = data[0] if isinstance(data, list) and data else None
        base64_image = (
            image_payload.get("b64_json") if isinstance(image_payload, dict) else None
        )
        if not isinstance(base64_image, str) or not base64_image.strip():
            return "error: GPT-Image-2 response did not contain data[0].b64_json."
        try:
            base64.b64decode(base64_image, validate=True)
        except ValueError:
            return "error: GPT-Image-2 returned invalid base64 image data."

        usage = response_data.get("usage", {})
        total_tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
        usage_text = "Image generated with gpt-image-2."
        if total_tokens is not None:
            usage_text += f" total_tokens={total_tokens}"

        mime_type = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
        }[output_format]
        return mcp.types.CallToolResult(
            content=[
                mcp.types.TextContent(type="text", text=usage_text),
                mcp.types.ImageContent(
                    type="image",
                    data=base64_image,
                    mimeType=mime_type,
                ),
            ]
        )


__all__ = ["ImageGenerationTool"]
