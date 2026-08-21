from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import Request
from starlette.datastructures import UploadFile as StarletteUploadFile


class _MultipartBodyTooLarge(OSError):
    """Signal a streaming multipart body limit while preserving parser cleanup."""


class UploadFileAdapter:
    def __init__(self, upload_file: StarletteUploadFile) -> None:
        self._upload_file = upload_file
        self.filename = upload_file.filename
        self.content_type = upload_file.content_type
        self.headers = upload_file.headers
        self.content_length = self._resolve_content_length()

    def _resolve_content_length(self) -> int | None:
        try:
            raw = self.headers.get("content-length")
            return int(raw) if raw else None
        except (TypeError, ValueError):
            return None

    async def save(
        self,
        destination: str | Path,
        *,
        max_bytes: int | None = None,
    ) -> int:
        """Save an uploaded file with an optional byte limit.

        Args:
            destination: Target file path.
            max_bytes: Maximum bytes allowed for this save operation.

        Returns:
            Number of bytes written.

        Raises:
            ValueError: If the upload exceeds ``max_bytes``.
        """
        path = Path(destination)
        written_bytes = 0
        try:
            await self._upload_file.seek(0)
        except Exception:
            pass
        with path.open("wb") as output:
            while True:
                chunk = await self._upload_file.read(1024 * 1024)
                if not chunk:
                    break
                next_size = written_bytes + len(chunk)
                if max_bytes is not None and next_size > max_bytes:
                    raise ValueError("Uploaded files exceed the configured size limit")
                output.write(chunk)
                written_bytes = next_size
        return written_bytes


class MultiDict:
    def __init__(self, pairs: list[tuple[str, Any]]) -> None:
        self._pairs = pairs

    def get(self, key: str, default: Any = None, type: Callable | None = None):
        for item_key, item_value in reversed(self._pairs):
            if item_key != key:
                continue
            if type is None:
                return item_value
            try:
                return type(item_value)
            except (TypeError, ValueError):
                return default
        return default

    def getlist(self, key: str) -> list[Any]:
        return [item_value for item_key, item_value in self._pairs if item_key == key]

    def keys(self):
        return dict.fromkeys(item_key for item_key, _ in self._pairs).keys()

    def values(self):
        return [self[key] for key in self.keys()]

    def __contains__(self, key: str) -> bool:
        return any(item_key == key for item_key, _ in self._pairs)

    def __getitem__(self, key: str):
        value = self.get(key)
        if value is None and key not in self:
            raise KeyError(key)
        return value

    def __bool__(self) -> bool:
        return bool(self._pairs)


async def multipart_parts(
    request: Request,
    *,
    extra_form: dict[str, Any] | None = None,
    max_files: int | float | None = None,
    max_fields: int | float | None = None,
    max_body_size: int | None = None,
) -> tuple[MultiDict, MultiDict]:
    """Parse multipart fields with optional count and total-body limits.

    Args:
        request: Incoming FastAPI request.
        extra_form: Form values injected when the request omits them.
        max_files: Starlette multipart file count limit override.
        max_fields: Starlette multipart field count limit override.
        max_body_size: Maximum raw request body bytes accepted while streaming.

    Returns:
        Parsed form values and uploaded files.

    Raises:
        ValueError: If the request body exceeds ``max_body_size``.
    """
    limit_message = ""
    original_receive = None
    if max_body_size is not None:
        limit_mib = max_body_size / (1024 * 1024)
        limit_message = f"上传内容超过 {limit_mib:g} MiB 安全上限"
        try:
            content_length = int(request.headers.get("content-length", ""))
        except (TypeError, ValueError):
            content_length = None
        if content_length is not None and content_length > max_body_size:
            raise ValueError(limit_message)

        original_receive = request._receive
        received_bytes = 0

        async def limited_receive():
            """Read one ASGI message while enforcing the raw body limit.

            Returns:
                The next ASGI receive message.

            Raises:
                _MultipartBodyTooLarge: If cumulative body bytes exceed the limit.
            """
            nonlocal received_bytes
            message = await original_receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > max_body_size:
                    raise _MultipartBodyTooLarge(limit_message)
            return message

        request._receive = limited_receive

    form_options: dict[str, int | float] = {}
    if max_files is not None:
        form_options["max_files"] = max_files
    if max_fields is not None:
        form_options["max_fields"] = max_fields
    try:
        form = await request.form(**form_options)
    except _MultipartBodyTooLarge as exc:
        raise ValueError(limit_message) from exc
    finally:
        if original_receive is not None:
            request._receive = original_receive

    form_pairs: list[tuple[str, Any]] = []
    file_pairs: list[tuple[str, Any]] = []
    for key, value in form.multi_items():
        if isinstance(value, StarletteUploadFile):
            file_pairs.append((key, UploadFileAdapter(value)))
        else:
            form_pairs.append((key, value))
    form_data = MultiDict(form_pairs)
    for key, value in (extra_form or {}).items():
        if value is not None and key not in form_data:
            form_pairs.append((key, value))
    return MultiDict(form_pairs), MultiDict(file_pairs)


async def single_upload(
    request: Request,
    *,
    field_name: str = "file",
) -> UploadFileAdapter | None:
    _, files = await multipart_parts(request)
    upload = files.get(field_name)
    if isinstance(upload, UploadFileAdapter):
        return upload
    return None
