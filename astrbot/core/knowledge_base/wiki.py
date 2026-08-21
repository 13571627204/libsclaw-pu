"""File-backed Wiki knowledge base storage.

Markdown pages and source files are the durable knowledge source. SQLite FTS,
embeddings, and graph tables are derived indexes that can be rebuilt.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import posixpath
import re
import shutil
import sqlite3
import stat
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

import aiofiles
import aiosqlite

from astrbot.core import logger
from astrbot.core.db.vec_db.base import BaseVecDB, Result
from astrbot.core.exceptions import KnowledgeBaseUploadError
from astrbot.core.knowledge_base.chunking.markdown import MarkdownChunker
from astrbot.core.knowledge_base.models import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
)
from astrbot.core.knowledge_base.retrieval.tokenizer import (
    build_fts5_or_query,
    load_stopwords,
    to_fts5_search_text,
)
from astrbot.core.provider.provider import EmbeddingProvider, RerankProvider

_MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
_WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
_WIKI_LINK_FULL_RE = re.compile(r"\[\[([^\]|#]+)(#[^\]|]+)?(?:\|([^\]]+))?\]\]")
_RELATION_WIKI_LINK_RE = re.compile(
    r"^[ \t]*[-*][ \t]*([^:：\n]{1,80})[ \t]*[:：][ \t]*"
    r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]"
    r"(?:[ \t]*[—-][ \t]*([^\n]+?))?[ \t]*$",
    re.MULTILINE,
)
_RELATION_MARKDOWN_LINK_RE = re.compile(
    r"^[ \t]*[-*][ \t]*([^:：\n]{1,80})[ \t]*[:：][ \t]*"
    r"\[([^\]]+)\]\(([^)]+)\)"
    r"(?:[ \t]*[—-][ \t]*([^\n]+?))?[ \t]*$",
    re.MULTILINE,
)
_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_SOURCE_RE = re.compile(
    r"^>\s*(?:\*\*)?(?:Source|来源)(?:\*\*)?\s*[:：]\s*(.+?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_RESERVED_PAGES = {"index.md", "log.md"}
_NODE_TYPES = {
    "entity",
    "concept",
    "source",
    "synthesis",
    "overview",
    "comparison",
    "other",
}
_DIRECTORY_NODE_TYPES = {
    "entities": "entity",
    "concepts": "concept",
    "sources": "source",
    "analysis": "synthesis",
    "playbooks": "concept",
}
_LEGACY_MIGRATION_VERSION = 1
_LEGACY_PAGE_NOTE = (
    "> Migrated from the legacy chunk database. Chunk boundaries are preserved."
)
_LEGACY_CHUNK_SEPARATOR = "\n\n---\n\n"
WIKI_IMPORT_MAX_INPUT_BYTES = 512 * 1024 * 1024
WIKI_IMPORT_MAX_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024
WIKI_IMPORT_MAX_COMPRESSION_RATIO = 200.0
_MARKDOWN_IMPORT_SUFFIXES = {".md", ".markdown", ".mdx"}


class WikiDocumentStorage:
    """Compatibility document-storage facade backed by WikiStore."""

    def __init__(self, store: WikiStore) -> None:
        self.store = store

    async def get_documents(
        self,
        metadata_filters: dict,
        ids: list | None = None,
        offset: int | None = 0,
        limit: int | None = 100,
    ) -> list[dict]:
        """Return indexed chunks in the legacy document shape.

        Args:
            metadata_filters: Metadata equality filters.
            ids: Optional internal integer chunk identifiers.
            offset: Number of matching rows to skip.
            limit: Maximum rows to return, or ``None`` for all rows.

        Returns:
            Chunk dictionaries compatible with the former document storage.
        """
        db = self.store._require_db()
        conditions: list[str] = []
        params: list[object] = []
        column_map = {
            "kb_id": "kb_id",
            "kb_doc_id": "doc_id",
            "chunk_index": "chunk_index",
            "page_path": "page_path",
        }
        for key, value in metadata_filters.items():
            column = column_map.get(key)
            if column is None:
                conditions.append("json_extract(metadata, ?) = ?")
                params.extend((f"$.{key}", value))
            else:
                conditions.append(f"{column} = ?")
                params.append(value)

        if ids:
            valid_ids = [int(identifier) for identifier in ids if int(identifier) >= 0]
            if valid_ids:
                placeholders = ",".join("?" for _ in valid_ids)
                conditions.append(f"id IN ({placeholders})")
                params.extend(valid_ids)

        sql = "SELECT * FROM chunks"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY doc_id, chunk_index"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        if offset is not None:
            if limit is None:
                sql += " LIMIT -1"
            sql += " OFFSET ?"
            params.append(offset)

        async with self.store._lock, db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
        return [self.store._chunk_row_to_legacy(row) for row in rows]

    async def get_document_by_doc_id(self, chunk_id: str) -> dict | None:
        """Return a single chunk by public chunk identifier.

        Args:
            chunk_id: Public chunk UUID.

        Returns:
            Legacy chunk dictionary when found.
        """
        db = self.store._require_db()
        async with (
            self.store._lock,
            db.execute(
                "SELECT * FROM chunks WHERE chunk_id = ?",
                (chunk_id,),
            ) as cursor,
        ):
            row = await cursor.fetchone()
        return self.store._chunk_row_to_legacy(row) if row else None

    async def delete_document_by_doc_id(self, chunk_id: str) -> None:
        """Delete a single indexed chunk.

        Args:
            chunk_id: Public chunk UUID.
        """
        await self.store.delete(chunk_id)

    async def delete_documents(self, metadata_filters: dict) -> None:
        """Delete chunks matching metadata filters.

        Args:
            metadata_filters: Metadata equality filters.
        """
        await self.store.delete_documents(metadata_filters)

    async def insert_document(self, doc_id: str, text: str, metadata: dict) -> int:
        """Insert one compatibility chunk.

        Args:
            doc_id: Public chunk identifier.
            text: Chunk text.
            metadata: Legacy chunk metadata.

        Returns:
            Internal integer identifier.
        """
        return await self.store.insert(text, metadata=metadata, id=doc_id)

    async def insert_documents_batch(
        self,
        doc_ids: list[str],
        texts: list[str],
        metadatas: list[dict],
    ) -> list[int]:
        """Insert compatibility chunks as one batch.

        Args:
            doc_ids: Public chunk identifiers.
            texts: Chunk texts.
            metadatas: Legacy chunk metadata.

        Returns:
            Internal integer identifiers.
        """
        return await self.store.insert_batch(texts, metadatas, doc_ids)

    async def count_documents(self, metadata_filters: dict) -> int:
        """Count chunks matching metadata filters.

        Args:
            metadata_filters: Metadata equality filters.

        Returns:
            Matching chunk count.
        """
        return await self.store.count_documents(metadata_filters)

    async def search_sparse(
        self,
        query_tokens: list[str],
        limit: int = 10,
    ) -> list[dict] | None:
        """Search chunks using FTS5 and a CJK LIKE fallback.

        Args:
            query_tokens: Tokenized query terms.
            limit: Maximum result count.

        Returns:
            Legacy sparse result dictionaries, or ``None`` when FTS5 is unavailable.
        """
        return await self.store.search_sparse(query_tokens, limit)

    async def close(self) -> None:
        """Close the owning Wiki store."""
        await self.store.close()


class WikiStore(BaseVecDB):
    """Per-knowledge-base Markdown wiki with rebuildable indexes."""

    def __init__(
        self,
        kb_dir: Path,
        kb_id: str,
        embedding_provider: EmbeddingProvider | None = None,
        rerank_provider: RerankProvider | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> None:
        """Initialize paths and providers for a single knowledge base.

        Args:
            kb_dir: Root directory dedicated to this knowledge base.
            kb_id: Stable knowledge base identifier.
            embedding_provider: Optional embedding provider.
            rerank_provider: Optional rerank provider.
            chunk_size: Default Markdown index chunk size.
            chunk_overlap: Default Markdown index chunk overlap.
        """
        self.kb_dir = Path(kb_dir)
        self.kb_id = kb_id
        self.knowledge_dir = self.kb_dir / "knowledge"
        self.sources_dir = self.kb_dir / "sources"
        self.assets_dir = self.kb_dir / "assets"
        self.index_dir = self.kb_dir / "index"
        self.db_path = self.index_dir / "wiki.db"
        self.migrations_dir = self.kb_dir / ".migrations"
        self.legacy_migration_path = self.migrations_dir / "faiss-to-wiki-v1.json"
        self.embedding_provider = embedding_provider
        self.rerank_provider = rerank_provider
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.document_storage = WikiDocumentStorage(self)
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()
        self._operation_lock = asyncio.Lock()
        self.fts5_available = False
        self._stopwords: set[str] | None = None
        self._last_initialize_rebuilt = False

    async def initialize(self) -> None:
        """Create the wiki layout and reconcile rebuildable derived indexes."""
        self._last_initialize_rebuilt = False
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        await self._ensure_reserved_pages()

        try:
            await self._open_database()
        except sqlite3.DatabaseError as exc:
            if not self._is_corrupt_database_error(exc):
                await self.close()
                raise
            await self._recover_corrupt_database(exc)

        async with self._operation_lock:
            try:
                await self._migrate_legacy_doc_db()
                index_matches = await self._index_matches_markdown()
            except sqlite3.DatabaseError as exc:
                if not self._is_corrupt_database_error(exc):
                    raise
                await self._recover_corrupt_database(exc)
                await self._migrate_legacy_doc_db()
                index_matches = False
            if not index_matches:
                await self._rebuild_index_locked()
                self._last_initialize_rebuilt = True

    async def _open_database(self) -> None:
        """Open the derived SQLite database and create its current schema."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA busy_timeout=5000")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._create_schema()

    @staticmethod
    def _is_corrupt_database_error(exc: sqlite3.DatabaseError) -> bool:
        """Return whether a SQLite error indicates an unusable derived database.

        Args:
            exc: SQLite exception raised while opening or validating the index.

        Returns:
            Whether deleting and rebuilding only the derived database is safe.
        """
        message = str(exc).lower()
        return any(
            marker in message
            for marker in (
                "file is not a database",
                "database disk image is malformed",
                "database schema is corrupt",
                "malformed database schema",
            )
        )

    async def _recover_corrupt_database(self, exc: sqlite3.DatabaseError) -> None:
        """Replace a corrupt derived database while preserving Markdown pages.

        Args:
            exc: Corruption exception that triggered recovery.
        """
        logger.warning(
            f"Rebuilding corrupt Wiki index {self.db_path} from Markdown: {exc}"
        )
        await self.close()
        for path in (
            self.db_path,
            Path(f"{self.db_path}-wal"),
            Path(f"{self.db_path}-shm"),
        ):
            path.unlink(missing_ok=True)
        await self._open_database()

    async def _index_matches_markdown(self) -> bool:
        """Validate page metadata, chunks, and the derived graph against Markdown.

        Returns:
            Whether the current derived index is complete and matches every page.

        Raises:
            sqlite3.DatabaseError: If SQLite cannot validate the derived database.
        """
        markdown_hashes: dict[str, str] = {}
        markdown_metadata: dict[str, tuple[str, str, str, str, str]] = {}
        markdown_edges: set[tuple[str, str, str, str]] = set()
        for path in sorted(self.knowledge_dir.rglob("*.md")):
            rel_path = path.relative_to(self.knowledge_dir).as_posix()
            if rel_path in _RESERVED_PAGES:
                continue
            content = path.read_text(encoding="utf-8")
            markdown_hashes[rel_path] = hashlib.sha256(
                content.encode("utf-8")
            ).hexdigest()
            metadata = self._extract_page_metadata(rel_path, content)
            markdown_metadata[rel_path] = (
                metadata["title"],
                metadata["category"],
                metadata["node_type"],
                metadata["source"],
                metadata["summary"],
            )
            markdown_edges.update(
                (rel_path, target, relation, evidence or label)
                for target, label, relation, evidence in self._extract_links(
                    rel_path,
                    content,
                )
            )

        db = self._require_db()
        async with self._lock:
            async with db.execute("PRAGMA integrity_check") as cursor:
                integrity_rows = await cursor.fetchall()
            if [row[0] for row in integrity_rows] != ["ok"]:
                return False
            async with db.execute("SELECT path, content_hash FROM pages") as cursor:
                indexed_hashes = {
                    row["path"]: row["content_hash"] for row in await cursor.fetchall()
                }
            if indexed_hashes != markdown_hashes:
                return False
            async with db.execute(
                "SELECT path, title, category, node_type, source, summary FROM pages"
            ) as cursor:
                indexed_metadata = {
                    row["path"]: (
                        row["title"],
                        row["category"],
                        row["node_type"],
                        row["source"] or "",
                        row["summary"] or "",
                    )
                    for row in await cursor.fetchall()
                }
            if indexed_metadata != markdown_metadata:
                return False
            async with db.execute(
                "SELECT source, target, relation, evidence FROM graph_edges"
            ) as cursor:
                indexed_edges = {
                    (
                        row["source"],
                        row["target"],
                        row["relation"],
                        row["evidence"] or "",
                    )
                    for row in await cursor.fetchall()
                }
            if indexed_edges != markdown_edges:
                return False
            async with db.execute(
                """
                SELECT 1
                FROM chunks AS chunk
                LEFT JOIN pages AS page ON page.path = chunk.page_path
                WHERE page.path IS NULL
                   OR chunk.doc_id != page.doc_id
                   OR chunk.kb_id != ?
                LIMIT 1
                """,
                (self.kb_id,),
            ) as cursor:
                if await cursor.fetchone():
                    return False
            async with db.execute(
                """
                SELECT page.path
                FROM pages AS page
                LEFT JOIN chunks AS chunk ON chunk.page_path = page.path
                GROUP BY page.path
                HAVING COUNT(chunk.id) = 0
                    OR MIN(chunk.chunk_index) != 0
                    OR MAX(chunk.chunk_index) != COUNT(chunk.id) - 1
                LIMIT 1
                """
            ) as cursor:
                if await cursor.fetchone():
                    return False
            async with db.execute("SELECT embedding FROM chunks") as cursor:
                embedding_rows = await cursor.fetchall()
            if self.embedding_provider:
                expected_dimension = self.embedding_provider.get_dim()
                for row in embedding_rows:
                    if not row["embedding"]:
                        return False
                    try:
                        embedding = json.loads(row["embedding"])
                    except (TypeError, json.JSONDecodeError):
                        return False
                    if (
                        not isinstance(embedding, list)
                        or len(embedding) != expected_dimension
                    ):
                        return False
            elif any(row["embedding"] is not None for row in embedding_rows):
                return False
            async with db.execute(
                """
                SELECT 1
                FROM pages AS page
                LEFT JOIN graph_nodes AS node
                    ON node.id = page.path AND node.page_path = page.path
                WHERE node.id IS NULL
                LIMIT 1
                """
            ) as cursor:
                if await cursor.fetchone():
                    return False
            async with db.execute(
                """
                SELECT 1
                FROM graph_nodes AS node
                LEFT JOIN pages AS page ON page.path = node.id
                WHERE page.path IS NULL
                LIMIT 1
                """
            ) as cursor:
                return await cursor.fetchone() is None

    async def _create_schema(self) -> None:
        db = self._require_db()
        async with self._lock:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS pages (
                    path TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    node_type TEXT NOT NULL DEFAULT 'other',
                    source TEXT,
                    summary TEXT,
                    content_hash TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id TEXT NOT NULL UNIQUE,
                    doc_id TEXT NOT NULL,
                    kb_id TEXT NOT NULL,
                    page_path TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    search_text TEXT NOT NULL,
                    embedding TEXT,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(doc_id, chunk_index),
                    FOREIGN KEY(page_path) REFERENCES pages(path) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_wiki_chunks_doc_id ON chunks(doc_id);
                CREATE INDEX IF NOT EXISTS idx_wiki_chunks_kb_id ON chunks(kb_id);
                CREATE INDEX IF NOT EXISTS idx_wiki_chunks_page_path ON chunks(page_path);

                CREATE TABLE IF NOT EXISTS graph_nodes (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    node_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    page_path TEXT,
                    source TEXT,
                    evidence TEXT,
                    confidence REAL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS graph_edges (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    relation TEXT NOT NULL DEFAULT 'links_to',
                    evidence TEXT,
                    confidence REAL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(source, target, relation)
                );

                CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source);
                CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target);
                """
            )
            try:
                await db.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                        search_text,
                        content='chunks',
                        content_rowid='id',
                        tokenize='unicode61'
                    )
                    """
                )
                await db.executescript(
                    """
                    CREATE TRIGGER IF NOT EXISTS wiki_chunks_ai AFTER INSERT ON chunks BEGIN
                        INSERT INTO chunks_fts(rowid, search_text)
                        VALUES (new.id, new.search_text);
                    END;
                    CREATE TRIGGER IF NOT EXISTS wiki_chunks_ad AFTER DELETE ON chunks BEGIN
                        INSERT INTO chunks_fts(chunks_fts, rowid, search_text)
                        VALUES ('delete', old.id, old.search_text);
                    END;
                    CREATE TRIGGER IF NOT EXISTS wiki_chunks_au AFTER UPDATE ON chunks BEGIN
                        INSERT INTO chunks_fts(chunks_fts, rowid, search_text)
                        VALUES ('delete', old.id, old.search_text);
                        INSERT INTO chunks_fts(rowid, search_text)
                        VALUES (new.id, new.search_text);
                    END;
                    """
                )
                self.fts5_available = True
            except aiosqlite.OperationalError as exc:
                self.fts5_available = False
                logger.warning(
                    f"SQLite FTS5 is unavailable for WikiStore {self.db_path}; "
                    f"keyword search will use LIKE/BM25 fallback: {exc}"
                )
            await db.commit()

    @property
    def stopwords(self) -> set[str]:
        """Return cached sparse-search stop words."""
        if self._stopwords is None:
            self._stopwords = load_stopwords(
                Path(__file__).parent / "retrieval" / "hit_stopwords.txt"
            )
        return self._stopwords

    async def _ensure_reserved_pages(self) -> None:
        index_path = self.knowledge_dir / "index.md"
        log_path = self.knowledge_dir / "log.md"
        if not index_path.exists():
            await self._atomic_write(index_path, "# Knowledge Index\n")
        if not log_path.exists():
            await self._atomic_write(log_path, "# Knowledge Log\n")

    async def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            async with aiofiles.open(temp_path, "w", encoding="utf-8") as file:
                await file.write(content)
                await file.flush()
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)

    async def _write_json_atomically(self, path: Path, payload: dict) -> None:
        """Persist a JSON state file with an atomic same-directory replace.

        Args:
            path: Destination JSON file path.
            payload: JSON-serializable state.
        """
        await self._atomic_write(
            path,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )

    async def _migrate_legacy_doc_db(self) -> None:
        """Migrate the former chunk database into deterministic Wiki pages.

        The legacy database is opened read-only and is never renamed or
        deleted. A completed marker is written only after every source row is
        represented in the new derived index, which makes interrupted runs
        safe to resume.

        Raises:
            RuntimeError: If legacy rows are malformed or cannot be indexed.
        """
        legacy_db_path = self.kb_dir / "doc.db"
        if not legacy_db_path.is_file():
            return

        fingerprint = hashlib.sha256(legacy_db_path.read_bytes()).hexdigest()
        if self.legacy_migration_path.is_file():
            try:
                marker = json.loads(
                    self.legacy_migration_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                marker = {}
            if marker.get("state") == "complete":
                return

        connection = sqlite3.connect(
            f"file:{legacy_db_path.as_posix()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        try:
            legacy_rows = connection.execute(
                "SELECT id, doc_id, text, metadata, created_at, updated_at "
                "FROM documents ORDER BY id"
            ).fetchall()
        finally:
            connection.close()

        migration_state = {
            "migration": "faiss-docdb-to-wiki",
            "version": _LEGACY_MIGRATION_VERSION,
            "kb_id": self.kb_id,
            "state": "running",
            "source": {
                "path": "doc.db",
                "sha256": fingerprint,
                "row_count": len(legacy_rows),
                "max_row_id": max((int(row["id"]) for row in legacy_rows), default=0),
            },
            "progress": {"documents_done": 0, "chunks_done": 0},
            "documents": {},
            "last_error": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._write_json_atomically(self.legacy_migration_path, migration_state)

        grouped: dict[str, list[dict]] = {}
        for row in legacy_rows:
            try:
                metadata = json.loads(row["metadata"] or "{}")
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Legacy chunk {row['doc_id']} has invalid metadata"
                ) from exc
            if not isinstance(metadata, dict):
                raise RuntimeError(
                    f"Legacy chunk {row['doc_id']} metadata must be an object"
                )
            metadata_kb_id = metadata.get("kb_id")
            if metadata_kb_id and str(metadata_kb_id) != self.kb_id:
                raise RuntimeError(
                    f"Legacy chunk {row['doc_id']} belongs to another knowledge base"
                )
            doc_id = str(metadata.get("kb_doc_id") or "").strip()
            if not doc_id:
                raise RuntimeError(f"Legacy chunk {row['doc_id']} is missing kb_doc_id")
            try:
                chunk_index = int(
                    metadata.get("chunk_index", len(grouped.get(doc_id, [])))
                )
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"Legacy chunk {row['doc_id']} has invalid chunk_index"
                ) from exc
            grouped.setdefault(doc_id, []).append(
                {
                    "chunk_id": str(row["doc_id"]),
                    "text": str(row["text"] or ""),
                    "metadata": metadata,
                    "chunk_index": chunk_index,
                }
            )

        preserved_legacy_ids: list[str] = []
        try:
            migrated_chunks = 0
            for documents_done, (doc_id, rows) in enumerate(
                sorted(grouped.items()), start=1
            ):
                rows.sort(key=lambda item: item["chunk_index"])
                indexes = [row["chunk_index"] for row in rows]
                if len(indexes) != len(set(indexes)):
                    raise RuntimeError(
                        f"Legacy document {doc_id} has duplicate chunk indexes"
                    )
                source = str(rows[0]["metadata"].get("source") or "legacy doc.db")
                title = Path(source).stem if source != "legacy doc.db" else doc_id
                page_path = f"legacy/{self._slugify(doc_id)}-{hashlib.sha256(doc_id.encode('utf-8')).hexdigest()[:8]}.md"
                page_chunks = [row["text"] for row in rows]
                markdown = (
                    "---\n"
                    f"doc_id: {doc_id}\n"
                    "type: source\n"
                    f"source: {' '.join(source.splitlines())}\n"
                    "---\n\n"
                    f"# {title}\n\n"
                    f"{_LEGACY_PAGE_NOTE}\n\n"
                    + _LEGACY_CHUNK_SEPARATOR.join(page_chunks)
                    + "\n"
                )
                target_path = self._resolve_page_path(page_path)
                indexed_content = markdown
                indexed_chunks = page_chunks
                indexed_chunk_ids: list[str] | None = [row["chunk_id"] for row in rows]
                if target_path.is_file():
                    indexed_content = target_path.read_text(encoding="utf-8")
                    existing_doc_id = self._parse_frontmatter(indexed_content).get(
                        "doc_id"
                    )
                    if existing_doc_id != doc_id:
                        raise RuntimeError(
                            f"Legacy target {page_path} already exists with a different "
                            "doc_id; refusing to overwrite Markdown"
                        )
                    legacy_body_prefix = f"{_LEGACY_PAGE_NOTE}\n\n"
                    existing_legacy_chunks = None
                    if legacy_body_prefix in indexed_content:
                        legacy_body = indexed_content.split(legacy_body_prefix, 1)[1]
                        if legacy_body.endswith("\n"):
                            legacy_body = legacy_body[:-1]
                        existing_legacy_chunks = legacy_body.split(
                            _LEGACY_CHUNK_SEPARATOR
                        )
                    if existing_legacy_chunks == page_chunks:
                        indexed_chunks = existing_legacy_chunks
                    else:
                        indexed_chunks = await self._chunk_markdown_content(
                            page_path,
                            indexed_content,
                        )
                        indexed_chunk_ids = None

                embeddings = await self._generate_embeddings(
                    indexed_chunks,
                    details={
                        "operation": "legacy_doc_db_migration",
                        "doc_id": doc_id,
                        "page_path": page_path,
                    },
                )
                await self._write_page_locked(
                    page_path,
                    indexed_content,
                    doc_id=doc_id,
                    chunks=indexed_chunks,
                    embeddings=embeddings,
                    chunk_ids=indexed_chunk_ids,
                    generate_embeddings=False,
                    require_existing=target_path.is_file(),
                )
                if indexed_chunk_ids is not None:
                    preserved_legacy_ids.extend(indexed_chunk_ids)
                migration_state["documents"][doc_id] = {
                    "doc_id": doc_id,
                    "chunk_ids": [row["chunk_id"] for row in rows],
                    "chunk_sha256": [
                        hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                        for chunk in page_chunks
                    ],
                }
                migrated_chunks += len(rows)
                migration_state["progress"] = {
                    "documents_done": documents_done,
                    "chunks_done": migrated_chunks,
                }
                migration_state["updated_at"] = datetime.now(timezone.utc).isoformat()
                await self._write_json_atomically(
                    self.legacy_migration_path, migration_state
                )

            if preserved_legacy_ids:
                db = self._require_db()
                for offset in range(0, len(preserved_legacy_ids), 900):
                    expected_ids = preserved_legacy_ids[offset : offset + 900]
                    placeholders = ",".join("?" for _ in expected_ids)
                    async with (
                        self._lock,
                        db.execute(
                            f"SELECT chunk_id FROM chunks WHERE chunk_id IN ({placeholders})",
                            expected_ids,
                        ) as cursor,
                    ):
                        actual_ids = {
                            row["chunk_id"] for row in await cursor.fetchall()
                        }
                    if actual_ids != set(expected_ids):
                        raise RuntimeError("Legacy migration validation failed")
        except Exception as exc:
            migration_state["state"] = "failed"
            migration_state["last_error"] = str(exc)
            migration_state["updated_at"] = datetime.now(timezone.utc).isoformat()
            await self._write_json_atomically(
                self.legacy_migration_path, migration_state
            )
            raise

        migration_state["state"] = "complete"
        migration_state["result"] = {
            "pages": len(grouped),
            "chunks": len(legacy_rows),
        }
        migration_state["last_error"] = None
        migration_state["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self._write_json_atomically(self.legacy_migration_path, migration_state)

    def _require_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("WikiStore is not initialized")
        return self._db

    def _resolve_page_path(self, rel_path: str, must_exist: bool = False) -> Path:
        normalized = unquote(rel_path or "").replace("\\", "/")
        pure_path = PurePosixPath(normalized)
        if (
            not normalized
            or pure_path.is_absolute()
            or ".." in pure_path.parts
            or any(part in {"", "."} for part in pure_path.parts)
            or pure_path.suffix.lower() != ".md"
        ):
            raise ValueError("Invalid wiki page path")
        full_path = (self.knowledge_dir / Path(*pure_path.parts)).resolve()
        knowledge_root = self.knowledge_dir.resolve()
        if not full_path.is_relative_to(knowledge_root):
            raise ValueError("Wiki page path escapes the knowledge directory")
        if must_exist and not full_path.is_file():
            raise FileNotFoundError(normalized)
        return full_path

    def _normalize_rel_path(self, rel_path: str) -> str:
        return (
            self._resolve_page_path(rel_path)
            .relative_to(self.knowledge_dir.resolve())
            .as_posix()
        )

    def _resolve_entry_path(self, rel_path: str, must_exist: bool = False) -> Path:
        """Resolve a page or directory path inside the knowledge directory.

        Args:
            rel_path: Relative page or directory path supplied by a caller.
            must_exist: Whether the resolved entry must already exist.

        Returns:
            Absolute path contained by the knowledge directory.

        Raises:
            ValueError: If the path is empty, absolute, or traverses outside.
            FileNotFoundError: If ``must_exist`` is true and the entry is absent.
        """
        normalized = unquote(rel_path or "").replace("\\", "/")
        pure_path = PurePosixPath(normalized)
        if (
            not normalized
            or pure_path.is_absolute()
            or ".." in pure_path.parts
            or any(part in {"", "."} for part in pure_path.parts)
        ):
            raise ValueError("Invalid wiki entry path")
        full_path = (self.knowledge_dir / Path(*pure_path.parts)).resolve()
        knowledge_root = self.knowledge_dir.resolve()
        if not full_path.is_relative_to(knowledge_root) or full_path == knowledge_root:
            raise ValueError("Wiki entry path escapes the knowledge directory")
        if must_exist and not full_path.exists():
            raise FileNotFoundError(normalized)
        return full_path

    def _normalize_entry_path(self, rel_path: str) -> str:
        """Normalize a page or directory path relative to ``knowledge/``.

        Args:
            rel_path: Relative page or directory path supplied by a caller.

        Returns:
            Normalized POSIX path.
        """
        return (
            self._resolve_entry_path(rel_path)
            .relative_to(self.knowledge_dir.resolve())
            .as_posix()
        )

    @staticmethod
    def _parse_frontmatter(content: str) -> dict[str, str]:
        match = _FRONTMATTER_RE.match(content)
        if not match:
            return {}
        metadata: dict[str, str] = {}
        for raw_line in match.group(1).splitlines():
            if ":" not in raw_line:
                continue
            key, value = raw_line.split(":", 1)
            metadata[key.strip().lower()] = value.strip().strip("\"'")
        return metadata

    @staticmethod
    def _strip_frontmatter(content: str) -> str:
        """Return Markdown body content without a leading frontmatter block.

        Args:
            content: Complete Markdown page content.

        Returns:
            Markdown body used for summaries and retrieval chunks.
        """
        match = _FRONTMATTER_RE.match(content)
        return content[match.end() :].lstrip("\n") if match else content

    def _extract_page_metadata(self, rel_path: str, content: str) -> dict[str, str]:
        frontmatter = self._parse_frontmatter(content)
        title_match = _TITLE_RE.search(content)
        source_match = _SOURCE_RE.search(content)
        path = PurePosixPath(rel_path)
        path_parts = path.parts
        title = (
            frontmatter.get("title")
            or (title_match.group(1).strip() if title_match else "")
            or Path(rel_path).stem.replace("-", " ").title()
        )
        declared_node_type = (
            frontmatter.get("type") or frontmatter.get("node_type") or ""
        ).lower()
        if declared_node_type in _NODE_TYPES:
            node_type = declared_node_type
        elif path.stem.casefold() == "_index":
            node_type = "overview"
        else:
            node_type = _DIRECTORY_NODE_TYPES.get(path_parts[0].casefold(), "other")
        summary = frontmatter.get("summary", "")
        if not summary:
            body_lines = [
                line.strip()
                for line in self._strip_frontmatter(content).splitlines()
                if line.strip()
                and not line.startswith("#")
                and not _SOURCE_RE.match(line)
                and not line.startswith("---")
            ]
            summary = body_lines[0][:200] if body_lines else ""
        return {
            "title": title,
            "category": path_parts[0] if len(path_parts) > 1 else "root",
            "node_type": node_type,
            "source": frontmatter.get("source")
            or (source_match.group(1).strip() if source_match else ""),
            "summary": summary,
        }

    async def _chunk_markdown_content(
        self,
        rel_path: str,
        content: str,
    ) -> list[str]:
        """Chunk a page body without indexing frontmatter as knowledge.

        Args:
            rel_path: Page path used to derive a fallback title.
            content: Complete persisted Markdown content.

        Returns:
            At least one retrieval chunk for the page.
        """
        body = self._strip_frontmatter(content).strip()
        chunker = MarkdownChunker(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        chunks = [
            chunk.strip()
            for chunk in await chunker.chunk(body)
            if chunk and chunk.strip()
        ]
        if chunks:
            return chunks
        return [self._extract_page_metadata(rel_path, content)["title"]]

    @staticmethod
    def _set_frontmatter_value(content: str, key: str, value: str) -> str:
        """Set a scalar key in the page frontmatter.

        Args:
            content: Complete Markdown page content.
            key: Frontmatter key.
            value: Scalar string value.

        Returns:
            Markdown content containing the requested frontmatter value.
        """
        match = _FRONTMATTER_RE.match(content)
        if match:
            lines = match.group(1).splitlines()
            replaced = False
            for index, line in enumerate(lines):
                if ":" not in line:
                    continue
                existing_key = line.split(":", 1)[0].strip().lower()
                if existing_key == key.lower():
                    lines[index] = f"{key}: {value}"
                    replaced = True
                    break
            if replaced:
                frontmatter = "\n".join(lines)
                return f"---\n{frontmatter}\n---\n" + content[match.end() :].lstrip(
                    "\n"
                )
            frontmatter = match.group(1).rstrip() + f"\n{key}: {value}"
            return f"---\n{frontmatter}\n---\n" + content[match.end() :].lstrip("\n")
        return f"---\n{key}: {value}\n---\n\n{content.lstrip()}"

    @staticmethod
    def _slugify(value: str) -> str:
        slug = _SLUG_RE.sub("-", value.lower()).strip("-")
        if slug:
            return slug[:80]
        return f"page-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]}"

    def build_ingested_page(
        self,
        doc_id: str,
        file_name: str,
        source: str,
        chunks: list[str],
        original_content: str | None = None,
        node_type: str = "source",
    ) -> tuple[str, str]:
        """Build a deterministic wiki page for an uploaded source.

        Args:
            doc_id: Stable document identifier.
            file_name: Original source name.
            source: Human-readable source description.
            chunks: Parsed and chunked source content.
            original_content: Parsed source text before overlapping chunking.
            node_type: Graph node type for the page.

        Returns:
            Relative page path and complete Markdown content.
        """
        title = (Path(file_name).stem or file_name or "Untitled").replace("\n", " ")
        slug = self._slugify(title)
        rel_path = f"sources/{slug}-{doc_id[:8]}.md"
        safe_type = node_type if node_type in _NODE_TYPES else "source"
        safe_source = " ".join(source.splitlines()).strip() or file_name
        body = original_content or "\n\n".join(
            chunk.strip() for chunk in chunks if chunk.strip()
        )
        markdown = (
            "---\n"
            f"doc_id: {doc_id}\n"
            f"type: {safe_type}\n"
            f"source: {safe_source}\n"
            "---\n\n"
            f"# {title}\n\n"
            f"> Source: {safe_source}\n\n"
            f"{body}\n"
        )
        return rel_path, markdown

    def _validate_embeddings(
        self,
        chunks: list[str],
        embeddings: list[list[float]] | None,
        *,
        details: dict | None = None,
    ) -> None:
        """Validate embedding count and configured provider dimension.

        Args:
            chunks: Text chunks that embeddings describe.
            embeddings: Generated embeddings, or ``None`` for lexical-only indexing.
            details: Extra error context for callers and API responses.

        Raises:
            KnowledgeBaseUploadError: If count or vector dimensions are invalid.
        """
        if embeddings is None:
            return
        if len(embeddings) != len(chunks):
            raise KnowledgeBaseUploadError(
                stage="embedding",
                user_message="向量化失败：嵌入结果数量与文本块数量不一致。",
                details={
                    **(details or {}),
                    "expected": len(chunks),
                    "actual": len(embeddings),
                },
            )
        expected_dim = (
            self.embedding_provider.get_dim() if self.embedding_provider else None
        )
        dimensions = {len(embedding) for embedding in embeddings}
        if len(dimensions) > 1 or (
            expected_dim is not None and dimensions and dimensions != {expected_dim}
        ):
            raise KnowledgeBaseUploadError(
                stage="embedding",
                user_message="向量化失败：嵌入向量维度与当前模型配置不一致。",
                details={
                    **(details or {}),
                    "expected_dimension": expected_dim,
                    "actual_dimensions": sorted(dimensions),
                },
            )

    async def _generate_embeddings(
        self,
        chunks: list[str],
        *,
        batch_size: int = 32,
        tasks_limit: int = 3,
        max_retries: int = 3,
        progress_callback=None,
        details: dict | None = None,
    ) -> list[list[float]] | None:
        """Generate and validate embeddings for a complete page update.

        Args:
            chunks: Text chunks to embed.
            batch_size: Embedding request batch size.
            tasks_limit: Maximum concurrent embedding batches.
            max_retries: Embedding request retry count.
            progress_callback: Optional ``(current, total)`` callback.
            details: Extra error context for callers and API responses.

        Returns:
            Validated embeddings, or ``None`` when no provider is configured.

        Raises:
            KnowledgeBaseUploadError: If generation or validation fails.
        """
        if not self.embedding_provider:
            if progress_callback:
                await progress_callback(len(chunks), len(chunks))
            return None
        try:
            embeddings = await self.embedding_provider.get_embeddings_batch(
                chunks,
                batch_size=batch_size,
                tasks_limit=tasks_limit,
                max_retries=max_retries,
                progress_callback=progress_callback,
            )
        except KnowledgeBaseUploadError:
            raise
        except Exception as exc:
            raise KnowledgeBaseUploadError(
                stage="embedding",
                user_message="向量化失败：无法为 Wiki 页面生成文本向量。",
                details=details,
            ) from exc
        self._validate_embeddings(chunks, embeddings, details=details)
        return embeddings

    async def upsert_document(
        self,
        *,
        doc_id: str,
        file_name: str,
        source: str,
        content: str,
        chunks: list[str],
        batch_size: int = 32,
        tasks_limit: int = 3,
        max_retries: int = 3,
        progress_callback=None,
    ) -> dict:
        """Create or replace an ingested source page and its derived indexes.

        Args:
            doc_id: Stable global document identifier.
            file_name: Original source file name.
            source: Human-readable provenance label.
            content: Parsed source text before chunk overlap is introduced.
            chunks: Precomputed retrieval chunks.
            batch_size: Embedding request batch size.
            tasks_limit: Maximum concurrent embedding batches.
            max_retries: Embedding request retry count.
            progress_callback: Optional ``(current, total)`` callback.

        Returns:
            Indexed page metadata.

        Raises:
            KnowledgeBaseUploadError: If configured embedding generation is invalid.
        """
        embeddings = await self._generate_embeddings(
            chunks,
            batch_size=batch_size,
            tasks_limit=tasks_limit,
            max_retries=max_retries,
            progress_callback=progress_callback,
            details={"file_name": file_name, "doc_id": doc_id},
        )

        rel_path, markdown = self.build_ingested_page(
            doc_id=doc_id,
            file_name=file_name,
            source=source,
            chunks=chunks,
            original_content=content,
        )
        page = await self.write_page(
            rel_path=rel_path,
            content=markdown,
            doc_id=doc_id,
            chunks=chunks,
            embeddings=embeddings,
        )
        await self.append_log("ingest", page["title"])
        return page

    @staticmethod
    def _normalize_import_path(raw_path: str, *, allow_empty: bool = False) -> str:
        """Validate and normalize an archive or import-relative path.

        Args:
            raw_path: Untrusted path supplied by a caller or archive member.
            allow_empty: Whether an empty path is valid for an optional prefix.

        Returns:
            A normalized POSIX relative path.

        Raises:
            ValueError: If the path is absolute, traverses upward, contains a
                Windows drive prefix or NUL byte, or has ambiguous components.
        """
        normalized = unquote(str(raw_path or "")).replace("\\", "/")
        if "\x00" in normalized:
            raise ValueError("Import path contains a NUL byte")
        if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
            raise ValueError("Import path must be relative")
        normalized = normalized.rstrip("/")
        if not normalized:
            if allow_empty:
                return ""
            raise ValueError("Import path cannot be empty")
        parts = normalized.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("Import path contains an unsafe component")
        return PurePosixPath(*parts).as_posix()

    @classmethod
    def _normalize_markdown_import_path(cls, raw_path: str) -> str | None:
        """Normalize supported Markdown aliases to a ``.md`` target path.

        Args:
            raw_path: Validated or untrusted relative source path.

        Returns:
            Normalized Markdown page path, or ``None`` for unsupported files.
        """
        normalized = cls._normalize_import_path(raw_path)
        pure_path = PurePosixPath(normalized)
        if pure_path.suffix.casefold() not in _MARKDOWN_IMPORT_SUFFIXES:
            return None
        return pure_path.with_suffix(".md").as_posix()

    @staticmethod
    def _decode_import_markdown(content: bytes, display_path: str) -> str:
        """Decode and validate one imported Markdown document.

        Args:
            content: Raw Markdown bytes.
            display_path: Human-readable source path used in errors.

        Returns:
            Strictly decoded, non-empty Markdown text.

        Raises:
            ValueError: If the bytes are not valid UTF-8 or contain no content.
        """
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"Markdown file is not valid UTF-8: {display_path}"
            ) from exc
        if not text.strip():
            raise ValueError(f"Markdown file is empty: {display_path}")
        return text

    @staticmethod
    def _zip_member_is_symlink(info: zipfile.ZipInfo) -> bool:
        """Return whether a ZIP entry represents a Unix symbolic link.

        Args:
            info: ZIP member metadata.

        Returns:
            Whether the member mode identifies a symbolic link.
        """
        return stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK

    def _collect_zip_import_candidates(
        self,
        archive_path: Path,
        prefix: str,
    ) -> tuple[list[dict], list[dict], int]:
        """Preflight one ZIP archive and read its Markdown members.

        Args:
            archive_path: Local ZIP archive path.
            prefix: Optional target directory relative to ``knowledge/``.

        Returns:
            Candidate pages, skipped entries, and declared expanded bytes.

        Raises:
            ValueError: If the archive is invalid, encrypted, unsafe, oversized,
                excessively compressed, or contains invalid Markdown.
        """
        candidates: list[dict] = []
        skipped: list[dict] = []
        expanded_bytes = 0
        compressed_bytes = 0
        try:
            archive = zipfile.ZipFile(archive_path)
        except (OSError, zipfile.BadZipFile) as exc:
            raise ValueError(f"Invalid ZIP archive: {archive_path.name}") from exc

        with archive:
            for info in archive.infolist():
                display_path = f"{archive_path.name}!/{info.filename}"
                member_path = self._normalize_import_path(info.filename)
                if info.flag_bits & 0x1:
                    raise ValueError(
                        f"Encrypted ZIP members are not supported: {display_path}"
                    )
                if self._zip_member_is_symlink(info):
                    raise ValueError(
                        f"ZIP symbolic links are not supported: {display_path}"
                    )
                if info.is_dir():
                    continue

                expanded_bytes += info.file_size
                compressed_bytes += info.compress_size
                if expanded_bytes > WIKI_IMPORT_MAX_EXPANDED_BYTES:
                    raise ValueError("ZIP expanded size exceeds the Wiki import limit")
                if info.file_size and (
                    not info.compress_size
                    or info.file_size / info.compress_size
                    > WIKI_IMPORT_MAX_COMPRESSION_RATIO
                ):
                    raise ValueError(
                        f"ZIP member compression ratio is unsafe: {display_path}"
                    )

                target_path = self._normalize_markdown_import_path(member_path)
                if target_path is None:
                    skipped.append({"path": display_path, "reason": "unsupported"})
                    continue
                if prefix:
                    target_path = self._normalize_markdown_import_path(
                        f"{prefix}/{target_path}"
                    )
                    if target_path is None:
                        raise ValueError("Import prefix produced a non-Markdown path")
                if target_path.casefold() in _RESERVED_PAGES:
                    skipped.append({"path": display_path, "reason": "reserved"})
                    continue
                try:
                    content = archive.read(info)
                except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                    raise ValueError(
                        f"Failed to read ZIP member: {display_path}"
                    ) from exc
                candidates.append(
                    {
                        "path": target_path,
                        "content": self._decode_import_markdown(content, display_path),
                        "source": display_path,
                    }
                )

            if expanded_bytes and (
                not compressed_bytes
                or expanded_bytes / compressed_bytes > WIKI_IMPORT_MAX_COMPRESSION_RATIO
            ):
                raise ValueError("ZIP aggregate compression ratio is unsafe")
        return candidates, skipped, expanded_bytes

    async def import_sources(
        self,
        sources: list[tuple[Path, str | None]],
        *,
        overwrite: bool = False,
    ) -> dict:
        """Import Markdown files, directories, and ZIP archives as Wiki pages.

        Directory and archive sources preserve their relative hierarchy. Their
        optional relative path is treated as a target directory prefix. For a
        direct Markdown file, the optional relative path is its exact target.
        All inputs are preflighted before any page is written, then the complete
        batch is indexed with one rebuild while holding one operation lock.

        Args:
            sources: Local paths, optionally paired with a target relative path.
            overwrite: Whether exact existing page paths may be replaced.

        Returns:
            Imported page metadata, skipped source entries, and rebuild counts.

        Raises:
            FileExistsError: If a target exists and overwrite is disabled.
            ValueError: If a source, path, archive, encoding, or batch is unsafe.
        """
        candidates: list[dict] = []
        skipped: list[dict] = []
        total_input_bytes = 0
        total_expanded_bytes = 0

        for source_spec in sources:
            if isinstance(source_spec, tuple):
                if len(source_spec) != 2:
                    raise ValueError("Wiki import source tuples must contain two items")
                local_path = Path(source_spec[0])
                requested_path = source_spec[1]
            else:
                local_path = Path(source_spec)
                requested_path = None
            source_label = str(requested_path or local_path.name)

            if local_path.is_symlink():
                raise ValueError(
                    f"Symbolic link sources are not supported: {source_label}"
                )
            if not local_path.exists():
                raise ValueError(f"Wiki import source does not exist: {source_label}")
            if requested_path is None:
                normalized_requested_path = ""
            else:
                normalized_requested_path = self._normalize_import_path(
                    requested_path,
                    allow_empty=True,
                )

            if local_path.is_dir():
                for root, directory_names, file_names in os.walk(
                    local_path,
                    followlinks=False,
                ):
                    root_path = Path(root)
                    for name in directory_names:
                        directory_path = root_path / name
                        if directory_path.is_symlink():
                            raise ValueError(
                                "Symbolic links are not supported: "
                                f"{directory_path.relative_to(local_path).as_posix()}"
                            )
                    for name in file_names:
                        file_path = root_path / name
                        relative_source = file_path.relative_to(local_path).as_posix()
                        if file_path.is_symlink():
                            raise ValueError(
                                f"Symbolic links are not supported: {relative_source}"
                            )
                        normalized_source = self._normalize_import_path(relative_source)
                        target_path = self._normalize_markdown_import_path(
                            normalized_source
                        )
                        display_path = relative_source
                        if target_path is None:
                            skipped.append(
                                {"path": display_path, "reason": "unsupported"}
                            )
                            continue
                        if normalized_requested_path:
                            target_path = self._normalize_markdown_import_path(
                                f"{normalized_requested_path}/{target_path}"
                            )
                            if target_path is None:
                                raise ValueError(
                                    "Import prefix produced a non-Markdown path"
                                )
                        if target_path.casefold() in _RESERVED_PAGES:
                            skipped.append({"path": display_path, "reason": "reserved"})
                            continue
                        if not file_path.is_file():
                            raise ValueError(
                                "Wiki import source is not a regular file: "
                                f"{relative_source}"
                            )
                        file_size = file_path.stat().st_size
                        total_input_bytes += file_size
                        total_expanded_bytes += file_size
                        if total_input_bytes > WIKI_IMPORT_MAX_INPUT_BYTES:
                            raise ValueError("Wiki import input size exceeds the limit")
                        if total_expanded_bytes > WIKI_IMPORT_MAX_EXPANDED_BYTES:
                            raise ValueError(
                                "Wiki import expanded size exceeds the limit"
                            )
                        content = await asyncio.to_thread(file_path.read_bytes)
                        candidates.append(
                            {
                                "path": target_path,
                                "content": self._decode_import_markdown(
                                    content,
                                    display_path,
                                ),
                                "source": display_path,
                            }
                        )
                continue

            if not local_path.is_file():
                raise ValueError(
                    f"Wiki import source is not a regular file: {source_label}"
                )
            source_size = local_path.stat().st_size
            if local_path.suffix.casefold() == ".zip":
                total_input_bytes += source_size
                if total_input_bytes > WIKI_IMPORT_MAX_INPUT_BYTES:
                    raise ValueError("Wiki import input size exceeds the limit")
                archive_candidates, archive_skipped, archive_expanded = (
                    self._collect_zip_import_candidates(
                        local_path,
                        normalized_requested_path,
                    )
                )
                total_expanded_bytes += archive_expanded
                if total_expanded_bytes > WIKI_IMPORT_MAX_EXPANDED_BYTES:
                    raise ValueError("Wiki import expanded size exceeds the limit")
                candidates.extend(archive_candidates)
                skipped.extend(archive_skipped)
                continue

            default_target = self._normalize_markdown_import_path(local_path.name)
            if default_target is None:
                skipped.append({"path": source_label, "reason": "unsupported"})
                continue
            if normalized_requested_path:
                target_path = self._normalize_markdown_import_path(
                    normalized_requested_path
                )
                if target_path is None:
                    raise ValueError(
                        "Direct Markdown target must use a Markdown suffix"
                    )
            else:
                target_path = default_target
            if target_path.casefold() in _RESERVED_PAGES:
                skipped.append({"path": target_path, "reason": "reserved"})
                continue
            total_input_bytes += source_size
            total_expanded_bytes += source_size
            if total_input_bytes > WIKI_IMPORT_MAX_INPUT_BYTES:
                raise ValueError("Wiki import input size exceeds the limit")
            if total_expanded_bytes > WIKI_IMPORT_MAX_EXPANDED_BYTES:
                raise ValueError("Wiki import expanded size exceeds the limit")
            content = await asyncio.to_thread(local_path.read_bytes)
            candidates.append(
                {
                    "path": target_path,
                    "content": self._decode_import_markdown(content, target_path),
                    "source": source_label,
                }
            )

        seen_targets: dict[str, str] = {}
        for candidate in candidates:
            folded_path = candidate["path"].casefold()
            previous_path = seen_targets.get(folded_path)
            if previous_path is not None:
                raise ValueError(
                    f"Duplicate or case-conflicting Wiki import paths: "
                    f"{previous_path} and {candidate['path']}"
                )
            seen_targets[folded_path] = candidate["path"]

        if not candidates:
            return {
                "imported": [],
                "skipped": skipped,
                "imported_count": 0,
                "skipped_count": len(skipped),
                "paths": [],
                "rebuild": None,
            }

        async with self._operation_lock:
            existing_paths: dict[str, str] = {}
            for existing_path in self.knowledge_dir.rglob("*.md"):
                relative_path = existing_path.relative_to(self.knowledge_dir).as_posix()
                folded_path = relative_path.casefold()
                previous_path = existing_paths.get(folded_path)
                if previous_path is not None and previous_path != relative_path:
                    raise ValueError(
                        f"Existing Wiki paths conflict by case: "
                        f"{previous_path} and {relative_path}"
                    )
                existing_paths[folded_path] = relative_path

            prepared_pages: list[dict] = []
            original_contents: dict[str, str | None] = {}
            for candidate in candidates:
                target_path = candidate["path"]
                existing_path = existing_paths.get(target_path.casefold())
                if existing_path is not None and existing_path != target_path:
                    raise ValueError(
                        f"Wiki import path conflicts by case with {existing_path}: "
                        f"{target_path}"
                    )
                if existing_path is not None and not overwrite:
                    raise FileExistsError(target_path)

                raw_target = self.knowledge_dir.joinpath(
                    *PurePosixPath(target_path).parts
                )
                probe = self.knowledge_dir
                for part in PurePosixPath(target_path).parts:
                    probe /= part
                    if probe.is_symlink():
                        raise ValueError(
                            f"Wiki import target uses a symbolic link: {target_path}"
                        )
                full_path = self._resolve_page_path(target_path)
                old_content = None
                if raw_target.is_file():
                    old_content = await asyncio.to_thread(
                        raw_target.read_text,
                        encoding="utf-8",
                    )
                original_contents[target_path] = old_content

                if old_content is not None:
                    doc_id = self._parse_frontmatter(old_content).get("doc_id")
                    if not doc_id:
                        page_metadata = await self.get_page_metadata(target_path)
                        doc_id = page_metadata["doc_id"] if page_metadata else None
                else:
                    doc_id = None
                doc_id = doc_id or str(uuid.uuid4())
                prepared_content = self._set_frontmatter_value(
                    candidate["content"],
                    "doc_id",
                    doc_id,
                )
                chunks = await self._chunk_markdown_content(
                    target_path,
                    prepared_content,
                )
                metadata = self._extract_page_metadata(target_path, prepared_content)
                prepared_pages.append(
                    {
                        "path": target_path,
                        "full_path": full_path,
                        "content": prepared_content,
                        "doc_id": doc_id,
                        "title": metadata["title"],
                        "category": metadata["category"],
                        "node_type": metadata["node_type"],
                        "source": metadata["source"],
                        "summary": metadata["summary"],
                        "chunk_count": len(chunks),
                        "size": len(prepared_content.encode("utf-8")),
                    }
                )

            written_pages: list[dict] = []
            try:
                for prepared in prepared_pages:
                    await self._atomic_write(
                        prepared["full_path"],
                        prepared["content"],
                    )
                    written_pages.append(prepared)
                rebuild_result = await self._rebuild_index_locked()
            except Exception:
                for prepared in reversed(written_pages):
                    old_content = original_contents[prepared["path"]]
                    try:
                        if old_content is None:
                            prepared["full_path"].unlink(missing_ok=True)
                        else:
                            await self._atomic_write(
                                prepared["full_path"],
                                old_content,
                            )
                    except Exception as restore_exc:
                        logger.error(
                            f"Failed to restore Wiki page {prepared['path']} after "
                            f"batch import failure: {restore_exc}"
                        )
                for prepared in reversed(written_pages):
                    parent = prepared["full_path"].parent
                    while parent != self.knowledge_dir and parent.exists():
                        try:
                            parent.rmdir()
                        except OSError:
                            break
                        parent = parent.parent
                raise

        imported = [
            {
                key: page[key]
                for key in (
                    "path",
                    "doc_id",
                    "title",
                    "category",
                    "node_type",
                    "source",
                    "summary",
                    "chunk_count",
                    "size",
                )
            }
            for page in prepared_pages
        ]
        return {
            "imported": imported,
            "skipped": skipped,
            "imported_count": len(imported),
            "skipped_count": len(skipped),
            "paths": [page["path"] for page in imported],
            "rebuild": rebuild_result,
        }

    async def write_page(
        self,
        rel_path: str,
        content: str,
        doc_id: str | None = None,
        chunks: list[str] | None = None,
        embeddings: list[list[float]] | None = None,
        chunk_ids: list[str] | None = None,
        generate_embeddings: bool = True,
        create_only: bool = False,
        require_existing: bool = False,
    ) -> dict:
        """Atomically write and index one Markdown page.

        Args:
            rel_path: Page path relative to ``knowledge/``.
            content: Complete Markdown content.
            doc_id: Optional stable document identifier.
            chunks: Optional precomputed chunks used for indexing.
            embeddings: Optional embeddings corresponding to ``chunks``.
            chunk_ids: Optional public chunk identifiers corresponding to ``chunks``.
            generate_embeddings: Whether to generate embeddings when omitted.
            create_only: Fail if the Markdown file already exists.
            require_existing: Fail if the Markdown file does not exist.

        Returns:
            Indexed page metadata.

        Raises:
            ValueError: If the path, content, or embedding shape is invalid.
            FileExistsError: If ``create_only`` targets an existing file.
            FileNotFoundError: If ``require_existing`` targets a missing file.
        """
        if create_only and require_existing:
            raise ValueError("create_only and require_existing cannot both be enabled")
        async with self._operation_lock:
            return await self._write_page_locked(
                rel_path=rel_path,
                content=content,
                doc_id=doc_id,
                chunks=chunks,
                embeddings=embeddings,
                chunk_ids=chunk_ids,
                generate_embeddings=generate_embeddings,
                create_only=create_only,
                require_existing=require_existing,
            )

    async def _write_page_locked(
        self,
        rel_path: str,
        content: str,
        doc_id: str | None = None,
        chunks: list[str] | None = None,
        embeddings: list[list[float]] | None = None,
        chunk_ids: list[str] | None = None,
        generate_embeddings: bool = True,
        create_only: bool = False,
        require_existing: bool = False,
    ) -> dict:
        """Write one page while the caller holds the operation lock.

        Args:
            rel_path: Page path relative to ``knowledge/``.
            content: Complete Markdown content.
            doc_id: Optional stable document identifier.
            chunks: Optional precomputed retrieval chunks.
            embeddings: Optional embeddings corresponding to ``chunks``.
            chunk_ids: Optional public chunk identifiers.
            generate_embeddings: Whether to generate missing embeddings.
            create_only: Fail when the Markdown file already exists.
            require_existing: Fail when the Markdown file does not exist.

        Returns:
            Indexed page metadata.

        Raises:
            FileExistsError: If a create-only target already exists.
            FileNotFoundError: If a required target does not exist.
        """
        normalized_path = self._normalize_rel_path(rel_path)
        if normalized_path in _RESERVED_PAGES:
            raise ValueError("Reserved wiki pages cannot be replaced through page CRUD")
        if not content.strip():
            raise ValueError("Wiki page content cannot be empty")

        full_path = self._resolve_page_path(normalized_path)
        page_exists = full_path.is_file()
        if create_only and page_exists:
            raise FileExistsError(normalized_path)
        if require_existing and not page_exists:
            raise FileNotFoundError(normalized_path)

        prepared_content = content
        frontmatter = self._parse_frontmatter(prepared_content)
        if doc_id is None:
            doc_id = frontmatter.get("doc_id")
        if doc_id is None and page_exists:
            existing_page = await self.get_page_metadata(normalized_path)
            if existing_page:
                doc_id = existing_page["doc_id"]
        doc_id = doc_id or str(uuid.uuid4())
        prepared_content = self._set_frontmatter_value(
            prepared_content, "doc_id", doc_id
        )

        if chunks is None:
            chunks = await self._chunk_markdown_content(
                normalized_path,
                prepared_content,
            )
        if chunk_ids is not None and len(chunk_ids) != len(chunks):
            raise ValueError("Chunk ID count must match chunk count")
        if embeddings is None and generate_embeddings:
            embeddings = await self._generate_embeddings(
                chunks,
                details={"page_path": normalized_path, "doc_id": doc_id},
            )
        else:
            self._validate_embeddings(
                chunks,
                embeddings,
                details={"page_path": normalized_path, "doc_id": doc_id},
            )

        old_content = None
        if page_exists:
            async with aiofiles.open(full_path, encoding="utf-8") as file:
                old_content = await file.read()

        await self._atomic_write(full_path, prepared_content)
        try:
            page = await self._index_page(
                normalized_path,
                prepared_content,
                doc_id=doc_id,
                chunks=chunks,
                embeddings=embeddings,
                chunk_ids=chunk_ids,
            )
        except Exception:
            if old_content is None:
                full_path.unlink(missing_ok=True)
            else:
                await self._atomic_write(full_path, old_content)
            raise
        await self._refresh_reserved_pages_best_effort()
        return page

    async def _index_page(
        self,
        rel_path: str,
        content: str,
        doc_id: str | None = None,
        chunks: list[str] | None = None,
        embeddings: list[list[float]] | None = None,
        chunk_ids: list[str] | None = None,
    ) -> dict:
        frontmatter = self._parse_frontmatter(content)
        if doc_id is None:
            doc_id = frontmatter.get("doc_id")
        db = self._require_db()
        async with (
            self._lock,
            db.execute(
                "SELECT doc_id, created_at FROM pages WHERE path = ?",
                (rel_path,),
            ) as cursor,
        ):
            existing = await cursor.fetchone()
        if doc_id is None:
            doc_id = existing["doc_id"] if existing else str(uuid.uuid4())
        content = self._set_frontmatter_value(content, "doc_id", doc_id)
        full_path = self._resolve_page_path(rel_path)
        async with aiofiles.open(full_path, encoding="utf-8") as file:
            persisted_content = await file.read()
        if persisted_content != content:
            await self._atomic_write(full_path, content)

        if chunks is None:
            chunks = await self._chunk_markdown_content(rel_path, content)
        if embeddings is not None and len(embeddings) != len(chunks):
            raise ValueError("Embedding count must match chunk count")
        if chunk_ids is not None and len(chunk_ids) != len(chunks):
            raise ValueError("Chunk ID count must match chunk count")

        now = datetime.now(timezone.utc).isoformat()
        created_at = existing["created_at"] if existing else now
        resolved_chunk_ids = chunk_ids or [
            str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{self.kb_id}:{doc_id}:{chunk_index}",
                )
            )
            for chunk_index in range(len(chunks))
        ]
        async with self._lock:
            try:
                await db.execute("BEGIN IMMEDIATE")
                page = await self._write_page_index_rows(
                    db,
                    rel_path=rel_path,
                    content=content,
                    doc_id=doc_id,
                    chunks=chunks,
                    embeddings=embeddings,
                    chunk_ids=resolved_chunk_ids,
                    created_at=created_at,
                    updated_at=now,
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        return page

    async def _write_page_index_rows(
        self,
        db: aiosqlite.Connection,
        *,
        rel_path: str,
        content: str,
        doc_id: str,
        chunks: list[str],
        embeddings: list[list[float]] | None,
        chunk_ids: list[str],
        created_at: str,
        updated_at: str,
    ) -> dict:
        """Replace one page's derived rows inside the caller's transaction.

        Args:
            db: Open SQLite connection with an active write transaction.
            rel_path: Page path relative to ``knowledge/``.
            content: Complete Markdown page content.
            doc_id: Stable page document identifier.
            chunks: Retrieval chunks derived from the page body.
            embeddings: Optional vectors corresponding to ``chunks``.
            chunk_ids: Validated public identifiers for every chunk.
            created_at: Original or newly assigned page creation timestamp.
            updated_at: Timestamp for all replacement rows.

        Returns:
            Indexed page metadata.
        """
        metadata = self._extract_page_metadata(rel_path, content)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        links = self._extract_links(rel_path, content)
        await db.execute("DELETE FROM chunks WHERE page_path = ?", (rel_path,))
        await db.execute("DELETE FROM graph_edges WHERE source = ?", (rel_path,))
        await db.execute(
            """
            INSERT INTO pages(
                path, doc_id, title, category, node_type, source, summary,
                content_hash, size, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                doc_id = excluded.doc_id,
                title = excluded.title,
                category = excluded.category,
                node_type = excluded.node_type,
                source = excluded.source,
                summary = excluded.summary,
                content_hash = excluded.content_hash,
                size = excluded.size,
                updated_at = excluded.updated_at
            """,
            (
                rel_path,
                doc_id,
                metadata["title"],
                metadata["category"],
                metadata["node_type"],
                metadata["source"] or None,
                metadata["summary"] or None,
                content_hash,
                len(content.encode("utf-8")),
                created_at,
                updated_at,
            ),
        )
        await db.execute(
            """
            INSERT INTO graph_nodes(
                id, label, node_type, category, page_path, source,
                evidence, confidence, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                label = excluded.label,
                node_type = excluded.node_type,
                category = excluded.category,
                page_path = excluded.page_path,
                source = excluded.source,
                evidence = excluded.evidence,
                confidence = excluded.confidence,
                metadata = excluded.metadata
            """,
            (
                rel_path,
                metadata["title"],
                metadata["node_type"],
                metadata["category"],
                rel_path,
                metadata["source"] or None,
                metadata["summary"] or None,
                1.0,
                json.dumps({"doc_id": doc_id}, ensure_ascii=False),
            ),
        )
        for chunk_index, (chunk, chunk_id) in enumerate(zip(chunks, chunk_ids)):
            chunk_metadata = {
                "kb_id": self.kb_id,
                "kb_doc_id": doc_id,
                "chunk_index": chunk_index,
                "page_path": rel_path,
            }
            embedding = embeddings[chunk_index] if embeddings is not None else None
            await db.execute(
                """
                INSERT INTO chunks(
                    chunk_id, doc_id, kb_id, page_path, chunk_index, text,
                    search_text, embedding, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    doc_id,
                    self.kb_id,
                    rel_path,
                    chunk_index,
                    chunk,
                    to_fts5_search_text(chunk, self.stopwords),
                    json.dumps(embedding) if embedding is not None else None,
                    json.dumps(chunk_metadata, ensure_ascii=False),
                    updated_at,
                    updated_at,
                ),
            )
        for target, label, relation, evidence in links:
            edge_id = hashlib.sha256(
                f"{rel_path}\0{target}\0{relation}".encode()
            ).hexdigest()
            await db.execute(
                """
                INSERT OR IGNORE INTO graph_edges(
                    id, source, target, relation, evidence, confidence, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge_id,
                    rel_path,
                    target,
                    relation,
                    evidence or label,
                    1.0,
                    json.dumps(
                        {
                            "kind": (
                                "typed_knowledge_relation"
                                if relation != "links_to"
                                else "markdown_link"
                            ),
                            "label": label,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

        return {
            "path": rel_path,
            "doc_id": doc_id,
            "title": metadata["title"],
            "category": metadata["category"],
            "node_type": metadata["node_type"],
            "source": metadata["source"],
            "summary": metadata["summary"],
            "chunk_count": len(chunks),
            "updated_at": updated_at,
        }

    async def page_path_for_doc_id(self, doc_id: str) -> str | None:
        """Return the indexed page path for a document identifier.

        Args:
            doc_id: Stable global document identifier.

        Returns:
            Relative page path when found.
        """
        db = self._require_db()
        async with (
            self._lock,
            db.execute(
                "SELECT path FROM pages WHERE doc_id = ?",
                (doc_id,),
            ) as cursor,
        ):
            row = await cursor.fetchone()
        return row["path"] if row else None

    async def get_page_metadata(self, rel_path: str) -> dict | None:
        """Return indexed metadata for one page without reading its content.

        Args:
            rel_path: Page path relative to ``knowledge/``.

        Returns:
            Indexed page metadata when found.
        """
        normalized_path = self._normalize_rel_path(rel_path)
        db = self._require_db()
        async with (
            self._lock,
            db.execute(
                "SELECT * FROM pages WHERE path = ?",
                (normalized_path,),
            ) as cursor,
        ):
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def delete_document_page(self, doc_id: str) -> bool:
        """Delete the page mapped to a global document identifier.

        Args:
            doc_id: Stable global document identifier.

        Returns:
            Whether a mapped page existed.
        """
        page_path = await self.page_path_for_doc_id(doc_id)
        if not page_path:
            return False
        return await self.delete_page(page_path)

    def _resolve_link_target(self, source_path: str, raw_target: str) -> str | None:
        """Resolve a Markdown link using page-relative and Wiki-root semantics.

        Args:
            source_path: Page containing the link.
            raw_target: Raw Markdown or Wiki link target.

        Returns:
            Normalized page path, or ``None`` for external or unsafe targets.
        """
        source_parent = PurePosixPath(source_path).parent
        target = unquote(raw_target.strip().split("#", 1)[0])
        if not target or "://" in target or target.startswith(("mailto:", "#")):
            return None
        if not target.lower().endswith(".md"):
            target += ".md"
        target_path = PurePosixPath(target)
        candidate_paths = [target_path]
        if not target_path.is_absolute() and not target.startswith(("./", "../")):
            candidate_paths = [source_parent / target_path, target_path]
        elif not target_path.is_absolute():
            candidate_paths = [source_parent / target_path]

        normalized_candidates: list[str] = []
        for candidate_path in candidate_paths:
            resolved_parts: list[str] = []
            escaped_root = False
            for part in candidate_path.parts:
                if part in {"", ".", "/"}:
                    continue
                if part == "..":
                    if not resolved_parts:
                        escaped_root = True
                        break
                    resolved_parts.pop()
                else:
                    resolved_parts.append(part)
            if escaped_root or not resolved_parts:
                continue
            try:
                normalized_candidate = self._normalize_rel_path(
                    PurePosixPath(*resolved_parts).as_posix()
                )
            except ValueError:
                continue
            if normalized_candidate not in normalized_candidates:
                normalized_candidates.append(normalized_candidate)
        if not normalized_candidates:
            return None
        for normalized_candidate in normalized_candidates:
            candidate_file = self.knowledge_dir.joinpath(
                *PurePosixPath(normalized_candidate).parts
            )
            if candidate_file.is_file():
                return normalized_candidate
        return normalized_candidates[0]

    def _extract_links(
        self,
        source_path: str,
        content: str,
    ) -> list[tuple[str, str, str, str]]:
        """Extract generic links and persistent typed knowledge relations.

        Args:
            source_path: Wiki page containing the links.
            content: Complete Markdown page content.

        Returns:
            Tuples containing target path, label, relation, and evidence.
        """
        links: list[tuple[str, str, str, str]] = []
        seen: set[tuple[str, str]] = set()
        typed_targets: set[str] = set()
        candidates = [
            (
                raw_target,
                alias or raw_target,
                relation,
                evidence or alias or raw_target,
            )
            for relation, raw_target, alias, evidence in _RELATION_WIKI_LINK_RE.findall(
                content
            )
        ]
        candidates.extend(
            (raw_target, label, relation, evidence or label)
            for relation, label, raw_target, evidence in _RELATION_MARKDOWN_LINK_RE.findall(
                content
            )
        )
        candidates.extend(
            (raw_target, label, "links_to", label)
            for label, raw_target in _MARKDOWN_LINK_RE.findall(content)
        )
        candidates.extend(
            (raw_target, alias or raw_target, "links_to", alias or raw_target)
            for raw_target, alias in _WIKI_LINK_RE.findall(content)
        )
        for raw_target, label, raw_relation, evidence in candidates:
            rel_target = self._resolve_link_target(source_path, raw_target)
            if rel_target is None:
                continue
            relation = (
                re.sub(
                    r"[\s/\\:：]+",
                    "_",
                    raw_relation.strip().casefold(),
                )[:80]
                or "links_to"
            )
            if rel_target == source_path:
                continue
            if relation == "links_to" and rel_target in typed_targets:
                continue
            relation_key = (rel_target, relation)
            if relation_key in seen:
                continue
            seen.add(relation_key)
            if relation != "links_to":
                typed_targets.add(rel_target)
            links.append(
                (
                    rel_target,
                    label.strip(),
                    relation,
                    " ".join(evidence.split()).strip()[:600],
                )
            )
        return links

    def _rewrite_links_for_move(
        self,
        *,
        old_source_path: str,
        new_source_path: str,
        content: str,
        path_mapping: dict[str, str],
        known_pages: set[str],
    ) -> str:
        """Rewrite internal links affected by moving a page or directory.

        Args:
            old_source_path: Page path before the move.
            new_source_path: Page path after the move.
            content: Original Markdown content.
            path_mapping: Old-to-new page path mapping for moved pages.
            known_pages: All page paths that existed before the move.

        Returns:
            Markdown with affected internal links expressed relative to the new
            source page path.
        """

        def relative_target(resolved_target: str) -> str:
            final_target = path_mapping.get(resolved_target, resolved_target)
            new_parent = PurePosixPath(new_source_path).parent.as_posix()
            return posixpath.relpath(final_target, start=new_parent)

        def rewrite_markdown(match: re.Match[str]) -> str:
            label, raw_target = match.groups()
            resolved_target = self._resolve_link_target(
                old_source_path,
                raw_target,
            )
            if resolved_target not in known_pages:
                return match.group(0)
            if (
                old_source_path == new_source_path
                and resolved_target not in path_mapping
            ):
                return match.group(0)
            fragment = ""
            if "#" in raw_target:
                fragment = "#" + raw_target.split("#", 1)[1]
            return f"[{label}]({relative_target(resolved_target)}{fragment})"

        def rewrite_wiki(match: re.Match[str]) -> str:
            raw_target, fragment, alias = match.groups()
            resolved_target = self._resolve_link_target(
                old_source_path,
                raw_target,
            )
            if resolved_target not in known_pages:
                return match.group(0)
            if (
                old_source_path == new_source_path
                and resolved_target not in path_mapping
            ):
                return match.group(0)
            alias_text = f"|{alias}" if alias is not None else ""
            return f"[[{relative_target(resolved_target)}{fragment or ''}{alias_text}]]"

        rewritten = _MARKDOWN_LINK_RE.sub(rewrite_markdown, content)
        return _WIKI_LINK_FULL_RE.sub(rewrite_wiki, rewritten)

    async def _refresh_reserved_pages(self) -> None:
        db = self._require_db()
        async with (
            self._lock,
            db.execute(
                "SELECT path, title, category, summary FROM pages ORDER BY category, title"
            ) as cursor,
        ):
            rows = await cursor.fetchall()

        sections: dict[str, list[str]] = {}
        for row in rows:
            summary = f" — {row['summary']}" if row["summary"] else ""
            sections.setdefault(row["category"], []).append(
                f"- [{row['title']}]({row['path']}){summary}"
            )
        index_lines = ["# Knowledge Index", ""]
        for category, entries in sections.items():
            index_lines.extend((f"## {category}", *entries, ""))
        await self._atomic_write(
            self.knowledge_dir / "index.md",
            "\n".join(index_lines).rstrip() + "\n",
        )

    async def _refresh_reserved_pages_best_effort(self) -> None:
        """Refresh the derived index page without failing committed page writes."""
        try:
            await self._refresh_reserved_pages()
        except Exception as exc:
            logger.warning(
                f"Failed to refresh reserved Wiki pages for {self.kb_id}: {exc}"
            )

    async def append_log(self, operation: str, title: str) -> None:
        """Append one Wiki operation to the per-base log.

        Args:
            operation: Operation name such as ``ingest`` or ``update``.
            title: Page title.
        """
        log_path = self.knowledge_dir / "log.md"
        async with aiofiles.open(log_path, "a", encoding="utf-8") as file:
            await file.write(
                f"\n## [{datetime.now(timezone.utc).date().isoformat()}] "
                f"{operation} | {title}\n"
            )

    async def list_tree(self) -> dict:
        """Return the knowledge page hierarchy and aggregate statistics."""
        db = self._require_db()
        async with (
            self._lock,
            db.execute(
                "SELECT path, title, category, node_type, source, summary, size, updated_at "
                "FROM pages ORDER BY path"
            ) as cursor,
        ):
            rows = await cursor.fetchall()

        root: dict = {
            "name": "knowledge",
            "path": "",
            "type": "directory",
            "children": [],
        }
        directories: dict[str, dict] = {"": root}
        total_size = 0
        for row in rows:
            total_size += row["size"]
            parts = PurePosixPath(row["path"]).parts
            parent_key = ""
            for part in parts[:-1]:
                current_key = f"{parent_key}/{part}".strip("/")
                if current_key not in directories:
                    directory = {
                        "name": part,
                        "path": current_key,
                        "type": "directory",
                        "children": [],
                    }
                    directories[parent_key]["children"].append(directory)
                    directories[current_key] = directory
                parent_key = current_key
            directories[parent_key]["children"].append(
                {
                    "name": parts[-1],
                    "path": row["path"],
                    "type": "page",
                    "title": row["title"],
                    "category": row["category"],
                    "node_type": row["node_type"],
                    "source": row["source"],
                    "summary": row["summary"],
                    "size": row["size"],
                    "updated_at": row["updated_at"],
                }
            )
        return {"tree": root, "page_count": len(rows), "total_size": total_size}

    async def read_page(self, rel_path: str) -> dict:
        """Read one Markdown page with indexed metadata and backlinks.

        Args:
            rel_path: Page path relative to ``knowledge/``.

        Returns:
            Page content, metadata, outgoing links, and backlinks.
        """
        async with self._operation_lock:
            return await self._read_page_locked(rel_path)

    async def _read_page_locked(self, rel_path: str) -> dict:
        """Read one page while the caller holds the operation lock.

        Args:
            rel_path: Page path relative to ``knowledge/``.

        Returns:
            Page content, metadata, outgoing links, and backlinks.
        """
        normalized_path = self._normalize_rel_path(rel_path)
        full_path = self._resolve_page_path(normalized_path, must_exist=True)
        async with aiofiles.open(full_path, encoding="utf-8") as file:
            content = await file.read()
        db = self._require_db()
        async with self._lock:
            async with db.execute(
                "SELECT * FROM pages WHERE path = ?", (normalized_path,)
            ) as cursor:
                page = await cursor.fetchone()
            async with db.execute(
                "SELECT target, relation, evidence, confidence FROM graph_edges "
                "WHERE source = ? ORDER BY target",
                (normalized_path,),
            ) as cursor:
                outgoing = [dict(row) for row in await cursor.fetchall()]
            async with db.execute(
                "SELECT source, relation, evidence, confidence FROM graph_edges "
                "WHERE target = ? ORDER BY source",
                (normalized_path,),
            ) as cursor:
                backlinks = [dict(row) for row in await cursor.fetchall()]
        return {
            "path": normalized_path,
            "content": content,
            "metadata": dict(page)
            if page
            else self._extract_page_metadata(normalized_path, content),
            "links": outgoing,
            "backlinks": backlinks,
        }

    async def delete_page(self, rel_path: str) -> bool:
        """Delete a page and all derived chunks and outgoing graph edges.

        Args:
            rel_path: Page path relative to ``knowledge/``.

        Returns:
            Whether a page existed.
        """
        async with self._operation_lock:
            return await self._delete_page_locked(rel_path)

    async def _delete_page_locked(self, rel_path: str) -> bool:
        """Delete one page while the caller holds the operation lock.

        Args:
            rel_path: Page path relative to ``knowledge/``.

        Returns:
            Whether a Markdown file existed.
        """
        normalized_path = self._normalize_rel_path(rel_path)
        if normalized_path in _RESERVED_PAGES:
            raise ValueError("Reserved wiki pages cannot be deleted")
        full_path = self._resolve_page_path(normalized_path)
        existed = full_path.is_file()
        staged_path = None
        if existed:
            staged_path = full_path.with_name(
                f".{full_path.name}.{uuid.uuid4().hex}.delete"
            )
            full_path.replace(staged_path)
        db = self._require_db()
        try:
            async with self._lock:
                await db.execute("BEGIN IMMEDIATE")
                await db.execute(
                    "DELETE FROM graph_edges WHERE source = ?", (normalized_path,)
                )
                await db.execute(
                    "DELETE FROM graph_nodes WHERE id = ?", (normalized_path,)
                )
                await db.execute("DELETE FROM pages WHERE path = ?", (normalized_path,))
                await db.commit()
        except Exception:
            async with self._lock:
                await db.rollback()
            if staged_path is not None and staged_path.exists():
                staged_path.replace(full_path)
            raise
        if staged_path is not None:
            try:
                staged_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning(
                    f"Failed to remove staged Wiki page {staged_path}: {exc}"
                )
        parent = full_path.parent
        while parent != self.knowledge_dir and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
        await self._refresh_reserved_pages_best_effort()
        return existed

    async def move_path(self, source_path: str, target_path: str) -> dict:
        """Move one Wiki page or directory and rebuild affected indexes.

        Internal Markdown and Wiki links are rewritten relative to their new
        source locations so incoming and outgoing graph edges remain valid.

        Args:
            source_path: Existing page or directory path.
            target_path: Exact destination page or directory path.

        Returns:
            Moved page mappings and rebuilt index counts.

        Raises:
            FileExistsError: If the destination already exists.
            FileNotFoundError: If the source does not exist.
            ValueError: If either path is unsafe or the move is invalid.
        """
        async with self._operation_lock:
            normalized_source = self._normalize_entry_path(source_path)
            normalized_target = self._normalize_entry_path(target_path)
            if normalized_source == normalized_target:
                raise ValueError("Wiki source and target paths are identical")
            if (
                normalized_source in _RESERVED_PAGES
                or normalized_target in _RESERVED_PAGES
            ):
                raise ValueError("Reserved wiki pages cannot be moved")

            source_full = self._resolve_entry_path(
                normalized_source,
                must_exist=True,
            )
            target_full = self._resolve_entry_path(normalized_target)
            if target_full.exists():
                raise FileExistsError(normalized_target)
            if source_full.is_dir() and target_full.is_relative_to(source_full):
                raise ValueError("Wiki directories cannot be moved into themselves")
            if source_full.is_file() and (
                source_full.suffix.casefold() != ".md"
                or target_full.suffix.casefold() != ".md"
            ):
                raise ValueError("Wiki page moves require Markdown paths")

            db = self._require_db()
            async with self._lock:
                async with db.execute(
                    "SELECT path, doc_id, title FROM pages ORDER BY path"
                ) as cursor:
                    page_rows = [dict(row) for row in await cursor.fetchall()]

            if source_full.is_file():
                selected_rows = [
                    row for row in page_rows if row["path"] == normalized_source
                ]
            else:
                source_prefix = f"{normalized_source}/"
                selected_rows = [
                    row for row in page_rows if row["path"].startswith(source_prefix)
                ]
            if not selected_rows:
                raise FileNotFoundError(normalized_source)

            path_mapping: dict[str, str] = {}
            for row in selected_rows:
                old_path = row["path"]
                if source_full.is_file():
                    new_path = normalized_target
                else:
                    relative_path = old_path.removeprefix(f"{normalized_source}/")
                    new_path = f"{normalized_target}/{relative_path}"
                path_mapping[old_path] = new_path

            original_contents: dict[str, str] = {}
            for page_path in sorted(row["path"] for row in page_rows):
                full_path = self._resolve_page_path(page_path, must_exist=True)
                original_contents[page_path] = await asyncio.to_thread(
                    full_path.read_text,
                    encoding="utf-8",
                )
            known_pages = set(original_contents)
            rewritten_contents = {
                path_mapping.get(
                    old_page_path, old_page_path
                ): self._rewrite_links_for_move(
                    old_source_path=old_page_path,
                    new_source_path=path_mapping.get(old_page_path, old_page_path),
                    content=original_content,
                    path_mapping=path_mapping,
                    known_pages=known_pages,
                )
                for old_page_path, original_content in original_contents.items()
            }

            target_full.parent.mkdir(parents=True, exist_ok=True)
            source_full.replace(target_full)
            try:
                for old_page_path, original_content in original_contents.items():
                    new_page_path = path_mapping.get(old_page_path, old_page_path)
                    rewritten_content = rewritten_contents[new_page_path]
                    if rewritten_content != original_content:
                        await self._atomic_write(
                            self._resolve_page_path(new_page_path),
                            rewritten_content,
                        )
                rebuild = await self._rebuild_index_locked()
            except Exception:
                if target_full.exists() and not source_full.exists():
                    source_full.parent.mkdir(parents=True, exist_ok=True)
                    target_full.replace(source_full)
                for old_page_path, original_content in original_contents.items():
                    await self._atomic_write(
                        self._resolve_page_path(old_page_path),
                        original_content,
                    )
                raise

            parent = target_full.parent
            source_parent = source_full.parent
            while source_parent != self.knowledge_dir and source_parent.exists():
                try:
                    source_parent.rmdir()
                except OSError:
                    break
                source_parent = source_parent.parent
            return {
                "source_path": normalized_source,
                "target_path": normalized_target,
                "entry_type": "page"
                if source_full.suffix.casefold() == ".md"
                else "directory",
                "moved": [
                    {
                        "doc_id": row["doc_id"],
                        "title": row["title"],
                        "old_path": row["path"],
                        "new_path": path_mapping[row["path"]],
                    }
                    for row in selected_rows
                ],
                "rebuild": rebuild,
                "parent_path": parent.relative_to(self.knowledge_dir).as_posix()
                if parent != self.knowledge_dir
                else "",
            }

    async def delete_path(self, rel_path: str, *, recursive: bool = False) -> dict:
        """Delete one Wiki page or directory.

        Args:
            rel_path: Existing page or directory path.
            recursive: Whether a directory and all contained pages may be deleted.

        Returns:
            Deleted page metadata and rebuilt index counts when applicable.

        Raises:
            FileNotFoundError: If the requested entry does not exist.
            ValueError: If the path is unsafe, reserved, or requires recursion.
        """
        async with self._operation_lock:
            normalized_path = self._normalize_entry_path(rel_path)
            if normalized_path in _RESERVED_PAGES:
                raise ValueError("Reserved wiki pages cannot be deleted")
            full_path = self._resolve_entry_path(normalized_path, must_exist=True)
            if full_path.is_file():
                page = await self.get_page_metadata(normalized_path)
                if not page:
                    raise FileNotFoundError(normalized_path)
                deleted = await self._delete_page_locked(normalized_path)
                return {
                    "entry_type": "page",
                    "deleted": [page] if deleted else [],
                    "rebuild": None,
                }
            if not recursive:
                raise ValueError("Deleting a Wiki directory requires recursive=true")

            db = self._require_db()
            prefix = f"{normalized_path}/"
            async with self._lock:
                async with db.execute(
                    "SELECT path, doc_id, title FROM pages WHERE path LIKE ? ORDER BY path",
                    (f"{prefix}%",),
                ) as cursor:
                    pages = [dict(row) for row in await cursor.fetchall()]
            if not pages:
                raise FileNotFoundError(normalized_path)

            trash_root = self.kb_dir / ".wiki-trash"
            trash_root.mkdir(parents=True, exist_ok=True)
            staged_path = trash_root / uuid.uuid4().hex
            full_path.replace(staged_path)
            try:
                rebuild = await self._rebuild_index_locked()
            except Exception:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                staged_path.replace(full_path)
                raise
            await asyncio.to_thread(shutil.rmtree, staged_path, True)
            try:
                trash_root.rmdir()
            except OSError:
                pass
            return {
                "entry_type": "directory",
                "deleted": pages,
                "rebuild": rebuild,
            }

    async def get_graph(self) -> dict:
        """Return the current per-base knowledge graph."""
        db = self._require_db()
        async with self._lock:
            async with db.execute("SELECT * FROM graph_nodes ORDER BY label") as cursor:
                nodes = [dict(row) for row in await cursor.fetchall()]
            async with db.execute(
                "SELECT * FROM graph_edges ORDER BY source, target"
            ) as cursor:
                edges = [dict(row) for row in await cursor.fetchall()]
        valid_nodes = {node["id"] for node in nodes}
        return {
            "nodes": nodes,
            "edges": [
                edge
                for edge in edges
                if edge["source"] in valid_nodes and edge["target"] in valid_nodes
            ],
        }

    async def rebuild_index(self) -> dict[str, int]:
        """Rebuild all derived indexes after all pages pass preflight.

        Returns:
            Counts of rebuilt pages and chunks.

        Raises:
            KnowledgeBaseUploadError: If embedding preflight fails. The current
                derived index remains unchanged in that case.
            ValueError: If page or chunk identifiers conflict.
        """
        async with self._operation_lock:
            return await self._rebuild_index_locked()

    async def _rebuild_index_locked(self) -> dict[str, int]:
        """Atomically rebuild all indexes while holding the operation lock.

        Returns:
            Counts of rebuilt pages and chunks.

        Raises:
            KnowledgeBaseUploadError: If embedding preflight fails.
            ValueError: If page or chunk identifiers conflict.
        """
        legacy_documents: dict[str, dict] = {}
        if self.legacy_migration_path.is_file():
            try:
                marker = json.loads(
                    self.legacy_migration_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                marker = {}
            marker_documents = marker.get("documents")
            if marker.get("state") == "complete" and isinstance(marker_documents, dict):
                legacy_documents = marker_documents

        prepared_pages: list[dict] = []
        seen_doc_ids: dict[str, str] = {}
        seen_chunk_ids: dict[str, str] = {}
        rebuild_time = datetime.now(timezone.utc).isoformat()
        for path in sorted(self.knowledge_dir.rglob("*.md")):
            rel_path = path.relative_to(self.knowledge_dir).as_posix()
            if rel_path in _RESERVED_PAGES:
                continue
            async with aiofiles.open(path, encoding="utf-8") as file:
                original_content = await file.read()
            frontmatter = self._parse_frontmatter(original_content)
            page_metadata = await self.get_page_metadata(rel_path)
            doc_id = frontmatter.get("doc_id") or (
                page_metadata["doc_id"] if page_metadata else str(uuid.uuid4())
            )
            conflicting_path = seen_doc_ids.get(doc_id)
            if conflicting_path is not None:
                raise ValueError(
                    f"Duplicate wiki doc_id {doc_id!r} in {conflicting_path} and {rel_path}"
                )
            seen_doc_ids[doc_id] = rel_path
            content = self._set_frontmatter_value(original_content, "doc_id", doc_id)
            page_chunks = await self._chunk_markdown_content(rel_path, content)
            chunk_ids: list[str] | None = None
            legacy_document = legacy_documents.get(doc_id)
            if (
                isinstance(legacy_document, dict)
                and legacy_document.get("doc_id") == doc_id
            ):
                legacy_chunk_ids = legacy_document.get("chunk_ids")
                legacy_chunk_hashes = legacy_document.get("chunk_sha256")
                legacy_body_prefix = f"{_LEGACY_PAGE_NOTE}\n\n"
                legacy_page_chunks = None
                if legacy_body_prefix in content:
                    legacy_body = content.split(legacy_body_prefix, 1)[1]
                    if legacy_body.endswith("\n"):
                        legacy_body = legacy_body[:-1]
                    legacy_page_chunks = legacy_body.split(_LEGACY_CHUNK_SEPARATOR)
                legacy_page_hashes = (
                    [
                        hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                        for chunk in legacy_page_chunks
                    ]
                    if legacy_page_chunks is not None
                    else None
                )
                if (
                    isinstance(legacy_chunk_ids, list)
                    and all(
                        isinstance(chunk_id, str) and chunk_id
                        for chunk_id in legacy_chunk_ids
                    )
                    and len(set(legacy_chunk_ids)) == len(legacy_chunk_ids)
                    and isinstance(legacy_chunk_hashes, list)
                    and all(
                        isinstance(chunk_hash, str)
                        for chunk_hash in legacy_chunk_hashes
                    )
                    and legacy_page_chunks is not None
                    and len(legacy_chunk_ids) == len(legacy_page_chunks)
                    and legacy_chunk_hashes == legacy_page_hashes
                ):
                    page_chunks = legacy_page_chunks
                    chunk_ids = list(legacy_chunk_ids)

            resolved_chunk_ids = chunk_ids or [
                str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{self.kb_id}:{doc_id}:{chunk_index}",
                    )
                )
                for chunk_index in range(len(page_chunks))
            ]
            for chunk_id in resolved_chunk_ids:
                conflicting_page = seen_chunk_ids.get(chunk_id)
                if conflicting_page is not None:
                    raise ValueError(
                        f"Duplicate wiki chunk_id {chunk_id!r} in "
                        f"{conflicting_page} and {rel_path}"
                    )
                seen_chunk_ids[chunk_id] = rel_path
            embeddings = await self._generate_embeddings(
                page_chunks,
                details={"page_path": rel_path, "doc_id": doc_id},
            )
            prepared_pages.append(
                {
                    "path": rel_path,
                    "content": content,
                    "doc_id": doc_id,
                    "chunks": page_chunks,
                    "embeddings": embeddings,
                    "chunk_ids": resolved_chunk_ids,
                    "created_at": (
                        page_metadata["created_at"] if page_metadata else rebuild_time
                    ),
                    "full_path": path,
                    "original_content": original_content,
                }
            )

        changed_files = [
            prepared
            for prepared in prepared_pages
            if prepared["content"] != prepared["original_content"]
        ]
        written_files: list[dict] = []
        try:
            for prepared in changed_files:
                await self._atomic_write(prepared["full_path"], prepared["content"])
                written_files.append(prepared)
        except Exception:
            for prepared in reversed(written_files):
                try:
                    await self._atomic_write(
                        prepared["full_path"], prepared["original_content"]
                    )
                except Exception as restore_exc:
                    logger.error(
                        f"Failed to restore Wiki page {prepared['path']} after "
                        f"rebuild preflight failure: {restore_exc}"
                    )
            raise

        db = self._require_db()
        try:
            async with self._lock:
                try:
                    await db.execute("BEGIN IMMEDIATE")
                    await db.execute("DELETE FROM graph_edges")
                    await db.execute("DELETE FROM graph_nodes")
                    await db.execute("DELETE FROM chunks")
                    await db.execute("DELETE FROM pages")
                    for prepared in prepared_pages:
                        await self._write_page_index_rows(
                            db,
                            rel_path=prepared["path"],
                            content=prepared["content"],
                            doc_id=prepared["doc_id"],
                            chunks=prepared["chunks"],
                            embeddings=prepared["embeddings"],
                            chunk_ids=prepared["chunk_ids"],
                            created_at=prepared["created_at"],
                            updated_at=rebuild_time,
                        )
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
        except Exception:
            for prepared in reversed(written_files):
                try:
                    await self._atomic_write(
                        prepared["full_path"], prepared["original_content"]
                    )
                except Exception as restore_exc:
                    logger.error(
                        f"Failed to restore Wiki page {prepared['path']} after "
                        f"index rollback: {restore_exc}"
                    )
            raise

        await self._refresh_reserved_pages_best_effort()
        return {
            "pages": len(prepared_pages),
            "chunks": sum(len(page["chunks"]) for page in prepared_pages),
        }

    async def insert(
        self,
        content: str,
        metadata: dict | None = None,
        id: str | None = None,
    ) -> int:
        """Insert a single compatibility chunk.

        Args:
            content: Chunk content.
            metadata: Legacy chunk metadata including ``kb_doc_id``.
            id: Optional public chunk identifier.

        Returns:
            Internal integer chunk identifier.
        """
        result = await self.insert_batch(
            contents=[content],
            metadatas=[metadata or {}],
            ids=[id or str(uuid.uuid4())],
        )
        return result[0]

    async def insert_batch(
        self,
        contents: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
        batch_size: int = 32,
        tasks_limit: int = 3,
        max_retries: int = 3,
        progress_callback=None,
    ) -> list[int]:
        """Insert compatibility chunks into the derived index.

        This method exists for callers that have not yet migrated to page-level
        writes. New ingestion should use :meth:`write_page` so Markdown remains
        the knowledge source.

        Args:
            contents: Chunk contents.
            metadatas: Legacy metadata dictionaries.
            ids: Optional public chunk identifiers.
            batch_size: Embedding request batch size.
            tasks_limit: Maximum concurrent embedding batches.
            max_retries: Embedding request retry count.
            progress_callback: Optional ``(current, total)`` callback.

        Returns:
            Internal integer chunk identifiers.
        """
        if not contents:
            return []
        metadatas = metadatas or [{} for _ in contents]
        ids = ids or [str(uuid.uuid4()) for _ in contents]
        if len(contents) != len(metadatas) or len(contents) != len(ids):
            raise KnowledgeBaseUploadError(
                stage="storage",
                user_message="存储失败：文本块、元数据和块 ID 数量不一致。",
            )

        embeddings = await self._generate_embeddings(
            contents,
            batch_size=batch_size,
            tasks_limit=tasks_limit,
            max_retries=max_retries,
            progress_callback=progress_callback,
            details={"operation": "legacy_insert_batch"},
        )

        grouped: dict[tuple[str, str], list[int]] = {}
        for index, metadata in enumerate(metadatas):
            doc_id = str(metadata.get("kb_doc_id") or uuid.uuid4())
            metadata["kb_doc_id"] = doc_id
            metadata["kb_id"] = str(metadata.get("kb_id") or self.kb_id)
            metadata["chunk_index"] = int(metadata.get("chunk_index", index))
            page_path = str(metadata.get("page_path") or f"legacy/{doc_id}.md")
            metadata["page_path"] = self._normalize_rel_path(page_path)
            grouped.setdefault((doc_id, metadata["page_path"]), []).append(index)

        for (doc_id, page_path), indexes in grouped.items():
            ordered_indexes = sorted(
                indexes, key=lambda item: metadatas[item]["chunk_index"]
            )
            page_chunks = [contents[index] for index in ordered_indexes]
            page_embeddings = (
                [embeddings[index] for index in ordered_indexes] if embeddings else None
            )
            page_content = (
                "---\n"
                f"doc_id: {doc_id}\n"
                "type: other\n"
                "source: legacy compatibility import\n"
                "---\n\n"
                f"# {Path(page_path).stem.replace('-', ' ').title()}\n\n"
                + "\n\n".join(page_chunks)
                + "\n"
            )
            await self.write_page(
                rel_path=page_path,
                content=page_content,
                doc_id=doc_id,
                chunks=page_chunks,
                embeddings=page_embeddings,
                generate_embeddings=False,
            )

        db = self._require_db()
        placeholders = ",".join("?" for _ in ids)
        async with (
            self._lock,
            db.execute(
                f"SELECT id, chunk_id FROM chunks WHERE chunk_id IN ({placeholders})",
                ids,
            ) as cursor,
        ):
            rows = await cursor.fetchall()
        id_map = {row["chunk_id"]: int(row["id"]) for row in rows}
        if len(id_map) != len(ids):
            # Page-level indexing uses stable IDs; map them back to the caller's
            # requested IDs only for this legacy compatibility entry point.
            async with self._lock:
                for index, requested_id in enumerate(ids):
                    metadata = metadatas[index]
                    await db.execute(
                        "UPDATE chunks SET chunk_id = ? WHERE doc_id = ? AND chunk_index = ?",
                        (
                            requested_id,
                            metadata["kb_doc_id"],
                            metadata["chunk_index"],
                        ),
                    )
                await db.commit()
            async with (
                self._lock,
                db.execute(
                    f"SELECT id, chunk_id FROM chunks WHERE chunk_id IN ({placeholders})",
                    ids,
                ) as cursor,
            ):
                rows = await cursor.fetchall()
            id_map = {row["chunk_id"]: int(row["id"]) for row in rows}
        return [id_map[chunk_id] for chunk_id in ids]

    async def retrieve(
        self,
        query: str,
        k: int = 5,
        fetch_k: int = 20,
        rerank: bool = False,
        metadata_filters: dict | None = None,
        **kwargs,
    ) -> list[Result]:
        """Retrieve dense results when an embedding provider is configured.

        Args:
            query: Query text.
            k: Maximum result count.
            fetch_k: Candidate count before metadata filtering.
            rerank: Whether to apply the configured reranker.
            metadata_filters: Legacy metadata equality filters.
            kwargs: Optional compatibility arguments such as ``top_k``.

        Returns:
            Dense retrieval results, or an empty list without embeddings.
        """
        if "top_k" in kwargs:
            k = int(kwargs["top_k"])
        if not self.embedding_provider:
            return []
        query_embedding = await self.embedding_provider.get_embedding(query)
        rows = await self.document_storage.get_documents(
            metadata_filters or {}, offset=None, limit=None
        )
        scored: list[Result] = []
        for row in rows:
            raw_embedding = row.get("embedding")
            if not raw_embedding:
                continue
            embedding = json.loads(raw_embedding)
            similarity = self._cosine_similarity(query_embedding, embedding)
            scored.append(Result(similarity=similarity, data=row))
        scored.sort(key=lambda result: result.similarity, reverse=True)
        top_results = scored[: max(k, fetch_k if metadata_filters else k)]
        if rerank and self.rerank_provider and top_results:
            reranked = await self.rerank_provider.rerank(
                query, [result.data["text"] for result in top_results]
            )
            top_results = [
                top_results[item.index]
                for item in sorted(
                    reranked, key=lambda item: item.relevance_score, reverse=True
                )
                if item.index < len(top_results)
            ]
        return top_results[:k]

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            return 0.0
        dot_product = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if not left_norm or not right_norm:
            return 0.0
        return dot_product / (left_norm * right_norm)

    async def search_sparse(
        self,
        query_tokens: list[str],
        limit: int = 10,
    ) -> list[dict] | None:
        """Search the derived chunk index with FTS5 and CJK LIKE fallback.

        Args:
            query_tokens: Tokenized query terms.
            limit: Maximum result count.

        Returns:
            Sparse result rows or ``None`` when no native sparse index exists.
        """
        db = self._require_db()
        results: list[dict] = []
        if self.fts5_available:
            fts_query = build_fts5_or_query(query_tokens)
            if fts_query:
                try:
                    async with (
                        self._lock,
                        db.execute(
                            """
                        SELECT chunks.*, bm25(chunks_fts) AS score
                        FROM chunks_fts
                        JOIN chunks ON chunks.id = chunks_fts.rowid
                        WHERE chunks_fts MATCH ?
                        ORDER BY score
                        LIMIT ?
                        """,
                            (fts_query, limit),
                        ) as cursor,
                    ):
                        rows = await cursor.fetchall()
                    results = [self._chunk_row_to_sparse(row) for row in rows]
                except aiosqlite.OperationalError:
                    results = []
        if results:
            return results

        cjk_terms = [token for token in query_tokens if _CJK_RE.search(token)]
        if not cjk_terms:
            return [] if self.fts5_available else None
        conditions = " OR ".join("text LIKE ?" for _ in cjk_terms)
        params: list[object] = [f"%{term}%" for term in cjk_terms]
        params.append(limit)
        async with (
            self._lock,
            db.execute(
                f"SELECT *, -0.5 AS score FROM chunks WHERE {conditions} LIMIT ?",
                params,
            ) as cursor,
        ):
            rows = await cursor.fetchall()
        return [self._chunk_row_to_sparse(row) for row in rows]

    def _chunk_row_to_legacy(self, row: aiosqlite.Row) -> dict:
        return {
            "id": row["id"],
            "doc_id": row["chunk_id"],
            "text": row["text"],
            "metadata": row["metadata"],
            "embedding": row["embedding"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _chunk_row_to_sparse(self, row: aiosqlite.Row) -> dict:
        result = self._chunk_row_to_legacy(row)
        result["score"] = row["score"]
        return result

    async def delete(self, chunk_id: str) -> None:
        """Delete a single derived chunk.

        Args:
            chunk_id: Public chunk UUID.
        """
        db = self._require_db()
        async with self._lock:
            await db.execute("DELETE FROM chunks WHERE chunk_id = ?", (chunk_id,))
            await db.commit()

    async def delete_documents(self, metadata_filters: dict) -> None:
        """Delete all chunks matching legacy metadata filters.

        Args:
            metadata_filters: Metadata equality filters.
        """
        db = self._require_db()
        page_paths: list[str] = []
        if "kb_doc_id" in metadata_filters:
            async with (
                self._lock,
                db.execute(
                    "SELECT DISTINCT page_path FROM chunks WHERE doc_id = ?",
                    (metadata_filters["kb_doc_id"],),
                ) as cursor,
            ):
                page_paths = [row["page_path"] for row in await cursor.fetchall()]
        if page_paths:
            for page_path in page_paths:
                await self.delete_page(page_path)
            return
        conditions: list[str] = []
        params: list[object] = []
        column_map = {"kb_id": "kb_id", "kb_doc_id": "doc_id", "page_path": "page_path"}
        for key, value in metadata_filters.items():
            column = column_map.get(key)
            if column:
                conditions.append(f"{column} = ?")
                params.append(value)
            else:
                conditions.append("json_extract(metadata, ?) = ?")
                params.extend((f"$.{key}", value))
        if not conditions:
            return
        async with self._lock:
            await db.execute(
                "DELETE FROM chunks WHERE " + " AND ".join(conditions), params
            )
            await db.commit()

    async def count_documents(self, metadata_filter: dict | None = None) -> int:
        """Count derived chunks matching legacy metadata filters.

        Args:
            metadata_filter: Metadata equality filters.

        Returns:
            Matching chunk count.
        """
        db = self._require_db()
        conditions: list[str] = []
        params: list[object] = []
        column_map = {"kb_id": "kb_id", "kb_doc_id": "doc_id", "page_path": "page_path"}
        for key, value in (metadata_filter or {}).items():
            column = column_map.get(key)
            if column:
                conditions.append(f"{column} = ?")
                params.append(value)
            else:
                conditions.append("json_extract(metadata, ?) = ?")
                params.extend((f"$.{key}", value))
        sql = "SELECT COUNT(*) FROM chunks"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        async with self._lock, db.execute(sql, params) as cursor:
            row = await cursor.fetchone()
        return int(row[0] if row else 0)

    async def close(self) -> None:
        """Close the derived SQLite index."""
        if self._db is not None:
            await self._db.close()
            self._db = None


__all__ = ["WikiDocumentStorage", "WikiStore"]
