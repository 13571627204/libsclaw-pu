import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from astrbot.core.knowledge_base.kb_helper import KBHelper
from astrbot.core.provider.provider import EmbeddingProvider
from astrbot.dashboard.api.knowledge_bases import (
    delete_knowledge_base_wiki_path,
    export_knowledge_base_wiki,
    list_knowledge_bases,
    move_knowledge_base_wiki_path,
)
from astrbot.dashboard.api.multipart import MultiDict
from astrbot.dashboard.schemas import (
    KnowledgeBaseRequest,
    KnowledgeWikiMoveRequest,
    KnowledgeWikiPageCreateRequest,
    KnowledgeWikiPageUpdateRequest,
)
from astrbot.dashboard.services.knowledge_base_service import (
    KnowledgeBaseService,
    KnowledgeBaseServiceError,
)


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        super().__init__({}, {})

    async def get_embedding(self, text: str) -> list[float]:
        return [0.1, 0.2]

    async def get_embeddings(self, text: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in text]

    def get_dim(self) -> int:
        return 2


def make_service(kb_manager) -> KnowledgeBaseService:
    service = KnowledgeBaseService.__new__(KnowledgeBaseService)
    service.core_lifecycle = SimpleNamespace(kb_manager=kb_manager)
    service.upload_progress = {}
    service.upload_tasks = {}
    return service


def make_kb(kb_id: str, kb_name: str):
    return SimpleNamespace(
        kb_id=kb_id,
        kb_name=kb_name,
        description="description",
        emoji="book",
        embedding_provider_id="embedding-1",
        rerank_provider_id="rerank-1",
        chunk_size=512,
        chunk_overlap=50,
        top_k_dense=50,
        top_k_sparse=50,
        top_m_final=5,
        model_dump=lambda: {"kb_id": kb_id, "kb_name": kb_name},
    )


def make_request(query_string: bytes) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/knowledge-bases",
            "query_string": query_string,
            "headers": [],
        }
    )


class FakeUpload:
    def __init__(self, filename: str, content: bytes = b"# Page") -> None:
        self.filename = filename
        self.content = content

    async def save(
        self,
        destination: str | Path,
        *,
        max_bytes: int | None = None,
    ) -> int:
        if max_bytes is not None and len(self.content) > max_bytes:
            raise ValueError("upload limit exceeded")
        Path(destination).write_bytes(self.content)
        return len(self.content)


def close_scheduled_coroutine(coroutine):
    coroutine.close()
    return MagicMock()


@pytest.mark.asyncio
async def test_list_kbs_applies_pagination():
    kb_manager = MagicMock()
    kb_manager.list_kbs = AsyncMock(
        return_value=[
            make_kb("kb-1", "one"),
            make_kb("kb-2", "two"),
            make_kb("kb-3", "three"),
        ]
    )
    kb_manager.get_kb = AsyncMock(
        side_effect=lambda kb_id: SimpleNamespace(init_error=None)
    )
    service = make_service(kb_manager)

    result = await service.list_kbs(page=2, page_size=2)

    assert result == {
        "items": [{"kb_id": "kb-3", "kb_name": "three"}],
        "page": 2,
        "page_size": 2,
        "total": 3,
    }


@pytest.mark.asyncio
async def test_list_documents_supports_all_page_size():
    documents = [SimpleNamespace(model_dump=lambda: {"doc_id": "doc-1"})]
    kb_helper = MagicMock()
    kb_helper.list_documents = AsyncMock(return_value=documents)
    kb_helper.count_documents = AsyncMock(return_value=37)
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=kb_helper)
    service = make_service(kb_manager)

    result = await service.list_documents(
        kb_id="kb-1",
        page=4,
        page_size=-1,
    )

    assert result == {
        "items": [{"doc_id": "doc-1"}],
        "page": 1,
        "page_size": -1,
        "total": 37,
    }
    kb_helper.list_documents.assert_awaited_once_with(
        offset=0,
        limit=37,
        search=None,
    )


@pytest.mark.asyncio
async def test_list_route_uses_default_page_size_without_query_params():
    service = MagicMock()
    service.list_kbs = AsyncMock(return_value={"items": [], "total": 0})

    response = await list_knowledge_bases(
        make_request(b""),
        _auth=object(),
        service=service,
    )

    assert response["status"] == "ok"
    service.list_kbs.assert_awaited_once_with(page=1, page_size=20)


@pytest.mark.asyncio
async def test_list_route_uses_default_page_size_when_page_is_explicit():
    service = MagicMock()
    service.list_kbs = AsyncMock(return_value={"items": [], "total": 0})

    response = await list_knowledge_bases(
        make_request(b"page=2"),
        _auth=object(),
        service=service,
    )

    assert response["status"] == "ok"
    service.list_kbs.assert_awaited_once_with(page=2, page_size=20)


def test_kb_helper_export_preserves_markdown_tree(tmp_path, monkeypatch):
    """Archive Markdown pages with paths relative to the knowledge root."""
    kb_dir = tmp_path / "kb-1"
    knowledge_dir = kb_dir / "knowledge"
    (knowledge_dir / "guides").mkdir(parents=True)
    (knowledge_dir / "index.md").write_text("# Index", encoding="utf-8")
    (knowledge_dir / "guides" / "setup.md").write_text("# Setup", encoding="utf-8")
    (knowledge_dir / "guides" / "ignored.txt").write_text("not wiki", encoding="utf-8")
    export_dir = tmp_path / "exports"
    monkeypatch.setattr(
        "astrbot.core.knowledge_base.kb_helper.get_astrbot_temp_path",
        lambda: str(export_dir),
    )
    helper = KBHelper.__new__(KBHelper)
    helper.kb_dir = kb_dir
    helper.kb = SimpleNamespace(kb_name="Docs/Team")

    archive_path, filename, page_count = helper.export_wiki_archive()

    try:
        assert filename == "Docs_Team.zip"
        assert page_count == 2
        with zipfile.ZipFile(archive_path) as archive:
            assert archive.namelist() == ["guides/setup.md", "index.md"]
            assert archive.read("guides/setup.md").decode() == "# Setup"
    finally:
        archive_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_export_wiki_service_uses_selected_knowledge_base(tmp_path):
    """Resolve the requested helper and create its Wiki archive."""
    archive_path = tmp_path / "Docs.zip"
    helper = SimpleNamespace(
        export_wiki_archive=MagicMock(return_value=(archive_path, "Docs.zip", 2))
    )
    kb_manager = SimpleNamespace(get_kb=AsyncMock(return_value=helper))
    service = make_service(kb_manager)

    result = await service.export_wiki("kb-1")

    assert result == (archive_path, "Docs.zip", 2)
    kb_manager.get_kb.assert_awaited_once_with("kb-1")
    helper.export_wiki_archive.assert_called_once_with()


@pytest.mark.asyncio
async def test_export_wiki_route_returns_zip_and_cleans_temporary_file(tmp_path):
    """Return a downloadable ZIP and remove it after the response completes."""
    archive_path = tmp_path / "kb-export.zip"
    archive_path.write_bytes(b"zip fixture")
    service = SimpleNamespace(
        export_wiki=AsyncMock(return_value=(archive_path, "Docs.zip", 2))
    )

    response = await export_knowledge_base_wiki(
        "kb-1",
        _auth=object(),
        service=service,
    )

    assert isinstance(response, FileResponse)
    assert response.media_type == "application/zip"
    assert response.headers["x-knowledge-page-count"] == "2"
    assert "Docs.zip" in response.headers["content-disposition"]
    assert archive_path.exists()
    assert response.background is not None
    await response.background()
    assert not archive_path.exists()


@pytest.mark.asyncio
async def test_export_wiki_route_returns_json_error():
    """Return a client error instead of an invalid file response."""
    service = SimpleNamespace(
        export_wiki=AsyncMock(side_effect=ValueError("没有可导出的页面"))
    )

    response = await export_knowledge_base_wiki(
        "kb-1",
        _auth=object(),
        service=service,
    )

    assert isinstance(response, JSONResponse)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_kb_accepts_legacy_name_field():
    kb = make_kb("kb-1", "From Name")
    kb_manager = MagicMock()
    kb_manager.provider_manager.get_provider_by_id = AsyncMock(
        return_value=FakeEmbeddingProvider()
    )
    kb_manager.create_kb = AsyncMock(return_value=SimpleNamespace(kb=kb))
    service = make_service(kb_manager)

    result, message = await service.create_kb(
        {
            "name": "From Name",
            "embedding_provider_id": "embedding-1",
            "top_k_dense": 12,
            "top_k_sparse": 8,
            "top_m_final": 3,
        }
    )

    assert message == "创建知识库成功"
    assert result == {"kb_id": "kb-1", "kb_name": "From Name"}
    kb_manager.create_kb.assert_awaited_once_with(
        kb_name="From Name",
        description=None,
        emoji=None,
        embedding_provider_id="embedding-1",
        rerank_provider_id=None,
        chunk_size=None,
        chunk_overlap=None,
        top_k_dense=12,
        top_k_sparse=8,
        top_m_final=3,
    )


@pytest.mark.asyncio
async def test_update_kb_preserves_omitted_fields():
    kb = make_kb("kb-1", "Docs")
    updated_kb = make_kb("kb-1", "Docs")
    updated_kb.chunk_size = 1024
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=SimpleNamespace(kb=kb))
    kb_manager.update_kb = AsyncMock(return_value=SimpleNamespace(kb=updated_kb))
    service = make_service(kb_manager)

    await service.update_kb({"kb_id": "kb-1", "chunk_size": 1024})

    kb_manager.update_kb.assert_awaited_once_with(
        kb_id="kb-1",
        kb_name="Docs",
        description="description",
        emoji="book",
        embedding_provider_id="embedding-1",
        rerank_provider_id="rerank-1",
        chunk_size=1024,
        chunk_overlap=50,
        top_k_dense=50,
        top_k_sparse=50,
        top_m_final=5,
    )


@pytest.mark.asyncio
async def test_update_kb_allows_explicit_rerank_provider_clear():
    kb = make_kb("kb-1", "Docs")
    updated_kb = make_kb("kb-1", "Docs")
    updated_kb.rerank_provider_id = None
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=SimpleNamespace(kb=kb))
    kb_manager.update_kb = AsyncMock(return_value=SimpleNamespace(kb=updated_kb))
    service = make_service(kb_manager)

    await service.update_kb({"kb_id": "kb-1", "rerank_provider_id": None})

    kb_manager.update_kb.assert_awaited_once()
    assert kb_manager.update_kb.await_args.kwargs["rerank_provider_id"] is None


@pytest.mark.asyncio
async def test_update_kb_reports_reinitialization_failure():
    kb = make_kb("kb-1", "Docs")
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=SimpleNamespace(kb=kb))
    kb_manager.update_kb = AsyncMock(return_value=SimpleNamespace(kb=kb))
    service = make_service(kb_manager)

    with pytest.raises(KnowledgeBaseServiceError, match="原配置已保留"):
        await service.update_kb({"kb_id": "kb-1", "chunk_size": 1024})


def test_knowledge_base_schemas_match_service_contract():
    create_payload = KnowledgeBaseRequest(
        kb_name="Docs",
        name="Legacy",
        emoji="book",
        top_k_dense=12,
        top_k_sparse=8,
        top_m_final=3,
        kb_id="body-kb-id",
    ).canonical_payload()
    assert create_payload == {
        "kb_name": "Docs",
        "emoji": "book",
        "top_k_dense": 12,
        "top_k_sparse": 8,
        "top_m_final": 3,
    }
    assert "kb_id" not in create_payload


def test_knowledge_base_request_preserves_explicit_null_updates():
    payload = KnowledgeBaseRequest(rerank_provider_id=None).canonical_payload()

    assert payload == {"rerank_provider_id": None}


def test_knowledge_base_request_omits_unset_none_fields():
    payload = KnowledgeBaseRequest(kb_name="Docs").canonical_payload()

    assert payload == {"kb_name": "Docs"}


def test_knowledge_base_request_uses_legacy_name_as_input_alias():
    payload = KnowledgeBaseRequest(name="Legacy Name").canonical_payload()

    assert payload == {"kb_name": "Legacy Name"}


def test_wiki_page_request_contract_distinguishes_create_and_update():
    create = KnowledgeWikiPageCreateRequest(
        path="notes/page.md",
        content="# Page",
    )

    assert create.path == "notes/page.md"
    with pytest.raises(ValidationError):
        KnowledgeWikiPageUpdateRequest(
            path="notes/page.md",
            content="# Page",
        )


@pytest.mark.asyncio
async def test_create_kb_raises_when_kb_name_is_missing():
    kb_manager = MagicMock()
    service = make_service(kb_manager)

    with pytest.raises(KnowledgeBaseServiceError, match="知识库名称不能为空"):
        await service.create_kb({"embedding_provider_id": "embedding-1"})


@pytest.mark.asyncio
async def test_create_kb_allows_missing_embedding_provider():
    kb_manager = MagicMock()
    kb_helper = MagicMock()
    kb_helper.kb.model_dump.return_value = {
        "kb_id": "kb-keyword-only",
        "kb_name": "Test KB",
        "embedding_provider_id": None,
    }
    kb_manager.create_kb = AsyncMock(return_value=kb_helper)
    service = make_service(kb_manager)

    result, message = await service.create_kb({"kb_name": "Test KB"})

    assert result["embedding_provider_id"] is None
    assert message == "创建知识库成功"
    kb_manager.create_kb.assert_awaited_once_with(
        kb_name="Test KB",
        description=None,
        emoji=None,
        embedding_provider_id=None,
        rerank_provider_id=None,
        chunk_size=None,
        chunk_overlap=None,
        top_k_dense=None,
        top_k_sparse=None,
        top_m_final=None,
    )


@pytest.mark.asyncio
async def test_create_kb_raises_when_embedding_provider_is_invalid():
    kb_manager = MagicMock()
    kb_manager.provider_manager.get_provider_by_id = AsyncMock(return_value=None)
    service = make_service(kb_manager)

    with pytest.raises(KnowledgeBaseServiceError, match="嵌入模型不存在或类型错误"):
        await service.create_kb(
            {"kb_name": "Test KB", "embedding_provider_id": "missing-provider"}
        )


@pytest.mark.asyncio
async def test_write_wiki_page_rejects_path_changes_for_existing_pages():
    kb_manager = MagicMock()
    service = make_service(kb_manager)

    with pytest.raises(KnowledgeBaseServiceError, match="暂不支持修改知识页面路径"):
        await service.write_wiki_page(
            "kb-1",
            {
                "path": "notes/renamed.md",
                "original_path": "notes/original.md",
                "content": "# Renamed",
            },
            require_existing=True,
        )

    kb_manager.get_kb.assert_not_called()


@pytest.mark.asyncio
async def test_write_wiki_page_update_requires_original_path():
    kb_manager = MagicMock()
    service = make_service(kb_manager)

    with pytest.raises(KnowledgeBaseServiceError, match="缺少参数 original_path"):
        await service.write_wiki_page(
            "kb-1",
            {"path": "notes/page.md", "content": "# Page"},
            require_existing=True,
        )

    kb_manager.get_kb.assert_not_called()


@pytest.mark.asyncio
async def test_delete_wiki_page_supports_pages_without_legacy_document_metadata():
    wiki_store = MagicMock()
    wiki_store.get_page_metadata = AsyncMock(
        return_value={"path": "notes/page.md", "doc_id": "wiki-doc"}
    )
    wiki_store.delete_page = AsyncMock(return_value=True)
    kb_helper = MagicMock()
    kb_helper.kb.kb_id = "kb-1"
    kb_helper.wiki_store = wiki_store
    kb_helper.get_document = AsyncMock(return_value=None)
    kb_helper.refresh_kb = AsyncMock()
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=kb_helper)
    kb_manager.kb_db.update_kb_stats = AsyncMock()
    service = make_service(kb_manager)

    result, message = await service.delete_wiki_page("kb-1", "notes/page.md")

    assert result is None
    assert message == "删除知识页面成功"
    wiki_store.delete_page.assert_awaited_once_with("notes/page.md")
    kb_manager.kb_db.update_kb_stats.assert_awaited_once_with(
        kb_id="kb-1",
        vec_db=wiki_store,
    )


@pytest.mark.asyncio
async def test_move_wiki_path_synchronizes_document_paths():
    moved_document = SimpleNamespace(file_path="notes/original.md")
    wiki_store = MagicMock()
    wiki_store.move_path = AsyncMock(
        return_value={
            "source_path": "notes",
            "target_path": "archive/notes",
            "entry_type": "directory",
            "moved": [
                {
                    "doc_id": "doc-1",
                    "title": "Original",
                    "old_path": "notes/original.md",
                    "new_path": "archive/notes/original.md",
                },
                {
                    "doc_id": "doc-without-row",
                    "title": "Detached",
                    "old_path": "notes/detached.md",
                    "new_path": "archive/notes/detached.md",
                },
            ],
            "rebuild": {"pages": 2, "chunks": 2},
            "parent_path": "archive",
        }
    )
    session = MagicMock()
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=False)
    session.begin.return_value = transaction
    database_context = MagicMock()
    database_context.__aenter__ = AsyncMock(return_value=session)
    database_context.__aexit__ = AsyncMock(return_value=False)
    kb_helper = MagicMock()
    kb_helper.kb.kb_id = "kb-1"
    kb_helper.get_document = AsyncMock(side_effect=[moved_document, None])
    kb_helper.refresh_kb = AsyncMock()
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=kb_helper)
    kb_manager.kb_db.get_db.return_value = database_context
    kb_manager.kb_db.update_kb_stats = AsyncMock()
    service = make_service(kb_manager)
    service._get_wiki_store = AsyncMock(return_value=wiki_store)

    result, message = await service.move_wiki_path(
        "kb-1",
        {"source_path": "notes", "target_path": "archive/notes"},
    )

    assert result["entry_type"] == "directory"
    assert message == "移动知识文件成功"
    assert moved_document.file_path == "archive/notes/original.md"
    session.add_all.assert_called_once_with([moved_document])
    kb_manager.kb_db.update_kb_stats.assert_awaited_once_with(
        kb_id="kb-1",
        vec_db=wiki_store,
    )
    kb_helper.refresh_kb.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_wiki_directory_removes_document_and_media_records(tmp_path):
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()
    source_file = sources_dir / "doc-1.md"
    source_file.write_text("# Source", encoding="utf-8")
    media_file = tmp_path / "attachment.png"
    media_file.write_bytes(b"image")
    wiki_store = MagicMock()
    wiki_store.sources_dir = sources_dir
    wiki_store.delete_path = AsyncMock(
        return_value={
            "entry_type": "directory",
            "deleted": [
                {"doc_id": "doc-1", "path": "notes/a.md", "title": "A"},
                {"doc_id": "doc-2", "path": "notes/b.md", "title": "B"},
            ],
            "rebuild": {"pages": 0, "chunks": 0},
        }
    )
    kb_helper = MagicMock()
    kb_helper.kb.kb_id = "kb-1"
    kb_helper.refresh_kb = AsyncMock()
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=kb_helper)
    kb_manager.kb_db.list_media_by_doc = AsyncMock(
        side_effect=[[SimpleNamespace(file_path=str(media_file))], []]
    )
    kb_manager.kb_db.delete_document_records = AsyncMock()
    kb_manager.kb_db.update_kb_stats = AsyncMock()
    service = make_service(kb_manager)
    service._get_wiki_store = AsyncMock(return_value=wiki_store)

    result, message = await service.delete_wiki_path(
        "kb-1",
        "notes",
        recursive=True,
    )

    assert result["entry_type"] == "directory"
    assert message == "删除知识文件成功"
    kb_manager.kb_db.delete_document_records.assert_awaited_once_with(
        ["doc-1", "doc-2"]
    )
    assert not source_file.exists()
    assert not media_file.exists()
    kb_helper.refresh_kb.assert_awaited_once()


@pytest.mark.asyncio
async def test_wiki_path_routes_forward_move_and_recursive_delete():
    service = MagicMock()
    service.move_wiki_path = AsyncMock(
        return_value=({"entry_type": "page", "moved": []}, "移动知识文件成功")
    )
    service.delete_wiki_path = AsyncMock(
        return_value=({"entry_type": "directory", "deleted": []}, "删除知识文件成功")
    )

    move_response = await move_knowledge_base_wiki_path(
        "kb-1",
        KnowledgeWikiMoveRequest(
            source_path="notes/page.md",
            target_path="archive/page.md",
        ),
        _auth=object(),
        service=service,
    )
    delete_response = await delete_knowledge_base_wiki_path(
        "kb-1",
        make_request(b"path=archive&recursive=true"),
        _auth=object(),
        service=service,
    )

    assert move_response["status"] == "ok"
    assert delete_response["status"] == "ok"
    service.move_wiki_path.assert_awaited_once_with(
        "kb-1",
        {
            "source_path": "notes/page.md",
            "target_path": "archive/page.md",
        },
    )
    service.delete_wiki_path.assert_awaited_once_with(
        "kb-1",
        "archive",
        recursive=True,
    )


@pytest.mark.asyncio
async def test_upload_document_accepts_more_than_ten_files(
    tmp_path,
    monkeypatch,
):
    kb_helper = SimpleNamespace(kb=SimpleNamespace(chunk_size=512, chunk_overlap=50))
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=kb_helper)
    service = make_service(kb_manager)
    service.background_upload_task = AsyncMock()
    staging_dir = tmp_path / "upload-staging"
    staging_dir.mkdir()
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.get_astrbot_temp_path",
        lambda: str(tmp_path),
    )
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.tempfile.mkdtemp",
        lambda **_kwargs: str(staging_dir),
    )
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.asyncio.create_task",
        close_scheduled_coroutine,
    )
    files = MultiDict(
        [("files[]", FakeUpload(f"page-{index}.md")) for index in range(11)]
    )

    result = await service.upload_document(
        content_type="multipart/form-data; boundary=test",
        form_data=MultiDict([("kb_id", "kb-1")]),
        files=files,
    )

    assert result["file_count"] == 11
    scheduled_files = service.background_upload_task.call_args.kwargs["files_to_upload"]
    assert len(scheduled_files) == 11
    assert [item["file_name"] for item in scheduled_files] == [
        f"page-{index}.md" for index in range(11)
    ]


@pytest.mark.asyncio
async def test_upload_document_rejects_cumulative_file_size(
    tmp_path,
    monkeypatch,
):
    """Reject document batches whose staged file bytes exceed the safety limit."""
    kb_helper = SimpleNamespace(kb=SimpleNamespace(chunk_size=512, chunk_overlap=50))
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=kb_helper)
    service = make_service(kb_manager)
    staging_dir = tmp_path / "oversized-upload-staging"
    staging_dir.mkdir()
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.KNOWLEDGE_UPLOAD_MAX_BYTES",
        8,
    )
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.get_astrbot_temp_path",
        lambda: str(tmp_path),
    )
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.tempfile.mkdtemp",
        lambda **_kwargs: str(staging_dir),
    )

    with pytest.raises(KnowledgeBaseServiceError, match="512 MiB"):
        await service.upload_document(
            content_type="multipart/form-data; boundary=test",
            form_data=MultiDict([("kb_id", "kb-1")]),
            files=MultiDict(
                [
                    ("files[]", FakeUpload("first.md", b"12345")),
                    ("files[]", FakeUpload("second.md", b"67890")),
                ]
            ),
        )

    assert not staging_dir.exists()


@pytest.mark.asyncio
async def test_upload_document_uses_knowledge_base_chunk_configuration(
    tmp_path,
    monkeypatch,
):
    kb_helper = SimpleNamespace(kb=SimpleNamespace(chunk_size=2048, chunk_overlap=0))
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=kb_helper)
    service = make_service(kb_manager)
    service.background_upload_task = AsyncMock()
    staging_dir = tmp_path / "configured-upload-staging"
    staging_dir.mkdir()
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.get_astrbot_temp_path",
        lambda: str(tmp_path),
    )
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.tempfile.mkdtemp",
        lambda **_kwargs: str(staging_dir),
    )
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.asyncio.create_task",
        close_scheduled_coroutine,
    )

    await service.upload_document(
        content_type="multipart/form-data; boundary=test",
        form_data=MultiDict(
            [
                ("kb_id", "kb-1"),
                ("chunk_size", "16"),
                ("chunk_overlap", "1"),
            ]
        ),
        files=MultiDict([("file", FakeUpload("configured.md"))]),
    )

    scheduled = service.background_upload_task.call_args.kwargs
    assert scheduled["chunk_size"] == 2048
    assert scheduled["chunk_overlap"] == 0


@pytest.mark.asyncio
async def test_import_wiki_preserves_file_and_path_order_for_staging(
    tmp_path,
    monkeypatch,
):
    kb_helper = MagicMock()
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=kb_helper)
    service = make_service(kb_manager)
    service.background_wiki_import_task = AsyncMock()
    staging_dir = tmp_path / "wiki-import-staging"
    staging_dir.mkdir()
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.get_astrbot_temp_path",
        lambda: str(tmp_path),
    )
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.tempfile.mkdtemp",
        lambda **_kwargs: str(staging_dir),
    )
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.asyncio.create_task",
        close_scheduled_coroutine,
    )
    first_content = b"# First"
    archive_content = b"PK placeholder"

    result = await service.import_wiki(
        content_type="multipart/form-data; boundary=test",
        form_data=MultiDict(
            [
                ("kb_id", "kb-1"),
                ("paths[]", "guides/first.md"),
                ("paths[]", ""),
                ("overwrite", "true"),
            ]
        ),
        files=MultiDict(
            [
                ("files[]", FakeUpload("first.md", first_content)),
                ("files[]", FakeUpload("knowledge.zip", archive_content)),
            ]
        ),
    )

    assert result["file_count"] == 2
    scheduled = service.background_wiki_import_task.call_args.kwargs
    assert scheduled["overwrite"] is True
    assert [relative_path for _path, relative_path in scheduled["sources"]] == [
        "guides/first.md",
        "",
    ]
    assert [path.read_bytes() for path, _relative_path in scheduled["sources"]] == [
        first_content,
        archive_content,
    ]
    assert scheduled["sources"][0][0].name.endswith("_first.md")
    assert scheduled["sources"][1][0].name.endswith("_knowledge.zip")


@pytest.mark.asyncio
async def test_import_wiki_defaults_zip_to_knowledge_root(
    tmp_path,
    monkeypatch,
):
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=MagicMock())
    service = make_service(kb_manager)
    service.background_wiki_import_task = AsyncMock()
    staging_dir = tmp_path / "wiki-root-import-staging"
    staging_dir.mkdir()
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.get_astrbot_temp_path",
        lambda: str(tmp_path),
    )
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.tempfile.mkdtemp",
        lambda **_kwargs: str(staging_dir),
    )
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.asyncio.create_task",
        close_scheduled_coroutine,
    )

    await service.import_wiki(
        content_type="multipart/form-data; boundary=test",
        form_data=MultiDict([("kb_id", "kb-1")]),
        files=MultiDict([("files", FakeUpload("knowledge.zip", b"PK placeholder"))]),
    )

    scheduled = service.background_wiki_import_task.call_args.kwargs
    assert scheduled["sources"][0][1] is None


@pytest.mark.asyncio
async def test_import_wiki_rejects_cumulative_file_size(tmp_path, monkeypatch):
    """Reject Wiki batches whose staged file bytes exceed the safety limit."""
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=MagicMock())
    service = make_service(kb_manager)
    staging_dir = tmp_path / "oversized-wiki-staging"
    staging_dir.mkdir()
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.KNOWLEDGE_UPLOAD_MAX_BYTES",
        8,
    )
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.get_astrbot_temp_path",
        lambda: str(tmp_path),
    )
    monkeypatch.setattr(
        "astrbot.dashboard.services.knowledge_base_service.tempfile.mkdtemp",
        lambda **_kwargs: str(staging_dir),
    )

    with pytest.raises(KnowledgeBaseServiceError, match="512 MiB"):
        await service.import_wiki(
            content_type="multipart/form-data; boundary=test",
            form_data=MultiDict(
                [
                    ("kb_id", "kb-1"),
                    ("paths[]", "first.md"),
                    ("paths[]", "second.md"),
                ]
            ),
            files=MultiDict(
                [
                    ("files[]", FakeUpload("first.md", b"12345")),
                    ("files[]", FakeUpload("second.md", b"67890")),
                ]
            ),
        )

    assert not staging_dir.exists()
