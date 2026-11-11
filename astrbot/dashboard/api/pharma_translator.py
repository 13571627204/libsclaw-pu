from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from astrbot.dashboard.responses import ApiError, ok
from astrbot.dashboard.services import pharma_competitor
from astrbot.dashboard.services.pharma_translator_service import (
    MAX_PDF_BYTES,
    PharmaTranslatorError,
    PharmaTranslatorService,
)

from .auth import AuthContext, require_scope

router = APIRouter(prefix="/pharma-translator", tags=["Pharma Translator"])
_BACKGROUND_TASKS: set[asyncio.Future[Any]] = set()


def _finish_background_task(task: asyncio.Future[Any]) -> None:
    _BACKGROUND_TASKS.discard(task)
    if not task.cancelled():
        task.exception()  # 已断开的请求无人等待结果，取走异常避免告警


async def _run_detached(coro: Any) -> Any:
    """长耗时 AI 任务：连接被代理/浏览器中断时仍在后台完成并落盘，前端可轮询项目取回结果。"""
    task = asyncio.ensure_future(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_finish_background_task)
    return await asyncio.shield(task)


class ConfirmProjectRequest(BaseModel):
    fields: list[dict[str, Any]] = Field(default_factory=list)
    keywords: list[dict[str, Any]] = Field(default_factory=list)
    comment: str = Field(default="", max_length=500)


class WorkflowActionRequest(BaseModel):
    action: str = Field(min_length=1, max_length=40)
    data: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] | None = None
    comment: str = Field(default="", max_length=500)


class LiteratureMatchRequest(BaseModel):
    kb_ids: list[str] = Field(default_factory=list, max_length=8)
    kb_names: list[str] = Field(default_factory=list, max_length=8)
    tier: str = Field(default="light", max_length=16)


class DimensionGenerateRequest(BaseModel):
    kb_ids: list[str] = Field(default_factory=list, max_length=8)
    kb_names: list[str] = Field(default_factory=list, max_length=8)
    search_mode: str = Field(default="auto", max_length=16)
    search_platforms: list[str] = Field(default_factory=list, max_length=4)


class UserVoicesRequest(BaseModel):
    voices: list[dict[str, Any]] = Field(min_length=1, max_length=20)


class CompetitorScanRequest(BaseModel):
    mode: str = Field(min_length=1, max_length=20)
    platforms: list[str] = Field(default_factory=list, max_length=4)
    keywords: list[str] = Field(default_factory=list, max_length=8)
    brands: list[str] = Field(default_factory=list, max_length=10)
    urls: list[str] = Field(default_factory=list, max_length=20)
    per_keyword: int = Field(default=20, ge=1, le=50)


class CompetitorAnalyzeRequest(BaseModel):
    our_price: str | None = Field(default=None, max_length=60)


class ContentBatchRequest(BaseModel):
    channels: list[str] = Field(default_factory=list, max_length=10)
    total: int = Field(default=30, ge=10, le=50)


class ContentChannelReworkRequest(BaseModel):
    channel: str = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=1, max_length=40)
    comment: str = Field(min_length=1, max_length=500)


class ContentTopicItem(BaseModel):
    no: int = Field(ge=1, le=100)
    selected: bool = True
    publish_time: str = Field(default="", max_length=60)


class ContentTopicsRequest(BaseModel):
    topics: list[ContentTopicItem] = Field(min_length=1, max_length=100)


class ContentImagesRequest(BaseModel):
    content_id: str = Field(min_length=1, max_length=64)
    indexes: list[int] = Field(default_factory=list, max_length=8)


class ComplianceReviewRequest(BaseModel):
    kb_ids: list[str] = Field(default_factory=list, max_length=8)
    kb_names: list[str] = Field(default_factory=list, max_length=8)
    ai_search: bool = True


class ComplianceFilterRequest(BaseModel):
    kb_ids: list[str] = Field(default_factory=list, max_length=8)
    kb_names: list[str] = Field(default_factory=list, max_length=8)
    ai_search: bool = True
    inventory: list[dict[str, Any]] | None = Field(default=None, max_length=100)


class ComplianceTicketRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    risk_ids: list[str] = Field(default_factory=list, max_length=20)


class ComplianceTicketAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)
    expert_name: str = Field(min_length=1, max_length=40)


class ComplianceAiAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


def get_service(request: Request) -> PharmaTranslatorService:
    return request.app.state.services.pharma_translator


async def require_pharma_scope(request: Request) -> AuthContext:
    return await require_scope(request, "data")


def _translate_error(exc: PharmaTranslatorError) -> ApiError:
    return ApiError(str(exc), status_code=exc.status_code)


async def _read_limited(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_PDF_BYTES:
            raise ApiError("上传文件超过 100 MB", status_code=413)
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/analyze")
async def analyze_leaflet(
    product_name: str = Form(default=""),
    product_type: str = Form(default="自动识别"),
    manual_text: str = Form(default=""),
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    content = await _read_limited(file)
    try:
        result = await service.analyze(
            username=auth.username,
            product_name=product_name,
            product_type=product_type,
            filename=file.filename or "document",
            content=content,
            manual_text=manual_text,
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.get("/projects")
async def list_projects(
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    return ok(service.list_projects(auth.username))


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        return ok(service.get_project(auth.username, project_id))
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        service.delete_project(auth.username, project_id)
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok({"project_id": project_id})


@router.post("/projects/{project_id}/confirm")
async def confirm_project(
    project_id: str,
    payload: ConfirmProjectRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = service.confirm_project(
            username=auth.username,
            project_id=project_id,
            fields=payload.fields,
            keywords=payload.keywords,
            comment=payload.comment,
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.post("/projects/{project_id}/workflow/actions")
async def apply_workflow_action(
    project_id: str,
    request_payload: WorkflowActionRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = service.workflow_action(
            username=auth.username,
            project_id=project_id,
            action=request_payload.action,
            payload=request_payload.data or request_payload.payload or {},
            comment=request_payload.comment,
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.post("/projects/{project_id}/dimensions/generate")
async def generate_dimensions(
    project_id: str,
    payload: DimensionGenerateRequest | None = None,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    payload = payload or DimensionGenerateRequest()
    try:
        return ok(
            await _run_detached(
                service.generate_dimensions(
                    auth.username,
                    project_id,
                    kb_ids=payload.kb_ids,
                    kb_names=payload.kb_names,
                    search_mode=payload.search_mode,
                    search_platforms=payload.search_platforms,
                )
            )
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc


@router.post("/projects/{project_id}/literature")
async def upload_literature(
    project_id: str,
    doc_kind: str = Form(...),
    files: list[UploadFile] = File(...),
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    if len(files) > 5:
        raise ApiError("单次最多上传 5 份文献", status_code=422)
    payloads: list[tuple[str, bytes]] = []
    for file in files:
        payloads.append((file.filename or "document", await _read_limited(file)))
    try:
        result = await service.add_literature(
            username=auth.username,
            project_id=project_id,
            files=payloads,
            doc_kind=doc_kind,
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.delete("/projects/{project_id}/literature/{doc_id}")
async def delete_literature(
    project_id: str,
    doc_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = service.remove_literature(
            username=auth.username, project_id=project_id, doc_id=doc_id
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.post("/projects/{project_id}/literature/match")
async def match_literature(
    project_id: str,
    payload: LiteratureMatchRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = await _run_detached(
            service.run_literature_match(
                username=auth.username,
                project_id=project_id,
                kb_ids=payload.kb_ids,
                kb_names=payload.kb_names,
                tier=payload.tier,
            )
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.get("/projects/{project_id}/literature/triple-table.csv")
async def export_literature_triple_table(
    project_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        filename, content = service.export_literature_triple_csv(
            auth.username, project_id
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
        },
    )


@router.get("/literature/redlines")
async def list_literature_redlines(
    project_id: str | None = None,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        return ok(service.list_literature_redlines(auth.username, project_id))
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc


@router.get("/projects/{project_id}/literature/archive")
async def get_literature_archive(
    project_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        return ok(service.get_literature_sku_archive(auth.username, project_id))
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc


@router.post("/projects/{project_id}/literature/archive/reuse")
async def reuse_literature_archive(
    project_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        return ok(service.reuse_literature_archive(auth.username, project_id))
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc


@router.post("/projects/{project_id}/user-voices")
async def add_user_voices(
    project_id: str,
    payload: UserVoicesRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = service.add_user_voices(
            username=auth.username, project_id=project_id, voices=payload.voices
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.delete("/projects/{project_id}/user-voices/{voice_id}")
async def remove_user_voice(
    project_id: str,
    voice_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = service.remove_user_voice(
            username=auth.username, project_id=project_id, voice_id=voice_id
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.get("/competitor/capabilities")
async def competitor_capabilities(
    auth: AuthContext = Depends(require_pharma_scope),
):
    return ok(pharma_competitor.capabilities())


@router.post("/projects/{project_id}/competitor/scan")
async def scan_competitors(
    project_id: str,
    payload: CompetitorScanRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = await _run_detached(
            service.scan_competitors(
                auth.username,
                project_id,
                mode=payload.mode,
                platforms=payload.platforms,
                keywords=payload.keywords,
                brands=payload.brands,
                urls=payload.urls,
                per_keyword=payload.per_keyword,
            )
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.post("/projects/{project_id}/competitor/analyze")
async def analyze_competitors(
    project_id: str,
    payload: CompetitorAnalyzeRequest | None = None,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        return ok(
            await _run_detached(
                service.analyze_competitors(
                    auth.username,
                    project_id,
                    our_price=payload.our_price if payload else None,
                )
            )
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc


@router.post("/projects/{project_id}/content-batch/generate")
async def generate_content_batch(
    project_id: str,
    payload: ContentBatchRequest | None = None,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    payload = payload or ContentBatchRequest()
    try:
        return ok(
            await _run_detached(
                service.generate_content_batch(
                    auth.username,
                    project_id,
                    channels=payload.channels,
                    total=payload.total,
                )
            )
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc


@router.post("/projects/{project_id}/content-batch/rework")
async def rework_content_channel(
    project_id: str,
    payload: ContentChannelReworkRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        return ok(
            service.start_rework(
                auth.username,
                project_id,
                channel=payload.channel,
                reason=payload.reason,
                comment=payload.comment,
            )
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc


@router.get("/projects/{project_id}/content-batch/rework")
async def rework_status(
    project_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        return ok(service.rework_status(auth.username, project_id))
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc


@router.post("/projects/{project_id}/content-batch/auto-fix")
async def auto_fix_content(
    project_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        return ok(service.start_auto_fix(auth.username, project_id))
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc


@router.get("/projects/{project_id}/content-batch/auto-fix")
async def auto_fix_status(
    project_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        return ok(service.auto_fix_status(auth.username, project_id))
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc


@router.post("/projects/{project_id}/content-batch/topics")
async def update_content_topics(
    project_id: str,
    payload: ContentTopicsRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        return ok(
            service.update_content_topics(
                auth.username,
                project_id,
                topics=[topic.model_dump() for topic in payload.topics],
            )
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc


@router.post("/projects/{project_id}/content-batch/images")
async def generate_content_images(
    project_id: str,
    payload: ContentImagesRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        return ok(
            await _run_detached(
                service.generate_content_images(
                    auth.username,
                    project_id,
                    content_id=payload.content_id,
                    indexes=payload.indexes or None,
                )
            )
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc


@router.get("/projects/{project_id}/content-images/{filename}")
async def get_content_image(
    project_id: str,
    filename: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        path = service.content_image_file(auth.username, project_id, filename)
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return FileResponse(path)


@router.get("/compliance/knowledge-base")
async def compliance_knowledge_base(
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    return ok(service.get_compliance_knowledge_base())


@router.post("/projects/{project_id}/compliance-filter/run")
async def run_compliance_filter(
    project_id: str,
    payload: ComplianceFilterRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = await _run_detached(
            service.run_compliance_filter(
                username=auth.username,
                project_id=project_id,
                kb_ids=payload.kb_ids,
                kb_names=payload.kb_names,
                ai_search=payload.ai_search,
                inventory=payload.inventory,
            )
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.post("/projects/{project_id}/compliance/review")
async def run_compliance_review(
    project_id: str,
    payload: ComplianceReviewRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = await _run_detached(
            service.run_compliance_review(
                username=auth.username,
                project_id=project_id,
                kb_ids=payload.kb_ids,
                kb_names=payload.kb_names,
                ai_search=payload.ai_search,
            )
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.get("/projects/{project_id}/compliance/review/progress")
async def compliance_review_progress(
    project_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    return ok(
        service.compliance_review_progress(
            username=auth.username, project_id=project_id
        )
    )


@router.post("/projects/{project_id}/compliance/expert-tickets")
async def create_compliance_expert_ticket(
    project_id: str,
    payload: ComplianceTicketRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = await service.create_compliance_expert_ticket(
            username=auth.username,
            project_id=project_id,
            question=payload.question,
            risk_ids=payload.risk_ids,
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.post("/projects/{project_id}/compliance/expert-tickets/{ticket_id}/answer")
async def answer_compliance_expert_ticket(
    project_id: str,
    ticket_id: str,
    payload: ComplianceTicketAnswerRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = await service.answer_compliance_expert_ticket(
            username=auth.username,
            project_id=project_id,
            ticket_id=ticket_id,
            answer=payload.answer,
            expert_name=payload.expert_name,
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.post("/projects/{project_id}/compliance/ai-ask")
async def ask_compliance_ai(
    project_id: str,
    payload: ComplianceAiAskRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = await service.ask_compliance_ai(
            username=auth.username,
            project_id=project_id,
            question=payload.question,
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.get("/projects/{project_id}/source")
async def get_source_file(
    project_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        path, filename = service.source_file(auth.username, project_id)
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return FileResponse(path, filename=filename)


@router.get("/projects/{project_id}/keywords.csv")
async def export_keywords(
    project_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        filename, content = service.export_csv(auth.username, project_id)
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
        },
    )


@router.get("/projects/{project_id}/delivery.json")
async def export_delivery(
    project_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        filename, content = service.export_delivery_json(auth.username, project_id)
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
        },
    )


_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_APPROVAL_EXPORTS = {
    "approval-report.md": (
        "export_approval_report_markdown",
        "text/markdown; charset=utf-8",
    ),
    "approval.xlsx": ("export_approval_excel", _XLSX_MEDIA),
    "feishu-bitable.xlsx": ("export_feishu_bitable", _XLSX_MEDIA),
    "full-report.json": ("export_full_report_json", "application/json; charset=utf-8"),
}


@router.get("/projects/{project_id}/exports/{kind}")
async def export_approval_file(
    project_id: str,
    kind: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    spec = _APPROVAL_EXPORTS.get(kind)
    if spec is None:
        raise ApiError("不支持的导出类型", status_code=404)
    try:
        filename, content = getattr(service, spec[0])(auth.username, project_id)
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return Response(
        content=content,
        media_type=spec[1],
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
        },
    )


class PublishStatusRequest(BaseModel):
    updates: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    comment: str = Field(default="", max_length=500)


class PerformanceRequest(BaseModel):
    platform: str = Field(min_length=1, max_length=20)
    records: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    comment: str = Field(default="", max_length=500)


@router.post("/projects/{project_id}/contents/publish-status")
async def update_publish_status(
    project_id: str,
    body: PublishStatusRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = service.update_publish_status(
            username=auth.username,
            project_id=project_id,
            updates=body.updates,
            comment=body.comment,
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.post("/projects/{project_id}/performance")
async def record_performance(
    project_id: str,
    body: PerformanceRequest,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = service.record_performance(
            username=auth.username,
            project_id=project_id,
            platform=body.platform,
            records=body.records,
            comment=body.comment,
        )
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.get("/projects/{project_id}/sku-reuse")
async def sku_reuse_status(
    project_id: str,
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    try:
        result = service.sku_reuse_status(auth.username, project_id)
    except PharmaTranslatorError as exc:
        raise _translate_error(exc) from exc
    return ok(result)


@router.get("/content-hits")
async def list_content_hits(
    auth: AuthContext = Depends(require_pharma_scope),
    service: PharmaTranslatorService = Depends(get_service),
):
    return ok({"items": service.list_content_hits(auth.username)})
