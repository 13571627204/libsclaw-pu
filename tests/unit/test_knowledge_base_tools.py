"""Tests for knowledge base tools."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.knowledge_base.wiki import WikiStore
from astrbot.core.message.components import File, Reply
from astrbot.core.message.message_event_result import MessageEventResult
from astrbot.core.tools.knowledge_base_tools import (
    KnowledgeBaseDeletePageTool,
    KnowledgeBaseEditPageTool,
    KnowledgeBaseExportTool,
    KnowledgeBaseImportAttachmentTool,
    KnowledgeBaseListPagesTool,
    KnowledgeBaseReadPageTool,
    KnowledgeBaseWritePageTool,
)


class _AsyncContext:
    """Minimal async context manager for mocked database sessions."""

    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def _make_kb_helper(kb_id: str, kb_name: str):
    """Create a mock knowledge base helper."""
    wiki_store = SimpleNamespace(
        list_tree=AsyncMock(
            return_value={
                "tree": {
                    "children": [
                        {
                            "type": "directory",
                            "path": "sources",
                            "children": [
                                {
                                    "type": "page",
                                    "name": "article.md",
                                    "path": "sources/article.md",
                                    "title": "Article",
                                    "node_type": "source",
                                    "summary": "Article summary",
                                    "source": "https://example.com/article",
                                }
                            ],
                        }
                    ]
                },
                "page_count": 1,
                "total_size": 100,
            }
        ),
        read_page=AsyncMock(
            return_value={
                "path": "sources/article.md",
                "content": "---\ndoc_id: doc-article\n---\n\n# Article\n\nold text",
                "metadata": {
                    "doc_id": "doc-article",
                    "title": "Article",
                    "source": "https://example.com/article",
                },
                "links": [],
                "backlinks": [],
            }
        ),
        write_page=AsyncMock(
            return_value={
                "path": "sources/article.md",
                "doc_id": "doc-article",
                "title": "Article",
                "chunk_count": 2,
            }
        ),
        get_page_metadata=AsyncMock(
            return_value={
                "path": "sources/article.md",
                "doc_id": "doc-article",
                "title": "Article",
            }
        ),
        delete_page=AsyncMock(return_value=True),
    )
    document = SimpleNamespace(
        doc_id="doc-article",
        doc_name="Article",
        file_size=100,
        file_path="sources/article.md",
        chunk_count=1,
    )
    helper = SimpleNamespace(
        kb=SimpleNamespace(
            kb_id=kb_id,
            kb_name=kb_name,
            chunk_size=800,
            chunk_overlap=80,
            embedding_provider_id=None,
        ),
        import_wiki_sources=AsyncMock(
            return_value={"imported": [{"path": "category/page.md"}], "skipped": []}
        ),
        export_wiki_archive=MagicMock(),
        upload_document=AsyncMock(
            return_value=SimpleNamespace(
                doc_id="doc-uploaded",
                file_path="sources/article.md",
                chunk_count=12,
            )
        ),
        wiki_store=wiki_store,
        get_document=AsyncMock(return_value=document),
        delete_document=AsyncMock(),
        refresh_kb=AsyncMock(),
    )
    helper._ensure_vec_db = AsyncMock(return_value=wiki_store)
    return helper


def _make_kb_manager(*helpers):
    """Create a mock knowledge base manager for the supplied helpers."""
    helpers_by_id = {helper.kb.kb_id: helper for helper in helpers}
    helpers_by_name = {helper.kb.kb_name: helper for helper in helpers}
    session = MagicMock()
    session.begin.return_value = _AsyncContext()
    kb_db = SimpleNamespace(
        get_db=MagicMock(return_value=_AsyncContext(session)),
        update_kb_stats=AsyncMock(),
    )
    return SimpleNamespace(
        get_kb=AsyncMock(side_effect=helpers_by_id.get),
        get_kb_by_name=AsyncMock(side_effect=helpers_by_name.get),
        list_kbs=AsyncMock(return_value=[helper.kb for helper in helpers]),
        kb_db=kb_db,
    )


def _make_context(components, kb_manager, *, role: str = "admin", config=None):
    """Create a tool execution context with the given message components."""
    event = SimpleNamespace(
        role=role,
        unified_msg_origin="feishu:private:test-user",
        message_obj=SimpleNamespace(message=components),
        track_temporary_local_file=MagicMock(),
    )
    plugin_context = SimpleNamespace(
        kb_manager=kb_manager,
        get_config=lambda **_kwargs: config or {},
    )
    return ContextWrapper(context=SimpleNamespace(event=event, context=plugin_context))


@pytest.mark.asyncio
async def test_save_text_allows_member_for_selected_kb(monkeypatch):
    """Allow an ordinary user to save into the session-selected knowledge base."""
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context([], manager, role="member")
    monkeypatch.setattr(
        "astrbot.core.tools.knowledge_base_tools.sp.session_get",
        AsyncMock(return_value={"kb_ids": ["kb-1"]}),
    )

    result = await KnowledgeBaseWritePageTool().call(
        context,
        title="Article",
        content="Article body",
        knowledge_base="kb-1",
    )

    assert "Saved Wiki page to Docs (kb-1)." in result
    helper.upload_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_member_cannot_save_to_unselected_kb(monkeypatch):
    """Keep ordinary users inside the knowledge bases selected for their session."""
    docs = _make_kb_helper("kb-1", "Docs")
    private = _make_kb_helper("kb-2", "Private")
    manager = _make_kb_manager(docs, private)
    context = _make_context([], manager, role="member")
    monkeypatch.setattr(
        "astrbot.core.tools.knowledge_base_tools.sp.session_get",
        AsyncMock(return_value={"kb_ids": ["kb-1"]}),
    )

    result = await KnowledgeBaseWritePageTool().call(
        context,
        title="Article",
        content="Article body",
        knowledge_base="kb-2",
    )

    assert result == (
        "error: Knowledge base 'Private' is not selected for the current session."
    )
    private.upload_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_text_works_without_embedding_provider():
    """Save extracted content with lexical indexing when embeddings are absent."""
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context([], manager)

    result = await KnowledgeBaseWritePageTool().call(
        context,
        title="天蚕土豆新书《神通者》",
        content="# 正文\n\n这是提取后的文章内容。",
        source="https://example.com/article",
        knowledge_base="Docs",
    )

    assert "Saved Wiki page to Docs (kb-1)." in result
    assert "no Embedding Provider required" in result
    manager.get_kb.assert_awaited_once_with("Docs")
    manager.get_kb_by_name.assert_awaited_once_with("Docs")
    helper.upload_document.assert_awaited_once_with(
        file_name="天蚕土豆新书《神通者》.md",
        file_content="# 正文\n\n这是提取后的文章内容。".encode(),
        file_type="md",
        chunk_size=800,
        chunk_overlap=80,
        source_label="https://example.com/article",
    )


@pytest.mark.asyncio
async def test_save_text_builds_structured_entity_concept_pages():
    """Create persistent structured pages and relations while saving an article."""
    helper = _make_kb_helper("kb-1", "Docs")
    helper.wiki_store.get_page_metadata.return_value = None
    manager = _make_kb_manager(helper)
    context = _make_context([], manager)

    result = await KnowledgeBaseWritePageTool().call(
        context,
        title="小米澎程发布会邀请函曝光",
        content="# 原文\n\n小米澎程是一款增程汽车。",
        source="https://mp.weixin.qq.com/s/example",
        summary="小米澎程发布会邀请函展示了产品空间设计线索。",
        category="汽车科技",
        entities=[
            {
                "name": "小米集团",
                "entity_type": "company",
                "summary": "智能汽车和消费电子企业。",
            },
            {
                "name": "小米澎程",
                "entity_type": "product",
                "summary": "小米旗下增程车型。",
            },
        ],
        concepts=[
            {
                "name": "增程汽车",
                "summary": "使用增程器补充电能的电驱汽车。",
            }
        ],
        relations=[
            {
                "source": "source",
                "target": "小米澎程",
                "relation": "introduces",
                "evidence": "文章介绍发布会邀请函。",
            },
            {
                "source": "小米澎程",
                "target": "小米集团",
                "relation": "属于",
                "evidence": "文章将其描述为小米产品。",
            },
            {
                "source": "小米澎程",
                "target": "增程汽车",
                "relation": "采用",
                "evidence": "文章称其为增程车型。",
            },
        ],
        knowledge_base="Docs",
    )

    upload_kwargs = helper.upload_document.await_args.kwargs
    uploaded_content = upload_kwargs["file_content"].decode()
    assert "## Summary" in uploaded_content
    assert "[[../entities/小米集团.md|小米集团]]" in uploaded_content
    assert "- introduces: [[../entities/小米澎程.md|小米澎程]]" in uploaded_content
    written_pages = {
        call.args[0]: call.args[1]
        for call in helper.wiki_store.write_page.await_args_list
    }
    assert set(written_pages) == {
        "concepts/汽车科技.md",
        "entities/小米集团.md",
        "entities/小米澎程.md",
        "concepts/增程汽车.md",
    }
    assert "type: entity" in written_pages["entities/小米澎程.md"]
    assert "- 属于: [[小米集团.md|小米集团]]" in written_pages["entities/小米澎程.md"]
    assert (
        "- 采用: [[../concepts/增程汽车.md|增程汽车]]"
        in written_pages["entities/小米澎程.md"]
    )
    assert "Structured nodes updated: 4" in result
    manager.kb_db.update_kb_stats.assert_awaited_once()
    helper.refresh_kb.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_text_structured_graph_works_with_real_wiki_store(tmp_path):
    """Persist source, entity, concept, and typed edges end to end."""
    store = WikiStore(tmp_path / "kb", "kb-1")
    await store.initialize()
    try:
        helper = _make_kb_helper("kb-1", "Docs")
        helper.wiki_store = store
        helper._ensure_vec_db = AsyncMock(return_value=store)

        async def upload_document(**kwargs):
            source_content = kwargs["file_content"].decode()
            page = await store.upsert_document(
                doc_id="doc-source",
                file_name=kwargs["file_name"],
                source=kwargs["source_label"],
                content=source_content,
                chunks=[source_content],
            )
            return SimpleNamespace(
                doc_id="doc-source",
                file_path=page["path"],
                chunk_count=page["chunk_count"],
            )

        helper.upload_document = AsyncMock(side_effect=upload_document)
        manager = _make_kb_manager(helper)
        context = _make_context([], manager)

        result = await KnowledgeBaseWritePageTool().call(
            context,
            title="Product article",
            content="Complete article body.",
            source="https://example.com/product",
            summary="A product announcement.",
            category="Automotive",
            entities=[
                {
                    "name": "Product X",
                    "entity_type": "product",
                    "summary": "A new vehicle.",
                }
            ],
            concepts=[
                {
                    "name": "Range Extender",
                    "summary": "A vehicle powertrain concept.",
                }
            ],
            relations=[
                {
                    "source": "Product X",
                    "target": "Range Extender",
                    "relation": "uses",
                    "evidence": "The article describes the powertrain.",
                }
            ],
            knowledge_base="Docs",
        )

        graph = await store.get_graph()
        nodes = {node["id"]: node for node in graph["nodes"]}
        edges = {
            (edge["source"], edge["target"], edge["relation"])
            for edge in graph["edges"]
        }
        source_path = next(path for path in nodes if path.startswith("sources/"))

        assert "Structured nodes updated: 3" in result
        assert nodes[source_path]["node_type"] == "source"
        assert nodes["entities/product-x.md"]["node_type"] == "entity"
        assert nodes["concepts/range-extender.md"]["node_type"] == "concept"
        product_edges = [
            edge for edge in graph["edges"] if edge["target"] == "entities/product-x.md"
        ]
        assert (source_path, "entities/product-x.md", "mentions") in edges, (
            product_edges
        )
        assert (
            "entities/product-x.md",
            "concepts/range-extender.md",
            "uses",
        ) in edges
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_save_text_rolls_back_source_when_graph_enrichment_fails():
    """Remove the new source and partial nodes if structured enrichment fails."""
    helper = _make_kb_helper("kb-1", "Docs")
    helper.wiki_store.get_page_metadata.return_value = None
    helper.wiki_store.write_page.side_effect = [
        {"path": "entities/first.md"},
        RuntimeError("graph write failed"),
    ]
    manager = _make_kb_manager(helper)
    context = _make_context([], manager)

    result = await KnowledgeBaseWritePageTool().call(
        context,
        title="Article",
        content="Article body",
        entities=[{"name": "First"}, {"name": "Second"}],
        knowledge_base="Docs",
    )

    assert result == (
        "error: Knowledge graph enrichment failed; the new source was rolled back. "
        "Please retry."
    )
    helper.wiki_store.delete_page.assert_awaited_once_with("entities/first.md")
    helper.delete_document.assert_awaited_once_with("doc-uploaded")


@pytest.mark.asyncio
async def test_save_text_uses_session_knowledge_base(monkeypatch):
    """Use the knowledge base selected for the current messaging session."""
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context([], manager)
    session_get = AsyncMock(return_value={"kb_ids": ["kb-1"]})
    monkeypatch.setattr(
        "astrbot.core.tools.knowledge_base_tools.sp.session_get",
        session_get,
    )

    await KnowledgeBaseWritePageTool().call(
        context,
        title="Article",
        content="Article body",
    )

    session_get.assert_awaited_once_with(
        "feishu:private:test-user",
        "kb_config",
        default={},
    )
    manager.get_kb.assert_awaited_once_with("kb-1")
    helper.upload_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_pages_returns_exact_paths():
    """List page titles with exact Wiki-relative paths for later operations."""
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context([], manager)

    result = await KnowledgeBaseListPagesTool().call(
        context,
        query="article",
        knowledge_base="kb-1",
    )

    assert "sources/article.md | Article" in result
    assert "type=source" in result
    helper.wiki_store.list_tree.assert_awaited_once()


@pytest.mark.asyncio
async def test_read_page_returns_complete_markdown():
    """Return complete Markdown content before editing or deleting a page."""
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context([], manager)

    result = await KnowledgeBaseReadPageTool().call(
        context,
        path="sources/article.md",
        knowledge_base="Docs",
    )

    assert "Path: sources/article.md" in result
    assert "# Article\n\nold text" in result
    helper.wiki_store.read_page.assert_awaited_once_with("sources/article.md")


@pytest.mark.asyncio
async def test_edit_page_replaces_one_exact_excerpt_and_refreshes_indexes():
    """Perform a safe partial edit and synchronize document metadata."""
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context([], manager)

    result = await KnowledgeBaseEditPageTool().call(
        context,
        path="sources/article.md",
        old_text="old text",
        replacement="new text",
        knowledge_base="kb-1",
    )

    assert "Updated Wiki page sources/article.md" in result
    assert "no Embedding Provider required" in result
    helper.wiki_store.write_page.assert_awaited_once_with(
        "sources/article.md",
        "---\ndoc_id: doc-article\n---\n\n# Article\n\nnew text",
        doc_id="doc-article",
        require_existing=True,
    )
    manager.kb_db.update_kb_stats.assert_awaited_once_with(
        kb_id="kb-1",
        vec_db=helper.wiki_store,
    )
    helper.refresh_kb.assert_awaited_once()


@pytest.mark.asyncio
async def test_edit_page_rejects_ambiguous_excerpt():
    """Reject partial edits when the selected text is not unique."""
    helper = _make_kb_helper("kb-1", "Docs")
    helper.wiki_store.read_page.return_value["content"] = "same text\nsame text"
    manager = _make_kb_manager(helper)
    context = _make_context([], manager)

    result = await KnowledgeBaseEditPageTool().call(
        context,
        path="sources/article.md",
        old_text="same text",
        replacement="replacement",
        knowledge_base="kb-1",
    )

    assert result == "error: old_text must match exactly once; found 2 matches."
    helper.wiki_store.write_page.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_page_requires_confirmation():
    """Do not delete a page unless the caller supplies explicit confirmation."""
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context([], manager)

    result = await KnowledgeBaseDeletePageTool().call(
        context,
        path="sources/article.md",
        expected_title="Article",
        confirm=False,
        knowledge_base="kb-1",
    )

    assert result == "error: Explicit deletion confirmation is required."
    helper.delete_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_page_rejects_title_mismatch():
    """Do not delete when the confirmed title does not match the selected path."""
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context([], manager)

    result = await KnowledgeBaseDeletePageTool().call(
        context,
        path="sources/article.md",
        expected_title="Different article",
        confirm=True,
        knowledge_base="kb-1",
    )

    assert "Page title confirmation does not match" in result
    helper.delete_document.assert_not_awaited()
    helper.wiki_store.delete_page.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_page_removes_document_and_derived_indexes():
    """Delete the backing document after resolving the exact Wiki page path."""
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context([], manager)

    result = await KnowledgeBaseDeletePageTool().call(
        context,
        path="sources/article.md",
        expected_title="Article",
        confirm=True,
        knowledge_base="kb-1",
    )

    assert result == "Deleted Wiki page sources/article.md from Docs (kb-1)."
    helper.wiki_store.get_page_metadata.assert_awaited_once_with("sources/article.md")
    helper.get_document.assert_awaited_once_with("doc-article")
    helper.delete_document.assert_awaited_once_with("doc-article")


@pytest.mark.asyncio
async def test_export_allows_member_for_selected_kb(tmp_path, monkeypatch):
    """Allow an ordinary user to export the session-selected knowledge base."""
    archive_path = tmp_path / "Docs.zip"
    archive_path.write_bytes(b"zip fixture")
    helper = _make_kb_helper("kb-1", "Docs")
    helper.export_wiki_archive.return_value = (archive_path, "Docs.zip", 1)
    manager = _make_kb_manager(helper)
    context = _make_context([], manager, role="member")
    monkeypatch.setattr(
        "astrbot.core.tools.knowledge_base_tools.sp.session_get",
        AsyncMock(return_value={"kb_ids": ["kb-1"]}),
    )

    result = await KnowledgeBaseExportTool().call(
        context,
        knowledge_base="kb-1",
    )

    assert isinstance(result, MessageEventResult)
    assert result.get_plain_text() == "Exported 1 Markdown pages from Docs (kb-1)."
    helper.export_wiki_archive.assert_called_once_with()


@pytest.mark.asyncio
async def test_export_sends_zip_as_direct_file_result(tmp_path):
    """Send the generated Wiki ZIP directly to the messaging platform."""
    archive_path = tmp_path / "kb-export.zip"
    archive_path.write_bytes(b"zip fixture")
    helper = _make_kb_helper("kb-1", "Docs")
    helper.export_wiki_archive.return_value = (archive_path, "Docs.zip", 3)
    manager = _make_kb_manager(helper)
    context = _make_context([], manager)

    result = await KnowledgeBaseExportTool().call(
        context,
        knowledge_base="Docs",
    )

    assert isinstance(result, MessageEventResult)
    assert result.get_plain_text() == "Exported 3 Markdown pages from Docs (kb-1)."
    assert len(result.chain) == 2
    assert isinstance(result.chain[1], File)
    assert result.chain[1].name == "Docs.zip"
    assert result.chain[1].file == str(archive_path)
    context.context.event.track_temporary_local_file.assert_called_once_with(
        str(archive_path)
    )
    helper.export_wiki_archive.assert_called_once_with()


@pytest.mark.asyncio
async def test_import_attachment_allows_member_for_selected_kb(
    tmp_path,
    monkeypatch,
):
    """Allow an ordinary user to import into the session-selected knowledge base."""
    source = tmp_path / "guide.md"
    source.write_text("# Guide", encoding="utf-8")
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context(
        [File(name=source.name, file=str(source))],
        manager,
        role="member",
    )
    monkeypatch.setattr(
        "astrbot.core.tools.knowledge_base_tools.sp.session_get",
        AsyncMock(return_value={"kb_ids": ["kb-1"]}),
    )

    result = await KnowledgeBaseImportAttachmentTool().call(
        context,
        knowledge_base="kb-1",
    )

    assert result.startswith("Imported 1 Wiki pages into Docs (kb-1).")
    helper.import_wiki_sources.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_attachment_uses_single_current_file_by_default(tmp_path):
    """Use the only current-message attachment when no name is supplied."""
    source = tmp_path / "guide.md"
    source.write_text("# Guide", encoding="utf-8")
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context([File(name=source.name, file=str(source))], manager)

    result = await KnowledgeBaseImportAttachmentTool().call(
        context,
        knowledge_base="kb-1",
        overwrite=True,
    )

    assert result.startswith("Imported 1 Wiki pages into Docs (kb-1).")
    manager.get_kb.assert_awaited_once_with("kb-1")
    helper.import_wiki_sources.assert_awaited_once_with(
        [(Path(source), "guide.md")],
        overwrite=True,
    )


@pytest.mark.asyncio
async def test_import_attachment_finds_file_in_quoted_message(tmp_path):
    """Find a file attachment embedded in a quoted message chain."""
    source = tmp_path / "quoted.zip"
    source.write_bytes(b"zip fixture")
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    reply = Reply(
        id="message-id",
        chain=[File(name=source.name, file=str(source))],
    )
    context = _make_context([reply], manager)

    await KnowledgeBaseImportAttachmentTool().call(
        context,
        knowledge_base="kb-1",
    )

    helper.import_wiki_sources.assert_awaited_once_with(
        [(Path(source), None)],
        overwrite=False,
    )


@pytest.mark.asyncio
async def test_import_attachment_selects_named_file_case_insensitively(tmp_path):
    """Select an exact attachment name when multiple files are present."""
    first = tmp_path / "first.md"
    second = tmp_path / "second.zip"
    first.write_text("# First", encoding="utf-8")
    second.write_bytes(b"zip fixture")
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context(
        [
            File(name=first.name, file=str(first)),
            File(name=second.name, file=str(second)),
        ],
        manager,
    )

    await KnowledgeBaseImportAttachmentTool().call(
        context,
        attachment_name="SECOND.ZIP",
        knowledge_base="kb-1",
    )

    helper.import_wiki_sources.assert_awaited_once_with(
        [(Path(second), None)],
        overwrite=False,
    )


@pytest.mark.asyncio
async def test_import_attachment_requires_name_for_multiple_files(tmp_path):
    """Reject an ambiguous request containing multiple attachments."""
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context(
        [
            File(name="first.md", file=str(tmp_path / "first.md")),
            File(name="second.zip", file=str(tmp_path / "second.zip")),
        ],
        manager,
    )

    result = await KnowledgeBaseImportAttachmentTool().call(context)

    assert result == (
        "error: Multiple attachments found; specify one of: first.md, second.zip"
    )
    manager.get_kb.assert_not_awaited()
    helper.import_wiki_sources.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_attachment_rejects_unsupported_file_type(tmp_path):
    """Reject attachments that are neither Markdown nor ZIP files."""
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context(
        [File(name="notes.txt", file=str(tmp_path / "notes.txt"))],
        manager,
    )

    result = await KnowledgeBaseImportAttachmentTool().call(
        context,
        knowledge_base="kb-1",
    )

    assert result == "error: Only Markdown files and ZIP archives are supported."
    manager.get_kb.assert_not_awaited()
    helper.import_wiki_sources.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("selector", "expected_id_calls", "expected_name_calls"),
    [
        ("kb-1", ["kb-1"], []),
        ("Docs", ["Docs"], ["Docs"]),
    ],
)
async def test_import_attachment_resolves_explicit_kb_id_or_name(
    tmp_path,
    selector,
    expected_id_calls,
    expected_name_calls,
):
    """Resolve an explicitly supplied knowledge base ID or name."""
    source = tmp_path / "guide.md"
    source.write_text("# Guide", encoding="utf-8")
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context([File(name=source.name, file=str(source))], manager)

    await KnowledgeBaseImportAttachmentTool().call(
        context,
        knowledge_base=selector,
    )

    assert [
        call.args[0] for call in manager.get_kb.await_args_list
    ] == expected_id_calls
    assert [
        call.args[0] for call in manager.get_kb_by_name.await_args_list
    ] == expected_name_calls
    helper.import_wiki_sources.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_attachment_uses_single_session_kb(tmp_path, monkeypatch):
    """Automatically select the only knowledge base configured for the session."""
    source = tmp_path / "guide.md"
    source.write_text("# Guide", encoding="utf-8")
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context([File(name=source.name, file=str(source))], manager)
    session_get = AsyncMock(return_value={"kb_ids": ["kb-1"]})
    monkeypatch.setattr(
        "astrbot.core.tools.knowledge_base_tools.sp.session_get",
        session_get,
    )

    result = await KnowledgeBaseImportAttachmentTool().call(context)

    assert result.startswith("Imported 1 Wiki pages into Docs (kb-1).")
    session_get.assert_awaited_once_with(
        "feishu:private:test-user",
        "kb_config",
        default={},
    )
    manager.get_kb.assert_awaited_once_with("kb-1")
    helper.import_wiki_sources.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_attachment_does_not_fallback_when_session_disables_kbs(
    tmp_path,
    monkeypatch,
):
    """Respect an explicit empty session knowledge base selection."""
    source = tmp_path / "guide.md"
    source.write_text("# Guide", encoding="utf-8")
    helper = _make_kb_helper("kb-1", "Docs")
    manager = _make_kb_manager(helper)
    context = _make_context([File(name=source.name, file=str(source))], manager)
    monkeypatch.setattr(
        "astrbot.core.tools.knowledge_base_tools.sp.session_get",
        AsyncMock(return_value={"kb_ids": []}),
    )

    result = await KnowledgeBaseImportAttachmentTool().call(context)

    assert result == (
        "error: Specify the target knowledge base because the current session "
        "does not resolve to exactly one."
    )
    manager.list_kbs.assert_not_awaited()
    manager.get_kb.assert_not_awaited()
    helper.import_wiki_sources.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_attachment_requires_target_for_multiple_session_kbs(
    tmp_path,
    monkeypatch,
):
    """Require an explicit target when the session has multiple knowledge bases."""
    source = tmp_path / "guide.md"
    source.write_text("# Guide", encoding="utf-8")
    docs = _make_kb_helper("kb-1", "Docs")
    handbook = _make_kb_helper("kb-2", "Handbook")
    manager = _make_kb_manager(docs, handbook)
    context = _make_context([File(name=source.name, file=str(source))], manager)
    monkeypatch.setattr(
        "astrbot.core.tools.knowledge_base_tools.sp.session_get",
        AsyncMock(return_value={"kb_ids": ["kb-1", "kb-2"]}),
    )

    result = await KnowledgeBaseImportAttachmentTool().call(context)

    assert result == (
        "error: Specify the target knowledge base because the current session "
        "does not resolve to exactly one. Current candidates: Docs, Handbook."
    )
    docs.import_wiki_sources.assert_not_awaited()
    handbook.import_wiki_sources.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_attachment_sanitizes_local_paths_in_errors(tmp_path):
    """Do not expose the downloaded attachment path in tool errors."""
    source = tmp_path / "guide.md"
    source.write_text("# Guide", encoding="utf-8")
    helper = _make_kb_helper("kb-1", "Docs")
    helper.import_wiki_sources.side_effect = ValueError(
        f"Markdown file is not valid UTF-8: {source}"
    )
    manager = _make_kb_manager(helper)
    context = _make_context([File(name=source.name, file=str(source))], manager)

    result = await KnowledgeBaseImportAttachmentTool().call(
        context,
        knowledge_base="kb-1",
    )

    assert result == (
        "error: Knowledge import failed: Markdown file is not valid UTF-8: guide.md"
    )
    assert str(source) not in result


@pytest.mark.asyncio
async def test_edit_and_delete_work_with_real_wiki_without_embeddings(tmp_path):
    """Edit and delete a lexical-only Wiki page without an embedding provider."""
    store = WikiStore(tmp_path / "kb", "kb-1")
    await store.initialize()
    try:
        await store.write_page(
            "notes/article.md",
            "# Article\n\nold searchable text",
            doc_id="doc-real",
        )
        helper = _make_kb_helper("kb-1", "Docs")
        helper.wiki_store = store
        helper._ensure_vec_db = AsyncMock(return_value=store)
        helper.get_document = AsyncMock(return_value=None)
        manager = _make_kb_manager(helper)
        context = _make_context([], manager)

        edit_result = await KnowledgeBaseEditPageTool().call(
            context,
            path="notes/article.md",
            old_text="old searchable text",
            replacement="new searchable text",
            knowledge_base="kb-1",
        )

        assert "Updated Wiki page notes/article.md" in edit_result
        updated = await store.read_page("notes/article.md")
        assert "new searchable text" in updated["content"]
        rows = await store.document_storage.get_documents(
            {"kb_doc_id": "doc-real"},
            offset=None,
            limit=None,
        )
        assert rows
        assert all(row["embedding"] is None for row in rows)

        delete_result = await KnowledgeBaseDeletePageTool().call(
            context,
            path="notes/article.md",
            expected_title="Article",
            confirm=True,
            knowledge_base="kb-1",
        )

        assert delete_result == "Deleted Wiki page notes/article.md from Docs (kb-1)."
        assert not (store.knowledge_dir / "notes" / "article.md").exists()
        assert await store.get_page_metadata("notes/article.md") is None
    finally:
        await store.close()
