import asyncio
import importlib
import json
import stat
import sys
import types
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from astrbot.core.db.vec_db.faiss_impl.document_storage import DocumentStorage
from astrbot.core.exceptions import KnowledgeBaseUploadError
from astrbot.core.knowledge_base.wiki import WikiStore


@pytest_asyncio.fixture
async def wiki_store(tmp_path):
    store = WikiStore(tmp_path / "kb-one", "kb-one")
    await store.initialize()
    try:
        yield store
    finally:
        await store.close()


@pytest_asyncio.fixture
async def legacy_kb_dir(tmp_path):
    kb_dir = tmp_path / "legacy-kb"
    kb_dir.mkdir()
    storage = DocumentStorage(str(kb_dir / "doc.db"))
    await storage.initialize()
    await storage.insert_documents_batch(
        doc_ids=["legacy-a-0", "legacy-a-1", "legacy-b-0"],
        texts=["alpha first", "alpha second", "beta only"],
        metadatas=[
            {
                "kb_id": "kb-legacy",
                "kb_doc_id": "doc-alpha",
                "chunk_index": 0,
                "source": "alpha.txt",
            },
            {
                "kb_id": "kb-legacy",
                "kb_doc_id": "doc-alpha",
                "chunk_index": 1,
                "source": "alpha.txt",
            },
            {
                "kb_id": "kb-legacy",
                "kb_doc_id": "doc-beta",
                "chunk_index": 0,
                "source": "beta.txt",
            },
        ],
    )
    await storage.close()
    return kb_dir


@pytest.fixture
def embedding_provider():
    provider = MagicMock()
    provider.get_dim.return_value = 2

    async def generate_embeddings(texts, **_kwargs):
        return [[float(index + 1), 0.5] for index, _text in enumerate(texts)]

    provider.get_embeddings_batch = AsyncMock(side_effect=generate_embeddings)
    provider.get_embedding = AsyncMock(return_value=[1.0, 0.5])
    return provider


@pytest.fixture
def kb_helper_class():
    original_manager = sys.modules.get("astrbot.core.provider.manager")
    original_helper = sys.modules.pop(
        "astrbot.core.knowledge_base.kb_helper",
        None,
    )
    stub_manager = types.ModuleType("astrbot.core.provider.manager")

    class ProviderManager: ...

    stub_manager.ProviderManager = ProviderManager
    sys.modules["astrbot.core.provider.manager"] = stub_manager
    try:
        module = importlib.import_module("astrbot.core.knowledge_base.kb_helper")
        yield module.KBHelper
    finally:
        sys.modules.pop("astrbot.core.knowledge_base.kb_helper", None)
        if original_helper is not None:
            sys.modules["astrbot.core.knowledge_base.kb_helper"] = original_helper
        if original_manager is not None:
            sys.modules["astrbot.core.provider.manager"] = original_manager
        else:
            sys.modules.pop("astrbot.core.provider.manager", None)


@pytest.mark.asyncio
async def test_wiki_stores_keep_pages_indexes_and_chunk_ids_isolated(tmp_path):
    first = WikiStore(tmp_path / "kb-one", "kb-one")
    second = WikiStore(tmp_path / "kb-two", "kb-two")
    await first.initialize()
    await second.initialize()

    try:
        first_page = await first.write_page(
            "notes/shared.md",
            "# First knowledge\n\nalpha-only material",
            doc_id="shared-document",
            chunks=["alpha-only material"],
        )
        second_page = await second.write_page(
            "notes/shared.md",
            "# Second knowledge\n\nbeta-only material",
            doc_id="shared-document",
            chunks=["beta-only material"],
        )

        first_rows = await first.document_storage.get_documents({})
        second_rows = await second.document_storage.get_documents({})

        assert first_page["path"] == second_page["path"] == "notes/shared.md"
        assert first.db_path != second.db_path
        assert first.knowledge_dir != second.knowledge_dir
        assert [row["text"] for row in first_rows] == ["alpha-only material"]
        assert [row["text"] for row in second_rows] == ["beta-only material"]
        assert first_rows[0]["doc_id"] != second_rows[0]["doc_id"]
        assert json.loads(first_rows[0]["metadata"])["kb_id"] == "kb-one"
        assert json.loads(second_rows[0]["metadata"])["kb_id"] == "kb-two"
        assert (
            "First knowledge" in (await first.read_page("notes/shared.md"))["content"]
        )
        assert (
            "Second knowledge" in (await second.read_page("notes/shared.md"))["content"]
        )
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_wiki_store_works_without_embedding_provider(wiki_store):
    progress_callback = AsyncMock()

    await wiki_store.insert_batch(
        contents=["agentic retrieval without vectors"],
        metadatas=[
            {
                "kb_id": "kb-one",
                "kb_doc_id": "doc-no-embedding",
                "chunk_index": 0,
            }
        ],
        ids=["chunk-no-embedding"],
        progress_callback=progress_callback,
    )

    assert await wiki_store.retrieve("agentic retrieval", k=5) == []
    assert await wiki_store.count_documents({"kb_doc_id": "doc-no-embedding"}) == 1
    progress_callback.assert_awaited_once_with(1, 1)


@pytest.mark.asyncio
async def test_wiki_sparse_search_supports_english_fts_and_chinese_like_fallback(
    wiki_store,
):
    await wiki_store.write_page(
        "search/hybrid.md",
        "# Hybrid search\n\nOrchestration combines lexical recall with 知识图谱检索。",
        doc_id="doc-search",
        chunks=["Orchestration combines lexical recall with 知识图谱检索。"],
    )

    if not wiki_store.fts5_available:
        pytest.skip("SQLite FTS5 is required to verify English sparse search")
    english_results = await wiki_store.search_sparse(["Orchestration"], limit=10)

    assert english_results is not None
    assert [result["text"] for result in english_results] == [
        "Orchestration combines lexical recall with 知识图谱检索。"
    ]

    wiki_store.fts5_available = False
    chinese_results = await wiki_store.search_sparse(["知识图谱"], limit=10)

    assert chinese_results is not None
    assert [result["text"] for result in chinese_results] == [
        "Orchestration combines lexical recall with 知识图谱检索。"
    ]


@pytest.mark.asyncio
async def test_markdown_and_wiki_links_create_graph_edges_and_backlinks(wiki_store):
    await wiki_store.write_page(
        "concepts/knowledge-graph.md",
        "# Knowledge Graph\n\nGraph concepts.",
        doc_id="doc-graph",
    )
    await wiki_store.write_page(
        "concepts/retrieval.md",
        "# Retrieval\n\nRetrieval concepts.",
        doc_id="doc-retrieval",
    )
    await wiki_store.write_page(
        "topics/agentic-rag.md",
        (
            "# Agentic RAG\n\n"
            "See [graph evidence](../concepts/knowledge-graph.md) and "
            "[[../concepts/retrieval|retrieval evidence]].\n\n"
            "Duplicate links are ignored: [[../concepts/knowledge-graph]]."
        ),
        doc_id="doc-agentic-rag",
    )

    source = await wiki_store.read_page("topics/agentic-rag.md")
    graph_target = await wiki_store.read_page("concepts/knowledge-graph.md")
    retrieval_target = await wiki_store.read_page("concepts/retrieval.md")
    graph = await wiki_store.get_graph()

    assert source["links"] == [
        {
            "target": "concepts/knowledge-graph.md",
            "relation": "links_to",
            "evidence": "graph evidence",
            "confidence": 1.0,
        },
        {
            "target": "concepts/retrieval.md",
            "relation": "links_to",
            "evidence": "retrieval evidence",
            "confidence": 1.0,
        },
    ]
    assert graph_target["backlinks"] == [
        {
            "source": "topics/agentic-rag.md",
            "relation": "links_to",
            "evidence": "graph evidence",
            "confidence": 1.0,
        }
    ]
    assert retrieval_target["backlinks"] == [
        {
            "source": "topics/agentic-rag.md",
            "relation": "links_to",
            "evidence": "retrieval evidence",
            "confidence": 1.0,
        }
    ]
    assert {node["id"] for node in graph["nodes"]} == {
        "concepts/knowledge-graph.md",
        "concepts/retrieval.md",
        "topics/agentic-rag.md",
    }
    assert {
        (edge["source"], edge["target"], edge["relation"]) for edge in graph["edges"]
    } == {
        ("topics/agentic-rag.md", "concepts/knowledge-graph.md", "links_to"),
        ("topics/agentic-rag.md", "concepts/retrieval.md", "links_to"),
    }


@pytest.mark.asyncio
async def test_typed_relation_lines_persist_graph_relation_and_evidence(wiki_store):
    """Preserve LLM-extracted relationship types in rebuildable Markdown."""
    await wiki_store.write_page(
        "entities/xiaomi.md",
        "# Xiaomi\n\nCompany.",
        doc_id="doc-xiaomi",
    )
    await wiki_store.write_page(
        "entities/pengcheng.md",
        (
            "# Pengcheng\n\n"
            "## Knowledge Relations\n\n"
            "- belongs_to: [[entities/xiaomi|Xiaomi]] — Described as a Xiaomi product."
        ),
        doc_id="doc-pengcheng",
    )

    page = await wiki_store.read_page("entities/pengcheng.md")
    graph = await wiki_store.get_graph()

    assert page["links"] == [
        {
            "target": "entities/xiaomi.md",
            "relation": "belongs_to",
            "evidence": "Described as a Xiaomi product.",
            "confidence": 1.0,
        }
    ]
    assert {
        (edge["source"], edge["target"], edge["relation"], edge["evidence"])
        for edge in graph["edges"]
    } == {
        (
            "entities/pengcheng.md",
            "entities/xiaomi.md",
            "belongs_to",
            "Described as a Xiaomi product.",
        )
    }


@pytest.mark.asyncio
async def test_initialize_validates_typed_relations_after_restart(tmp_path):
    """Validate a persisted typed graph edge when reopening a wiki store."""
    kb_dir = tmp_path / "kb-typed-restart"
    store = WikiStore(kb_dir, "kb-typed-restart")
    await store.initialize()
    await store.write_page(
        "entities/company.md",
        "# Company\n\nCompany entity.",
        doc_id="doc-company",
    )
    await store.write_page(
        "entities/product.md",
        (
            "# Product\n\n"
            "## Knowledge Relations\n\n"
            "- belongs_to: [[company|Company]] — Product ownership evidence."
        ),
        doc_id="doc-product",
    )
    await store.close()

    reopened = WikiStore(kb_dir, "kb-typed-restart")
    await reopened.initialize()
    try:
        graph = await reopened.get_graph()

        assert reopened._last_initialize_rebuilt is False
        assert {
            (
                edge["source"],
                edge["target"],
                edge["relation"],
                edge["evidence"],
            )
            for edge in graph["edges"]
        } == {
            (
                "entities/product.md",
                "entities/company.md",
                "belongs_to",
                "Product ownership evidence.",
            )
        }
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_relative_relation_resolves_before_target_page_exists(wiki_store):
    """Resolve structured source links correctly regardless of page write order."""
    await wiki_store.write_page(
        "sources/article.md",
        (
            "# Article\n\n"
            "## Knowledge Relations\n\n"
            "- mentions: [[../entities/xiaomi|Xiaomi]]"
        ),
        doc_id="doc-article",
    )
    await wiki_store.write_page(
        "entities/xiaomi.md",
        "# Xiaomi\n\nCompany.",
        doc_id="doc-xiaomi",
    )

    graph = await wiki_store.get_graph()

    assert {
        (edge["source"], edge["target"], edge["relation"]) for edge in graph["edges"]
    } == {("sources/article.md", "entities/xiaomi.md", "mentions")}


@pytest.mark.asyncio
async def test_metaclaw_directories_infer_graph_node_types(wiki_store):
    pages = {
        "entities/company.md": "# Company\n\nEntity page.",
        "concepts/method.md": "# Method\n\nConcept page.",
        "sources/report.md": "# Report\n\n> 来源：公开资料\n\nSource page.",
        "analysis/findings.md": "# Findings\n\nAnalysis page.",
        "playbooks/growth/chapter.md": "# Chapter\n\nPlaybook page.",
        "playbooks/growth/_index.md": "# Growth Playbook\n\nOverview page.",
        "entities/comparison.md": (
            "---\nnode_type: comparison\n---\n\n# Comparison\n\nExplicit type."
        ),
    }
    for index, (path, content) in enumerate(pages.items()):
        await wiki_store.write_page(path, content, doc_id=f"doc-meta-{index}")

    graph = await wiki_store.get_graph()
    nodes = {node["id"]: node for node in graph["nodes"]}

    assert nodes["entities/company.md"]["node_type"] == "entity"
    assert nodes["concepts/method.md"]["node_type"] == "concept"
    assert nodes["sources/report.md"]["node_type"] == "source"
    assert nodes["sources/report.md"]["source"] == "公开资料"
    assert nodes["sources/report.md"]["evidence"] == "Source page."
    assert nodes["analysis/findings.md"]["node_type"] == "synthesis"
    assert nodes["playbooks/growth/chapter.md"]["node_type"] == "concept"
    assert nodes["playbooks/growth/_index.md"]["node_type"] == "overview"
    assert nodes["entities/comparison.md"]["node_type"] == "comparison"


@pytest.mark.asyncio
async def test_metaclaw_links_support_page_and_knowledge_root_relative_paths(
    wiki_store,
):
    await wiki_store.write_page(
        "sources/local.md",
        "# Local source\n\nLocal page.",
        doc_id="doc-local-source",
    )
    await wiki_store.write_page(
        "analysis/root.md",
        "# Root analysis\n\nRoot page.",
        doc_id="doc-root-analysis",
    )
    await wiki_store.write_page(
        "sources/report.md",
        ("# Report\n\n[Local](local.md) and [Root relative](analysis/root.md)."),
        doc_id="doc-link-report",
    )

    graph = await wiki_store.get_graph()

    assert {(edge["source"], edge["target"]) for edge in graph["edges"]} == {
        ("sources/report.md", "sources/local.md"),
        ("sources/report.md", "analysis/root.md"),
    }


@pytest.mark.asyncio
async def test_initialize_rebuilds_legacy_other_node_types(tmp_path):
    kb_dir = tmp_path / "kb-meta-upgrade"
    store = WikiStore(kb_dir, "kb-meta-upgrade")
    await store.initialize()
    await store.write_page(
        "entities/company.md",
        "# Company\n\nEntity page.",
        doc_id="doc-company",
    )
    db = store._require_db()
    await db.execute(
        "UPDATE pages SET node_type = 'other' WHERE path = 'entities/company.md'"
    )
    await db.execute(
        "UPDATE graph_nodes SET node_type = 'other' WHERE id = 'entities/company.md'"
    )
    await db.commit()
    await store.close()

    reopened = WikiStore(kb_dir, "kb-meta-upgrade")
    await reopened.initialize()
    try:
        graph = await reopened.get_graph()

        assert reopened._last_initialize_rebuilt is True
        assert graph["nodes"][0]["node_type"] == "entity"
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_move_directory_preserves_doc_ids_and_rewrites_internal_links(
    wiki_store,
):
    entity = await wiki_store.write_page(
        "entities/company.md",
        "# Company\n\n[Method](../concepts/growth/method.md)",
        doc_id="doc-company",
    )
    method = await wiki_store.write_page(
        "concepts/growth/method.md",
        "# Method\n\n[Company](../../entities/company.md)",
        doc_id="doc-method",
    )

    result = await wiki_store.move_path(
        "concepts/growth",
        "playbooks/growth",
    )
    graph = await wiki_store.get_graph()
    moved_page = await wiki_store.read_page("playbooks/growth/method.md")
    entity_page = await wiki_store.read_page("entities/company.md")

    assert result["entry_type"] == "directory"
    assert result["moved"] == [
        {
            "doc_id": method["doc_id"],
            "title": "Method",
            "old_path": "concepts/growth/method.md",
            "new_path": "playbooks/growth/method.md",
        }
    ]
    assert moved_page["metadata"]["doc_id"] == method["doc_id"]
    assert entity_page["metadata"]["doc_id"] == entity["doc_id"]
    assert "../playbooks/growth/method.md" in entity_page["content"]
    assert "../../entities/company.md" in moved_page["content"]
    assert {(edge["source"], edge["target"]) for edge in graph["edges"]} == {
        ("entities/company.md", "playbooks/growth/method.md"),
        ("playbooks/growth/method.md", "entities/company.md"),
    }


@pytest.mark.asyncio
async def test_delete_directory_requires_recursive_and_removes_all_pages(wiki_store):
    await wiki_store.write_page(
        "analysis/first.md",
        "# First\n\nFirst page.",
        doc_id="doc-first",
    )
    await wiki_store.write_page(
        "analysis/nested/second.md",
        "# Second\n\nSecond page.",
        doc_id="doc-second",
    )
    await wiki_store.write_page(
        "entities/company.md",
        "# Company\n\nCompany page.",
        doc_id="doc-company",
    )

    with pytest.raises(ValueError, match="recursive=true"):
        await wiki_store.delete_path("analysis")

    result = await wiki_store.delete_path("analysis", recursive=True)
    graph = await wiki_store.get_graph()

    assert result["entry_type"] == "directory"
    assert {page["doc_id"] for page in result["deleted"]} == {
        "doc-first",
        "doc-second",
    }
    assert {node["id"] for node in graph["nodes"]} == {"entities/company.md"}
    assert not (wiki_store.knowledge_dir / "analysis").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../outside.md",
        "%2e%2e/outside.md",
        "..\\outside.md",
        "/absolute/outside.md",
    ],
)
async def test_wiki_page_paths_reject_traversal_and_absolute_paths(
    wiki_store,
    tmp_path,
    unsafe_path,
):
    outside_path = tmp_path / "outside.md"

    with pytest.raises(ValueError, match="wiki page path|knowledge directory"):
        await wiki_store.write_page(unsafe_path, "# Must not be written")

    assert not outside_path.exists()


@pytest.mark.asyncio
async def test_import_sources_preserves_directory_tree_and_normalizes_aliases(
    wiki_store,
    tmp_path,
):
    source_dir = tmp_path / "wiki-source"
    (source_dir / "guides" / "nested").mkdir(parents=True)
    (source_dir / "guides" / "intro.markdown").write_text(
        "# Intro\n\nDirectory import",
        encoding="utf-8",
    )
    (source_dir / "guides" / "nested" / "details.mdx").write_text(
        "# Details\n\nNested import",
        encoding="utf-8",
    )
    (source_dir / "index.md").write_text("# Reserved", encoding="utf-8")
    (source_dir / "notes.txt").write_text("ignored", encoding="utf-8")

    result = await wiki_store.import_sources([(source_dir, "manual")])

    assert {page["path"] for page in result["imported"]} == {
        "manual/guides/intro.md",
        "manual/guides/nested/details.md",
        "manual/index.md",
    }
    assert result["skipped"] == [{"path": "notes.txt", "reason": "unsupported"}]
    assert (
        "Directory import"
        in (await wiki_store.read_page("manual/guides/intro.md"))["content"]
    )


@pytest.mark.asyncio
async def test_import_sources_zip_preserves_tree_and_reports_skips(
    wiki_store,
    tmp_path,
):
    archive_path = tmp_path / "wiki.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("category/topic.markdown", "# Topic\n\nZIP import")
        archive.writestr("category/deep/page.mdx", "# Deep\n\nNested ZIP page")
        archive.writestr("index.md", "# Reserved")
        archive.writestr("asset.png", b"not-an-image")

    result = await wiki_store.import_sources([archive_path])

    assert {page["path"] for page in result["imported"]} == {
        "category/topic.md",
        "category/deep/page.md",
    }
    assert result["skipped"] == [
        {"path": "wiki.zip!/index.md", "reason": "reserved"},
        {"path": "wiki.zip!/asset.png", "reason": "unsupported"},
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../escape.md",
        "/absolute.md",
        "C:/drive.md",
        "folder/../escape.md",
        "bad\x00.md",
    ],
)
async def test_import_sources_rejects_unsafe_relative_paths(
    wiki_store,
    tmp_path,
    unsafe_path,
):
    source = tmp_path / "source.md"
    source.write_text("# Safe source", encoding="utf-8")

    with pytest.raises(ValueError, match="Import path"):
        await wiki_store.import_sources([(source, unsafe_path)])


@pytest.mark.asyncio
async def test_import_sources_rejects_zip_path_traversal(wiki_store, tmp_path):
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.md", "# Escape")

    with pytest.raises(ValueError, match="Import path"):
        await wiki_store.import_sources([archive_path])

    assert not (tmp_path / "escape.md").exists()


@pytest.mark.asyncio
async def test_import_sources_rejects_local_and_zip_symlinks(wiki_store, tmp_path):
    source = tmp_path / "source.md"
    source.write_text("# Source", encoding="utf-8")
    source_link = tmp_path / "source-link.md"
    try:
        source_link.symlink_to(source)
    except OSError:
        pass
    else:
        with pytest.raises(ValueError, match="Symbolic link"):
            await wiki_store.import_sources([source_link])

    archive_path = tmp_path / "symlink.zip"
    link_info = zipfile.ZipInfo("link.md")
    link_info.create_system = 3
    link_info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(link_info, "target.md")

    with pytest.raises(ValueError, match="symbolic links"):
        await wiki_store.import_sources([archive_path])


@pytest.mark.asyncio
async def test_import_sources_rejects_normalized_and_case_duplicates(
    wiki_store,
    tmp_path,
):
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("# First", encoding="utf-8")
    second.write_text("# Second", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate or case-conflicting"):
        await wiki_store.import_sources(
            [
                (first, "Topics/Shared.markdown"),
                (second, "topics/shared.mdx"),
            ]
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [b"\xff\xfe", b"  \n\t"])
async def test_import_sources_rejects_invalid_or_empty_markdown(
    wiki_store,
    tmp_path,
    content,
):
    source = tmp_path / "invalid.md"
    source.write_bytes(content)

    with pytest.raises(ValueError, match="valid UTF-8|is empty") as exc_info:
        await wiki_store.import_sources([source])

    assert str(source) not in str(exc_info.value)
    assert "invalid.md" in str(exc_info.value)


@pytest.mark.asyncio
async def test_import_sources_conflict_preflight_writes_nothing(
    wiki_store,
    tmp_path,
):
    await wiki_store.write_page("existing.md", "# Existing\n\nold marker")
    new_source = tmp_path / "new.md"
    conflict_source = tmp_path / "conflict.md"
    new_source.write_text("# New\n\nnew marker", encoding="utf-8")
    conflict_source.write_text("# Replacement", encoding="utf-8")

    with pytest.raises(FileExistsError):
        await wiki_store.import_sources(
            [(new_source, "new.md"), (conflict_source, "existing.md")]
        )

    assert not (wiki_store.knowledge_dir / "new.md").exists()
    assert "old marker" in (await wiki_store.read_page("existing.md"))["content"]


@pytest.mark.asyncio
async def test_import_sources_rebuild_failure_restores_all_files_and_old_index(
    wiki_store,
    tmp_path,
    monkeypatch,
):
    await wiki_store.write_page("existing.md", "# Existing\n\nold-index-marker")
    replacement = tmp_path / "replacement.md"
    new_source = tmp_path / "new.md"
    replacement.write_text("# Existing\n\nreplacement marker", encoding="utf-8")
    new_source.write_text("# New\n\nnew marker", encoding="utf-8")

    async def fail_rebuild():
        raise RuntimeError("rebuild failed")

    monkeypatch.setattr(wiki_store, "_rebuild_index_locked", fail_rebuild)

    with pytest.raises(RuntimeError, match="rebuild failed"):
        await wiki_store.import_sources(
            [(replacement, "existing.md"), (new_source, "new.md")],
            overwrite=True,
        )

    assert "old-index-marker" in (wiki_store.knowledge_dir / "existing.md").read_text(
        encoding="utf-8"
    )
    assert not (wiki_store.knowledge_dir / "new.md").exists()
    results = await wiki_store.search_sparse(["old-index-marker"], limit=10)
    assert results and any("old-index-marker" in row["text"] for row in results)


@pytest.mark.asyncio
async def test_import_sources_overwrite_preserves_document_id(wiki_store, tmp_path):
    original = await wiki_store.write_page(
        "topics/overwrite.md",
        "# Original\n\nold content",
    )
    source = tmp_path / "replacement.markdown"
    source.write_text("# Replacement\n\nnew content", encoding="utf-8")

    result = await wiki_store.import_sources(
        [(source, "topics/overwrite.markdown")],
        overwrite=True,
    )

    imported = result["imported"][0]
    page = await wiki_store.read_page("topics/overwrite.md")
    assert imported["doc_id"] == original["doc_id"]
    assert page["metadata"]["doc_id"] == original["doc_id"]
    assert "new content" in page["content"]


@pytest.mark.asyncio
async def test_import_sources_has_no_file_count_limit(wiki_store, tmp_path):
    source_dir = tmp_path / "many-pages"
    source_dir.mkdir()
    for index in range(12):
        (source_dir / f"page-{index}.md").write_text(
            f"# Page {index}\n\ncontent {index}",
            encoding="utf-8",
        )

    result = await wiki_store.import_sources([source_dir])

    assert result["imported_count"] == 12


@pytest.mark.asyncio
async def test_rebuild_index_restores_derived_state_from_markdown(wiki_store):
    await wiki_store.write_page(
        "notes/rebuild.md",
        "# Rebuild source\n\nold-index-marker",
        doc_id="doc-rebuild",
        chunks=["old-index-marker"],
    )
    page_path = wiki_store.knowledge_dir / "notes" / "rebuild.md"
    page_path.write_text(
        page_path.read_text(encoding="utf-8").replace(
            "old-index-marker", "new-index-marker"
        ),
        encoding="utf-8",
    )

    rebuilt = await wiki_store.rebuild_index()
    old_results = await wiki_store.search_sparse(["old-index-marker"], limit=10)
    new_results = await wiki_store.search_sparse(["new-index-marker"], limit=10)
    page = await wiki_store.read_page("notes/rebuild.md")

    assert rebuilt["pages"] == 1
    assert rebuilt["chunks"] == await wiki_store.count_documents()
    assert old_results == []
    assert new_results is not None
    assert any("new-index-marker" in result["text"] for result in new_results)
    assert page["metadata"]["doc_id"] == "doc-rebuild"
    assert "new-index-marker" in page["content"]


@pytest.mark.asyncio
async def test_initialize_migrates_legacy_doc_db_once_and_preserves_chunk_ids(
    legacy_kb_dir,
):
    store = WikiStore(legacy_kb_dir, "kb-legacy")
    await store.initialize()
    try:
        rows = await store.document_storage.get_documents({}, offset=None, limit=None)
        tree = await store.list_tree()
        markdown_paths = sorted(
            path.relative_to(store.knowledge_dir).as_posix()
            for path in store.knowledge_dir.rglob("*.md")
            if path.name not in {"index.md", "log.md"}
        )

        assert tree["page_count"] == 2
        assert len(markdown_paths) == 2
        assert {row["doc_id"] for row in rows} == {
            "legacy-a-0",
            "legacy-a-1",
            "legacy-b-0",
        }
        assert {json.loads(row["metadata"])["kb_doc_id"] for row in rows} == {
            "doc-alpha",
            "doc-beta",
        }
    finally:
        await store.close()

    second = WikiStore(legacy_kb_dir, "kb-legacy")
    await second.initialize()
    try:
        second_rows = await second.document_storage.get_documents(
            {}, offset=None, limit=None
        )
        second_tree = await second.list_tree()

        assert second_tree["page_count"] == 2
        assert {row["doc_id"] for row in second_rows} == {
            "legacy-a-0",
            "legacy-a-1",
            "legacy-b-0",
        }
    finally:
        await second.close()


@pytest.mark.asyncio
async def test_legacy_migration_generates_embeddings_for_dense_retrieval(
    legacy_kb_dir,
    embedding_provider,
):
    store = WikiStore(
        legacy_kb_dir,
        "kb-legacy",
        embedding_provider=embedding_provider,
    )
    await store.initialize()
    try:
        rows = await store.document_storage.get_documents({}, offset=None, limit=None)
        dense_results = await store.retrieve("alpha", k=3)
        marker = json.loads(store.legacy_migration_path.read_text(encoding="utf-8"))

        assert all(row["embedding"] is not None for row in rows)
        assert {result.data["doc_id"] for result in dense_results} == {
            "legacy-a-0",
            "legacy-a-1",
            "legacy-b-0",
        }
        assert marker["state"] == "complete"
        assert embedding_provider.get_embeddings_batch.await_count == 2
        embedding_provider.get_embedding.assert_awaited_once_with("alpha")
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_legacy_migration_embedding_failure_does_not_mark_complete(
    legacy_kb_dir,
    embedding_provider,
):
    embedding_provider.get_embeddings_batch.side_effect = RuntimeError(
        "embedding unavailable"
    )
    failed = WikiStore(
        legacy_kb_dir,
        "kb-legacy",
        embedding_provider=embedding_provider,
    )
    try:
        with pytest.raises(KnowledgeBaseUploadError) as exc_info:
            await failed.initialize()
        marker = json.loads(failed.legacy_migration_path.read_text(encoding="utf-8"))
        assert exc_info.value.stage == "embedding"
        assert marker["state"] == "failed"
    finally:
        await failed.close()

    async def generate_embeddings(texts, **_kwargs):
        return [[float(index + 1), 0.5] for index, _text in enumerate(texts)]

    embedding_provider.get_embeddings_batch.side_effect = generate_embeddings
    resumed = WikiStore(
        legacy_kb_dir,
        "kb-legacy",
        embedding_provider=embedding_provider,
    )
    await resumed.initialize()
    try:
        rows = await resumed.document_storage.get_documents({}, offset=None, limit=None)
        marker = json.loads(resumed.legacy_migration_path.read_text(encoding="utf-8"))
        assert marker["state"] == "complete"
        assert all(row["embedding"] is not None for row in rows)
    finally:
        await resumed.close()


@pytest.mark.asyncio
async def test_rebuild_preserves_legacy_chunk_ids_after_wiki_db_is_deleted(
    legacy_kb_dir,
):
    store = WikiStore(legacy_kb_dir, "kb-legacy")
    await store.initialize()
    try:
        first_rows = await store.document_storage.get_documents(
            {}, offset=None, limit=None
        )
        marker = json.loads(store.legacy_migration_path.read_text(encoding="utf-8"))
    finally:
        await store.close()

    assert marker["state"] == "complete"
    assert marker["documents"]["doc-alpha"]["chunk_ids"] == [
        "legacy-a-0",
        "legacy-a-1",
    ]
    assert len(marker["documents"]["doc-alpha"]["chunk_sha256"]) == 2

    store.db_path.unlink()
    rebuilt = WikiStore(legacy_kb_dir, "kb-legacy")
    await rebuilt.initialize()
    try:
        rebuilt_rows = await rebuilt.document_storage.get_documents(
            {}, offset=None, limit=None
        )
        assert [row["doc_id"] for row in rebuilt_rows] == [
            row["doc_id"] for row in first_rows
        ]
    finally:
        await rebuilt.close()


@pytest.mark.asyncio
async def test_rebuild_stops_reusing_legacy_chunk_ids_after_content_changes(
    legacy_kb_dir,
):
    store = WikiStore(legacy_kb_dir, "kb-legacy")
    await store.initialize()
    page_path = await store.page_path_for_doc_id("doc-alpha")
    assert page_path is not None
    markdown_path = store.knowledge_dir / page_path
    original_content = markdown_path.read_text(encoding="utf-8")
    markdown_path.write_text(
        original_content.replace("alpha second", "alpha second edited"),
        encoding="utf-8",
    )
    await store.close()

    store.db_path.unlink()
    rebuilt = WikiStore(legacy_kb_dir, "kb-legacy")
    await rebuilt.initialize()
    try:
        alpha_rows = await rebuilt.document_storage.get_documents(
            {"kb_doc_id": "doc-alpha"}, offset=None, limit=None
        )
        assert [row["doc_id"] for row in alpha_rows] != [
            "legacy-a-0",
            "legacy-a-1",
        ]
        assert all(
            row["doc_id"] not in {"legacy-a-0", "legacy-a-1"} for row in alpha_rows
        )
    finally:
        await rebuilt.close()


@pytest.mark.asyncio
async def test_legacy_migration_failure_can_resume_without_duplicate_pages(
    legacy_kb_dir,
    monkeypatch,
):
    original_index_page = WikiStore._index_page
    failed_once = False

    async def fail_second_document(self, rel_path, content, *args, **kwargs):
        nonlocal failed_once
        if not failed_once and kwargs.get("doc_id") == "doc-beta":
            failed_once = True
            raise RuntimeError("simulated migration interruption")
        return await original_index_page(self, rel_path, content, *args, **kwargs)

    monkeypatch.setattr(WikiStore, "_index_page", fail_second_document)
    interrupted = WikiStore(legacy_kb_dir, "kb-legacy")
    try:
        with pytest.raises(RuntimeError, match="migration interruption"):
            await interrupted.initialize()
    finally:
        await interrupted.close()

    monkeypatch.setattr(WikiStore, "_index_page", original_index_page)
    resumed = WikiStore(legacy_kb_dir, "kb-legacy")
    await resumed.initialize()
    try:
        rows = await resumed.document_storage.get_documents({}, offset=None, limit=None)
        tree = await resumed.list_tree()

        assert tree["page_count"] == 2
        assert {row["doc_id"] for row in rows} == {
            "legacy-a-0",
            "legacy-a-1",
            "legacy-b-0",
        }
        assert len(rows) == 3
    finally:
        await resumed.close()


@pytest.mark.asyncio
async def test_write_page_generates_embeddings_when_provider_is_configured(
    tmp_path,
    embedding_provider,
):
    store = WikiStore(
        tmp_path / "kb-embedding",
        "kb-embedding",
        embedding_provider=embedding_provider,
    )
    await store.initialize()
    try:
        await store.write_page(
            "notes/dense.md",
            "# Dense page\n\nfirst dense chunk\n\nsecond dense chunk",
            doc_id="doc-dense",
            chunks=["first dense chunk", "second dense chunk"],
        )
        rows = await store.document_storage.get_documents(
            {"kb_doc_id": "doc-dense"}, offset=None, limit=None
        )

        embedding_provider.get_embeddings_batch.assert_awaited_once()
        assert [json.loads(row["embedding"]) for row in rows] == [
            [1.0, 0.5],
            [2.0, 0.5],
        ]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_write_page_rejects_invalid_embedding_dimension_atomically(
    tmp_path,
    embedding_provider,
):
    embedding_provider.get_embeddings_batch.side_effect = None
    embedding_provider.get_embeddings_batch.return_value = [[0.1, 0.2, 0.3]]
    store = WikiStore(
        tmp_path / "kb-invalid-embedding",
        "kb-invalid-embedding",
        embedding_provider=embedding_provider,
    )
    await store.initialize()
    try:
        with pytest.raises(KnowledgeBaseUploadError) as exc_info:
            await store.write_page(
                "notes/invalid.md",
                "# Invalid vector\n\ncontent",
                doc_id="doc-invalid",
                chunks=["content"],
            )

        assert exc_info.value.stage == "embedding"
        assert not (store.knowledge_dir / "notes" / "invalid.md").exists()
        assert await store.get_page_metadata("notes/invalid.md") is None
        assert await store.count_documents({"kb_doc_id": "doc-invalid"}) == 0
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_rebuild_index_regenerates_embeddings_from_markdown(
    tmp_path,
    embedding_provider,
):
    store = WikiStore(
        tmp_path / "kb-rebuild-embedding",
        "kb-rebuild-embedding",
        embedding_provider=embedding_provider,
    )
    await store.initialize()
    try:
        await store.write_page(
            "notes/rebuild-dense.md",
            "# Rebuild dense\n\nembedding source text",
            doc_id="doc-rebuild-dense",
            chunks=["embedding source text"],
            embeddings=[[9.0, 9.0]],
        )
        embedding_provider.get_embeddings_batch.reset_mock()

        await store.rebuild_index()
        rows = await store.document_storage.get_documents(
            {"kb_doc_id": "doc-rebuild-dense"}, offset=None, limit=None
        )

        embedding_provider.get_embeddings_batch.assert_awaited_once()
        assert rows
        assert all(row["embedding"] is not None for row in rows)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_rebuild_embedding_failure_keeps_previous_derived_index(
    tmp_path,
    embedding_provider,
):
    store = WikiStore(
        tmp_path / "kb-rebuild-invalid-embedding",
        "kb-rebuild-invalid-embedding",
        embedding_provider=embedding_provider,
    )
    await store.initialize()
    try:
        await store.write_page(
            "notes/stable.md",
            "# Stable page\n\nstable indexed content",
            doc_id="doc-stable",
            chunks=["stable indexed content"],
            embeddings=[[9.0, 9.0]],
        )
        before = await store.document_storage.get_documents(
            {"kb_doc_id": "doc-stable"}, offset=None, limit=None
        )
        embedding_provider.get_embeddings_batch.side_effect = None
        embedding_provider.get_embeddings_batch.return_value = [[0.1, 0.2, 0.3]]

        with pytest.raises(KnowledgeBaseUploadError) as exc_info:
            await store.rebuild_index()

        after = await store.document_storage.get_documents(
            {"kb_doc_id": "doc-stable"}, offset=None, limit=None
        )
        assert exc_info.value.stage == "embedding"
        assert [row["doc_id"] for row in after] == [row["doc_id"] for row in before]
        assert [row["embedding"] for row in after] == [
            row["embedding"] for row in before
        ]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_kb_helper_rejects_single_chunk_delete_without_mutating_wiki(
    wiki_store,
    kb_helper_class,
):
    await wiki_store.write_page(
        "notes/immutable-chunks.md",
        "# Immutable chunks\n\nfirst chunk\n\nsecond chunk",
        doc_id="doc-immutable",
        chunks=["first chunk", "second chunk"],
    )
    before_rows = await wiki_store.document_storage.get_documents(
        {"kb_doc_id": "doc-immutable"}, offset=None, limit=None
    )
    before_content = (
        wiki_store.knowledge_dir / "notes" / "immutable-chunks.md"
    ).read_text(encoding="utf-8")

    helper = kb_helper_class.__new__(kb_helper_class)
    helper.kb = SimpleNamespace(kb_id="kb-one")
    helper.wiki_store = wiki_store
    helper.vec_db = wiki_store
    helper.kb_db = MagicMock()
    helper.kb_db.get_document_by_id = AsyncMock(
        return_value=SimpleNamespace(kb_id="kb-one", doc_id="doc-immutable")
    )
    helper.kb_db.update_kb_stats = AsyncMock()
    helper.refresh_kb = AsyncMock()
    helper.refresh_document = AsyncMock()

    with pytest.raises(ValueError, match=r"Wiki.*(?:不支持|禁止).*单.*块"):
        await helper.delete_chunk(before_rows[0]["doc_id"], "doc-immutable")

    after_rows = await wiki_store.document_storage.get_documents(
        {"kb_doc_id": "doc-immutable"}, offset=None, limit=None
    )
    after_content = (
        wiki_store.knowledge_dir / "notes" / "immutable-chunks.md"
    ).read_text(encoding="utf-8")
    assert [row["doc_id"] for row in after_rows] == [
        row["doc_id"] for row in before_rows
    ]
    assert after_content == before_content
    helper.kb_db.update_kb_stats.assert_not_awaited()
    helper.refresh_kb.assert_not_awaited()
    helper.refresh_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_kb_helper_import_wiki_sources_syncs_document_metadata(
    wiki_store,
    kb_helper_class,
    tmp_path,
):
    source = tmp_path / "helper-import.md"
    source.write_text("# Helper import\n\nmetadata sync", encoding="utf-8")

    class AsyncContext:
        def __init__(self, value=None):
            self.value = value

        async def __aenter__(self):
            return self.value

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    session = MagicMock()
    session.begin.return_value = AsyncContext()
    helper = kb_helper_class.__new__(kb_helper_class)
    helper.kb = SimpleNamespace(kb_id="kb-one")
    helper.kb_db = MagicMock()
    helper.kb_db.get_document_by_id = AsyncMock(return_value=None)
    helper.kb_db.get_db.return_value = AsyncContext(session)
    helper.kb_db.update_kb_stats = AsyncMock()
    helper._ensure_vec_db = AsyncMock(return_value=wiki_store)
    helper.refresh_kb = AsyncMock()

    result = await helper.import_wiki_sources([(source, "manual/helper.md")])

    assert result["paths"] == ["manual/helper.md"]
    assert result["documents"][0]["file_path"] == "manual/helper.md"
    document = session.add.call_args.args[0]
    assert document.kb_id == "kb-one"
    assert document.doc_name == "Helper import"
    assert document.chunk_count == result["imported"][0]["chunk_count"]
    helper.kb_db.update_kb_stats.assert_awaited_once_with(
        kb_id="kb-one",
        vec_db=wiki_store,
    )
    helper.refresh_kb.assert_awaited_once()


@pytest.mark.asyncio
async def test_kb_helper_import_wiki_sources_rolls_back_when_metadata_fails(
    wiki_store,
    kb_helper_class,
    tmp_path,
):
    source = tmp_path / "retry-import.md"
    source.write_text("# Retry import\n\nmetadata retry", encoding="utf-8")

    class AsyncContext:
        def __init__(self, value=None, error=None):
            self.value = value
            self.error = error

        async def __aenter__(self):
            if self.error is not None:
                raise self.error
            return self.value

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    helper = kb_helper_class.__new__(kb_helper_class)
    helper.kb = SimpleNamespace(kb_id="kb-one")
    helper.kb_db = MagicMock()
    helper.kb_db.get_document_by_id = AsyncMock(return_value=None)
    helper.kb_db.get_db.return_value = AsyncContext(
        error=RuntimeError("metadata unavailable")
    )
    helper.kb_db.update_kb_stats = AsyncMock()
    helper._ensure_vec_db = AsyncMock(return_value=wiki_store)
    helper.refresh_kb = AsyncMock()

    with pytest.raises(RuntimeError, match="metadata unavailable"):
        await helper.import_wiki_sources([(source, "manual/retry.md")])

    assert not (wiki_store.knowledge_dir / "manual" / "retry.md").exists()
    assert await wiki_store.get_page_metadata("manual/retry.md") is None

    session = MagicMock()
    session.begin.return_value = AsyncContext()
    helper.kb_db.get_db.return_value = AsyncContext(session)
    result = await helper.import_wiki_sources([(source, "manual/retry.md")])

    assert result["paths"] == ["manual/retry.md"]
    assert (wiki_store.knowledge_dir / "manual" / "retry.md").is_file()


@pytest.mark.asyncio
async def test_kb_helper_import_wiki_sources_keeps_overwrite_for_safe_retry(
    wiki_store,
    kb_helper_class,
    tmp_path,
):
    """Keep an overwritten page when metadata fails so overwrite can be retried."""
    await wiki_store.write_page("manual/existing.md", "# Existing\n\nold content")
    source = tmp_path / "replacement.md"
    source.write_text("# Replacement\n\nnew content", encoding="utf-8")

    class AsyncContext:
        async def __aenter__(self):
            raise RuntimeError("metadata unavailable")

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    helper = kb_helper_class.__new__(kb_helper_class)
    helper.kb = SimpleNamespace(kb_id="kb-one")
    helper.kb_db = MagicMock()
    helper.kb_db.get_document_by_id = AsyncMock(return_value=None)
    helper.kb_db.get_db.return_value = AsyncContext()
    helper.kb_db.update_kb_stats = AsyncMock()
    helper._ensure_vec_db = AsyncMock(return_value=wiki_store)
    helper.refresh_kb = AsyncMock()

    with pytest.raises(RuntimeError, match="metadata unavailable"):
        await helper.import_wiki_sources(
            [(source, "manual/existing.md")],
            overwrite=True,
        )

    page = await wiki_store.read_page("manual/existing.md")
    assert "new content" in page["content"]


@pytest.mark.asyncio
async def test_kb_helper_import_wiki_sources_keeps_success_when_stats_fail(
    wiki_store,
    kb_helper_class,
    tmp_path,
):
    source = tmp_path / "stats-import.md"
    source.write_text("# Stats import\n\nmetadata is durable", encoding="utf-8")

    class AsyncContext:
        def __init__(self, value=None):
            self.value = value

        async def __aenter__(self):
            return self.value

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    session = MagicMock()
    session.begin.return_value = AsyncContext()
    helper = kb_helper_class.__new__(kb_helper_class)
    helper.kb = SimpleNamespace(kb_id="kb-one")
    helper.kb_db = MagicMock()
    helper.kb_db.get_document_by_id = AsyncMock(return_value=None)
    helper.kb_db.get_db.return_value = AsyncContext(session)
    helper.kb_db.update_kb_stats = AsyncMock(
        side_effect=RuntimeError("statistics unavailable")
    )
    helper._ensure_vec_db = AsyncMock(return_value=wiki_store)
    helper.refresh_kb = AsyncMock()

    result = await helper.import_wiki_sources([(source, "manual/stats.md")])

    assert result["paths"] == ["manual/stats.md"]
    assert result["warnings"][0]["stage"] == "statistics"
    assert (wiki_store.knowledge_dir / "manual" / "stats.md").is_file()
    helper.refresh_kb.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_document_storage_preserves_chunk_shape(wiki_store):
    internal_ids = await wiki_store.insert_batch(
        contents=["first compatibility chunk", "second compatibility chunk"],
        metadatas=[
            {
                "kb_id": "kb-one",
                "kb_doc_id": "doc-legacy",
                "chunk_index": 0,
                "custom": "value",
            },
            {
                "kb_id": "kb-one",
                "kb_doc_id": "doc-legacy",
                "chunk_index": 1,
                "custom": "value",
            },
        ],
        ids=["chunk-legacy-0", "chunk-legacy-1"],
    )

    rows = await wiki_store.document_storage.get_documents(
        {"kb_doc_id": "doc-legacy"},
        offset=None,
        limit=None,
    )
    sparse_rows = await wiki_store.document_storage.search_sparse(
        ["compatibility"], limit=10
    )

    assert all(isinstance(internal_id, int) for internal_id in internal_ids)
    assert [row["doc_id"] for row in rows] == [
        "chunk-legacy-0",
        "chunk-legacy-1",
    ]
    assert all(
        {
            "id",
            "doc_id",
            "text",
            "metadata",
            "embedding",
            "created_at",
            "updated_at",
        }
        <= row.keys()
        for row in rows
    )
    assert [json.loads(row["metadata"])["chunk_index"] for row in rows] == [0, 1]
    assert all(json.loads(row["metadata"])["kb_id"] == "kb-one" for row in rows)
    assert all(json.loads(row["metadata"])["kb_doc_id"] == "doc-legacy" for row in rows)
    assert all(
        json.loads(row["metadata"])["page_path"] == "legacy/doc-legacy.md"
        for row in rows
    )
    assert sparse_rows is not None
    assert {row["doc_id"] for row in sparse_rows} == {
        "chunk-legacy-0",
        "chunk-legacy-1",
    }
    assert all("score" in row for row in sparse_rows)


@pytest.mark.asyncio
async def test_write_page_keeps_committed_content_when_index_refresh_fails(
    wiki_store,
    monkeypatch,
):
    await wiki_store.write_page(
        "notes/refresh.md",
        "# Refresh\n\nold content",
        doc_id="doc-refresh",
        chunks=["old content"],
    )
    monkeypatch.setattr(
        wiki_store,
        "_refresh_reserved_pages",
        AsyncMock(side_effect=OSError("index.md is temporarily unavailable")),
    )

    await wiki_store.write_page(
        "notes/refresh.md",
        "# Refresh\n\nnew content",
        doc_id="doc-refresh",
        chunks=["new content"],
    )

    persisted = (wiki_store.knowledge_dir / "notes" / "refresh.md").read_text(
        encoding="utf-8"
    )
    rows = await wiki_store.document_storage.get_documents(
        {"kb_doc_id": "doc-refresh"}, offset=None, limit=None
    )
    assert "new content" in persisted
    assert [row["text"] for row in rows] == ["new content"]


@pytest.mark.asyncio
async def test_write_page_create_and_update_guards_share_operation_lock(wiki_store):
    results = await asyncio.gather(
        wiki_store.write_page(
            "notes/create-once.md",
            "# First\n\nfirst body",
            create_only=True,
        ),
        wiki_store.write_page(
            "notes/create-once.md",
            "# Second\n\nsecond body",
            create_only=True,
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(result, dict) for result in results) == 1
    assert sum(isinstance(result, FileExistsError) for result in results) == 1
    with pytest.raises(FileNotFoundError):
        await wiki_store.write_page(
            "notes/missing.md",
            "# Missing\n\nbody",
            require_existing=True,
        )


@pytest.mark.asyncio
async def test_initialize_reconciles_external_markdown_edits(tmp_path):
    kb_dir = tmp_path / "kb-reconcile"
    store = WikiStore(kb_dir, "kb-reconcile")
    await store.initialize()
    await store.write_page(
        "notes/external.md",
        "# External\n\nold external value",
        doc_id="doc-external",
        chunks=["old external value"],
    )
    page_path = store.knowledge_dir / "notes" / "external.md"
    await store.close()
    page_path.write_text(
        page_path.read_text(encoding="utf-8").replace(
            "old external value", "new external value"
        ),
        encoding="utf-8",
    )

    reopened = WikiStore(kb_dir, "kb-reconcile")
    await reopened.initialize()
    try:
        rows = await reopened.document_storage.get_documents(
            {"kb_doc_id": "doc-external"}, offset=None, limit=None
        )
        assert any("new external value" in row["text"] for row in rows)
        assert all("doc_id:" not in row["text"] for row in rows)
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_initialize_rebuilds_when_embedding_capability_changes(
    tmp_path,
    embedding_provider,
):
    kb_dir = tmp_path / "kb-embedding-reconcile"
    lexical_store = WikiStore(kb_dir, "kb-embedding-reconcile")
    await lexical_store.initialize()
    try:
        await lexical_store.write_page(
            "notes/page.md",
            "# Page\n\nreconcile embedding content",
            doc_id="doc-embedding-reconcile",
        )
    finally:
        await lexical_store.close()

    embedding_provider.get_embeddings_batch.reset_mock()
    dense_store = WikiStore(
        kb_dir,
        "kb-embedding-reconcile",
        embedding_provider=embedding_provider,
    )
    await dense_store.initialize()
    try:
        rows = await dense_store.document_storage.get_documents(
            {"kb_doc_id": "doc-embedding-reconcile"},
            offset=None,
            limit=None,
        )
        assert rows
        assert all(row["embedding"] is not None for row in rows)
        embedding_provider.get_embeddings_batch.assert_awaited_once()
    finally:
        await dense_store.close()


@pytest.mark.asyncio
async def test_initialize_recovers_corrupt_derived_database(tmp_path):
    kb_dir = tmp_path / "kb-corrupt"
    store = WikiStore(kb_dir, "kb-corrupt")
    await store.initialize()
    await store.write_page(
        "notes/durable.md",
        "# Durable\n\nmarkdown survives",
        doc_id="doc-durable",
        chunks=["markdown survives"],
    )
    db_path = store.db_path
    await store.close()
    db_path.write_bytes(b"not a sqlite database")

    recovered = WikiStore(kb_dir, "kb-corrupt")
    await recovered.initialize()
    try:
        rows = await recovered.document_storage.get_documents(
            {"kb_doc_id": "doc-durable"}, offset=None, limit=None
        )
        assert rows
        assert any("markdown survives" in row["text"] for row in rows)
    finally:
        await recovered.close()


@pytest.mark.asyncio
async def test_rebuild_rejects_duplicate_doc_ids_without_changing_index(wiki_store):
    await wiki_store.write_page(
        "notes/first.md",
        "# First\n\nfirst stable body",
        doc_id="doc-first",
        chunks=["first stable body"],
    )
    await wiki_store.write_page(
        "notes/second.md",
        "# Second\n\nsecond stable body",
        doc_id="doc-second",
        chunks=["second stable body"],
    )
    before = await wiki_store.document_storage.get_documents(
        {}, offset=None, limit=None
    )
    second_path = wiki_store.knowledge_dir / "notes" / "second.md"
    second_path.write_text(
        second_path.read_text(encoding="utf-8").replace("doc-second", "doc-first"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate wiki doc_id"):
        await wiki_store.rebuild_index()

    after = await wiki_store.document_storage.get_documents({}, offset=None, limit=None)
    assert [(row["doc_id"], row["text"]) for row in after] == [
        (row["doc_id"], row["text"]) for row in before
    ]


@pytest.mark.asyncio
async def test_rebuild_rolls_back_all_rows_when_later_page_fails(
    wiki_store,
    monkeypatch,
):
    await wiki_store.write_page(
        "notes/first.md",
        "# First\n\nfirst stable body",
        doc_id="doc-first",
        chunks=["first stable body"],
    )
    await wiki_store.write_page(
        "notes/second.md",
        "# Second\n\nsecond stable body",
        doc_id="doc-second",
        chunks=["second stable body"],
    )
    before = await wiki_store.document_storage.get_documents(
        {}, offset=None, limit=None
    )
    original_write_rows = wiki_store._write_page_index_rows

    async def fail_second_page(db, **kwargs):
        if kwargs["rel_path"] == "notes/second.md":
            raise RuntimeError("simulated second page failure")
        return await original_write_rows(db, **kwargs)

    monkeypatch.setattr(wiki_store, "_write_page_index_rows", fail_second_page)
    with pytest.raises(RuntimeError, match="second page failure"):
        await wiki_store.rebuild_index()

    after = await wiki_store.document_storage.get_documents({}, offset=None, limit=None)
    assert [(row["doc_id"], row["text"]) for row in after] == [
        (row["doc_id"], row["text"]) for row in before
    ]


@pytest.mark.asyncio
async def test_missing_migration_marker_never_overwrites_edited_markdown(legacy_kb_dir):
    store = WikiStore(legacy_kb_dir, "kb-legacy")
    await store.initialize()
    page_path = await store.page_path_for_doc_id("doc-alpha")
    assert page_path is not None
    markdown_path = store.knowledge_dir / page_path
    await store.close()
    markdown_path.write_text(
        markdown_path.read_text(encoding="utf-8").replace(
            "alpha second", "user edited truth"
        ),
        encoding="utf-8",
    )
    store.legacy_migration_path.unlink()

    recovered = WikiStore(legacy_kb_dir, "kb-legacy")
    await recovered.initialize()
    try:
        assert "user edited truth" in markdown_path.read_text(encoding="utf-8")
        marker = json.loads(recovered.legacy_migration_path.read_text(encoding="utf-8"))
        assert marker["state"] == "complete"
    finally:
        await recovered.close()


@pytest.mark.asyncio
async def test_frontmatter_is_excluded_from_summary_and_retrieval_chunks(wiki_store):
    page = await wiki_store.write_page(
        "notes/body-only.md",
        "# Body Only\n\nActual knowledge summary.",
        doc_id="doc-body-only",
    )
    rows = await wiki_store.document_storage.get_documents(
        {"kb_doc_id": "doc-body-only"}, offset=None, limit=None
    )

    assert page["summary"] == "Actual knowledge summary."
    assert rows
    assert all("doc_id:" not in row["text"] for row in rows)
