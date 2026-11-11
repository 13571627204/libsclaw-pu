from __future__ import annotations

import io
import json
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from PIL import Image

from astrbot.dashboard.api.auth import AuthContext
from astrbot.dashboard.api.pharma_translator import (
    require_pharma_scope,
)
from astrbot.dashboard.api.pharma_translator import (
    router as pharma_router,
)
from astrbot.dashboard.responses import ApiError
from astrbot.dashboard.services.pharma_translator_service import (
    PharmaTranslatorService,
)

LEAFLET_TEXT = """
OTC
【药品名称】通用名称：安神补脑液
【功能主治】生精补髓，益气养血，强脑安神。
【规格】每支装10毫升
【用法用量】口服。一次10毫升，一日2次。
【不良反应】尚不明确。
【批准文号】国药准字Z22000001
"""


def _png_bytes() -> bytes:
    image = Image.new("RGB", (1400, 1800), "white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest_asyncio.fixture
async def pharma_client(tmp_path):
    app = FastAPI()
    app.state.services = SimpleNamespace(
        pharma_translator=PharmaTranslatorService(tmp_path)
    )
    app.include_router(pharma_router, prefix="/api/v1")
    app.dependency_overrides[require_pharma_scope] = lambda: AuthContext(
        username="api-reviewer", scopes=["data"], via="test"
    )

    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "message": exc.message},
        )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client, app


@pytest.mark.asyncio
async def test_analyze_multipart_contract_does_not_return_framework_422(
    pharma_client,
):
    client, _app = pharma_client
    response = await client.post(
        "/api/v1/pharma-translator/analyze",
        data={
            "product_name": "",
            "product_type": "自动识别",
            "manual_text": LEAFLET_TEXT,
        },
        files={"file": ("leaflet.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 200, response.text
    project = response.json()["data"]
    assert len(project["fields"]) == 11
    assert sum(field["critical"] for field in project["fields"]) == 8
    assert project["workflow"]["current_step"] == 1
    assert project["ocr_provider"] == "manual_review_text"
    assert all(
        field["source_type"] == "manual_review"
        for field in project["fields"]
        if field["source_text"]
    )


@pytest.mark.asyncio
async def test_image_upload_without_manual_text_uses_ocr_result(
    pharma_client, monkeypatch
):
    client, app = pharma_client
    service = app.state.services.pharma_translator
    polygon = [[10, 20], [900, 20], [900, 100], [10, 100]]
    monkeypatch.setattr(
        service,
        "_rapidocr_ocr",
        lambda _content: [
            {
                "page_no": 1,
                "text": LEAFLET_TEXT,
                "confidence": 0.97,
                "start_offset": 0,
                "end_offset": len(LEAFLET_TEXT),
                "blocks": [
                    {
                        "text": line,
                        "confidence": 0.98,
                        "polygon": polygon,
                    }
                    for line in LEAFLET_TEXT.splitlines()
                    if line.strip()
                ],
            }
        ],
    )

    response = await client.post(
        "/api/v1/pharma-translator/analyze",
        data={"product_type": "自动识别"},
        files={"file": ("leaflet.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 200, response.text
    project = response.json()["data"]
    assert project["ocr_provider"] == "rapidocr_local"
    values = {field["field_code"]: field["value"] for field in project["fields"]}
    assert values["drug_name"] == "安神补脑液"
    assert values["dosage"] == "口服。一次10毫升，一日2次。"
    assert values["adverse_reactions"] == "尚不明确。"
    assert all(
        field["source_type"] == "document_extracted"
        for field in project["fields"]
        if field["value"]
    )


@pytest.mark.asyncio
async def test_workflow_action_accepts_data_and_advances_profile(pharma_client):
    client, _app = pharma_client
    created = await client.post(
        "/api/v1/pharma-translator/analyze",
        data={"product_type": "自动识别", "manual_text": LEAFLET_TEXT},
        files={"file": ("leaflet.png", _png_bytes(), "image/png")},
    )
    project = created.json()["data"]
    for field in project["fields"]:
        field["confirmed"] = True

    response = await client.post(
        f"/api/v1/pharma-translator/projects/{project['project_id']}/workflow/actions",
        json={
            "action": "confirm_profile",
            "data": {"fields": project["fields"]},
            "comment": "逐项对照原文",
        },
    )

    assert response.status_code == 200, response.text
    advanced = response.json()["data"]
    assert advanced["workflow"]["current_step"] == 2
    assert advanced["workflow"]["step_status"]["1"] == "passed"
    assert advanced["dimensions"]
    assert advanced["safety_constraints"]
    assert advanced["claims"]


@pytest.mark.asyncio
async def test_delete_project_removes_owned_files_and_history(pharma_client):
    client, app = pharma_client
    created = await client.post(
        "/api/v1/pharma-translator/analyze",
        data={"manual_text": LEAFLET_TEXT},
        files={"file": ("leaflet.png", _png_bytes(), "image/png")},
    )
    project_id = created.json()["data"]["project_id"]
    service = app.state.services.pharma_translator
    project_dir = service._project_dir("api-reviewer", project_id)
    assert project_dir.exists()

    deleted = await client.delete(f"/api/v1/pharma-translator/projects/{project_id}")
    assert deleted.status_code == 200
    assert not project_dir.exists()
    assert all(
        item["project_id"] != project_id
        for item in (await client.get("/api/v1/pharma-translator/projects")).json()[
            "data"
        ]
    )
    assert (
        await client.get(f"/api/v1/pharma-translator/projects/{project_id}")
    ).status_code == 422
    assert (
        await client.delete(f"/api/v1/pharma-translator/projects/{project_id}")
    ).status_code == 422


@pytest.mark.asyncio
async def test_delete_project_cannot_remove_another_users_project(pharma_client):
    client, app = pharma_client
    created = await client.post(
        "/api/v1/pharma-translator/analyze",
        data={"manual_text": LEAFLET_TEXT},
        files={"file": ("leaflet.png", _png_bytes(), "image/png")},
    )
    project_id = created.json()["data"]["project_id"]
    service = app.state.services.pharma_translator
    with pytest.raises(Exception, match="项目不存在或无权访问"):
        service.delete_project("another-user", project_id)
    assert service._project_dir("api-reviewer", project_id).exists()


@pytest.mark.asyncio
async def test_missing_file_is_the_only_framework_validation_error(pharma_client):
    client, _app = pharma_client
    response = await client.post(
        "/api/v1/pharma-translator/analyze",
        data={"manual_text": LEAFLET_TEXT},
    )
    assert response.status_code == 422
    assert response.json()["detail"]


@pytest.mark.asyncio
async def test_delivery_export_is_blocked_before_final_approval(pharma_client):
    client, _app = pharma_client
    created = await client.post(
        "/api/v1/pharma-translator/analyze",
        data={"manual_text": LEAFLET_TEXT},
        files={"file": ("leaflet.png", _png_bytes(), "image/png")},
    )
    project_id = created.json()["data"]["project_id"]
    response = await client.get(
        f"/api/v1/pharma-translator/projects/{project_id}/delivery.json"
    )
    assert response.status_code == 422
    assert "终审" in response.json()["message"]


@pytest.mark.asyncio
async def test_invalid_rework_target_returns_readable_422(pharma_client):
    client, _app = pharma_client
    created = await client.post(
        "/api/v1/pharma-translator/analyze",
        data={"manual_text": LEAFLET_TEXT},
        files={"file": ("leaflet.png", _png_bytes(), "image/png")},
    )
    project_id = created.json()["data"]["project_id"]

    response = await client.post(
        f"/api/v1/pharma-translator/projects/{project_id}/workflow/actions",
        json={
            "action": "rework",
            "data": {"target_step": "not-a-number"},
            "comment": "退回重新核对",
        },
    )

    assert response.status_code == 422
    assert response.json()["message"] == "返工目标步骤必须为整数"


@pytest.mark.asyncio
async def test_dimension_generation_route_uses_configured_model_and_visible_errors(
    pharma_client,
):
    client, app = pharma_client
    created = await client.post(
        "/api/v1/pharma-translator/analyze",
        data={
            "manual_text": LEAFLET_TEXT + "\n【成分】鹿茸、干姜。\n【适用人群】成年人。"
        },
        files={"file": ("leaflet.png", _png_bytes(), "image/png")},
    )
    project = created.json()["data"]
    url = f"/api/v1/pharma-translator/projects/{project['project_id']}/dimensions/generate"
    blocked = await client.post(url)
    assert blocked.status_code == 422
    assert "只能在第 2 步" in blocked.json()["message"]
    service = app.state.services.pharma_translator
    for field in project["fields"]:
        field["confirmed"] = True
    service.workflow_action(
        username="api-reviewer",
        project_id=project["project_id"],
        action="confirm_profile",
        payload={"fields": project["fields"]},
    )
    missing = await client.post(url)
    assert missing.status_code == 422
    assert (
        "未配置可用的生成模型，请在模型提供商启用当前对话模型或支持的OpenAI兼容provider"
        in missing.json()["message"]
    )

    async def text_chat(**kwargs):
        evidence = json.loads(kwargs["prompt"])["evidence"]
        return SimpleNamespace(
            completion_text=json.dumps(
                {
                    code: [
                        {"text": item["text"], "evidence_ids": [item["evidence_id"]]}
                        for item in evidence
                        if item["dimension_id"] == code
                    ]
                    for code in ("ingredients", "audience")
                },
                ensure_ascii=False,
            )
        )

    provider = SimpleNamespace(
        provider_config={
            "id": "kimi",
            "type": "openai_chat_completion",
            "api_base": "https://api.moonshot.cn/v1",
        },
        text_chat=text_chat,
    )
    service.core_lifecycle = SimpleNamespace(
        provider_manager=SimpleNamespace(
            provider_insts=[provider],
            get_using_provider=lambda _kind: provider,
        )
    )
    generated = await client.post(url)
    assert generated.status_code == 200, generated.text
    result = generated.json()["data"]
    assert result["workflow"]["current_step"] == 2
    assert result["audit_events"][-1]["action"] == "generate_dimensions"
    assert "kimi（openai_chat_completion）" in result["audit_events"][-1]["comment"]
    assert all(
        item["evidence_ids"]
        and item["model_provider"] == "kimi（openai_chat_completion）"
        for dimension in result["dimensions"]
        if dimension["dimension_id"] in {"ingredients", "audience"}
        for item in dimension["items"]
        if item["source_type"] == "model_generated"
    )


def test_openapi_contains_workflow_and_delivery_routes(pharma_client):
    _client, app = pharma_client
    paths = app.openapi()["paths"]
    assert "/api/v1/pharma-translator/analyze" in paths
    assert "/api/v1/pharma-translator/projects/{project_id}/workflow/actions" in paths
    assert (
        "/api/v1/pharma-translator/projects/{project_id}/dimensions/generate" in paths
    )
    assert "/api/v1/pharma-translator/projects/{project_id}/literature" in paths
    assert (
        "/api/v1/pharma-translator/projects/{project_id}/literature/{doc_id}" in paths
    )
    assert "/api/v1/pharma-translator/projects/{project_id}/literature/match" in paths
    assert "/api/v1/pharma-translator/projects/{project_id}/user-voices" in paths
    assert (
        "/api/v1/pharma-translator/projects/{project_id}/user-voices/{voice_id}"
        in paths
    )
    assert "/api/v1/pharma-translator/projects/{project_id}/delivery.json" in paths
    prefix = "/api/v1/pharma-translator"
    assert f"{prefix}/compliance/knowledge-base" in paths
    assert f"{prefix}/projects/{{project_id}}/compliance/review" in paths
    assert f"{prefix}/projects/{{project_id}}/compliance/expert-tickets" in paths
    assert (
        f"{prefix}/projects/{{project_id}}/compliance/expert-tickets/{{ticket_id}}/answer"
        in paths
    )


@pytest.mark.asyncio
async def test_compliance_knowledge_base_route(pharma_client):
    client, _app = pharma_client
    response = await client.get("/api/v1/pharma-translator/compliance/knowledge-base")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["builder"].startswith("中睿医药商学院")
    assert data["expert_sla_hours"] == 24
    assert len(data["replacements"]) == 7


@pytest.mark.asyncio
async def test_literature_routes_upload_match_and_delete(pharma_client):
    """文献验证 API：上传 → 匹配 → 确认 → 删除的全链路契约。"""
    client, _app = pharma_client
    created = await client.post(
        "/api/v1/pharma-translator/analyze",
        data={"manual_text": LEAFLET_TEXT},
        files={"file": ("leaflet.png", _png_bytes(), "image/png")},
    )
    project = created.json()["data"]
    project_id = project["project_id"]
    for field in project["fields"]:
        field["confirmed"] = True

    # 第 1 步就上传文献 → 422
    premature = await client.post(
        f"/api/v1/pharma-translator/projects/{project_id}/literature",
        data={"doc_kind": "clinical"},
        files={"files": ("研究.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert premature.status_code == 422

    await client.post(
        f"/api/v1/pharma-translator/projects/{project_id}/workflow/actions",
        json={"action": "confirm_profile", "data": {"fields": project["fields"]}},
    )
    # 推进到第 3 步
    service = _app.state.services.pharma_translator
    current = service.get_project("api-reviewer", project_id)
    dimensions = [
        {
            **dimension,
            "items": [{**item, "confirmed": True} for item in dimension["items"]],
        }
        for dimension in current["dimensions"]
    ]
    constraints = [
        {**item, "confirmed": True} for item in current["safety_constraints"]
    ]
    await client.post(
        f"/api/v1/pharma-translator/projects/{project_id}/workflow/actions",
        json={
            "action": "confirm_dimensions",
            "data": {
                "dimensions": dimensions,
                "safety_constraints": constraints,
            },
        },
    )

    matched = await client.post(
        f"/api/v1/pharma-translator/projects/{project_id}/literature/match",
        json={"kb_ids": [], "kb_names": []},
    )
    assert matched.status_code == 200, matched.text
    result = matched.json()["data"]
    assert result["literature"]["matched_at"]
    assert result["literature_claims"]

    claims = [
        {
            "claim_id": claim["claim_id"],
            "accepted": claim["evidence_level"] in {"strong", "weak"}
            and bool(claim["citations"]),
        }
        for claim in result["literature_claims"]
    ]
    confirmed = await client.post(
        f"/api/v1/pharma-translator/projects/{project_id}/workflow/actions",
        json={"action": "confirm_literature", "data": {"claims": claims}},
    )
    assert confirmed.status_code == 422
    assert "签字" in confirmed.text

    confirmed = await client.post(
        f"/api/v1/pharma-translator/projects/{project_id}/workflow/actions",
        json={
            "action": "confirm_literature",
            "data": {
                "claims": claims,
                "signoff": {
                    "signer_name": "李医学",
                    "signer_title": "医学部经理",
                    "checklist": {
                        "claims_complete": True,
                        "matches_valid": True,
                        "levels_accurate": True,
                        "redlines_complete": True,
                    },
                },
            },
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    advanced = confirmed.json()["data"]
    assert advanced["workflow"]["current_step"] == 4
    assert advanced["workflow"]["state"] == "SCENE_CONFIRMATION"
    assert advanced["scenes"]
    assert advanced["unusable_claims"]
    assert advanced["literature_signoff"]["signer_name"] == "李医学"

    csv_resp = await client.get(
        f"/api/v1/pharma-translator/projects/{project_id}/literature/triple-table.csv"
    )
    assert csv_resp.status_code == 200, csv_resp.text
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "证据等级" in csv_resp.content.decode("utf-8-sig")

    redlines = await client.get(
        "/api/v1/pharma-translator/literature/redlines",
        params={"project_id": project_id},
    )
    assert redlines.status_code == 200, redlines.text
    assert redlines.json()["data"]["items"]

    archive = await client.get(
        f"/api/v1/pharma-translator/projects/{project_id}/literature/archive"
    )
    assert archive.status_code == 200, archive.text
    record = archive.json()["data"]
    assert record["signoff"]["signer_name"] == "李医学"
    assert record["triple_table"]


@pytest.mark.asyncio
async def test_user_voice_routes_import_and_delete(pharma_client):
    """用户原话 API：步骤门禁、来源声明校验、导入/删除契约。"""
    client, _app = pharma_client
    created = await client.post(
        "/api/v1/pharma-translator/analyze",
        data={"manual_text": LEAFLET_TEXT},
        files={"file": ("leaflet.png", _png_bytes(), "image/png")},
    )
    project = created.json()["data"]
    project_id = project["project_id"]
    voices_url = f"/api/v1/pharma-translator/projects/{project_id}/user-voices"

    # 第 1 步导入 → 422
    premature = await client.post(
        voices_url,
        json={
            "voices": [
                {"text": "又到3点了还睡不着", "source": "小红书评论抽样（已获授权）"}
            ]
        },
    )
    assert premature.status_code == 422

    for field in project["fields"]:
        field["confirmed"] = True
    await client.post(
        f"/api/v1/pharma-translator/projects/{project_id}/workflow/actions",
        json={"action": "confirm_profile", "data": {"fields": project["fields"]}},
    )
    service = _app.state.services.pharma_translator
    current = service.get_project("api-reviewer", project_id)
    dimensions = [
        {
            **dimension,
            "items": [{**item, "confirmed": True} for item in dimension["items"]],
        }
        for dimension in current["dimensions"]
    ]
    constraints = [
        {**item, "confirmed": True} for item in current["safety_constraints"]
    ]
    await client.post(
        f"/api/v1/pharma-translator/projects/{project_id}/workflow/actions",
        json={
            "action": "confirm_dimensions",
            "data": {"dimensions": dimensions, "safety_constraints": constraints},
        },
    )

    # 缺少来源声明 → 422
    missing_source = await client.post(
        voices_url, json={"voices": [{"text": "又到3点了还睡不着", "source": ""}]}
    )
    assert missing_source.status_code == 422
    assert "来源声明" in missing_source.json()["message"]

    imported = await client.post(
        voices_url,
        json={
            "voices": [
                {
                    "text": "又到3点了还睡不着，脑子停不下来",
                    "source": "小红书评论抽样（已获授权）",
                },
                {"text": "一到下午就没精神", "source": "电商评论导出（已授权）"},
            ]
        },
    )
    assert imported.status_code == 200, imported.text
    pool = imported.json()["data"]["user_voices_pool"]
    assert len(pool) == 2
    assert all(voice["source"] and voice["voice_id"] for voice in pool)

    removed = await client.delete(f"{voices_url}/{pool[0]['voice_id']}")
    assert removed.status_code == 200, removed.text
    remaining = removed.json()["data"]["user_voices_pool"]
    assert [voice["voice_id"] for voice in remaining] == [pool[1]["voice_id"]]

    missing = await client.delete(f"{voices_url}/not-exists")
    assert missing.status_code == 422
