from __future__ import annotations

import asyncio
import shutil
import tempfile
import traceback
import uuid
from pathlib import Path
from typing import Any

import aiofiles

from astrbot.core import logger
from astrbot.core.core_lifecycle import AstrBotCoreLifecycle
from astrbot.core.knowledge_base.models import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
)
from astrbot.core.provider.provider import EmbeddingProvider, RerankProvider
from astrbot.core.utils.astrbot_path import get_astrbot_temp_path
from astrbot.dashboard.schemas import KnowledgeBaseRequest

KNOWLEDGE_UPLOAD_MAX_BYTES = 512 * 1024 * 1024
KNOWLEDGE_UPLOAD_MAX_REQUEST_BYTES = KNOWLEDGE_UPLOAD_MAX_BYTES + 16 * 1024 * 1024


class KnowledgeBaseServiceError(Exception):
    pass


class KnowledgeBaseService:
    def __init__(self, core_lifecycle: AstrBotCoreLifecycle) -> None:
        self.core_lifecycle = core_lifecycle
        self.upload_progress: dict[str, dict[str, Any]] = {}
        self.upload_tasks: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _payload(data: object) -> dict[str, Any]:
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _canonical_kb_payload(data: object) -> dict[str, Any]:
        """Normalize knowledge base create/update payloads.

        Uses KnowledgeBaseRequest to handle the legacy ``name`` →
        ``kb_name`` migration while preserving operational fields
        like ``kb_id``.
        """
        raw = KnowledgeBaseService._payload(data)
        canonical = KnowledgeBaseRequest(**raw).canonical_payload()
        raw.update(canonical)
        return raw

    def get_kb_manager(self):
        return self.core_lifecycle.kb_manager

    def init_task(self, task_id: str, status: str = "pending") -> None:
        self.upload_tasks[task_id] = {
            "status": status,
            "result": None,
            "error": None,
        }

    def set_task_result(
        self,
        task_id: str,
        status: str,
        result: Any = None,
        error: str | None = None,
    ) -> None:
        self.upload_tasks[task_id] = {
            "status": status,
            "result": result,
            "error": error,
        }
        if task_id in self.upload_progress:
            self.upload_progress[task_id]["status"] = status

    def update_progress(
        self,
        task_id: str,
        *,
        status: str | None = None,
        file_index: int | None = None,
        file_name: str | None = None,
        stage: str | None = None,
        current: int | None = None,
        total: int | None = None,
    ) -> None:
        if task_id not in self.upload_progress:
            return
        progress = self.upload_progress[task_id]
        if status is not None:
            progress["status"] = status
        if file_index is not None:
            progress["file_index"] = file_index
        if file_name is not None:
            progress["file_name"] = file_name
        if stage is not None:
            progress["stage"] = stage
        if current is not None:
            progress["current"] = current
        if total is not None:
            progress["total"] = total

    def make_progress_callback(self, task_id: str, file_idx: int, file_name: str):
        async def _callback(stage: str, current: int, total: int) -> None:
            self.update_progress(
                task_id,
                status="processing",
                file_index=file_idx,
                file_name=file_name,
                stage=stage,
                current=current,
                total=total,
            )

        return _callback

    @staticmethod
    def format_failed_doc_error(file_name: str, error: Exception) -> str:
        message = str(error).strip() or "上传失败：发生未知错误。"
        if message.startswith(file_name):
            return message
        return f"{file_name}: {message}"

    async def background_upload_task(
        self,
        task_id: str,
        kb_helper,
        files_to_upload: list[dict[str, Any]],
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
        tasks_limit: int,
        max_retries: int,
        staging_dir: Path | None = None,
    ) -> None:
        try:
            self.init_task(task_id, status="processing")
            self.upload_progress[task_id] = {
                "status": "processing",
                "file_index": 0,
                "file_total": len(files_to_upload),
                "stage": "waiting",
                "current": 0,
                "total": 100,
            }

            uploaded_docs = []
            failed_docs = []

            for file_idx, file_info in enumerate(files_to_upload):
                try:
                    self.update_progress(
                        task_id,
                        status="processing",
                        file_index=file_idx,
                        file_name=file_info["file_name"],
                        stage="parsing",
                        current=0,
                        total=100,
                    )
                    progress_callback = self.make_progress_callback(
                        task_id, file_idx, file_info["file_name"]
                    )
                    file_content = file_info.get("file_content")
                    file_path = file_info.get("file_path")
                    if file_content is None and file_path is not None:
                        async with aiofiles.open(file_path, "rb") as file_obj:
                            file_content = await file_obj.read()
                    doc = await kb_helper.upload_document(
                        file_name=file_info["file_name"],
                        file_content=file_content,
                        file_type=file_info["file_type"],
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                        batch_size=batch_size,
                        tasks_limit=tasks_limit,
                        max_retries=max_retries,
                        progress_callback=progress_callback,
                    )
                    uploaded_docs.append(doc.model_dump())
                except Exception as exc:
                    logger.error(f"上传文档 {file_info['file_name']} 失败: {exc}")
                    failed_docs.append(
                        {
                            "file_name": file_info["file_name"],
                            "error": self.format_failed_doc_error(
                                file_info["file_name"], exc
                            ),
                        },
                    )

            self.set_task_result(
                task_id,
                "completed",
                result={
                    "task_id": task_id,
                    "uploaded": uploaded_docs,
                    "failed": failed_docs,
                    "total": len(files_to_upload),
                    "success_count": len(uploaded_docs),
                    "failed_count": len(failed_docs),
                },
            )
        except Exception as exc:
            logger.error(f"后台上传任务 {task_id} 失败: {exc}")
            logger.error(traceback.format_exc())
            self.set_task_result(task_id, "failed", error=str(exc))
        finally:
            if staging_dir is not None:
                await asyncio.to_thread(shutil.rmtree, staging_dir, True)

    async def background_wiki_import_task(
        self,
        task_id: str,
        kb_helper,
        sources: list[tuple[Path, str | None]],
        overwrite: bool,
        staging_dir: Path,
    ) -> None:
        """Import staged Markdown sources and clean up their temporary files.

        Args:
            task_id: Background task identifier.
            kb_helper: Target knowledge base helper.
            sources: Staged local files with optional Wiki-relative paths.
            overwrite: Whether existing pages may be replaced.
            staging_dir: Temporary directory removed after completion.
        """
        try:
            self.init_task(task_id, status="processing")
            self.upload_progress[task_id] = {
                "status": "processing",
                "file_index": 0,
                "file_total": len(sources),
                "stage": "indexing",
                "current": 0,
                "total": 100,
            }
            result = await kb_helper.import_wiki_sources(
                sources,
                overwrite=overwrite,
            )
            self.update_progress(
                task_id,
                status="processing",
                stage="indexing",
                current=100,
                total=100,
            )
            imported = result.get("imported", [])
            self.set_task_result(
                task_id,
                "completed",
                result={
                    "task_id": task_id,
                    **result,
                    "success_count": len(imported),
                    "failed_count": 0,
                },
            )
        except Exception as exc:
            logger.error("Wiki import task %s failed: %s", task_id, exc, exc_info=True)
            self.set_task_result(task_id, "failed", error=str(exc))
        finally:
            await asyncio.to_thread(shutil.rmtree, staging_dir, True)

    async def background_import_task(
        self,
        task_id: str,
        kb_helper,
        documents: list[dict[str, Any]],
        batch_size: int,
        tasks_limit: int,
        max_retries: int,
    ) -> None:
        try:
            self.init_task(task_id, status="processing")
            self.upload_progress[task_id] = {
                "status": "processing",
                "file_index": 0,
                "file_total": len(documents),
                "stage": "waiting",
                "current": 0,
                "total": 100,
            }

            uploaded_docs = []
            failed_docs = []

            for file_idx, doc_info in enumerate(documents):
                file_name = doc_info.get("file_name", f"imported_doc_{file_idx}")
                chunks = doc_info.get("chunks", [])

                try:
                    self.update_progress(
                        task_id,
                        status="processing",
                        file_index=file_idx,
                        file_name=file_name,
                        stage="importing",
                        current=0,
                        total=100,
                    )
                    progress_callback = self.make_progress_callback(
                        task_id, file_idx, file_name
                    )
                    doc = await kb_helper.upload_document(
                        file_name=file_name,
                        file_content=None,
                        file_type=doc_info.get("file_type")
                        or (
                            file_name.rsplit(".", 1)[-1].lower()
                            if "." in file_name
                            else "txt"
                        ),
                        batch_size=batch_size,
                        tasks_limit=tasks_limit,
                        max_retries=max_retries,
                        progress_callback=progress_callback,
                        pre_chunked_text=chunks,
                    )
                    uploaded_docs.append(doc.model_dump())
                except Exception as exc:
                    logger.error(f"导入文档 {file_name} 失败: {exc}")
                    failed_docs.append(
                        {
                            "file_name": file_name,
                            "error": self.format_failed_doc_error(file_name, exc),
                        },
                    )

            self.set_task_result(
                task_id,
                "completed",
                result={
                    "task_id": task_id,
                    "uploaded": uploaded_docs,
                    "failed": failed_docs,
                    "total": len(documents),
                    "success_count": len(uploaded_docs),
                    "failed_count": len(failed_docs),
                },
            )
        except Exception as exc:
            logger.error(f"后台导入任务 {task_id} 失败: {exc}")
            logger.error(traceback.format_exc())
            self.set_task_result(task_id, "failed", error=str(exc))

    async def list_kbs(self, *, page: int, page_size: int) -> dict[str, Any]:
        kb_manager = self.get_kb_manager()
        kbs = await kb_manager.list_kbs()
        total = len(kbs)

        # Clamp page and page_size to at least 1 before calculating offsets/slices.
        page = max(page, 1)
        page_size = max(page_size, 1)
        start = (page - 1) * page_size
        end = start + page_size
        paged_kbs = kbs[start:end]

        kb_list = []
        for kb in paged_kbs:
            kb_dict = kb.model_dump()
            kb_helper = await kb_manager.get_kb(kb.kb_id)
            if kb_helper and kb_helper.init_error:
                kb_dict["init_error"] = kb_helper.init_error
            kb_list.append(kb_dict)

        return {"items": kb_list, "page": page, "page_size": page_size, "total": total}

    async def list_kbs_from_dashboard_query(self, *, page, page_size) -> dict[str, Any]:
        return await self.list_kbs(
            page=self._to_int(page, 1),
            page_size=self._to_int(page_size, 20),
        )

    async def create_kb(self, data: object) -> tuple[dict[str, Any], str]:
        kb_manager = self.get_kb_manager()
        payload = self._canonical_kb_payload(data)
        kb_name = payload.get("kb_name")
        if not kb_name:
            raise KnowledgeBaseServiceError("知识库名称不能为空")

        embedding_provider_id = payload.get("embedding_provider_id")
        rerank_provider_id = payload.get("rerank_provider_id")

        if embedding_provider_id:
            provider = await kb_manager.provider_manager.get_provider_by_id(
                embedding_provider_id,
            )
            if not provider or not isinstance(provider, EmbeddingProvider):
                raise KnowledgeBaseServiceError(
                    f"嵌入模型不存在或类型错误({type(provider)})"
                )
            try:
                vec = await provider.get_embedding("astrbot")
                if len(vec) != provider.get_dim():
                    raise ValueError(
                        f"嵌入向量维度不匹配，实际是 {len(vec)}，然而配置是 {provider.get_dim()}",
                    )
            except Exception as exc:
                raise KnowledgeBaseServiceError(f"测试嵌入模型失败: {exc!s}") from exc

        if rerank_provider_id:
            rerank_provider = await kb_manager.provider_manager.get_provider_by_id(
                rerank_provider_id,
            )
            if not isinstance(rerank_provider, RerankProvider):
                raise KnowledgeBaseServiceError("重排序模型不存在")
            try:
                result = await rerank_provider.rerank(
                    query="astrbot",
                    documents=["astrbot knowledge base"],
                )
                if not result:
                    raise ValueError("重排序模型返回结果异常")
            except Exception as exc:
                raise KnowledgeBaseServiceError(
                    f"测试重排序模型失败: {exc!s}，请检查平台日志输出。"
                ) from exc

        kb_helper = await kb_manager.create_kb(
            kb_name=kb_name,
            description=payload.get("description"),
            emoji=payload.get("emoji"),
            embedding_provider_id=embedding_provider_id,
            rerank_provider_id=rerank_provider_id,
            chunk_size=payload.get("chunk_size"),
            chunk_overlap=payload.get("chunk_overlap"),
            top_k_dense=payload.get("top_k_dense"),
            top_k_sparse=payload.get("top_k_sparse"),
            top_m_final=payload.get("top_m_final"),
        )
        return kb_helper.kb.model_dump(), "创建知识库成功"

    async def get_kb(self, kb_id: str | None) -> dict[str, Any]:
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")
        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        return kb_helper.kb.model_dump()

    async def get_kb_from_dashboard_query(self, kb_id: str | None) -> dict[str, Any]:
        return await self.get_kb(kb_id)

    async def export_wiki(self, kb_id: str | None) -> tuple[Path, str, int]:
        """Export one knowledge base Wiki as a Markdown-only ZIP archive.

        Args:
            kb_id: Stable knowledge base identifier.

        Returns:
            The temporary archive path, user-facing filename, and exported page
            count.

        Raises:
            KnowledgeBaseServiceError: If the knowledge base does not exist.
            ValueError: If no Markdown pages are available for export.
        """
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")
        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        return await asyncio.to_thread(kb_helper.export_wiki_archive)

    async def _get_wiki_store(self, kb_id: str | None):
        """Resolve the Wiki store owned by one knowledge base.

        Args:
            kb_id: Stable knowledge base identifier.

        Returns:
            The Wiki store attached to the requested knowledge base helper.

        Raises:
            KnowledgeBaseServiceError: If the knowledge base or Wiki store is
                unavailable.
        """
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")
        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        wiki_store = getattr(kb_helper, "wiki_store", None) or getattr(
            kb_helper, "vec_db", None
        )
        required_methods = (
            "list_tree",
            "read_page",
            "write_page",
            "delete_page",
            "rebuild_index",
            "get_graph",
        )
        if wiki_store is None or any(
            not hasattr(wiki_store, method) for method in required_methods
        ):
            raise KnowledgeBaseServiceError("知识库 Wiki 内核尚未初始化")
        return wiki_store

    async def list_wiki_tree(self, kb_id: str | None) -> dict[str, Any]:
        """Return the Markdown page tree for one knowledge base.

        Args:
            kb_id: Stable knowledge base identifier.

        Returns:
            Tree and aggregate page statistics.
        """
        wiki_store = await self._get_wiki_store(kb_id)
        return await wiki_store.list_tree()

    async def read_wiki_page(
        self,
        kb_id: str | None,
        path: str | None,
    ) -> dict[str, Any]:
        """Read one Markdown page from a knowledge base.

        Args:
            kb_id: Stable knowledge base identifier.
            path: Page path relative to the knowledge directory.

        Returns:
            Page content, metadata, links, and backlinks.

        Raises:
            KnowledgeBaseServiceError: If the path is missing or the page does
                not exist.
        """
        if not path or not path.strip():
            raise KnowledgeBaseServiceError("缺少参数 path")
        wiki_store = await self._get_wiki_store(kb_id)
        try:
            return await wiki_store.read_page(path)
        except FileNotFoundError as exc:
            raise KnowledgeBaseServiceError("知识页面不存在") from exc

    async def write_wiki_page(
        self,
        kb_id: str | None,
        data: object,
        *,
        require_existing: bool = False,
    ) -> tuple[dict[str, Any], str]:
        """Create or replace one Markdown page in a knowledge base.

        Args:
            kb_id: Stable knowledge base identifier.
            data: Request payload containing ``path`` and Markdown ``content``.
            require_existing: Whether the request must update an existing page.

        Returns:
            Indexed page metadata and a success message.

        Raises:
            KnowledgeBaseServiceError: If the page path or content is missing.
        """
        payload = self._payload(data)
        path = payload.get("path")
        content = payload.get("content")
        original_path = payload.get("original_path")
        if not isinstance(path, str) or not path.strip():
            raise KnowledgeBaseServiceError("缺少参数 path")
        if not isinstance(content, str) or not content.strip():
            raise KnowledgeBaseServiceError("缺少参数 content")
        if original_path is not None:
            if not isinstance(original_path, str) or not original_path.strip():
                raise KnowledgeBaseServiceError("参数 original_path 无效")
            if original_path.strip() != path.strip():
                raise KnowledgeBaseServiceError(
                    "暂不支持修改知识页面路径；请新建页面后删除旧页面"
                )
        if require_existing and original_path is None:
            raise KnowledgeBaseServiceError("更新知识页面时缺少参数 original_path")
        kb_manager = self.get_kb_manager()
        kb_helper = await kb_manager.get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        wiki_store = await self._get_wiki_store(kb_id)
        try:
            page = await wiki_store.write_page(
                path,
                content,
                create_only=not require_existing,
                require_existing=require_existing,
            )
        except FileExistsError as exc:
            raise KnowledgeBaseServiceError("知识页面已存在") from exc
        except FileNotFoundError as exc:
            raise KnowledgeBaseServiceError("知识页面不存在") from exc

        document = await kb_helper.get_document(page["doc_id"])
        if not document:
            from astrbot.core.knowledge_base.models import KBDocument

            document = KBDocument(
                doc_id=page["doc_id"],
                kb_id=kb_helper.kb.kb_id,
                doc_name=page["title"],
                file_type="md",
                file_size=len(content.encode("utf-8")),
                file_path=page["path"],
                chunk_count=page["chunk_count"],
                media_count=0,
            )
            async with kb_manager.kb_db.get_db() as session, session.begin():
                session.add(document)
            await kb_helper.refresh_document(page["doc_id"])
        else:
            document.doc_name = page["title"]
            document.file_size = len(content.encode("utf-8"))
            document.file_path = page["path"]
            document.chunk_count = page["chunk_count"]
            async with kb_manager.kb_db.get_db() as session, session.begin():
                session.add(document)
            await kb_helper.refresh_document(page["doc_id"])
        await kb_manager.kb_db.update_kb_stats(
            kb_id=kb_helper.kb.kb_id,
            vec_db=wiki_store,
        )
        await kb_helper.refresh_kb()
        return page, "保存知识页面成功"

    async def delete_wiki_page(
        self,
        kb_id: str | None,
        path: str | None,
    ) -> tuple[None, str]:
        """Delete one Markdown page from a knowledge base.

        Args:
            kb_id: Stable knowledge base identifier.
            path: Page path relative to the knowledge directory.

        Returns:
            An empty result and a success message.

        Raises:
            KnowledgeBaseServiceError: If the path is missing or the page does
                not exist.
        """
        if not path or not path.strip():
            raise KnowledgeBaseServiceError("缺少参数 path")
        kb_manager = self.get_kb_manager()
        kb_helper = await kb_manager.get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        wiki_store = await self._get_wiki_store(kb_id)
        page = await wiki_store.get_page_metadata(path)
        if not page:
            raise KnowledgeBaseServiceError("知识页面不存在")
        document = await kb_helper.get_document(page["doc_id"])
        if document:
            await kb_helper.delete_document(page["doc_id"])
        else:
            await wiki_store.delete_page(path)
            await kb_manager.kb_db.update_kb_stats(
                kb_id=kb_helper.kb.kb_id,
                vec_db=wiki_store,
            )
            await kb_helper.refresh_kb()
        return None, "删除知识页面成功"

    async def move_wiki_path(
        self,
        kb_id: str | None,
        data: object,
    ) -> tuple[dict[str, Any], str]:
        """Move one Wiki page or directory and synchronize document paths.

        Args:
            kb_id: Stable knowledge base identifier.
            data: Payload containing ``source_path`` and ``target_path``.

        Returns:
            Move result and a success message.

        Raises:
            KnowledgeBaseServiceError: If paths are missing or invalid.
        """
        payload = self._payload(data)
        source_path = payload.get("source_path")
        target_path = payload.get("target_path")
        if not isinstance(source_path, str) or not source_path.strip():
            raise KnowledgeBaseServiceError("缺少参数 source_path")
        if not isinstance(target_path, str) or not target_path.strip():
            raise KnowledgeBaseServiceError("缺少参数 target_path")
        kb_manager = self.get_kb_manager()
        kb_helper = await kb_manager.get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        wiki_store = await self._get_wiki_store(kb_id)
        try:
            result = await wiki_store.move_path(
                source_path.strip(),
                target_path.strip(),
            )
        except FileNotFoundError as exc:
            raise KnowledgeBaseServiceError("知识文件或文件夹不存在") from exc
        except FileExistsError as exc:
            raise KnowledgeBaseServiceError("目标位置已存在同名内容") from exc

        updated_documents = []
        for moved_page in result["moved"]:
            document = await kb_helper.get_document(moved_page["doc_id"])
            if document:
                document.file_path = moved_page["new_path"]
                updated_documents.append(document)
        if updated_documents:
            async with kb_manager.kb_db.get_db() as session, session.begin():
                session.add_all(updated_documents)
        await kb_manager.kb_db.update_kb_stats(
            kb_id=kb_helper.kb.kb_id,
            vec_db=wiki_store,
        )
        await kb_helper.refresh_kb()
        return result, "移动知识文件成功"

    async def delete_wiki_path(
        self,
        kb_id: str | None,
        path: str | None,
        *,
        recursive: bool = False,
    ) -> tuple[dict[str, Any], str]:
        """Delete one Wiki page or directory and synchronize document rows.

        Args:
            kb_id: Stable knowledge base identifier.
            path: Page or directory path relative to ``knowledge/``.
            recursive: Whether contained pages may be deleted with a directory.

        Returns:
            Delete result and a success message.

        Raises:
            KnowledgeBaseServiceError: If the path is missing or invalid.
        """
        if not path or not path.strip():
            raise KnowledgeBaseServiceError("缺少参数 path")
        kb_manager = self.get_kb_manager()
        kb_helper = await kb_manager.get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        wiki_store = await self._get_wiki_store(kb_id)
        try:
            result = await wiki_store.delete_path(
                path.strip(),
                recursive=recursive,
            )
        except FileNotFoundError as exc:
            raise KnowledgeBaseServiceError("知识文件或文件夹不存在") from exc

        doc_ids = [page["doc_id"] for page in result["deleted"]]
        media_paths: list[Path] = []
        for doc_id in doc_ids:
            media_paths.extend(
                Path(media.file_path)
                for media in await kb_manager.kb_db.list_media_by_doc(doc_id)
            )
        await kb_manager.kb_db.delete_document_records(doc_ids)
        for doc_id in doc_ids:
            for source_path in wiki_store.sources_dir.glob(f"{doc_id}.*"):
                source_path.unlink(missing_ok=True)
        for media_path in media_paths:
            media_path.unlink(missing_ok=True)
        await kb_manager.kb_db.update_kb_stats(
            kb_id=kb_helper.kb.kb_id,
            vec_db=wiki_store,
        )
        await kb_helper.refresh_kb()
        return result, "删除知识文件成功"

    async def rebuild_wiki_index(
        self,
        kb_id: str | None,
    ) -> tuple[dict[str, int], str]:
        """Rebuild one knowledge base's derived Wiki indexes.

        Args:
            kb_id: Stable knowledge base identifier.

        Returns:
            Rebuilt page and chunk counts with a success message.
        """
        wiki_store = await self._get_wiki_store(kb_id)
        result = await wiki_store.rebuild_index()
        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        await self.get_kb_manager().kb_db.update_kb_stats(
            kb_id=kb_helper.kb.kb_id,
            vec_db=wiki_store,
        )
        await kb_helper.refresh_kb()
        return result, "重建知识库索引成功"

    async def get_wiki_graph(self, kb_id: str | None) -> dict[str, Any]:
        """Return the graph derived from one knowledge base's Wiki links.

        Args:
            kb_id: Stable knowledge base identifier.

        Returns:
            Graph nodes and edges for the requested knowledge base.
        """
        wiki_store = await self._get_wiki_store(kb_id)
        return await wiki_store.get_graph()

    async def update_kb(self, data: object) -> tuple[dict[str, Any], str]:
        payload = self._canonical_kb_payload(data)
        kb_id = payload.get("kb_id")
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")

        update_keys = [
            "kb_name",
            "description",
            "emoji",
            "embedding_provider_id",
            "rerank_provider_id",
            "chunk_size",
            "chunk_overlap",
            "top_k_dense",
            "top_k_sparse",
            "top_m_final",
        ]
        provided_updates = {key: payload[key] for key in update_keys if key in payload}
        if not provided_updates:
            raise KnowledgeBaseServiceError("至少需要提供一个更新字段")

        current_kb = await self.get_kb_manager().get_kb(kb_id)
        if not current_kb:
            raise KnowledgeBaseServiceError("知识库不存在")
        current = current_kb.kb
        update_data = {key: getattr(current, key, None) for key in update_keys}
        update_data.update(provided_updates)

        kb_helper = await self.get_kb_manager().update_kb(
            kb_id=kb_id,
            **update_data,
        )
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        failed_fields = [
            key
            for key, value in provided_updates.items()
            if getattr(kb_helper.kb, key, None) != value
        ]
        if failed_fields:
            raise KnowledgeBaseServiceError(
                "知识库更新失败，原配置已保留: " + ", ".join(failed_fields)
            )
        return kb_helper.kb.model_dump(), "更新知识库成功"

    async def delete_kb(self, data: object) -> tuple[None, str]:
        payload = self._payload(data)
        kb_id = payload.get("kb_id")
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")
        success = await self.get_kb_manager().delete_kb(kb_id)
        if not success:
            raise KnowledgeBaseServiceError("知识库不存在")
        return None, "删除知识库成功"

    async def get_kb_stats(self, kb_id: str | None) -> dict[str, Any]:
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")
        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        kb = kb_helper.kb
        return {
            "kb_id": kb.kb_id,
            "kb_name": kb.kb_name,
            "doc_count": kb.doc_count,
            "chunk_count": kb.chunk_count,
            "created_at": kb.created_at.isoformat(),
            "updated_at": kb.updated_at.isoformat(),
        }

    async def get_kb_stats_from_dashboard_query(
        self,
        kb_id: str | None,
    ) -> dict[str, Any]:
        return await self.get_kb_stats(kb_id)

    async def list_documents(
        self,
        *,
        kb_id: str | None,
        page: int,
        page_size: int,
        search: str | None = None,
    ) -> dict[str, Any]:
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")
        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")

        if search is not None:
            search = search.strip()
            if not search:
                search = None

        page = max(page, 1)
        total = await kb_helper.count_documents(search=search)
        if page_size == -1:
            page = 1
            offset = 0
            limit = max(total, 1)
        else:
            page_size = max(page_size, 1)
            offset = (page - 1) * page_size
            limit = page_size
        doc_list = await kb_helper.list_documents(
            offset=offset,
            limit=limit,
            search=search,
        )
        return {
            "items": [doc.model_dump() for doc in doc_list],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    async def list_documents_from_dashboard_query(
        self,
        *,
        kb_id: str | None,
        page,
        page_size,
        search: str | None = None,
    ) -> dict[str, Any]:
        return await self.list_documents(
            kb_id=kb_id,
            page=self._to_int(page, 1),
            page_size=self._to_int(page_size, 100),
            search=search,
        )

    async def upload_document(
        self,
        *,
        content_type: str | None,
        form_data,
        files,
    ) -> dict[str, Any]:
        if content_type and "multipart/form-data" not in content_type:
            raise KnowledgeBaseServiceError("Content-Type 须为 multipart/form-data")

        kb_id = form_data.get("kb_id")
        batch_size = int(form_data.get("batch_size", 32))
        tasks_limit = int(form_data.get("tasks_limit", 3))
        max_retries = int(form_data.get("max_retries", 3))
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")
        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        chunk_size = (
            kb_helper.kb.chunk_size
            if kb_helper.kb.chunk_size is not None
            else DEFAULT_CHUNK_SIZE
        )
        chunk_overlap = (
            kb_helper.kb.chunk_overlap
            if kb_helper.kb.chunk_overlap is not None
            else DEFAULT_CHUNK_OVERLAP
        )

        file_list = []
        for key in files.keys():
            if key == "file" or key.startswith("file") or key == "files[]":
                file_list.extend(files.getlist(key))
        if not file_list:
            raise KnowledgeBaseServiceError("缺少文件")

        temp_root = Path(get_astrbot_temp_path())
        temp_root.mkdir(parents=True, exist_ok=True)
        staging_dir = Path(tempfile.mkdtemp(prefix="kb_upload_", dir=temp_root))
        files_to_upload = []
        remaining_upload_bytes = KNOWLEDGE_UPLOAD_MAX_BYTES
        try:
            for file in file_list:
                file_name = Path(
                    str(file.filename or "document").replace("\\", "/")
                ).name
                if file_name in {"", ".", ".."}:
                    file_name = "document"
                temp_file_path = staging_dir / f"{uuid.uuid4()}_{file_name}"
                content_length = getattr(file, "content_length", None)
                if (
                    isinstance(content_length, int)
                    and content_length > remaining_upload_bytes
                ):
                    raise KnowledgeBaseServiceError(
                        "上传文件总大小超过 512 MiB 安全上限"
                    )
                try:
                    saved_bytes = await file.save(
                        temp_file_path,
                        max_bytes=remaining_upload_bytes,
                    )
                except ValueError as exc:
                    raise KnowledgeBaseServiceError(
                        "上传文件总大小超过 512 MiB 安全上限"
                    ) from exc
                remaining_upload_bytes -= saved_bytes
                file_type = (
                    file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
                )
                files_to_upload.append(
                    {
                        "file_name": file_name,
                        "file_path": temp_file_path,
                        "file_type": file_type,
                    },
                )
        except Exception:
            await asyncio.to_thread(shutil.rmtree, staging_dir, True)
            raise

        task_id = str(uuid.uuid4())
        self.init_task(task_id, status="pending")
        asyncio.create_task(
            self.background_upload_task(
                task_id=task_id,
                kb_helper=kb_helper,
                files_to_upload=files_to_upload,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                batch_size=batch_size,
                tasks_limit=tasks_limit,
                max_retries=max_retries,
                staging_dir=staging_dir,
            ),
        )
        return {
            "task_id": task_id,
            "file_count": len(files_to_upload),
            "message": "task created, processing in background",
        }

    async def import_wiki(
        self,
        *,
        content_type: str | None,
        form_data,
        files,
    ) -> dict[str, Any]:
        """Stage Markdown files or ZIP archives for atomic Wiki import.

        Args:
            content_type: Request Content-Type header.
            form_data: Multipart text fields including paths and overwrite.
            files: Multipart upload files.

        Returns:
            Background task metadata.

        Raises:
            KnowledgeBaseServiceError: If the request or knowledge base is invalid.
        """
        if content_type and "multipart/form-data" not in content_type:
            raise KnowledgeBaseServiceError("Content-Type 须为 multipart/form-data")

        kb_id = form_data.get("kb_id")
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")
        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")

        file_list = []
        for key in files.keys():
            if key in {"file", "files", "files[]"} or key.startswith("file"):
                file_list.extend(files.getlist(key))
        if not file_list:
            raise KnowledgeBaseServiceError("请选择 Markdown 文件、文件夹或 ZIP")

        relative_paths = [
            str(value)
            for key in ("paths", "paths[]")
            for value in form_data.getlist(key)
        ]
        if relative_paths and len(relative_paths) != len(file_list):
            raise KnowledgeBaseServiceError("上传文件与相对路径数量不一致")
        overwrite = str(form_data.get("overwrite", "false")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        temp_root = Path(get_astrbot_temp_path())
        temp_root.mkdir(parents=True, exist_ok=True)
        staging_dir = Path(tempfile.mkdtemp(prefix="wiki_import_", dir=temp_root))
        sources: list[tuple[Path, str | None]] = []
        remaining_upload_bytes = KNOWLEDGE_UPLOAD_MAX_BYTES
        try:
            for index, file in enumerate(file_list):
                file_name = Path(
                    str(file.filename or "knowledge.md").replace("\\", "/")
                ).name
                if file_name in {"", ".", ".."}:
                    file_name = "knowledge.md"
                staged_path = staging_dir / f"{uuid.uuid4()}_{file_name}"
                content_length = getattr(file, "content_length", None)
                if (
                    isinstance(content_length, int)
                    and content_length > remaining_upload_bytes
                ):
                    raise KnowledgeBaseServiceError(
                        "上传文件总大小超过 512 MiB 安全上限"
                    )
                try:
                    saved_bytes = await file.save(
                        staged_path,
                        max_bytes=remaining_upload_bytes,
                    )
                except ValueError as exc:
                    raise KnowledgeBaseServiceError(
                        "上传文件总大小超过 512 MiB 安全上限"
                    ) from exc
                remaining_upload_bytes -= saved_bytes
                if relative_paths:
                    relative_path = relative_paths[index]
                elif Path(file_name).suffix.lower() == ".zip":
                    relative_path = None
                else:
                    relative_path = file_name
                sources.append((staged_path, relative_path))
        except Exception:
            await asyncio.to_thread(shutil.rmtree, staging_dir, True)
            raise

        task_id = str(uuid.uuid4())
        self.init_task(task_id, status="pending")
        asyncio.create_task(
            self.background_wiki_import_task(
                task_id=task_id,
                kb_helper=kb_helper,
                sources=sources,
                overwrite=overwrite,
                staging_dir=staging_dir,
            )
        )
        return {
            "task_id": task_id,
            "file_count": len(sources),
            "message": "Wiki import task created, processing in background",
        }

    @staticmethod
    def validate_import_request(data: dict[str, Any]):
        kb_id = data.get("kb_id")
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")

        documents = data.get("documents")
        if not documents or not isinstance(documents, list):
            raise KnowledgeBaseServiceError("缺少参数 documents 或格式错误")

        for doc in documents:
            if (
                not isinstance(doc, dict)
                or "file_name" not in doc
                or "chunks" not in doc
            ):
                raise KnowledgeBaseServiceError(
                    "文档格式错误，必须包含 file_name 和 chunks"
                )
            if not isinstance(doc["chunks"], list):
                raise KnowledgeBaseServiceError("chunks 必须是列表")
            if not all(
                isinstance(chunk, str) and chunk.strip() for chunk in doc["chunks"]
            ):
                raise KnowledgeBaseServiceError("chunks 必须是非空字符串列表")

        return (
            kb_id,
            documents,
            data.get("batch_size", 32),
            data.get("tasks_limit", 3),
            data.get("max_retries", 3),
        )

    async def import_documents(self, data: object) -> dict[str, Any]:
        payload = self._payload(data)
        kb_id, documents, batch_size, tasks_limit, max_retries = (
            self.validate_import_request(payload)
        )

        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")

        task_id = str(uuid.uuid4())
        self.init_task(task_id, status="pending")
        asyncio.create_task(
            self.background_import_task(
                task_id=task_id,
                kb_helper=kb_helper,
                documents=documents,
                batch_size=batch_size,
                tasks_limit=tasks_limit,
                max_retries=max_retries,
            ),
        )
        return {
            "task_id": task_id,
            "doc_count": len(documents),
            "message": "import task created, processing in background",
        }

    def get_upload_progress(self, task_id: str | None) -> dict[str, Any]:
        if not task_id:
            raise KnowledgeBaseServiceError("缺少参数 task_id")
        if task_id not in self.upload_tasks:
            raise KnowledgeBaseServiceError("找不到该任务")

        task_info = self.upload_tasks[task_id]
        status = task_info["status"]
        response_data = {
            "task_id": task_id,
            "status": status,
        }
        if status == "processing" and task_id in self.upload_progress:
            response_data["progress"] = self.upload_progress[task_id]
        if status == "completed":
            response_data["result"] = task_info["result"]
        if status == "failed":
            response_data["error"] = task_info["error"]
        return response_data

    def get_upload_progress_from_dashboard_query(
        self,
        task_id: str | None,
    ) -> dict[str, Any]:
        return self.get_upload_progress(task_id)

    async def get_document(
        self,
        *,
        kb_id: str | None,
        doc_id: str | None,
    ) -> dict[str, Any]:
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")
        if not doc_id:
            raise KnowledgeBaseServiceError("缺少参数 doc_id")
        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        doc = await kb_helper.get_document(doc_id)
        if not doc:
            raise KnowledgeBaseServiceError("文档不存在")
        return doc.model_dump()

    async def get_document_from_dashboard_query(
        self,
        *,
        kb_id: str | None,
        doc_id: str | None,
    ) -> dict[str, Any]:
        return await self.get_document(kb_id=kb_id, doc_id=doc_id)

    async def delete_document(self, data: object) -> tuple[None, str]:
        payload = self._payload(data)
        kb_id = payload.get("kb_id")
        doc_id = payload.get("doc_id")
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")
        if not doc_id:
            raise KnowledgeBaseServiceError("缺少参数 doc_id")
        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        await kb_helper.delete_document(doc_id)
        return None, "删除文档成功"

    async def delete_chunk(self, data: object) -> tuple[None, str]:
        payload = self._payload(data)
        kb_id = payload.get("kb_id")
        chunk_id = payload.get("chunk_id")
        doc_id = payload.get("doc_id")
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")
        if not chunk_id:
            raise KnowledgeBaseServiceError("缺少参数 chunk_id")
        if not doc_id:
            raise KnowledgeBaseServiceError("缺少参数 doc_id")
        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")
        await kb_helper.delete_chunk(chunk_id, doc_id)
        return None, "删除文本块成功"

    async def list_chunks(
        self,
        *,
        kb_id: str | None,
        doc_id: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")
        if not doc_id:
            raise KnowledgeBaseServiceError("缺少参数 doc_id")
        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")

        offset = (page - 1) * page_size
        return {
            "items": await kb_helper.get_chunks_by_doc_id(
                doc_id=doc_id,
                offset=offset,
                limit=page_size,
            ),
            "page": page,
            "page_size": page_size,
            "total": await kb_helper.get_chunk_count_by_doc_id(doc_id),
        }

    async def list_chunks_from_dashboard_query(
        self,
        *,
        kb_id: str | None,
        doc_id: str | None,
        page,
        page_size,
    ) -> dict[str, Any]:
        return await self.list_chunks(
            kb_id=kb_id,
            doc_id=doc_id,
            page=self._to_int(page, 1),
            page_size=self._to_int(page_size, 100),
        )

    async def retrieve(self, data: object) -> dict[str, Any]:
        payload = self._payload(data)
        query = payload.get("query")
        kb_names = payload.get("kb_names")
        kb_ids = payload.get("kb_ids")

        if not query:
            raise KnowledgeBaseServiceError("缺少参数 query")
        kb_manager = self.get_kb_manager()
        if kb_ids is not None and not isinstance(kb_ids, list):
            raise KnowledgeBaseServiceError("参数 kb_ids 格式错误")
        if kb_names is not None and not isinstance(kb_names, list):
            raise KnowledgeBaseServiceError("参数 kb_names 格式错误")
        if not kb_ids and not kb_names:
            raise KnowledgeBaseServiceError("缺少参数 kb_ids 或 kb_names")

        top_k = payload.get("top_k", 5)
        results = await kb_manager.retrieve(
            query=query,
            kb_names=kb_names or [],
            kb_ids=kb_ids or [],
            top_m_final=top_k,
        )
        result_list = results["results"] if results else []
        response_data = {
            "results": result_list,
            "total": len(result_list),
            "query": query,
        }

        return response_data

    async def upload_document_from_url(self, data: object) -> dict[str, Any]:
        payload = self._payload(data)
        kb_id = payload.get("kb_id")
        if not kb_id:
            raise KnowledgeBaseServiceError("缺少参数 kb_id")
        url = payload.get("url")
        if not url:
            raise KnowledgeBaseServiceError("缺少参数 url")

        kb_helper = await self.get_kb_manager().get_kb(kb_id)
        if not kb_helper:
            raise KnowledgeBaseServiceError("知识库不存在")

        task_id = str(uuid.uuid4())
        self.init_task(task_id, status="pending")
        asyncio.create_task(
            self.background_upload_from_url_task(
                task_id=task_id,
                kb_helper=kb_helper,
                url=url,
                chunk_size=(
                    kb_helper.kb.chunk_size
                    if kb_helper.kb.chunk_size is not None
                    else DEFAULT_CHUNK_SIZE
                ),
                chunk_overlap=(
                    kb_helper.kb.chunk_overlap
                    if kb_helper.kb.chunk_overlap is not None
                    else DEFAULT_CHUNK_OVERLAP
                ),
                batch_size=payload.get("batch_size", 32),
                tasks_limit=payload.get("tasks_limit", 3),
                max_retries=payload.get("max_retries", 3),
                enable_cleaning=payload.get("enable_cleaning", False),
                cleaning_provider_id=payload.get("cleaning_provider_id"),
            ),
        )
        return {
            "task_id": task_id,
            "url": url,
            "message": "URL upload task created, processing in background",
        }

    async def background_upload_from_url_task(
        self,
        task_id: str,
        kb_helper,
        url: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
        tasks_limit: int,
        max_retries: int,
        enable_cleaning: bool,
        cleaning_provider_id: str | None,
    ) -> None:
        try:
            self.init_task(task_id, status="processing")
            self.upload_progress[task_id] = {
                "status": "processing",
                "file_index": 0,
                "file_total": 1,
                "file_name": f"URL: {url}",
                "stage": "extracting",
                "current": 0,
                "total": 100,
            }
            progress_callback = self.make_progress_callback(task_id, 0, f"URL: {url}")
            doc = await kb_helper.upload_from_url(
                url=url,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                batch_size=batch_size,
                tasks_limit=tasks_limit,
                max_retries=max_retries,
                progress_callback=progress_callback,
                enable_cleaning=enable_cleaning,
                cleaning_provider_id=cleaning_provider_id,
            )
            self.set_task_result(
                task_id,
                "completed",
                result={
                    "task_id": task_id,
                    "uploaded": [doc.model_dump()],
                    "failed": [],
                    "total": 1,
                    "success_count": 1,
                    "failed_count": 0,
                },
            )
        except Exception as exc:
            logger.error(f"后台上传URL任务 {task_id} 失败: {exc}")
            logger.error(traceback.format_exc())
            self.set_task_result(task_id, "failed", error=str(exc))

    @staticmethod
    def _to_int(value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


__all__ = [
    "KNOWLEDGE_UPLOAD_MAX_BYTES",
    "KNOWLEDGE_UPLOAD_MAX_REQUEST_BYTES",
    "KnowledgeBaseService",
    "KnowledgeBaseServiceError",
]
