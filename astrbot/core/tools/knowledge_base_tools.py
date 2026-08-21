import asyncio
import hashlib
import posixpath
import re
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.dataclasses import dataclass

from astrbot.api import logger, sp
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.knowledge_base.kb_helper import KBHelper
from astrbot.core.knowledge_base.models import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    KBDocument,
)
from astrbot.core.message.components import File, Reply
from astrbot.core.message.message_event_result import MessageEventResult
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.star.context import Context
from astrbot.core.tools.registry import builtin_tool

_KNOWLEDGE_BASE_TOOL_CONFIG = {
    "kb_agentic_mode": True,
}


class _KnowledgeEntityInput(BaseModel):
    """Validated entity extracted from one knowledge source."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=120)
    entity_type: str = Field(default="other", max_length=80)
    summary: str = Field(default="", max_length=600)


class _KnowledgeConceptInput(BaseModel):
    """Validated concept extracted from one knowledge source."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(default="", max_length=600)


class _KnowledgeRelationInput(BaseModel):
    """Validated directed relationship between extracted knowledge nodes."""

    model_config = ConfigDict(extra="ignore")

    source: str = Field(min_length=1, max_length=120)
    target: str = Field(min_length=1, max_length=120)
    relation: str = Field(min_length=1, max_length=80)
    evidence: str = Field(default="", max_length=600)


class _KnowledgeAnalysisInput(BaseModel):
    """Validated structured analysis supplied with an ingested source."""

    model_config = ConfigDict(extra="ignore")

    summary: str = Field(default="", max_length=1200)
    category: str = Field(default="", max_length=120)
    entities: list[_KnowledgeEntityInput] = Field(
        default_factory=list,
        max_length=40,
    )
    concepts: list[_KnowledgeConceptInput] = Field(
        default_factory=list,
        max_length=30,
    )
    relations: list[_KnowledgeRelationInput] = Field(
        default_factory=list,
        max_length=80,
    )


def _knowledge_page_slug(value: str) -> str:
    """Return a stable, readable, Wiki-safe slug for a knowledge node.

    Args:
        value: Entity, concept, or category display name.

    Returns:
        A lowercase path segment that preserves readable CJK characters.
    """
    normalized = re.sub(r"\s+", "-", value.strip().casefold())
    normalized = re.sub(r'[\x00-\x1f/\\:*?"<>|#%]+', "-", normalized)
    normalized = normalized.strip(" .-_")
    if normalized:
        return normalized[:100]
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"node-{digest}"


def _knowledge_relation_name(value: str) -> str:
    """Normalize a relationship label for graph persistence.

    Args:
        value: Human- or model-generated relationship label.

    Returns:
        A compact relationship identifier.
    """
    normalized = re.sub(r"[\s/\\:：]+", "_", value.strip().casefold())
    normalized = re.sub(r"[^\w\-\u3400-\u9fff]", "", normalized)
    return normalized[:80] or "related_to"


def _relative_wiki_target(source_path: str, target_path: str) -> str:
    """Return a page-relative target that resolves before the target exists.

    Args:
        source_path: Page path containing the Wiki link.
        target_path: Target page path relative to the Wiki root.

    Returns:
        POSIX relative path from the source page directory to the target page.
    """
    source_parent = PurePosixPath(source_path).parent.as_posix()
    return posixpath.relpath(target_path, start=source_parent)


async def _resolve_target_knowledge_base(
    event: AstrMessageEvent,
    plugin_context: Context,
    selector: str,
) -> tuple[KBHelper | None, str | None]:
    """Resolve one writable knowledge base for an agent tool call.

    Args:
        event: Current platform message event.
        plugin_context: Runtime context containing the knowledge base manager.
        selector: Optional knowledge base name or stable identifier.

    Returns:
        A tuple containing the resolved helper and an optional user-facing error.
    """
    kb_manager = plugin_context.kb_manager
    selected_helper = None
    if selector:
        selected_helper = await kb_manager.get_kb(selector)
        if selected_helper is None:
            selected_helper = await kb_manager.get_kb_by_name(selector)
        if selected_helper is None:
            return None, f"error: Knowledge base {selector!r} does not exist."
        if getattr(event, "role", None) == "admin":
            return selected_helper, None

    configured_helpers = []
    session_config = await sp.session_get(
        event.unified_msg_origin,
        "kb_config",
        default={},
    )
    has_explicit_session_selection = bool(session_config and "kb_ids" in session_config)
    if has_explicit_session_selection:
        for kb_id in session_config.get("kb_ids", []):
            helper = await kb_manager.get_kb(kb_id)
            if helper is not None:
                configured_helpers.append(helper)
    else:
        config = plugin_context.get_config(umo=event.unified_msg_origin)
        for kb_name in config.get("kb_names", []):
            helper = await kb_manager.get_kb_by_name(kb_name)
            if helper is not None:
                configured_helpers.append(helper)

    unique_helpers = {helper.kb.kb_id: helper for helper in configured_helpers}
    if not unique_helpers and not has_explicit_session_selection:
        all_kbs = await kb_manager.list_kbs()
        if len(all_kbs) == 1:
            only_kb = all_kbs[0]
            helper = await kb_manager.get_kb(only_kb.kb_id)
            if helper is not None:
                unique_helpers[only_kb.kb_id] = helper
    if selected_helper is not None:
        if selected_helper.kb.kb_id not in unique_helpers:
            return None, (
                f"error: Knowledge base {selected_helper.kb.kb_name!r} is not "
                "selected for the current session."
            )
        return selected_helper, None
    if len(unique_helpers) != 1:
        names = ", ".join(helper.kb.kb_name for helper in unique_helpers.values())
        suffix = f" Current candidates: {names}." if names else ""
        return None, (
            "error: Specify the target knowledge base because the current "
            f"session does not resolve to exactly one.{suffix}"
        )
    return next(iter(unique_helpers.values())), None


async def _write_structured_knowledge_pages(
    kb_helper: KBHelper,
    plugin_context: Context,
    document: KBDocument,
    title: str,
    source_label: str,
    nodes: list[dict[str, str]],
    relations: list[_KnowledgeRelationInput],
) -> dict[str, int]:
    """Create or enrich entity and concept pages for one ingested source.

    Existing pages are preserved and receive only missing relationship lines.
    Every changed page is snapshotted so a later failure can restore the Wiki to
    its state before enrichment.

    Args:
        kb_helper: Active knowledge base helper.
        plugin_context: Runtime context used to refresh knowledge base statistics.
        document: Newly persisted source document.
        title: Source article title.
        source_label: Source URL or provenance label.
        nodes: Deduplicated entity and concept page specifications.
        relations: Directed relationships extracted from the source.

    Returns:
        Counts of changed node pages and persisted relationship lines.

    Raises:
        Exception: If a page write or statistics refresh fails after rollback.
    """
    if not nodes:
        return {"nodes": 0, "relations": 0}

    wiki_store = await kb_helper._ensure_vec_db()
    source_path = document.file_path
    aliases: dict[str, tuple[str, str]] = {
        "source": (source_path, title),
        "article": (source_path, title),
        "文章": (source_path, title),
        title.casefold(): (source_path, title),
    }
    for node in nodes:
        aliases[node["name"].casefold()] = (node["path"], node["name"])

    outgoing_lines: dict[str, list[str]] = {node["path"]: [] for node in nodes}
    for node in nodes:
        source_target = _relative_wiki_target(node["path"], source_path)
        outgoing_lines[node["path"]].append(
            f"- sourced_from: [[{source_target}|{title}]]"
        )

    for relation in relations:
        resolved_source = aliases.get(relation.source.strip().casefold())
        resolved_target = aliases.get(relation.target.strip().casefold())
        if (
            resolved_source is None
            or resolved_target is None
            or resolved_source[0] == resolved_target[0]
            or resolved_source[0] == source_path
        ):
            continue
        relation_name = _knowledge_relation_name(relation.relation)
        evidence = " ".join(relation.evidence.split()).strip()[:300]
        evidence_suffix = f" — {evidence}" if evidence else ""
        relative_target = _relative_wiki_target(
            resolved_source[0],
            resolved_target[0],
        )
        outgoing_lines.setdefault(resolved_source[0], []).append(
            f"- {relation_name}: "
            f"[[{relative_target}|{resolved_target[1]}]]{evidence_suffix}"
        )

    previous_content: dict[str, str | None] = {}
    changed_paths: list[str] = []
    relationship_count = 0
    try:
        for node in nodes:
            path = node["path"]
            metadata = await wiki_store.get_page_metadata(path)
            if metadata is not None:
                page = await wiki_store.read_page(path)
                original_content = str(page.get("content") or "")
            else:
                original_content = None
            previous_content[path] = original_content

            unique_lines = []
            for line in outgoing_lines.get(path, []):
                if line not in unique_lines and (
                    original_content is None or line not in original_content
                ):
                    unique_lines.append(line)
            relationship_count += len(unique_lines)

            if original_content is None:
                summary = " ".join(node["summary"].split()).strip()
                safe_summary = summary[:600] or (
                    f"Knowledge {node['node_type']} extracted from {title}."
                )
                safe_source = " ".join(source_label.split()).strip() or title
                type_detail = (
                    f"\n\nEntity type: {node['entity_type']}"
                    if node["node_type"] == "entity" and node["entity_type"]
                    else ""
                )
                relation_block = "\n".join(unique_lines)
                updated_content = (
                    "---\n"
                    f"type: {node['node_type']}\n"
                    f"summary: {safe_summary}\n"
                    f"source: {safe_source}\n"
                    "---\n\n"
                    f"# {node['name']}\n\n"
                    f"{safe_summary}{type_detail}\n\n"
                    "## Knowledge Relations\n\n"
                    f"{relation_block}\n"
                )
            elif unique_lines:
                separator = (
                    "\n"
                    if "## Knowledge Relations" in original_content
                    else "\n\n## Knowledge Relations\n\n"
                )
                updated_content = (
                    original_content.rstrip()
                    + separator
                    + "\n".join(unique_lines)
                    + "\n"
                )
            else:
                continue

            await wiki_store.write_page(path, updated_content)
            changed_paths.append(path)

        kb_manager = plugin_context.kb_manager
        await kb_manager.kb_db.update_kb_stats(
            kb_id=kb_helper.kb.kb_id,
            vec_db=wiki_store,
        )
        await kb_helper.refresh_kb()
    except Exception:
        for path in reversed(changed_paths):
            original_content = previous_content[path]
            try:
                if original_content is None:
                    await wiki_store.delete_page(path)
                else:
                    await wiki_store.write_page(path, original_content)
            except Exception as restore_exc:  # noqa: BLE001
                logger.error(
                    "Failed to restore structured knowledge page %s: %s",
                    path,
                    restore_exc,
                    exc_info=True,
                )
        raise

    return {
        "nodes": len(changed_paths),
        "relations": relationship_count,
    }


async def retrieve_knowledge_base(
    query: str,
    umo: str,
    context: Context,
) -> str | None:
    """Retrieve knowledge base context for the given query."""
    kb_mgr = context.kb_manager
    config = context.get_config(umo=umo)

    session_config = await sp.session_get(umo, "kb_config", default={})
    kb_ids: list[str] = []
    kb_names: list[str] = []
    if session_config and "kb_ids" in session_config:
        kb_ids = session_config.get("kb_ids", [])
        if not kb_ids:
            logger.info(f"[知识库] 会话 {umo} 已被配置为不使用知识库")
            return None

        top_k = session_config.get("top_k", 5)
        invalid_kb_ids = []
        for kb_id in kb_ids:
            kb_helper = await kb_mgr.get_kb(kb_id)
            if kb_helper:
                kb_names.append(kb_helper.kb.kb_name)
            else:
                logger.warning(f"[知识库] 知识库不存在或未加载: {kb_id}")
                invalid_kb_ids.append(kb_id)

        if invalid_kb_ids:
            logger.warning(
                f"[知识库] 会话 {umo} 配置的以下知识库无效: {invalid_kb_ids}",
            )
        if not kb_names:
            return None
        logger.debug(f"[知识库] 使用会话级配置，知识库数量: {len(kb_names)}")
    else:
        kb_names = config.get("kb_names", [])
        top_k = config.get("kb_final_top_k", 5)
        logger.debug(f"[知识库] 使用全局配置，知识库数量: {len(kb_names)}")

    top_k_fusion = config.get("kb_fusion_top_k", 20)
    if not kb_names:
        return None

    logger.debug(f"[知识库] 开始检索知识库，数量: {len(kb_names)}, top_k={top_k}")
    kb_context = await kb_mgr.retrieve(
        query=query,
        kb_names=kb_names,
        kb_ids=kb_ids,
        top_k_fusion=top_k_fusion,
        top_m_final=top_k,
    )
    if not kb_context:
        return None

    formatted = kb_context.get("context_text", "")
    if formatted:
        results = kb_context.get("results", [])
        logger.debug(f"[知识库] 为会话 {umo} 注入了 {len(results)} 条相关知识块")
        return formatted
    return None


@builtin_tool(config=_KNOWLEDGE_BASE_TOOL_CONFIG)
@dataclass
class KnowledgeBaseQueryTool(FunctionTool[AstrAgentContext]):
    name: str = "astr_kb_search"
    description: str = "查询知识库相关内容。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A concise keyword query for the knowledge base.",
                },
            },
            "required": ["query"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        query = kwargs.get("query", "")
        if not query:
            return "error: Query parameter is empty."
        result = await retrieve_knowledge_base(
            query=query,
            umo=context.context.event.unified_msg_origin,
            context=context.context.context,
        )
        if not result:
            return "No relevant knowledge found."
        return result


@builtin_tool(config=_KNOWLEDGE_BASE_TOOL_CONFIG)
@dataclass
class KnowledgeBaseListPagesTool(FunctionTool[AstrAgentContext]):
    name: str = "astr_kb_list_pages"
    description: str = "列出知识库中的 Markdown Wiki 页面。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Optional case-insensitive filter matched against page "
                        "path, title, summary, and source."
                    ),
                },
                "knowledge_base": {
                    "type": "string",
                    "description": (
                        "Target knowledge base name or stable ID. Omit only when "
                        "the current session resolves to exactly one knowledge base."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum pages to return, from 1 to 200.",
                    "default": 50,
                },
            },
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        """List manageable Wiki pages for the current conversation.

        Args:
            context: Current agent execution context.
            **kwargs: Tool arguments containing the target and optional filter.

        Returns:
            A compact newline-delimited page list or a user-facing error.
        """
        event = context.context.event
        plugin_context = context.context.context
        selector = str(kwargs.get("knowledge_base") or "").strip()
        kb_helper, error = await _resolve_target_knowledge_base(
            event,
            plugin_context,
            selector,
        )
        if error:
            return error
        if kb_helper is None:
            return "error: Knowledge base could not be resolved."

        try:
            wiki_store = await kb_helper._ensure_vec_db()
            tree_result = await wiki_store.list_tree()
        except Exception as exc:
            logger.error(
                "Failed to list Wiki pages for knowledge base %s: %s",
                kb_helper.kb.kb_id,
                exc,
                exc_info=True,
            )
            return f"error: Knowledge page listing failed: {str(exc).strip() or 'Unknown error'}"

        pages = []
        stack = list(reversed(tree_result.get("tree", {}).get("children", [])))
        while stack:
            entry = stack.pop()
            if entry.get("type") == "directory":
                stack.extend(reversed(entry.get("children", [])))
            elif entry.get("type") == "page":
                pages.append(entry)

        query = str(kwargs.get("query") or "").strip().casefold()
        if query:
            pages = [
                page
                for page in pages
                if query
                in " ".join(
                    str(page.get(field) or "")
                    for field in ("path", "title", "summary", "source")
                ).casefold()
            ]
        try:
            limit = max(1, min(int(kwargs.get("limit", 50)), 200))
        except (TypeError, ValueError):
            limit = 50
        selected_pages = pages[:limit]
        if not selected_pages:
            return f"No matching Wiki pages found in {kb_helper.kb.kb_name}."

        lines = []
        for page in selected_pages:
            summary = " ".join(str(page.get("summary") or "").split())
            summary_text = f" | {summary[:160]}" if summary else ""
            lines.append(
                f"- {page.get('path')} | {page.get('title') or page.get('name')}"
                f" | type={page.get('node_type') or 'other'}{summary_text}"
            )
        remaining = len(pages) - len(selected_pages)
        suffix = f"\n... {remaining} more matching pages." if remaining > 0 else ""
        return (
            f"Wiki pages in {kb_helper.kb.kb_name} ({len(pages)} matched):\n"
            + "\n".join(lines)
            + suffix
        )


@builtin_tool(config=_KNOWLEDGE_BASE_TOOL_CONFIG)
@dataclass
class KnowledgeBaseReadPageTool(FunctionTool[AstrAgentContext]):
    name: str = "astr_kb_read_page"
    description: str = "读取指定知识库页面完整内容。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Exact Wiki-relative Markdown path.",
                },
                "knowledge_base": {
                    "type": "string",
                    "description": (
                        "Target knowledge base name or stable ID. Omit only when "
                        "the current session resolves to exactly one knowledge base."
                    ),
                },
            },
            "required": ["path"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        """Read one Wiki page for a management operation.

        Args:
            context: Current agent execution context.
            **kwargs: Tool arguments containing the target page path.

        Returns:
            Complete Markdown content plus metadata or a user-facing error.
        """
        event = context.context.event
        plugin_context = context.context.context
        path = str(kwargs.get("path") or "").strip()
        if not path:
            return "error: Wiki page path is empty."
        selector = str(kwargs.get("knowledge_base") or "").strip()
        kb_helper, error = await _resolve_target_knowledge_base(
            event,
            plugin_context,
            selector,
        )
        if error:
            return error
        if kb_helper is None:
            return "error: Knowledge base could not be resolved."

        try:
            wiki_store = await kb_helper._ensure_vec_db()
            page = await wiki_store.read_page(path)
        except FileNotFoundError:
            return f"error: Wiki page {path!r} does not exist."
        except Exception as exc:
            logger.error(
                "Failed to read Wiki page %s from knowledge base %s: %s",
                path,
                kb_helper.kb.kb_id,
                exc,
                exc_info=True,
            )
            return f"error: Knowledge page read failed: {str(exc).strip() or 'Unknown error'}"

        metadata = page.get("metadata", {})
        return (
            f"Knowledge base: {kb_helper.kb.kb_name} ({kb_helper.kb.kb_id})\n"
            f"Path: {page.get('path', path)}\n"
            f"Title: {metadata.get('title') or ''}\n"
            f"Source: {metadata.get('source') or ''}\n"
            "Markdown content:\n"
            f"{page.get('content', '')}"
        )


@builtin_tool(config=_KNOWLEDGE_BASE_TOOL_CONFIG)
@dataclass
class KnowledgeBaseEditPageTool(FunctionTool[AstrAgentContext]):
    name: str = "astr_kb_edit_page"
    description: str = "编辑已有知识库页面，并更新索引。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Exact Wiki-relative Markdown path.",
                },
                "old_text": {
                    "type": "string",
                    "description": (
                        "Exact unique text to replace. Read the page first and "
                        "include enough surrounding text to make it unique."
                    ),
                },
                "replacement": {
                    "type": "string",
                    "description": (
                        "Replacement text. May be empty to remove old_text."
                    ),
                },
                "full_content": {
                    "type": "string",
                    "description": (
                        "Complete replacement Markdown. Do not combine with "
                        "old_text/replacement."
                    ),
                },
                "knowledge_base": {
                    "type": "string",
                    "description": (
                        "Target knowledge base name or stable ID. Omit only when "
                        "the current session resolves to exactly one knowledge base."
                    ),
                },
            },
            "required": ["path"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        """Edit one Wiki page and synchronize all derived metadata.

        Args:
            context: Current agent execution context.
            **kwargs: Tool arguments selecting partial or complete replacement.

        Returns:
            Updated page metadata or a user-facing error.
        """
        event = context.context.event
        plugin_context = context.context.context
        path = str(kwargs.get("path") or "").strip()
        if not path:
            return "error: Wiki page path is empty."
        full_content_value = kwargs.get("full_content")
        old_text_value = kwargs.get("old_text")
        has_full_content = full_content_value is not None
        has_partial_edit = old_text_value is not None or "replacement" in kwargs
        if has_full_content and has_partial_edit:
            return "error: Use either full_content or old_text/replacement, not both."
        if not has_full_content and not has_partial_edit:
            return "error: Provide full_content or an old_text/replacement edit."
        if has_partial_edit and (old_text_value is None or "replacement" not in kwargs):
            return (
                "error: Both old_text and replacement are required for a partial edit."
            )

        selector = str(kwargs.get("knowledge_base") or "").strip()
        kb_helper, error = await _resolve_target_knowledge_base(
            event,
            plugin_context,
            selector,
        )
        if error:
            return error
        if kb_helper is None:
            return "error: Knowledge base could not be resolved."

        try:
            wiki_store = await kb_helper._ensure_vec_db()
            existing_page = await wiki_store.read_page(path)
            existing_content = existing_page.get("content", "")
            if has_full_content:
                updated_content = str(full_content_value or "").strip()
                if not updated_content:
                    return "error: full_content cannot be empty."
            else:
                old_text = str(old_text_value)
                if not old_text:
                    return "error: old_text cannot be empty."
                replacement = str(kwargs.get("replacement") or "")
                occurrence_count = existing_content.count(old_text)
                if occurrence_count != 1:
                    return (
                        "error: old_text must match exactly once; "
                        f"found {occurrence_count} matches."
                    )
                updated_content = existing_content.replace(old_text, replacement, 1)
            if updated_content == existing_content:
                return "error: The requested edit does not change the page."

            existing_doc_id = existing_page.get("metadata", {}).get("doc_id")
            updated_page = await wiki_store.write_page(
                path,
                updated_content,
                doc_id=existing_doc_id,
                require_existing=True,
            )

            document = await kb_helper.get_document(updated_page["doc_id"])
            if document is None:
                document = KBDocument(
                    doc_id=updated_page["doc_id"],
                    kb_id=kb_helper.kb.kb_id,
                    doc_name=updated_page["title"],
                    file_type="md",
                    file_size=len(updated_content.encode("utf-8")),
                    file_path=updated_page["path"],
                    chunk_count=updated_page["chunk_count"],
                    media_count=0,
                )
            else:
                document.doc_name = updated_page["title"]
                document.file_size = len(updated_content.encode("utf-8"))
                document.file_path = updated_page["path"]
                document.chunk_count = updated_page["chunk_count"]
            kb_manager = plugin_context.kb_manager
            async with kb_manager.kb_db.get_db() as session, session.begin():
                session.add(document)
            await kb_manager.kb_db.update_kb_stats(
                kb_id=kb_helper.kb.kb_id,
                vec_db=wiki_store,
            )
            await kb_helper.refresh_kb()
        except FileNotFoundError:
            return f"error: Wiki page {path!r} does not exist."
        except Exception as exc:
            logger.error(
                "Failed to edit Wiki page %s in knowledge base %s: %s",
                path,
                kb_helper.kb.kb_id,
                exc,
                exc_info=True,
            )
            return f"error: Knowledge page edit failed: {str(exc).strip() or 'Unknown error'}"

        embedding_provider_id = getattr(
            kb_helper.kb,
            "embedding_provider_id",
            None,
        )
        index_mode = (
            "hybrid vector and keyword indexing"
            if embedding_provider_id
            else "keyword indexing; no Embedding Provider required"
        )
        return (
            f"Updated Wiki page {updated_page['path']} in {kb_helper.kb.kb_name}. "
            f"Title: {updated_page['title']}. Chunks: {updated_page['chunk_count']}. "
            f"Index mode: {index_mode}."
        )


@builtin_tool(config=_KNOWLEDGE_BASE_TOOL_CONFIG)
@dataclass
class KnowledgeBaseDeletePageTool(FunctionTool[AstrAgentContext]):
    name: str = "astr_kb_delete_page"
    description: str = "删除指定知识库页面。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Exact Wiki-relative Markdown path to delete.",
                },
                "expected_title": {
                    "type": "string",
                    "description": (
                        "Exact page title returned by astr_kb_list_pages or "
                        "astr_kb_read_page. Deletion stops if it does not match."
                    ),
                },
                "confirm": {
                    "type": "boolean",
                    "description": (
                        "Must be true only after the user explicitly "
                        "confirmed deletion of this exact page."
                    ),
                },
                "knowledge_base": {
                    "type": "string",
                    "description": (
                        "Target knowledge base name or stable ID. Omit only when "
                        "the current session resolves to exactly one knowledge base."
                    ),
                },
            },
            "required": ["path", "expected_title", "confirm"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        """Delete one explicitly confirmed Wiki page.

        Args:
            context: Current agent execution context.
            **kwargs: Tool arguments containing the exact path and confirmation.

        Returns:
            A deletion confirmation or a user-facing error.
        """
        event = context.context.event
        plugin_context = context.context.context
        if kwargs.get("confirm") is not True:
            return "error: Explicit deletion confirmation is required."

        path = str(kwargs.get("path") or "").strip()
        if not path:
            return "error: Wiki page path is empty."
        expected_title = " ".join(
            str(kwargs.get("expected_title") or "").split()
        ).strip()
        if not expected_title:
            return "error: Exact expected_title is required for deletion."
        selector = str(kwargs.get("knowledge_base") or "").strip()
        kb_helper, error = await _resolve_target_knowledge_base(
            event,
            plugin_context,
            selector,
        )
        if error:
            return error
        if kb_helper is None:
            return "error: Knowledge base could not be resolved."

        try:
            wiki_store = await kb_helper._ensure_vec_db()
            page = await wiki_store.get_page_metadata(path)
            if not page:
                return f"error: Wiki page {path!r} does not exist."
            actual_title = " ".join(str(page.get("title") or "").split()).strip()
            if actual_title != expected_title:
                return (
                    "error: Page title confirmation does not match; "
                    f"expected {expected_title!r}, actual {actual_title!r}."
                )
            document = await kb_helper.get_document(page["doc_id"])
            if document is not None:
                await kb_helper.delete_document(page["doc_id"])
            else:
                deleted = await wiki_store.delete_page(path)
                if not deleted:
                    return f"error: Wiki page {path!r} does not exist."
                kb_manager = plugin_context.kb_manager
                await kb_manager.kb_db.update_kb_stats(
                    kb_id=kb_helper.kb.kb_id,
                    vec_db=wiki_store,
                )
                await kb_helper.refresh_kb()
        except Exception as exc:
            logger.error(
                "Failed to delete Wiki page %s from knowledge base %s: %s",
                path,
                kb_helper.kb.kb_id,
                exc,
                exc_info=True,
            )
            return f"error: Knowledge page deletion failed: {str(exc).strip() or 'Unknown error'}"

        return (
            f"Deleted Wiki page {path} from {kb_helper.kb.kb_name} "
            f"({kb_helper.kb.kb_id})."
        )


@builtin_tool(config=_KNOWLEDGE_BASE_TOOL_CONFIG)
@dataclass
class KnowledgeBaseWritePageTool(FunctionTool[AstrAgentContext]):
    name: str = "astr_kb_save_text"
    description: str = "把文章、笔记或文本保存为知识库 Markdown 页面。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Page or article title.",
                },
                "content": {
                    "type": "string",
                    "description": (
                        "Complete extracted article or note content in Markdown "
                        "or plain text."
                    ),
                },
                "source": {
                    "type": "string",
                    "description": "Optional source URL or provenance label.",
                },
                "summary": {
                    "type": "string",
                    "maxLength": 1200,
                    "description": "Concise factual summary of the complete source.",
                },
                "category": {
                    "type": "string",
                    "maxLength": 120,
                    "description": (
                        "Primary stable topic category. It becomes a concept node."
                    ),
                },
                "entities": {
                    "type": "array",
                    "maxItems": 40,
                    "description": (
                        "Important named people, organizations, products, places, "
                        "events, or other concrete entities."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "maxLength": 120},
                            "entity_type": {
                                "type": "string",
                                "maxLength": 80,
                            },
                            "summary": {"type": "string", "maxLength": 600},
                        },
                        "required": ["name"],
                        "additionalProperties": False,
                    },
                },
                "concepts": {
                    "type": "array",
                    "maxItems": 30,
                    "description": (
                        "Reusable abstract topics, technologies, methods, or ideas."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "maxLength": 120},
                            "summary": {"type": "string", "maxLength": 600},
                        },
                        "required": ["name"],
                        "additionalProperties": False,
                    },
                },
                "relations": {
                    "type": "array",
                    "maxItems": 80,
                    "description": (
                        "Directed factual relations. Endpoints must match an entity "
                        "or concept name, or use 'source' for the article."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string", "maxLength": 120},
                            "target": {"type": "string", "maxLength": 120},
                            "relation": {"type": "string", "maxLength": 80},
                            "evidence": {"type": "string", "maxLength": 600},
                        },
                        "required": ["source", "target", "relation"],
                        "additionalProperties": False,
                    },
                },
                "knowledge_base": {
                    "type": "string",
                    "description": (
                        "Target knowledge base name or stable ID. Omit only when "
                        "the current session resolves to exactly one knowledge base."
                    ),
                },
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        event = context.context.event
        plugin_context = context.context.context
        title = " ".join(str(kwargs.get("title") or "").split()).strip()
        content = str(kwargs.get("content") or "").strip()
        source = " ".join(str(kwargs.get("source") or "").split()).strip()
        if not title:
            return "error: Page title is empty."
        if not content:
            return "error: Page content is empty."
        try:
            analysis = _KnowledgeAnalysisInput.model_validate(
                {
                    "summary": kwargs.get("summary", ""),
                    "category": kwargs.get("category", ""),
                    "entities": kwargs.get("entities", []),
                    "concepts": kwargs.get("concepts", []),
                    "relations": kwargs.get("relations", []),
                }
            )
        except ValidationError as exc:
            first_error = exc.errors(include_url=False)[0]
            location = ".".join(str(part) for part in first_error.get("loc", ()))
            return (
                "error: Structured knowledge analysis is invalid at "
                f"{location or 'input'}: {first_error.get('msg', 'validation failed')}."
            )

        nodes_by_name: dict[str, dict[str, str]] = {}
        category = " ".join(analysis.category.split()).strip()
        if category:
            nodes_by_name[category.casefold()] = {
                "name": category,
                "path": f"concepts/{_knowledge_page_slug(category)}.md",
                "node_type": "concept",
                "entity_type": "",
                "summary": f"Primary topic category extracted from {title}.",
            }
        for entity in analysis.entities:
            name = " ".join(entity.name.split()).strip()
            if not name:
                continue
            nodes_by_name[name.casefold()] = {
                "name": name,
                "path": f"entities/{_knowledge_page_slug(name)}.md",
                "node_type": "entity",
                "entity_type": " ".join(entity.entity_type.split()).strip()[:80],
                "summary": " ".join(entity.summary.split()).strip()[:600],
            }
        for concept in analysis.concepts:
            name = " ".join(concept.name.split()).strip()
            if not name:
                continue
            existing = nodes_by_name.get(name.casefold())
            if existing is None or existing["node_type"] != "entity":
                nodes_by_name[name.casefold()] = {
                    "name": name,
                    "path": f"concepts/{_knowledge_page_slug(name)}.md",
                    "node_type": "concept",
                    "entity_type": "",
                    "summary": " ".join(concept.summary.split()).strip()[:600],
                }
        nodes = list(nodes_by_name.values())

        source_relation_lines = []
        for node in nodes:
            relation_name = (
                "categorized_as"
                if category and node["name"].casefold() == category.casefold()
                else "mentions"
                if node["node_type"] == "entity"
                else "discusses"
            )
            source_target = _relative_wiki_target(
                "sources/source.md",
                node["path"],
            )
            source_relation_lines.append(
                f"- {relation_name}: [[{source_target}|{node['name']}]]"
            )
        source_aliases = {"source", "article", "文章", title.casefold()}
        for relation in analysis.relations:
            target = nodes_by_name.get(relation.target.strip().casefold())
            if (
                relation.source.strip().casefold() not in source_aliases
                or target is None
            ):
                continue
            relation_name = _knowledge_relation_name(relation.relation)
            evidence = " ".join(relation.evidence.split()).strip()[:300]
            evidence_suffix = f" — {evidence}" if evidence else ""
            source_target = _relative_wiki_target(
                "sources/source.md",
                target["path"],
            )
            source_relation_lines.append(
                f"- {relation_name}: "
                f"[[{source_target}|{target['name']}]]{evidence_suffix}"
            )
        source_relation_lines = list(dict.fromkeys(source_relation_lines))

        analysis_sections = []
        summary = " ".join(analysis.summary.split()).strip()
        if summary:
            analysis_sections.append(f"## Summary\n\n{summary}")
        if category:
            category_node = nodes_by_name[category.casefold()]
            category_target = _relative_wiki_target(
                "sources/source.md",
                category_node["path"],
            )
            analysis_sections.append(
                f"## Category\n\n[[{category_target}|{category_node['name']}]]"
            )
        if source_relation_lines:
            analysis_sections.append(
                "## Knowledge Relations\n\n" + "\n".join(source_relation_lines)
            )
        enriched_content = content
        if analysis_sections:
            enriched_content = (
                "\n\n".join(analysis_sections) + "\n\n## Original Content\n\n" + content
            )

        selector = str(kwargs.get("knowledge_base") or "").strip()
        kb_helper, error = await _resolve_target_knowledge_base(
            event,
            plugin_context,
            selector,
        )
        if error:
            return error
        if kb_helper is None:
            return "error: Knowledge base could not be resolved."

        file_stem = re.sub(r"[\x00-\x1f/\\]+", " ", title).strip(" .")
        file_name = f"{(file_stem or 'knowledge-page')[:180]}.md"
        chunk_size = getattr(kb_helper.kb, "chunk_size", None)
        chunk_overlap = getattr(kb_helper.kb, "chunk_overlap", None)
        try:
            document = await kb_helper.upload_document(
                file_name=file_name,
                file_content=enriched_content.encode("utf-8"),
                file_type="md",
                chunk_size=(
                    chunk_size if chunk_size is not None else DEFAULT_CHUNK_SIZE
                ),
                chunk_overlap=(
                    chunk_overlap
                    if chunk_overlap is not None
                    else DEFAULT_CHUNK_OVERLAP
                ),
                source_label=source or title,
            )
        except Exception as exc:
            logger.error(
                "Failed to save extracted text to knowledge base %s: %s",
                kb_helper.kb.kb_id,
                exc,
                exc_info=True,
            )
            error_message = str(exc).strip() or "Unknown save error"
            return f"error: Knowledge save failed: {error_message}"

        graph_result = {"nodes": 0, "relations": 0}
        if nodes:
            try:
                graph_result = await _write_structured_knowledge_pages(
                    kb_helper=kb_helper,
                    plugin_context=plugin_context,
                    document=document,
                    title=title,
                    source_label=source or title,
                    nodes=nodes,
                    relations=analysis.relations,
                )
            except Exception as exc:
                try:
                    await kb_helper.delete_document(document.doc_id)
                except Exception as rollback_exc:  # noqa: BLE001
                    logger.error(
                        "Failed to roll back source document %s after graph "
                        "enrichment failure: %s",
                        document.doc_id,
                        rollback_exc,
                        exc_info=True,
                    )
                logger.error(
                    "Failed to enrich knowledge graph for source %s: %s",
                    title,
                    exc,
                    exc_info=True,
                )
                return (
                    "error: Knowledge graph enrichment failed; the new source was "
                    "rolled back. Please retry."
                )

        embedding_provider_id = getattr(
            kb_helper.kb,
            "embedding_provider_id",
            None,
        )
        index_mode = (
            "hybrid vector and keyword indexing"
            if embedding_provider_id
            else "keyword indexing; no Embedding Provider required"
        )
        return (
            f"Saved Wiki page to {kb_helper.kb.kb_name} "
            f"({kb_helper.kb.kb_id}). Path: {document.file_path}. "
            f"Chunks: {document.chunk_count}. Structured nodes updated: "
            f"{graph_result['nodes']}. Relationships added: "
            f"{graph_result['relations']}. Index mode: {index_mode}."
        )


@builtin_tool(config=_KNOWLEDGE_BASE_TOOL_CONFIG)
@dataclass
class KnowledgeBaseExportTool(FunctionTool[AstrAgentContext]):
    name: str = "astr_kb_export"
    description: str = "导出知识库为 ZIP 附件。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "knowledge_base": {
                    "type": "string",
                    "description": (
                        "Target knowledge base name or stable ID. Omit only when "
                        "the current session resolves to exactly one knowledge base."
                    ),
                },
            },
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult | MessageEventResult:
        """Create and send one knowledge base Wiki archive.

        Args:
            context: Current agent execution context and platform event.
            **kwargs: Tool arguments containing the optional knowledge base
                selector.

        Returns:
            A direct file message result or a user-facing error string.
        """
        event = context.context.event
        plugin_context = context.context.context
        selector = str(kwargs.get("knowledge_base") or "").strip()
        kb_helper, error = await _resolve_target_knowledge_base(
            event,
            plugin_context,
            selector,
        )
        if error:
            return error
        if kb_helper is None:
            return "error: Knowledge base could not be resolved."

        try:
            archive_path, filename, page_count = await asyncio.to_thread(
                kb_helper.export_wiki_archive
            )
        except Exception as exc:
            logger.error(
                "Failed to export knowledge base %s: %s",
                kb_helper.kb.kb_id,
                exc,
                exc_info=True,
            )
            return (
                f"error: Knowledge export failed: {str(exc).strip() or 'Unknown error'}"
            )

        event.track_temporary_local_file(str(archive_path))
        result = MessageEventResult().message(
            f"Exported {page_count} Markdown pages from "
            f"{kb_helper.kb.kb_name} ({kb_helper.kb.kb_id})."
        )
        result.chain.append(File(name=filename, file=str(archive_path)))
        return result


@builtin_tool(config=_KNOWLEDGE_BASE_TOOL_CONFIG)
@dataclass
class KnowledgeBaseImportAttachmentTool(FunctionTool[AstrAgentContext]):
    name: str = "astr_kb_import_attachment"
    description: str = "从当前消息或引用消息的附件导入 Markdown 或 ZIP 到知识库。"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "attachment_name": {
                    "type": "string",
                    "description": (
                        "Exact attachment filename. Omit only when the message "
                        "contains exactly one file attachment."
                    ),
                },
                "knowledge_base": {
                    "type": "string",
                    "description": (
                        "Target knowledge base name or stable ID. Omit only when "
                        "the current session resolves to exactly one knowledge base."
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": (
                        "Replace pages with identical paths. Defaults to false; "
                        "enable only when the user explicitly requests replacement."
                    ),
                    "default": False,
                },
            },
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        event = context.context.event
        plugin_context = context.context.context
        attachments: list[File] = []
        for component in event.message_obj.message:
            if isinstance(component, File):
                attachments.append(component)
            elif isinstance(component, Reply) and component.chain:
                attachments.extend(
                    item for item in component.chain if isinstance(item, File)
                )
        if not attachments:
            return (
                "error: No file attachment was found in the current or quoted "
                "message. Reply to the attachment and try again."
            )

        requested_name = str(kwargs.get("attachment_name") or "").strip()
        if requested_name:
            matching = [
                attachment
                for attachment in attachments
                if (attachment.name or "").casefold() == requested_name.casefold()
            ]
            if len(matching) != 1:
                available = ", ".join(
                    attachment.name or "unnamed" for attachment in attachments
                )
                return (
                    f"error: Attachment {requested_name!r} is missing or ambiguous. "
                    f"Available attachments: {available}"
                )
            attachment = matching[0]
        elif len(attachments) == 1:
            attachment = attachments[0]
        else:
            available = ", ".join(
                attachment.name or "unnamed" for attachment in attachments
            )
            return f"error: Multiple attachments found; specify one of: {available}"

        attachment_name = Path(
            str(attachment.name or "knowledge.zip").replace("\\", "/")
        ).name
        attachment_name = attachment_name or "knowledge.zip"
        if Path(attachment_name).suffix.lower() not in {
            ".md",
            ".markdown",
            ".mdx",
            ".zip",
        }:
            return "error: Only Markdown files and ZIP archives are supported."

        selector = str(kwargs.get("knowledge_base") or "").strip()
        kb_helper, error = await _resolve_target_knowledge_base(
            event,
            plugin_context,
            selector,
        )
        if error:
            return error
        if kb_helper is None:
            return "error: Knowledge base could not be resolved."

        file_path = await attachment.get_file()
        if not file_path or not Path(file_path).is_file():
            return "error: The attachment could not be downloaded to a local file."

        target_path = (
            None if Path(attachment_name).suffix.lower() == ".zip" else attachment_name
        )
        try:
            result = await kb_helper.import_wiki_sources(
                [(Path(file_path), target_path)],
                overwrite=bool(kwargs.get("overwrite", False)),
            )
        except Exception as exc:
            logger.error(
                "Failed to import knowledge attachment %s: %s",
                attachment_name,
                exc,
                exc_info=True,
            )
            error_message = str(exc).strip() or "Unknown import error"
            for local_path in {file_path, str(Path(file_path).resolve())}:
                if local_path:
                    error_message = error_message.replace(local_path, attachment_name)
            return f"error: Knowledge import failed: {error_message}"

        imported = result.get("imported", [])
        imported_paths = [str(page.get("path", "")) for page in imported]
        preview = ", ".join(path for path in imported_paths[:20] if path)
        if len(imported_paths) > 20:
            preview += f", ... and {len(imported_paths) - 20} more"
        skipped = result.get("skipped", [])
        skipped_text = f" Skipped {len(skipped)} entries." if skipped else ""
        return (
            f"Imported {len(imported)} Wiki pages into "
            f"{kb_helper.kb.kb_name} ({kb_helper.kb.kb_id})."
            f"{skipped_text} Paths: {preview or 'none'}"
        )


__all__ = [
    "KnowledgeBaseDeletePageTool",
    "KnowledgeBaseEditPageTool",
    "KnowledgeBaseImportAttachmentTool",
    "KnowledgeBaseListPagesTool",
    "KnowledgeBaseQueryTool",
    "KnowledgeBaseReadPageTool",
    "KnowledgeBaseWritePageTool",
    "retrieve_knowledge_base",
]
