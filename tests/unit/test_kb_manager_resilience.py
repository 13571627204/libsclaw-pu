"""
Unit tests for knowledge base manager resilience behavior.

Tests the following scenarios:
1. update_kb preserves old instance when re-initialization fails
2. update_kb switches instance only after new instance initializes successfully
3. _ensure_vec_db clears stale init_error after successful initialization

These tests use lazy imports and mocks to avoid circular import issues
in the astrbot core module chain.
"""

import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def stub_provider_manager_module():
    """Stub provider manager module to avoid circular imports in unit tests."""
    original_module = sys.modules.get("astrbot.core.provider.manager")
    stub_module = types.ModuleType("astrbot.core.provider.manager")

    class ProviderManager: ...

    setattr(stub_module, "ProviderManager", ProviderManager)
    sys.modules["astrbot.core.provider.manager"] = stub_module

    try:
        yield
    finally:
        if original_module is not None:
            sys.modules["astrbot.core.provider.manager"] = original_module
        else:
            sys.modules.pop("astrbot.core.provider.manager", None)


@pytest.fixture
def mock_provider_manager():
    """Create a mock ProviderManager."""
    manager = MagicMock()
    manager.get_provider_by_id = AsyncMock()
    manager.acm = MagicMock()
    manager.acm.default_conf = {}
    return manager


@pytest.fixture
def mock_kb_db():
    """Create a mock KBSQLiteDatabase."""
    db = MagicMock()
    db.get_db = MagicMock()
    db.list_kbs = AsyncMock(return_value=[])
    db.get_kb_by_id = AsyncMock()
    return db


@pytest.fixture
def mock_knowledge_base():
    """Create a mock KnowledgeBase instance."""
    # Use lazy import to avoid circular import
    from astrbot.core.knowledge_base.models import KnowledgeBase

    kb = KnowledgeBase(
        kb_name="test_kb",
        description="Test knowledge base",
        emoji="📚",
        embedding_provider_id="test-embedding-provider",
        rerank_provider_id=None,
        chunk_size=512,
        chunk_overlap=50,
        top_k_dense=50,
        top_k_sparse=50,
        top_m_final=5,
    )
    return kb


@pytest.fixture
def mock_embedding_provider():
    """Create a mock EmbeddingProvider."""
    provider = MagicMock()
    provider.get_embeddings_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    return provider


def test_knowledge_base_default_chunk_configuration():
    """Use the Wiki-oriented chunk defaults for new knowledge bases."""
    from astrbot.core.knowledge_base.models import KnowledgeBase

    kb = KnowledgeBase(kb_name="default_chunks")

    assert kb.chunk_size == 800
    assert kb.chunk_overlap == 80


@pytest.mark.asyncio
async def test_update_kb_loaded_model_updates_chunk_settings_without_orm_copy_error(
    tmp_path: Path,
    stub_provider_manager_module,
):
    """Update settings on an ORM-loaded knowledge base without broken copy state."""
    from astrbot.core.knowledge_base.kb_db_sqlite import KBSQLiteDatabase
    from astrbot.core.knowledge_base.kb_mgr import KnowledgeBaseManager
    from astrbot.core.knowledge_base.models import KnowledgeBase

    kb_db = KBSQLiteDatabase(str(tmp_path / "kb.db"))
    await kb_db.initialize()
    await kb_db.migrate_to_v1()
    try:
        original = KnowledgeBase(
            kb_name="loaded-kb",
            chunk_size=512,
            chunk_overlap=50,
        )
        async with kb_db.get_db() as session:
            session.add(original)
            await session.commit()

        loaded = await kb_db.get_kb_by_id(original.kb_id)
        assert loaded is not None
        old_helper = types.SimpleNamespace(
            kb=loaded,
            init_error=None,
            terminate=AsyncMock(),
        )
        candidate_helper = types.SimpleNamespace(
            initialize=AsyncMock(),
            terminate=AsyncMock(),
            wiki_store=types.SimpleNamespace(
                rebuild_index=AsyncMock(return_value={}),
                _last_initialize_rebuilt=False,
            ),
            init_error=None,
        )
        manager = KnowledgeBaseManager.__new__(KnowledgeBaseManager)
        manager.provider_manager = MagicMock()
        manager.kb_db = kb_db
        manager.kb_insts = {loaded.kb_id: old_helper}

        with patch(
            "astrbot.core.knowledge_base.kb_mgr.KBHelper",
            return_value=candidate_helper,
        ):
            result = await manager.update_kb(
                kb_id=loaded.kb_id,
                kb_name=loaded.kb_name,
                chunk_size=800,
                chunk_overlap=80,
            )

        persisted = await kb_db.get_kb_by_id(loaded.kb_id)
        assert result is candidate_helper
        assert persisted is not None
        assert persisted.chunk_size == 800
        assert persisted.chunk_overlap == 80
    finally:
        await kb_db.close()


@pytest.mark.asyncio
async def test_update_kb_preserves_old_instance_when_reinit_fails(
    stub_provider_manager_module,
    mock_provider_manager,
    mock_kb_db,
    mock_knowledge_base,
    mock_embedding_provider,
):
    """
    Test that update_kb preserves the old KBHelper instance when
    re-initialization fails, ensuring the knowledge base remains available.
    """
    # Lazy import to avoid circular import
    from astrbot.core.knowledge_base.kb_helper import KBHelper
    from astrbot.core.knowledge_base.kb_mgr import KnowledgeBaseManager

    # Setup: create an existing KBHelper with working vec_db
    mock_provider_manager.get_provider_by_id.return_value = mock_embedding_provider

    # Create KBHelper using __new__ to avoid __init__ side effects
    old_helper = KBHelper.__new__(KBHelper)
    old_helper.kb = mock_knowledge_base
    old_helper.prov_mgr = mock_provider_manager
    old_helper.kb_db = mock_kb_db
    old_helper.kb_root_dir = "/tmp/test_kb"
    old_helper.chunker = MagicMock()
    old_helper.init_error = None
    old_helper.vec_db = MagicMock()  # Simulate existing working vec_db
    old_helper.terminate = AsyncMock()

    # Create KBManager and inject the existing helper
    kb_mgr = KnowledgeBaseManager.__new__(KnowledgeBaseManager)
    kb_mgr.provider_manager = mock_provider_manager
    kb_mgr.kb_db = mock_kb_db
    kb_mgr.kb_insts = {mock_knowledge_base.kb_id: old_helper}
    kb_mgr.retrieval_manager = MagicMock()

    # Mock KBHelper creation to simulate initialization failure
    with patch.object(KBHelper, "initialize", new_callable=AsyncMock) as mock_init:
        # First call (for new_helper) should fail
        mock_init.side_effect = Exception("Embedding provider unavailable")

        # Execute update_kb with a different embedding provider
        result = await kb_mgr.update_kb(
            kb_id=mock_knowledge_base.kb_id,
            kb_name="updated_kb",
            embedding_provider_id="new-embedding-provider",
        )

        # Verify: the old helper should be returned, not a new one
        assert result is not None
        assert result is old_helper
        assert kb_mgr.kb_insts[mock_knowledge_base.kb_id] is old_helper

        # Verify: old helper's vec_db should still be available
        assert hasattr(result, "vec_db")
        assert result.vec_db is not None

        # Verify: failure does not replace the existing helper state
        assert result.init_error is None
        assert result.kb.kb_name == "test_kb"
        assert result.kb.embedding_provider_id == "test-embedding-provider"


@pytest.mark.asyncio
async def test_update_kb_switches_instance_only_after_new_reinit_success(
    stub_provider_manager_module,
    mock_provider_manager,
    mock_kb_db,
    mock_knowledge_base,
    mock_embedding_provider,
):
    """
    Test that update_kb only switches to the new KBHelper instance
    after the new instance successfully initializes.
    """
    # Lazy import to avoid circular import
    from astrbot.core.knowledge_base.kb_helper import KBHelper
    from astrbot.core.knowledge_base.kb_mgr import KnowledgeBaseManager

    # Setup: create an existing KBHelper
    mock_provider_manager.get_provider_by_id.return_value = mock_embedding_provider

    old_helper = KBHelper.__new__(KBHelper)
    old_helper.kb = mock_knowledge_base
    old_helper.prov_mgr = mock_provider_manager
    old_helper.kb_db = mock_kb_db
    old_helper.kb_root_dir = "/tmp/test_kb"
    old_helper.chunker = MagicMock()
    old_helper.init_error = None
    old_helper.vec_db = MagicMock()
    old_helper.terminate = AsyncMock()

    kb_mgr = KnowledgeBaseManager.__new__(KnowledgeBaseManager)
    kb_mgr.provider_manager = mock_provider_manager
    kb_mgr.kb_db = mock_kb_db
    kb_mgr.kb_insts = {mock_knowledge_base.kb_id: old_helper}
    kb_mgr.retrieval_manager = MagicMock()

    # Mock session context for database operations
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_db_context = MagicMock()
    mock_db_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_db_context.__aexit__ = AsyncMock()
    mock_kb_db.get_db.return_value = mock_db_context

    # Mock KBHelper.initialize to succeed
    with patch.object(KBHelper, "initialize", new_callable=AsyncMock) as mock_init:
        mock_init.return_value = None

        # Execute update_kb
        result = await kb_mgr.update_kb(
            kb_id=mock_knowledge_base.kb_id,
            kb_name="updated_kb",
            embedding_provider_id="test-embedding-provider",
        )

        # Verify: a new helper should be returned
        assert result is not None
        assert result is not old_helper
        assert result.init_error is None
        assert kb_mgr.kb_insts[mock_knowledge_base.kb_id] is result

        # Verify: old helper should be terminated
        old_helper.terminate.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_vec_db_clears_stale_init_error(
    tmp_path: Path,
    stub_provider_manager_module,
    mock_provider_manager,
    mock_kb_db,
    mock_knowledge_base,
    mock_embedding_provider,
):
    """
    Test that _ensure_vec_db clears the init_error attribute
    after successful initialization, removing stale error state.
    """
    # Lazy import to avoid circular import
    from astrbot.core.knowledge_base.kb_helper import KBHelper

    # Setup: create KBHelper with stale init_error
    mock_provider_manager.get_provider_by_id.return_value = mock_embedding_provider
    mock_knowledge_base.chunk_overlap = 0

    helper = KBHelper.__new__(KBHelper)
    helper.kb = mock_knowledge_base
    helper.prov_mgr = mock_provider_manager
    helper.kb_db = mock_kb_db
    helper.kb_root_dir = str(tmp_path)
    helper.chunker = MagicMock()
    helper.init_error = "Previous initialization failed"
    helper.kb_dir = tmp_path / mock_knowledge_base.kb_id
    helper.kb_medias_dir = helper.kb_dir / "medias" / mock_knowledge_base.kb_id
    helper.kb_files_dir = helper.kb_dir / "files" / mock_knowledge_base.kb_id

    from astrbot.core.knowledge_base.wiki import WikiStore

    store = await helper._ensure_vec_db()
    try:
        reused_store = await helper._ensure_vec_db()

        assert helper.init_error is None
        assert isinstance(store, WikiStore)
        assert store.chunk_overlap == 0
        assert helper.vec_db is store
        assert helper.wiki_store is store
        assert reused_store is store
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_ensure_vec_db_sets_init_error_on_failure(
    stub_provider_manager_module,
    mock_provider_manager,
    mock_kb_db,
    mock_knowledge_base,
):
    """
    Test that _ensure_vec_db does NOT clear init_error when
    initialization fails, preserving the error state.
    """
    # Lazy import to avoid circular import
    from astrbot.core.knowledge_base.kb_helper import KBHelper

    # Setup: provider unavailable
    mock_provider_manager.get_provider_by_id.return_value = None

    helper = KBHelper.__new__(KBHelper)
    helper.kb = mock_knowledge_base
    helper.prov_mgr = mock_provider_manager
    helper.kb_db = mock_kb_db
    helper.kb_root_dir = "/tmp/test_kb"
    helper.chunker = MagicMock()
    helper.init_error = "Previous initialization failed"
    helper.kb_dir = Path("/tmp/test_kb") / mock_knowledge_base.kb_id
    helper.kb_medias_dir = helper.kb_dir / "medias" / mock_knowledge_base.kb_id
    helper.kb_files_dir = helper.kb_dir / "files" / mock_knowledge_base.kb_id

    # Execute _ensure_vec_db - should raise exception
    try:
        await helper._ensure_vec_db()
        pytest.fail("Expected exception but none was raised")
    except ValueError as e:
        # Verify: exception should be raised
        assert "无法找到" in str(e) or "未配置" in str(e)

        # Verify: init_error should NOT be cleared (still has previous error)
        # Note: _ensure_vec_db doesn't set init_error; that's done by the caller
        assert helper.init_error is not None


@pytest.mark.asyncio
async def test_update_kb_clears_embedding_provider_and_rebuilds_index(
    stub_provider_manager_module,
    mock_provider_manager,
    mock_kb_db,
    mock_knowledge_base,
):
    from astrbot.core.knowledge_base.kb_helper import KBHelper
    from astrbot.core.knowledge_base.kb_mgr import KnowledgeBaseManager

    old_helper = KBHelper.__new__(KBHelper)
    old_helper.kb = mock_knowledge_base
    old_helper.init_error = None
    old_helper.terminate = AsyncMock()

    candidate_helper = MagicMock()
    candidate_helper.initialize = AsyncMock()
    candidate_helper.terminate = AsyncMock()
    candidate_helper.wiki_store = MagicMock()
    candidate_helper.wiki_store.rebuild_index = AsyncMock(return_value={})

    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    db_context = MagicMock()
    db_context.__aenter__ = AsyncMock(return_value=session)
    db_context.__aexit__ = AsyncMock(return_value=False)
    mock_kb_db.get_db.return_value = db_context

    manager = KnowledgeBaseManager.__new__(KnowledgeBaseManager)
    manager.provider_manager = mock_provider_manager
    manager.kb_db = mock_kb_db
    manager.kb_insts = {mock_knowledge_base.kb_id: old_helper}

    with patch(
        "astrbot.core.knowledge_base.kb_mgr.KBHelper",
        return_value=candidate_helper,
    ) as helper_class:
        result = await manager.update_kb(
            kb_id=mock_knowledge_base.kb_id,
            kb_name=mock_knowledge_base.kb_name,
            embedding_provider_id=None,
        )

    candidate_kb = helper_class.call_args.kwargs["kb"]
    assert candidate_kb.embedding_provider_id is None
    assert result is candidate_helper
    assert result.kb.embedding_provider_id is None
    candidate_helper.wiki_store.rebuild_index.assert_awaited_once()
    candidate_helper.terminate.assert_not_awaited()
    old_helper.terminate.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_kb_omitted_embedding_provider_keeps_existing_value(
    stub_provider_manager_module,
    mock_provider_manager,
    mock_kb_db,
    mock_knowledge_base,
):
    from astrbot.core.knowledge_base.kb_helper import KBHelper
    from astrbot.core.knowledge_base.kb_mgr import KnowledgeBaseManager

    old_helper = KBHelper.__new__(KBHelper)
    old_helper.kb = mock_knowledge_base
    old_helper.init_error = None
    old_helper.terminate = AsyncMock()

    candidate_helper = MagicMock()
    candidate_helper.initialize = AsyncMock()
    candidate_helper.terminate = AsyncMock()

    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    db_context = MagicMock()
    db_context.__aenter__ = AsyncMock(return_value=session)
    db_context.__aexit__ = AsyncMock()
    mock_kb_db.get_db.return_value = db_context

    manager = KnowledgeBaseManager.__new__(KnowledgeBaseManager)
    manager.provider_manager = mock_provider_manager
    manager.kb_db = mock_kb_db
    manager.kb_insts = {mock_knowledge_base.kb_id: old_helper}

    with patch(
        "astrbot.core.knowledge_base.kb_mgr.KBHelper",
        return_value=candidate_helper,
    ) as helper_class:
        result = await manager.update_kb(
            kb_id=mock_knowledge_base.kb_id,
            kb_name="renamed-kb",
        )

    candidate_kb = helper_class.call_args.kwargs["kb"]
    assert candidate_kb.embedding_provider_id == "test-embedding-provider"
    assert result is candidate_helper
    assert result.kb.embedding_provider_id == "test-embedding-provider"


@pytest.mark.asyncio
async def test_update_kb_rebuild_failure_closes_candidate_and_keeps_old_state(
    stub_provider_manager_module,
    mock_provider_manager,
    mock_kb_db,
    mock_knowledge_base,
):
    from astrbot.core.knowledge_base.kb_helper import KBHelper
    from astrbot.core.knowledge_base.kb_mgr import KnowledgeBaseManager

    old_helper = KBHelper.__new__(KBHelper)
    old_helper.kb = mock_knowledge_base
    old_helper.init_error = None
    old_helper.terminate = AsyncMock()
    old_helper.wiki_store = MagicMock()
    old_helper.wiki_store.rebuild_index = AsyncMock(return_value={})

    candidate_helper = MagicMock()
    candidate_helper.initialize = AsyncMock()
    candidate_helper.terminate = AsyncMock()
    candidate_helper.wiki_store = MagicMock()
    candidate_helper.wiki_store.rebuild_index = AsyncMock(
        side_effect=RuntimeError("embedding rebuild failed")
    )

    manager = KnowledgeBaseManager.__new__(KnowledgeBaseManager)
    manager.provider_manager = mock_provider_manager
    manager.kb_db = mock_kb_db
    manager.kb_insts = {mock_knowledge_base.kb_id: old_helper}

    with patch(
        "astrbot.core.knowledge_base.kb_mgr.KBHelper",
        return_value=candidate_helper,
    ):
        result = await manager.update_kb(
            kb_id=mock_knowledge_base.kb_id,
            kb_name=mock_knowledge_base.kb_name,
            embedding_provider_id="replacement-provider",
        )

    assert result is old_helper
    assert mock_knowledge_base.embedding_provider_id == "test-embedding-provider"
    assert manager.kb_insts[mock_knowledge_base.kb_id] is old_helper
    candidate_helper.terminate.assert_awaited_once()
    old_helper.terminate.assert_not_awaited()
    old_helper.wiki_store.rebuild_index.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_kb_commit_failure_closes_candidate_and_restores_old_index(
    stub_provider_manager_module,
    mock_provider_manager,
    mock_kb_db,
    mock_knowledge_base,
):
    from astrbot.core.knowledge_base.kb_helper import KBHelper
    from astrbot.core.knowledge_base.kb_mgr import KnowledgeBaseManager

    old_helper = KBHelper.__new__(KBHelper)
    old_helper.kb = mock_knowledge_base
    old_helper.init_error = None
    old_helper.terminate = AsyncMock()
    old_helper.wiki_store = MagicMock()
    old_helper.wiki_store.rebuild_index = AsyncMock(return_value={})

    candidate_helper = MagicMock()
    candidate_helper.initialize = AsyncMock()
    candidate_helper.terminate = AsyncMock()
    candidate_helper.wiki_store = MagicMock()
    candidate_helper.wiki_store.rebuild_index = AsyncMock(return_value={})

    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock(side_effect=RuntimeError("kb metadata commit failed"))
    db_context = MagicMock()
    db_context.__aenter__ = AsyncMock(return_value=session)
    db_context.__aexit__ = AsyncMock(return_value=False)
    mock_kb_db.get_db.return_value = db_context

    manager = KnowledgeBaseManager.__new__(KnowledgeBaseManager)
    manager.provider_manager = mock_provider_manager
    manager.kb_db = mock_kb_db
    manager.kb_insts = {mock_knowledge_base.kb_id: old_helper}

    with (
        patch(
            "astrbot.core.knowledge_base.kb_mgr.KBHelper",
            return_value=candidate_helper,
        ),
        pytest.raises(RuntimeError, match="metadata commit failed"),
    ):
        await manager.update_kb(
            kb_id=mock_knowledge_base.kb_id,
            kb_name=mock_knowledge_base.kb_name,
            embedding_provider_id="replacement-provider",
        )

    assert mock_knowledge_base.embedding_provider_id == "test-embedding-provider"
    assert manager.kb_insts[mock_knowledge_base.kb_id] is old_helper
    candidate_helper.terminate.assert_awaited_once()
    old_helper.wiki_store.rebuild_index.assert_awaited_once()
