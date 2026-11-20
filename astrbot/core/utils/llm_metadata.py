import json
import os
from typing import Literal, TypedDict

import aiohttp

from astrbot.core import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
from astrbot.core.utils.http_ssl import build_tls_connector


class LLMModalities(TypedDict):
    input: list[Literal["text", "image", "audio", "video"]]
    output: list[Literal["text", "image", "audio", "video"]]


class LLMLimit(TypedDict):
    context: int
    output: int


class LLMMetadata(TypedDict):
    id: str
    reasoning: bool
    tool_call: bool
    knowledge: str
    release_date: str
    modalities: LLMModalities
    open_weights: bool
    limit: LLMLimit


LLM_METADATAS: dict[str, LLMMetadata] = {}

LLM_METADATA_URL = "https://models.dev/api.json"
_CACHE_FILE = "llm_metadata_cache.json"


def _cache_path() -> str:
    return os.path.join(get_astrbot_data_path(), _CACHE_FILE)


def _load_cache() -> int:
    try:
        with open(_cache_path(), encoding="utf-8") as f:
            models = json.load(f)
    except (OSError, ValueError):
        return 0
    if not isinstance(models, dict):
        return 0
    LLM_METADATAS.clear()
    LLM_METADATAS.update(models)
    return len(models)


def _save_cache(models: dict[str, LLMMetadata]) -> None:
    path = _cache_path()
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(models, f, ensure_ascii=False)
        os.replace(tmp_path, path)
    except OSError as e:
        logger.debug(f"Failed to write LLM metadata cache: {e}")


def _parse_models(data: dict) -> dict[str, LLMMetadata]:
    models: dict[str, LLMMetadata] = {}
    for info in data.values():
        if not isinstance(info, dict):
            continue
        for model in info.get("models", {}).values():
            model_id = model.get("id")
            if not model_id:
                continue
            models[model_id] = LLMMetadata(
                id=model_id,
                reasoning=model.get("reasoning", False),
                tool_call=model.get("tool_call", False),
                knowledge=model.get("knowledge", "none"),
                release_date=model.get("release_date", ""),
                modalities=model.get("modalities", {"input": [], "output": []}),
                open_weights=model.get("open_weights", False),
                limit=model.get("limit", {"context": 0, "output": 0}),
            )
    return models


async def update_llm_metadata() -> None:
    cached_count = _load_cache()
    url = os.environ.get("ASTRBOT_LLM_METADATA_URL", LLM_METADATA_URL)
    try:
        async with aiohttp.ClientSession(
            trust_env=True,
            connector=build_tls_connector(),
            timeout=aiohttp.ClientTimeout(total=30),
        ) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
    except Exception as e:
        # models.dev 仅用于补充模型上下文长度等元数据，不可达时不影响正常使用。
        if cached_count:
            logger.debug(
                f"LLM metadata source unreachable, using local cache "
                f"({cached_count} models): {e}"
            )
        else:
            logger.info(
                "LLM metadata source (models.dev) is unreachable; skipping. "
                "Model context limits will use configured/fallback values."
            )
            logger.debug(f"LLM metadata fetch error: {e}")
        return

    models = _parse_models(data)
    if not models:
        return
    # Replace the global cache in-place so references remain valid
    LLM_METADATAS.clear()
    LLM_METADATAS.update(models)
    _save_cache(models)
    logger.info(f"Successfully fetched metadata for {len(models)} LLMs.")
