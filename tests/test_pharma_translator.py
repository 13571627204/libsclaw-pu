from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from astrbot.dashboard.services.pharma_translator_service import (
    PharmaTranslatorError,
    PharmaTranslatorService,
)

LEAFLET_TEXT = """
OTC
【药 品 名 称】
通用名称：安神补脑液
汉语拼音：Anshen Bunaoye
【功能主治】生精补髓，益气养血，强脑安神。用于肾精不足、气血两亏所致的头晕、乏力、健忘、失眠。
【规 格】每支装10毫升
【用法用量】口服。一次10毫升，一日2次。
【不良反应】尚不明确。
【批准文号】国药准字Z22000001
"""


def _png_bytes() -> bytes:
    image = Image.new("RGB", (1400, 1800), "white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize("status_code", [413, 422, 503])
def test_pharma_error_preserves_message_and_http_status(status_code: int):
    error = PharmaTranslatorError("请检查上传文件", status_code=status_code)
    assert str(error) == "请检查上传文件"
    assert error.status_code == status_code
    assert PharmaTranslatorError("默认校验错误").status_code == 422


@pytest.mark.asyncio
async def test_analyze_generates_traceable_fields_and_keyword_table(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)

    project = await service.analyze(
        username="tenant-a-user",
        product_name="",
        product_type="自动识别",
        filename="leaflet.png",
        content=_png_bytes(),
        manual_text=LEAFLET_TEXT,
    )

    fields = {field["field_code"]: field for field in project["fields"]}
    assert set(fields) == {
        "drug_name",
        "approval_type",
        "product_type",
        "specification",
        "appearance",
        "dosage",
        "adverse_reactions",
        "indications",
        "approval_number",
        "ingredients",
        "audience",
    }
    assert fields["drug_name"]["value"] == "安神补脑液"
    assert fields["approval_number"]["value"] == "国药准字Z22000001"
    assert fields["approval_type"]["value"] == "药品批准文号"
    assert fields["product_type"]["value"] == "OTC"
    assert fields["specification"]["value"] == "每支装10毫升"
    assert fields["dosage"]["value"].startswith("口服")
    assert fields["adverse_reactions"]["value"] == "尚不明确。"
    assert fields["indications"]["value"].startswith("生精补髓")
    assert fields["approval_number"]["source_text"]
    assert fields["approval_number"]["page_no"] == 1
    assert project["product_name"] == "安神补脑液"
    assert project["product_type"] == "OTC"

    keywords = project["keywords"]
    assert any(item["keyword"] == "安神补脑液" for item in keywords)
    assert any(item["source_field"] == "indications" for item in keywords)
    assert not any(item["source_field"] == "dosage" for item in keywords)
    assert not any(item["source_field"] == "adverse_reactions" for item in keywords)


@pytest.mark.parametrize(
    ("ocr_text", "expected"),
    [
        (
            "【药品名称】\n【药 品 名 称】：安神补脑液\n【规 格】每支装10毫升",
            "安神补脑液",
        ),
        (
            "规格：\n规 格 : 每支装10毫升\n用法用量：口服。",
            "每支装10毫升",
        ),
        (
            "【规格】\n规格：\n规格：每支装10毫升\n【用法用量】口服。",
            "每支装10毫升",
        ),
    ],
)
def test_repeated_ocr_headings_use_nonempty_evidence(
    tmp_path: Path, ocr_text: str, expected: str
):
    service = PharmaTranslatorService(tmp_path)
    fields = service.extract_fields(ocr_text, pages=service._pages_from_text(ocr_text))
    code = "drug_name" if "药品名称" in ocr_text else "specification"
    field = next(field for field in fields if field["field_code"] == code)

    assert field["value"] == expected
    assert expected in field["source_text"]
    assert field["source_text"].count(expected) == 1
    assert field["start_offset"] == ocr_text.index(expected)
    assert field["end_offset"] == field["start_offset"] + len(expected)
    assert field["page_no"] == 1


def test_ocr_empty_headings_do_not_create_field_values(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    text = "【药品名称】\n药品名称：\n【规格】每支装10毫升"
    fields = service.extract_fields(text, pages=service._pages_from_text(text))
    drug_name = next(field for field in fields if field["field_code"] == "drug_name")

    assert drug_name["value"] == ""
    assert drug_name["source_text"] == ""


def test_repeated_ocr_heading_uses_later_page_evidence(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    text = "【规格】\f【规格】每支装10毫升\n【用法用量】口服。"
    pages = service._pages_from_text(text)
    full_text = "\n\n".join(page["text"] for page in pages)
    fields = service.extract_fields(full_text, pages=pages)
    specification = next(
        field for field in fields if field["field_code"] == "specification"
    )

    assert specification["value"] == "每支装10毫升"
    assert specification["page_no"] == 2
    assert (
        full_text[specification["start_offset"] : specification["end_offset"]]
        == specification["value"]
    )
    assert specification["source_text"] == "【规格】每支装10毫升"


@pytest.mark.asyncio
async def test_analyze_populates_fields_from_repeated_ocr_headings(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    ocr_text = (
        "【药品名称】\n通用名称：安神补脑液\n"
        "【规格】\n规 格：每支装10毫升\n"
        "【用法用量】口服。一次10毫升，一日2次。\n"
        "【批准文号】国药准字Z22000001"
    )
    project = await service.analyze(
        username="ocr-review",
        product_name="",
        product_type="自动识别",
        filename="leaflet.png",
        content=_png_bytes(),
        manual_text=ocr_text,
    )
    fields = {field["field_code"]: field for field in project["fields"]}

    assert fields["drug_name"]["value"] == "安神补脑液"
    assert fields["specification"]["value"] == "每支装10毫升"
    assert fields["dosage"]["value"] == "口服。一次10毫升，一日2次。"
    assert fields["approval_number"]["value"] == "国药准字Z22000001"
    for code in ("drug_name", "specification", "dosage", "approval_number"):
        field = fields[code]
        assert field["value"] in field["source_text"]
        assert ocr_text[field["start_offset"] : field["end_offset"]] == field["value"]
        assert field["page_no"] == 1


@pytest.mark.asyncio
async def test_confirm_requires_every_populated_critical_field(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await service.analyze(
        username="reviewer",
        product_name="",
        product_type="自动识别",
        filename="leaflet.png",
        content=_png_bytes(),
        manual_text=LEAFLET_TEXT,
    )

    with pytest.raises(PharmaTranslatorError, match="关键字段尚未人工确认"):
        service.confirm_project(
            username="reviewer",
            project_id=project["project_id"],
            fields=project["fields"],
            keywords=project["keywords"],
        )

    for field in project["fields"]:
        if field["critical"] and field["value"]:
            field["confirmed"] = True
    confirmed = service.confirm_project(
        username="reviewer",
        project_id=project["project_id"],
        fields=project["fields"],
        keywords=project["keywords"],
        comment="已逐项对照原图",
    )

    assert confirmed["status"] == "confirmed"
    assert confirmed["confirmed_by"] == "reviewer"
    assert confirmed["audit_events"][-1]["action"] == "confirm"


@pytest.mark.asyncio
async def test_projects_are_isolated_by_authenticated_user(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await service.analyze(
        username="tenant-a",
        product_name="",
        product_type="自动识别",
        filename="leaflet.png",
        content=_png_bytes(),
        manual_text=LEAFLET_TEXT,
    )

    assert len(service.list_projects("tenant-a")) == 1
    assert service.list_projects("tenant-b") == []
    with pytest.raises(PharmaTranslatorError, match="不存在或无权访问"):
        service.get_project("tenant-b", project["project_id"])


def test_file_magic_must_match_extension(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    with pytest.raises(PharmaTranslatorError, match="实际格式"):
        service._validate_file("fake.png", b"not-a-real-image")


@pytest.mark.asyncio
async def test_missing_drug_name_is_not_inferred_from_filename(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await service.analyze(
        username="no-guess",
        product_name="",
        product_type="自动识别",
        filename="cf8d64f25d4d5262f7e3e79ecba6f4f.png",
        content=_png_bytes(),
        manual_text="【用法用量】口服。一次10毫升，一日2次。",
    )

    assert project["product_name"] == "待确认药品"
    drug_name = next(
        field for field in project["fields"] if field["field_code"] == "drug_name"
    )
    assert drug_name["value"] == ""


@pytest.mark.asyncio
async def test_export_csv_contains_source_and_confirmation_columns(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await service.analyze(
        username="exporter",
        product_name="",
        product_type="自动识别",
        filename="leaflet.png",
        content=_png_bytes(),
        manual_text=LEAFLET_TEXT,
    )

    filename, content = service.export_csv("exporter", project["project_id"])
    decoded = content.decode("utf-8-sig")
    assert filename.endswith("_关键词表.csv")
    assert "原文证据" in decoded
    assert "来源字段" in decoded
    assert "安神补脑液" in decoded
