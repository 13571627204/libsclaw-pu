from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from astrbot.dashboard.api.pharma_translator import WorkflowActionRequest
from astrbot.dashboard.services.pharma_translator_service import (
    CONTENT_IMAGE_SIZES,
    FINAL_APPROVAL_CHECKLIST,
    PERFORMANCE_PLATFORMS,
    PharmaTranslatorError,
    PharmaTranslatorService,
)


def _final_payload(**overrides):
    payload = {
        "signer_name": "王总监",
        "signer_title": "品牌总监",
        "checklist": list(FINAL_APPROVAL_CHECKLIST),
        "duration_minutes": 45,
        "business_goal_note": "达成首轮种草目标",
        "publish_authorization": {"authorized": True, "channels": ["小红书"]},
    }
    payload.update(overrides)
    return payload


LEAFLET_TEXT = """
OTC
【药品名称】安神补脑液
【功能主治】生精补髓，益气养血，强脑安神。用于肾精不足、气血两亏所致的头晕、乏力、健忘、失眠。
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


async def _new_project(
    service: PharmaTranslatorService, text: str = LEAFLET_TEXT
) -> dict:
    return await service.analyze(
        username="workflow-user",
        product_name="",
        product_type="自动识别",
        filename="leaflet.png",
        content=_png_bytes(),
        manual_text=text,
    )


def _confirm_all_fields(project: dict) -> list[dict]:
    fields = []
    for field in project["fields"]:
        fields.append({**field, "confirmed": bool(field["value"])})
    return fields


def _confirm_dimensions(project: dict) -> tuple[list[dict], list[dict]]:
    dimensions = []
    for dimension in project["dimensions"]:
        dimensions.append(
            {
                **dimension,
                "items": [{**item, "confirmed": True} for item in dimension["items"]],
            }
        )
    constraints = [
        {**constraint, "confirmed": True}
        for constraint in project["safety_constraints"]
    ]
    return dimensions, constraints


def _workflow_action(
    service: PharmaTranslatorService,
    project: dict,
    action: str,
    data: dict | None = None,
    comment: str = "",
) -> dict:
    return service.workflow_action(
        username="workflow-user",
        project_id=project["project_id"],
        action=action,
        payload=data or {},
        comment=comment,
    )


def _compliance_payload(project: dict, decision: str = "keep") -> dict:
    """合规部签字：逐条批注所有 ⚠️谨慎/🟢替换项。"""
    reviews = {
        risk["risk_id"]: {"decision": decision, "note": "合规部已逐条复核"}
        for risk in project["compliance"]["risks"]
        if risk["level"] in {"caution", "replace"}
    }
    return {
        "signer_name": "张合规",
        "signer_title": "合规部经理",
        "citation_covered": True,
        "reviews": reviews,
    }


LITERATURE_SIGNOFF = {
    "signer_name": "李医学",
    "signer_title": "医学部经理",
    "checklist": {
        "claims_complete": True,
        "matches_valid": True,
        "levels_accurate": True,
        "redlines_complete": True,
    },
}


async def _pass_literature(service: PharmaTranslatorService, project: dict) -> dict:
    """完成第 3 步文献验证：执行匹配并接受全部有证据的卖点。"""
    project = await service.run_literature_match(
        username="workflow-user", project_id=project["project_id"]
    )
    claims = [
        {
            **claim,
            "accepted": claim["evidence_level"] in {"strong", "weak"}
            and bool(claim["citations"]),
        }
        for claim in project["literature_claims"]
    ]
    return _workflow_action(
        service,
        project,
        "confirm_literature",
        {"claims": claims, "signoff": LITERATURE_SIGNOFF},
    )


COMPETITOR_SAMPLES = [
    {
        "platform": "douyin",
        "kind": "post",
        "channel": "search",
        "keyword": "失眠",
        "title": "熬夜失眠怎么办",
        "text": "天天熬夜加班，晚上躺床上两小时都睡不着，第二天头晕乏力",
        "likes": 5200,
        "comments": 310,
        "price": None,
        "url": "https://www.douyin.com/video/1",
    },
    {
        "platform": "xiaohongshu",
        "kind": "post",
        "channel": "search",
        "keyword": "补脑",
        "title": "考研党补脑好物",
        "text": "考研复习记忆力下降，配料表里有人参，成分党放心入",
        "likes": 880,
        "comments": 42,
        "price": 39.9,
        "url": "https://www.xiaohongshu.com/explore/2",
    },
    {
        "platform": "douyin",
        "kind": "comment",
        "channel": "comment",
        "keyword": "失眠",
        "title": "",
        "text": "吃了一周还是半夜醒来，健忘越来越严重了",
        "likes": 1200,
        "comments": 0,
        "price": 59.0,
        "url": "https://www.douyin.com/video/1",
    },
]


def _competitor_analysis_output() -> dict:
    return {
        "formula_templates": [
            {
                "platform": "douyin",
                "opening": "痛点提问",
                "middle": "场景共鸣",
                "ending": "引导评论",
                "item_ids": ["c001", "c999"],
            }
        ],
        "trust_anchors": [
            {
                "type": "ingredient",
                "label": "成分党背书",
                "item_ids": ["c002"],
                "suggestion": "展示批准文号与成分",
            },
            {"type": "user", "label": "无引用应丢弃", "item_ids": ["c404"]},
        ],
        "gap_map": [
            {
                "scene": "更年期睡眠",
                "opportunity": "样本中无竞品覆盖",
                "entry_angle": "更年期夜醒",
                "suggested_priority": "P0",
                "item_ids": [],
            },
            {"scene": "", "opportunity": "缺场景应丢弃"},
        ],
        "user_voices": [
            {"item_id": "c003", "pain_point": "夜醒", "quote": "半夜醒来"},
            {"item_id": "c003", "pain_point": "编造", "quote": "完全治好了失眠"},
        ],
        "platform_strategy": [
            {
                "platform": "douyin",
                "tone": "口语化",
                "strategy": "痛点短视频",
                "item_ids": ["c001"],
            }
        ],
    }


async def _pass_competitor(
    service: PharmaTranslatorService, project: dict, monkeypatch
) -> dict:
    """完成第 5 步竞品扫描：mock TikHub 采集 + 固定模型分析 + 选定 P0 切口。"""
    from astrbot.dashboard.services import pharma_competitor

    async def fake_tikhub(platforms, keywords, per_keyword=20):
        return [dict(item) for item in COMPETITOR_SAMPLES], []

    monkeypatch.setattr(pharma_competitor, "collect_tikhub", fake_tikhub)
    project = await service.scan_competitors(
        "workflow-user",
        project["project_id"],
        mode="deep",
        platforms=["douyin", "xiaohongshu"],
        keywords=["失眠"],
    )
    previous = service.core_lifecycle
    _attach_models(service, [_JsonChatProvider(_competitor_analysis_output())])
    try:
        project = await service.analyze_competitors(
            "workflow-user", project["project_id"]
        )
    finally:
        service.core_lifecycle = previous
    gaps = [
        {"gap_id": gap["gap_id"], "selected": True, "priority": "P0"}
        for gap in project["competitor"]["analysis"]["gap_map"]
    ]
    return _workflow_action(service, project, "confirm_competitor", {"gaps": gaps})


def _compliance_filter_payload(project: dict, decision: str = "keep") -> dict:
    """Step 6 合规部确认：逐条复核 + 存量处置执行 + 广审排期。"""
    state = project["compliance_filter"]
    return {
        "signer_name": "张合规",
        "signer_title": "合规部经理",
        "reviews": {
            risk["risk_id"]: {"decision": decision, "note": "合规部已逐条复核"}
            for risk in state["risks"]
            if risk["level"] in {"caution", "replace"}
        },
        "disposals": {
            item["disposal_id"]: {"status": "done", "note": "已联系渠道"}
            for item in state["disposals"]
        },
        "ad_review_schedule": {"apply_date": "2026-12-01"},
    }


async def _pass_compliance_filter(
    service: PharmaTranslatorService, project: dict, inventory: list | None = None
) -> dict:
    project = await service.run_compliance_filter(
        username="workflow-user",
        project_id=project["project_id"],
        ai_search=False,
        inventory=inventory,
    )
    return _workflow_action(
        service,
        project,
        "confirm_compliance_filter",
        _compliance_filter_payload(project),
    )


@pytest.mark.asyncio
async def test_seven_step_workflow_generates_traceable_approved_delivery(
    tmp_path: Path, monkeypatch
):
    service = PharmaTranslatorService(tmp_path)
    project = await _new_project(service)
    assert project["workflow"]["current_step"] == 1
    assert project["dimensions"] == []

    project = _workflow_action(
        service,
        project,
        "confirm_profile",
        {"fields": _confirm_all_fields(project)},
    )
    assert project["workflow"]["current_step"] == 2
    assert {item["dimension_id"] for item in project["dimensions"]} == {
        "ingredients",
        "efficacy",
        "audience",
        "endorsement",
        "channels",
        "brand_product",
    }
    assert {item["source_field"] for item in project["safety_constraints"]} == {
        "dosage",
        "adverse_reactions",
    }

    dimensions, constraints = _confirm_dimensions(project)
    project = _workflow_action(
        service,
        project,
        "confirm_dimensions",
        {"dimensions": dimensions, "safety_constraints": constraints},
    )
    assert project["workflow"]["current_step"] == 3
    assert project["literature_claims"]
    assert project["scenes"] == []

    project = await _pass_literature(service, project)
    assert project["workflow"]["current_step"] == 4
    assert project["scenes"]
    assert project["claims"]
    assert all(
        claim["evidence_level"] in {"strong", "weak"} for claim in project["claims"]
    )

    project = _workflow_action(
        service,
        project,
        "confirm_scenes",
        {"scenes": project["scenes"]},
    )
    assert project["workflow"]["current_step"] == 5
    project = await _pass_competitor(service, project, monkeypatch)
    assert project["workflow"]["current_step"] == 6
    analysis = project["competitor"]["analysis"]
    assert [gap["priority"] for gap in analysis["gap_map"]] == ["P0"]
    assert analysis["formula_templates"][0]["item_ids"] == ["c001"]
    assert [anchor["label"] for anchor in analysis["trust_anchors"]] == ["成分党背书"]
    assert [voice["quote"] for voice in analysis["user_voices"]] == ["半夜醒来"]
    assert analysis["price_bands"]["count"] == 0
    project = await _pass_compliance_filter(service, project)
    assert project["compliance_filter"]["status"] == "confirmed"
    assert project["compliance_filter"]["record"]["kb_version"]
    assert project["workflow"]["current_step"] == 9
    assert project["approvals"]["medical"]["operator"] == "workflow-user"

    project = _workflow_action(
        service,
        project,
        "generate_contents",
        {"platforms": ["公众号"], "count": 2, "tone": "专业克制"},
    )
    assert len(project["contents"]) == 2
    assert project["compliance"]["status"] == "clear"
    valid_claims = {
        claim["claim_id"] for claim in project["claims"] if claim["medical_confirmed"]
    }
    assert all(
        set(content["claim_ids"]) <= valid_claims for content in project["contents"]
    )

    project = _workflow_action(service, project, "market_confirm")
    project = _workflow_action(
        service, project, "compliance_confirm", _compliance_payload(project)
    )
    record = project["approvals"]["compliance"]["record"]
    assert record["kb_version"] == project["compliance"]["kb_version"]
    assert record["retrieval_date"]
    assert record["signer_name"] == "张合规"
    project = _workflow_action(service, project, "final_approve", _final_payload())
    assert project["workflow"]["status"] == "approved"
    assert project["status"] == "approved"
    assert len(project["version_history"]) == 14
    filename, delivery = service.export_delivery_json(
        "workflow-user", project["project_id"]
    )
    assert filename.endswith("_内容交付包.json")
    assert b'"contents"' in delivery
    project_dir = service._project_dir("workflow-user", project["project_id"])
    assert len(list((project_dir / "versions").glob("*.json"))) == 14


async def _reach_content_step(service, monkeypatch, text: str = LEAFLET_TEXT) -> dict:
    project = await _new_project(service, text)
    project = _workflow_action(
        service, project, "confirm_profile", {"fields": _confirm_all_fields(project)}
    )
    dimensions, constraints = _confirm_dimensions(project)
    project = _workflow_action(
        service,
        project,
        "confirm_dimensions",
        {"dimensions": dimensions, "safety_constraints": constraints},
    )
    project = await _pass_literature(service, project)
    project = _workflow_action(
        service, project, "confirm_scenes", {"scenes": project["scenes"]}
    )
    project = await _pass_competitor(service, project, monkeypatch)
    project = await _pass_compliance_filter(service, project)
    assert project["workflow"]["current_step"] == 9
    return project


def _content_batch_output(
    claim_no: str, scene_no: str, *, with_unverified: bool = True
) -> dict:
    return {
        "topic_matrix": [
            {
                "group": scene_no,
                "group_name": "失眠场景",
                "topics": [
                    {
                        "title": f"选题{index}",
                        "channel": "小红书图文" if index % 2 else "不存在渠道",
                        "claim_nos": [claim_no, "F99"],
                        "publish_time": "周三 21:00",
                    }
                    for index in range(1, 4)
                ],
            },
            {
                "group": "缺口截流",
                "topics": [{"title": "选题4", "channel": "抖音短视频"}],
            },
        ],
        "platform_plan": [
            {
                "platform": "小红书",
                "form": "图文笔记",
                "monthly_count": "20条",
                "note": "主战场",
            }
        ],
        "comment_replies": [
            {"q": f"问题{index}？", "a": "请仔细阅读说明书或咨询药师～"}
            for index in range(1, 6)
        ],
        "items": [
            {
                "scene_no": scene_no,
                "title": "加班后睡不着的第N天",
                "title_options": ["备选1", "备选2", "备选3"],
                "body": "场景描述。效果因个体差异而不同，请仔细阅读说明书并在医师或药师指导下使用。",
                "hashtags": ["睡眠"],
                "claim_nos": [claim_no],
                "publish_time": {"slot": "周三 21:00", "reason": "睡前活跃"},
                "assets": ["图1 夜晚书桌"],
                "faq": [{"q": f"Q{index}", "a": "请咨询药师"} for index in range(3)],
                "ad_review_tips": ["避免疗效承诺"],
            },
            {"title": "无卖点", "body": "x", "claim_nos": []},
            *(
                [
                    {
                        "title": "未验证卖点",
                        "body": "据说三天见效。效果因个体差异而不同，请仔细阅读说明书并在医师或药师指导下使用。",
                        "claim_nos": ["F99"],
                    }
                ]
                if with_unverified
                else []
            ),
        ],
    }


@pytest.mark.asyncio
async def test_content_batch_generates_matrix_samples_and_dual_signoff(
    tmp_path: Path, monkeypatch
):
    service = PharmaTranslatorService(tmp_path)
    project = await _reach_content_step(service, monkeypatch)
    claim_no = project["claims"][0]["claim_no"]
    scene = next(scene for scene in project["scenes"] if scene.get("selected"))
    provider = _JsonChatProvider(
        _content_batch_output(claim_no, scene.get("scene_no") or scene["scene_id"])
    )
    _attach_models(service, [provider])

    project = await service.generate_content_batch(
        "workflow-user",
        project["project_id"],
        channels=["小红书图文", "抖音短视频", "无效"],
        total=30,
    )
    assert len(provider.calls) == 10  # 选题矩阵 1 + 小红书图文 5 批 + 抖音 4 批
    batch = project["content_batch"]
    assert batch["channels"] == ["小红书图文", "抖音短视频"]
    assert {row["channel"]: row["quota"] for row in batch["channel_stats"]} == {
        "小红书图文": 15,
        "抖音短视频": 15,
    }
    topics = [topic for group in batch["topic_matrix"] for topic in group["topics"]]
    assert [topic["no"] for topic in topics] == [1, 2, 3, 4]
    assert all(topic["claim_nos"] in ([claim_no], []) for topic in topics)
    assert topics[1]["channel"] == "小红书图文"
    assert len(batch["comment_replies"]) == 5
    roles = [content["batch_role"] for content in project["contents"]]
    assert roles == ["full"] * 4 + ["comment_replies"]
    assert batch["content_count"] == 5
    first = project["contents"][0]
    assert first["channel"] == "小红书图文" and len(first["faq"]) == 3
    assert first["publish_time"]["slot"] == "周三 21:00"
    assert first["claim_nos"] == [claim_no]
    assert "配图建议不足 6 张" in first["quality_issues"]
    douyin = [c for c in project["contents"] if c["channel"] == "抖音短视频"]
    assert any("钩子" in issue for issue in douyin[0]["quality_issues"])
    unverified = [c for c in project["contents"] if c.get("unverified_claim_refs")]
    assert {c["channel"] for c in unverified} == {"小红书图文", "抖音短视频"}
    assert unverified[0]["unverified_claim_refs"] == ["F99"]
    assert unverified[0]["compliance_label"]
    assert any(
        risk["rule_id"] == "rule_claim_alignment_002"
        for risk in project["compliance"]["risks"]
    )
    assert project["compliance"]["status"] == "blocked"
    assert all(content.get("compliance_label") for content in project["contents"])
    assert project["workflow"]["current_step"] == 9

    with pytest.raises(PharmaTranslatorError, match="批注"):
        await service.rework_content_channel(
            "workflow-user",
            project["project_id"],
            channel="抖音短视频",
            reason="unverified_claim",
            comment="",
        )
    with pytest.raises(PharmaTranslatorError, match="返工渠道"):
        await service.rework_content_channel(
            "workflow-user",
            project["project_id"],
            channel="公众号",
            reason="tone_mismatch",
            comment="x",
        )
    provider.output = _content_batch_output(
        claim_no, scene.get("scene_no") or scene["scene_id"], with_unverified=False
    )
    for channel in ("小红书图文", "抖音短视频"):
        project = await service.rework_content_channel(
            "workflow-user",
            project["project_id"],
            channel=channel,
            reason="unverified_claim",
            comment="删除未验证卖点 F99",
        )
    reworks = project["content_batch"]["reworks"]
    assert [(row["channel"], row["replaced"], row["generated"]) for row in reworks] == [
        ("小红书图文", 2, 1),
        ("抖音短视频", 2, 1),
    ]
    assert [c["channel"] for c in project["contents"]] == [
        "小红书图文",
        "抖音短视频",
        "评论区预埋",
    ]
    assert not any(c.get("unverified_claim_refs") for c in project["contents"])
    assert project["compliance"]["status"] != "blocked"

    with pytest.raises(PharmaTranslatorError, match="确认清单"):
        _workflow_action(service, project, "market_confirm", {"checklist": ["tone"]})
    project = _workflow_action(
        service,
        project,
        "market_confirm",
        {"checklist": ["topics", "tone", "labels", "comment_replies", "claims"]},
    )
    assert project["approvals"]["market"]["checklist"] == [
        "topics",
        "tone",
        "labels",
        "comment_replies",
        "claims",
    ]
    project = _workflow_action(
        service, project, "compliance_confirm", _compliance_payload(project)
    )
    assert project["approvals"]["compliance"]["record"]["signer_name"] == "张合规"

    for bad, pattern in (
        (_final_payload(signer_name="李助理代签"), "代签"),
        (_final_payload(signer_title="市场专员"), "品牌总监或业务负责人"),
        (_final_payload(checklist=["completeness"]), "终审确认清单"),
        (_final_payload(publish_authorization={"authorized": False}), "授权发布"),
    ):
        with pytest.raises(PharmaTranslatorError, match=pattern):
            _workflow_action(service, project, "final_approve", bad)
    chain = project["audit_chain"]
    assert [row["step"] for row in chain] == [1, 2, 3, 4, 5, 6, 7]
    assert all(row["status"] == "confirmed" for row in chain[:6])
    assert chain[6]["status"] != "confirmed"

    project = _workflow_action(service, project, "final_approve", _final_payload())
    final = project["approvals"]["final"]["record"]
    assert final["signer_name"] == "王总监"
    assert final["publish_authorization"]["authorized"] is True
    assert all(row["status"] == "confirmed" for row in final["audit_chain"])
    assert project["audit_chain"][6]["status"] == "confirmed"

    _, delivery = service.export_delivery_json("workflow-user", project["project_id"])
    delivery_json = json.loads(delivery)
    package = delivery_json["final_package"]
    assert set(package["contents_by_channel"]) == {
        "小红书图文",
        "抖音短视频",
        "评论区预埋",
    }
    assert len(package["checklist"]) == 5
    assert package["signatures"]["market"] and package["signatures"]["compliance"]
    assert len(package["reworks"]) == 2
    assert len(delivery_json["seven_step_audit_chain"]) == 7
    assert delivery_json["final_authorization"]["signer_name"] == "王总监"

    filename, report = service.export_approval_report_markdown(
        "workflow-user", project["project_id"]
    )
    text = report.decode("utf-8")
    assert filename.endswith("_全流程报告.md")
    for heading in ("7.1 七步确认留痕表", "7.2 导出物清单", "7.3 复用机制", "Step 7"):
        assert heading in text
    for step_no in range(1, 8):
        assert f"## Step {step_no} " in text
    assert "用户上传 / 选择 / 输入" in text and "AI 生成内容" in text

    filename, full = service.export_full_report_json(
        "workflow-user", project["project_id"]
    )
    assert filename.endswith("_全流程报告.json")
    full_json = json.loads(full)
    assert [step["step_no"] for step in full_json["steps"]] == list(range(1, 8))
    assert full_json["steps"][6]["documents"]
    assert all("publish_status" in row for row in full_json["contents"])
    assert len(full_json["audit_chain"]) == 7

    import openpyxl

    filename, workbook = service.export_approval_excel(
        "workflow-user", project["project_id"]
    )
    assert filename.endswith("_审批包.xlsx")
    sheets = openpyxl.load_workbook(io.BytesIO(workbook)).sheetnames
    assert "七步确认留痕表" in sheets and "卖点-文献三联表" in sheets
    assert {"全流程明细", "配图清单", "链接汇总"} <= set(sheets)
    filename, bitable = service.export_feishu_bitable(
        "workflow-user", project["project_id"]
    )
    assert filename.endswith("_多维表格.xlsx")
    book = openpyxl.load_workbook(io.BytesIO(bitable))
    header = [cell.value for cell in book[book.sheetnames[0]][1]]
    assert any("发布状态" in str(value) for value in header)

    reuse = service.sku_reuse_status("workflow-user", project["project_id"])
    assert reuse["available"] is True and reuse["reusable_steps"] == [1, 2, 3, 4]

    content_id = project["contents"][0]["content_id"]
    with pytest.raises(PharmaTranslatorError, match="发布状态无效"):
        service.update_publish_status(
            username="workflow-user",
            project_id=project["project_id"],
            updates=[{"content_id": content_id, "publish_status": "bogus"}],
        )
    project = service.update_publish_status(
        username="workflow-user",
        project_id=project["project_id"],
        updates=[
            {
                "content_id": content_id,
                "publish_status": "published",
                "publish_url": "https://www.xiaohongshu.com/explore/1",
            }
        ],
    )
    published = next(c for c in project["contents"] if c["content_id"] == content_id)
    assert published["publish_status"] == "published" and published["published_at"]

    platform = next(iter(PERFORMANCE_PLATFORMS))
    project = service.record_performance(
        username="workflow-user",
        project_id=project["project_id"],
        platform=platform,
        records=[
            {
                "content_id": content_id,
                "impressions": 1000,
                "likes": 200,
                "collects": 100,
            }
        ],
    )
    assert project["performance"]["records"][0]["is_hit"] is True
    hits = service.list_content_hits("workflow-user")
    assert hits and hits[0]["content_id"] == content_id
    assert (
        service._top_performers(
            "workflow-user",
            service._read_owned_project("workflow-user", project["project_id"]),
        )[0]["title"]
        == published["title"]
    )

    with pytest.raises(PharmaTranslatorError, match="返工原因无效"):
        _workflow_action(
            service, project, "rework", {"target_step": 9, "reason": "x"}, "复盘"
        )
    project = _workflow_action(
        service,
        project,
        "rework",
        {"target_step": 9, "reason": "budget_overrun"},
        "预算超限复盘",
    )
    review = project["final_reviews"][-1]
    assert review["reason_text"] == "预算超限" and review["was_approved"] is True
    assert project["workflow"]["status"] != "approved"


@pytest.mark.asyncio
async def test_content_batch_topics_samples_and_matched_images(
    tmp_path: Path, monkeypatch
):
    service = PharmaTranslatorService(tmp_path)
    project = await _reach_content_step(service, monkeypatch)
    claim_no = project["claims"][0]["claim_no"]
    scene = next(scene for scene in project["scenes"] if scene.get("selected"))
    output = _content_batch_output(claim_no, scene.get("scene_no") or scene["scene_id"])
    output["items"][0]["assets"] = ["图1 下午3点工位犯困", "图2 成分表平铺"]
    provider = _JsonChatProvider(output)
    _attach_models(service, [provider])
    project = await service.generate_content_batch(
        "workflow-user", project["project_id"], channels=["小红书图文"], total=30
    )
    samples = sorted(
        (c for c in project["contents"] if c.get("sample_no")),
        key=lambda c: c["sample_no"],
    )
    assert [c["sample_no"] for c in samples] == [1, 2]
    assert not samples[0].get("unverified_claim_refs")

    with pytest.raises(PharmaTranslatorError, match="至少勾选"):
        service.update_content_topics(
            "workflow-user",
            project["project_id"],
            topics=[{"no": n, "selected": False} for n in range(1, 5)],
        )
    project = service.update_content_topics(
        "workflow-user",
        project["project_id"],
        topics=[
            {"no": 1, "selected": False},
            {"no": 2, "selected": True, "publish_time": "11/12 周四 15:00"},
        ],
    )
    topics = [t for g in project["content_batch"]["topic_matrix"] for t in g["topics"]]
    assert [t["selected"] for t in topics] == [False, True, True, True]
    assert topics[1]["publish_time"] == "11/12 周四 15:00"
    assert project["content_batch"]["selected_topic_count"] == 3

    monkeypatch.setattr(
        service,
        "_web_search_settings",
        lambda: {
            "content_image_base_url": "http://127.0.0.1:11434/v1/",
            "content_image_model": "x/z-image-turbo",
        },
    )
    prompts: list[tuple[str, str]] = []

    async def fake_image(settings, prompt, size):
        assert settings["base_url"] == "http://127.0.0.1:11434/v1"
        assert settings["api_key"] == ""
        prompts.append((prompt, size))
        buffer = io.BytesIO()
        # 每次返回不同画面，避免被配图去重（dHash）判为重复
        seed = len(prompts)
        image = Image.new("L", (9, 8))
        image.putdata(
            [((x * 7 + y * 13) * seed * 37) % 256 for y in range(8) for x in range(9)]
        )
        image.convert("RGB").save(buffer, format="PNG")
        return buffer.getvalue(), "png"

    monkeypatch.setattr(service, "_request_content_image", fake_image)
    target = next(
        c for c in project["contents"] if c["assets"][:1] == ["图1 下午3点工位犯困"]
    )
    project = await service.generate_content_images(
        "workflow-user", project["project_id"], content_id=target["content_id"]
    )
    content = next(
        c for c in project["contents"] if c["content_id"] == target["content_id"]
    )
    assert [image["index"] for image in content["images"]] == [1, 2]
    assert any("下午3点工位犯困" in prompt for prompt, _ in prompts)
    assert content["images"][0]["asset"] == "图1 下午3点工位犯困"
    assert {size for _, size in prompts} == {"1024x1536"}
    path = service.content_image_file(
        "workflow-user", project["project_id"], content["images"][0]["filename"]
    )
    assert path.is_file()
    assert content["images"][0]["size"] == "1080x1440"
    assert content["images"][0]["aspect"] == "3:4"
    assert path.suffix == ".jpg"
    with Image.open(path) as saved:
        assert saved.size == (1080, 1440)
    with pytest.raises(PharmaTranslatorError, match="配图不存在"):
        service.content_image_file(
            "workflow-user", project["project_id"], "../project.json"
        )

    old_name = content["images"][0]["filename"]
    project = await service.generate_content_images(
        "workflow-user",
        project["project_id"],
        content_id=target["content_id"],
        indexes=[1],
    )
    content = next(
        c for c in project["contents"] if c["content_id"] == target["content_id"]
    )
    assert content["images"][0]["filename"] != old_name
    assert (path.parent / old_name).exists()
    stale_name = content["images"][0]["filename"].rsplit("_", 1)[0] + "_deadbeef.jpg"
    fallback = service.content_image_file(
        "workflow-user", project["project_id"], stale_name
    )
    assert fallback.is_file()
    assert fallback.name == content["images"][0]["filename"]
    assert project["workflow"]["current_step"] == 9

    project_dir, project = service._read_owned_project_with_dir(
        "workflow-user", project["project_id"]
    )
    project["compliance"]["status"] = "clear"
    project["compliance"]["risks"] = []
    service._write_project(project_dir, project)

    project = _workflow_action(
        service,
        project,
        "market_confirm",
        {"checklist": ["topics", "tone", "labels", "comment_replies", "claims"]},
    )
    project = _workflow_action(
        service, project, "compliance_confirm", _compliance_payload(project)
    )
    project = _workflow_action(service, project, "final_approve", _final_payload())
    assert project["workflow"]["status"] == "approved"
    approved_name = content["images"][0]["filename"]

    project = await service.generate_content_images(
        "workflow-user",
        project["project_id"],
        content_id=target["content_id"],
        indexes=[1],
    )
    content = next(
        c for c in project["contents"] if c["content_id"] == target["content_id"]
    )
    assert content["images"][0]["filename"] != approved_name
    assert project["workflow"]["status"] == "active"
    assert project["workflow"]["state"] == "COMPLIANCE_CONFIRMATION"
    assert project["workflow"]["step_status"]["9"] == "in_review"
    assert project["status"] == "rework"
    assert all(
        project["approvals"][role] is None for role in ("market", "compliance", "final")
    )
    assert project["final_reviews"][-1]["reason"] == "content_image_regenerated"
    assert project["final_reviews"][-1]["was_approved"] is True

    project = _workflow_action(service, project, "terminate", comment="停止配图修改")
    with pytest.raises(PharmaTranslatorError, match="已终止"):
        await service.generate_content_images(
            "workflow-user",
            project["project_id"],
            content_id=target["content_id"],
            indexes=[1],
        )


def test_content_model_json_repairs_inner_quotes():
    raw = '说明：\n```json\n{"items":[{"title":"下午3点准时"断电"的人","body":"第一行\n第二行"}]}\n```'
    parsed = PharmaTranslatorService._loads_model_json(raw)
    assert parsed["items"][0]["title"] == '下午3点准时"断电"的人'
    assert parsed["items"][0]["body"] == "第一行\n第二行"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # 元素之间漏逗号
        (
            '{"a":[{"x":1}{"x":2}],"b":"y" "c":"z"}',
            {"a": [{"x": 1}, {"x": 2}], "b": "y", "c": "z"},
        ),
        # 正文英文引号后紧跟英文逗号，导致字符串被提前截断
        ('{"t":"他说"好",然后走了","n":1}', {"t": '他说"好",然后走了', "n": 1}),
        # 尾随逗号
        ('{"a":[1,2,],"b":{"c":1,},}', {"a": [1, 2], "b": {"c": 1}}),
        # 输出被截断
        ('{"a":[{"x":"未写', {"a": [{"x": "未写"}]}),
    ],
)
def test_content_model_json_repairs_common_errors(raw, expected):
    assert PharmaTranslatorService._loads_model_json(raw) == expected


@pytest.mark.asyncio
async def test_content_groups_retry_failed_group_once(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    calls = {"n": 0}

    class FlakyProvider:
        async def text_chat(self, **_):
            calls["n"] += 1
            text = "模型开小差了" if calls["n"] == 1 else '{"items":[]}'
            return type("R", (), {"completion_text": text})()

    outcomes = await service._run_content_groups(FlakyProvider(), "p", ["s"])
    assert outcomes == [{"items": []}] and calls["n"] == 2


@pytest.mark.asyncio
async def test_compliance_ai_review_recovers_after_timeout(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    service._generation_providers = lambda: []
    calls = {"n": 0}

    class SlowThenOkProvider:
        async def text_chat(self, **_):
            calls["n"] += 1
            if calls["n"] == 1:
                raise asyncio.TimeoutError()
            text = (
                '```json\n{"findings":[{"content_id":"c1","level":"caution",'
                '"matched_text":"快速见效","message":"疗效承诺",}]}\n```'
            )
            return type("R", (), {"completion_text": text})()

    data = {
        "product_name": "测试药",
        "contents": [
            {"content_id": "c1", "title": "快速见效", "body": "正文"},
            {"content_id": "c2", "title": "标题", "body": "正文"},
        ],
    }
    risks = await service._ai_review_compliance(data, [], [], SlowThenOkProvider())
    assert any(r.get("matched_text") == "快速见效" for r in risks)


@pytest.mark.asyncio
async def test_compliance_ai_review_switches_to_local_backup(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)

    class DeadProvider:
        async def text_chat(self, **_):
            raise asyncio.TimeoutError()

    class LocalProvider:
        provider_config = {"id": "ollama-local"}

        async def text_chat(self, **_):
            text = (
                '{"findings":[{"content_id":"c1","level":"caution",'
                '"matched_text":"快速见效","message":"疗效承诺"}]}'
            )
            return type("R", (), {"completion_text": text})()

    backup = LocalProvider()
    service._generation_providers = lambda: [(backup, "本地模型")]
    data = {
        "product_name": "测试药",
        "contents": [{"content_id": "c1", "title": "快速见效", "body": "正文"}],
    }
    failures: list[str] = []
    risks = await service._ai_review_compliance(
        data, [], [], DeadProvider(), failures=failures
    )
    assert any(r.get("matched_text") == "快速见效" for r in risks)
    assert any("ollama-local" in item for item in failures)


def test_content_image_fit_ratios_and_reply_examples():
    buffer = io.BytesIO()
    Image.new("RGB", (1024, 1536), "white").save(buffer, format="PNG")
    for channel in ("视频号", "公众号"):
        _, aspect, output_size = CONTENT_IMAGE_SIZES[channel]
        payload, extension = PharmaTranslatorService._fit_content_image(
            buffer.getvalue(), output_size
        )
        assert extension == "jpg"
        with Image.open(io.BytesIO(payload)) as fitted:
            assert fitted.size == output_size
        assert aspect in {"6:7", "2.35:1"}
    rules = PharmaTranslatorService._content_reply_rules()
    assert "经期建议先停一停" in rules and "补血益气、健脾和胃" in rules


@pytest.mark.asyncio
async def test_content_batch_blocks_rx_public_channels_without_model(
    tmp_path: Path, monkeypatch
):
    service = PharmaTranslatorService(tmp_path)
    project = await _reach_content_step(
        service, monkeypatch, LEAFLET_TEXT.replace("OTC", "处方药")
    )
    if project["product_type"] != "RX":
        pytest.skip("样例说明书未识别为处方药")
    provider = _JsonChatProvider({})
    _attach_models(service, [provider])
    project = await service.generate_content_batch(
        "workflow-user", project["project_id"], channels=["抖音短视频"]
    )
    assert provider.calls == []
    assert project["contents"] == [] and project["content_batch"] is None
    assert project["workflow"]["step_status"]["9"] == "blocked"


@pytest.mark.asyncio
async def test_workflow_enforces_order_empty_evidence_and_terminal_state(
    tmp_path: Path,
):
    service = PharmaTranslatorService(tmp_path)
    project = await _new_project(service)

    with pytest.raises(PharmaTranslatorError, match="只能在第 4 步"):
        _workflow_action(service, project, "confirm_scenes", {"scenes": []})

    fields = _confirm_all_fields(project)
    fields[0]["value"] = ""
    fields[0]["confirmed"] = True
    with pytest.raises(PharmaTranslatorError, match="缺失、无来源"):
        _workflow_action(service, project, "confirm_profile", {"fields": fields})

    project = _workflow_action(
        service,
        project,
        "terminate",
        comment="资料不完整，终止项目",
    )
    assert project["workflow"]["status"] == "terminated"
    with pytest.raises(PharmaTranslatorError, match="已终止"):
        _workflow_action(
            service,
            project,
            "confirm_profile",
            {"fields": _confirm_all_fields(project)},
        )


DIMENSION_TEXT = "【主要成份】鹿茸、制何首乌，\n\n淫羊藿、干姜。\n【适宜人群】成年气血不足人群。\n【不适宜人群】孕妇、儿童。\n【禁忌】对本品过敏者禁用。"


@pytest.fixture(autouse=True)
def _no_real_dimension_search(monkeypatch):
    """多维生成默认 auto 搜索：测试中禁止真实联网采集。"""
    from astrbot.dashboard.services import pharma_competitor

    monkeypatch.setattr(
        pharma_competitor,
        "capabilities",
        lambda: {"tikhub_configured": False, "opencli_available": False},
    )


class FakeChatProvider:
    def __init__(
        self,
        output=None,
        api_base="https://api.moonshot.cn/v1",
        provider_type="openai_chat_completion",
        provider_id="kimi",
        failure=None,
    ):
        self.provider_config = {
            "id": provider_id,
            "type": provider_type,
            "api_base": api_base,
        }
        self.output = output
        self.failure = failure
        self.calls = []

    async def text_chat(self, **kwargs):
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        evidence = json.loads(kwargs["prompt"])["evidence"]
        result = {
            code: [
                {"text": item["text"], "evidence_ids": [item["evidence_id"]]}
                for item in evidence
                if item["dimension_id"] == code
            ]
            for code in ("ingredients", "audience")
        }
        return SimpleNamespace(
            completion_text=json.dumps(self.output or result, ensure_ascii=False)
        )


def _attach_models(service, providers, current=None):
    service.core_lifecycle = SimpleNamespace(
        provider_manager=SimpleNamespace(
            provider_insts=providers,
            get_using_provider=lambda _kind: (
                current or (providers[0] if providers else None)
            ),
        )
    )


class _JsonChatProvider:
    """直接返回固定 JSON 的最小对话模型（用于文献 AI 分析测试）。"""

    def __init__(self, output):
        self.provider_config = {"id": "kimi", "type": "openai_chat_completion"}
        self.output = output
        self.calls = []

    async def text_chat(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            completion_text=json.dumps(self.output, ensure_ascii=False)
        )


async def _dimension_project(service, text=LEAFLET_TEXT + DIMENSION_TEXT):
    project = await _new_project(service, text)
    return _workflow_action(
        service, project, "confirm_profile", {"fields": _confirm_all_fields(project)}
    )


@pytest.mark.asyncio
async def test_direct_dimensions_keep_multiline_ingredients_and_positive_audience(
    tmp_path,
):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    fields = {field["field_code"]: field for field in project["fields"]}
    assert not fields["ingredients"]["critical"] and not fields["audience"]["critical"]
    dimensions = {item["dimension_id"]: item["items"] for item in project["dimensions"]}
    assert "淫羊藿" in dimensions["ingredients"][0]["text"]
    assert "成年气血不足" in dimensions["audience"][0]["text"]
    assert "孕妇" not in dimensions["audience"][0]["text"]
    assert all(
        item["confirmed"]
        for code in ("ingredients", "audience")
        for item in dimensions[code]
    )
    assert not service._field_value(
        service.extract_fields("不适宜人群：孕妇\n禁忌人群：儿童"), "audience"
    )


@pytest.mark.asyncio
async def test_notes_are_normalized_before_direct_dimension_extraction(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    project = await _new_project(service)
    project = _workflow_action(
        service,
        project,
        "confirm_profile",
        {
            "fields": _confirm_all_fields(project),
            "user_notes": [
                {"title": "厂家补充", "text": DIMENSION_TEXT},
                {"title": "适用人群", "text": "成年人"},
            ],
        },
    )
    dimensions = {item["dimension_id"]: item["items"] for item in project["dimensions"]}
    assert dimensions["ingredients"][0]["source_type"] == "manual_input"
    assert dimensions["ingredients"][0]["source_label"] == "厂家补充"
    assert dimensions["ingredients"][0]["page_no"] is None
    assert any(item["text"] == "成年人" for item in dimensions["audience"])


@pytest.mark.asyncio
async def test_generation_prefers_current_chat_provider_and_preserves_other_dimensions(
    tmp_path,
):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    fallback = FakeChatProvider(
        provider_id="fuse",
        provider_type="anthropic_chat_completion",
        api_base="https://www.fusecode.cc",
    )
    other = FakeChatProvider(
        provider_id="backup", api_base="https://api.example.com/v1"
    )
    selected = FakeChatProvider(
        provider_id="kimi", api_base="https://api.moonshot.cn/v1"
    )
    _attach_models(service, [fallback, other, selected], selected)
    original_other = [
        item
        for item in project["dimensions"]
        if item["dimension_id"] not in {"ingredients", "audience"}
    ]
    generated = await service.generate_dimensions(
        "workflow-user", project["project_id"]
    )
    assert len(selected.calls) == 1 and not fallback.calls and not other.calls
    assert "禁忌" in selected.calls[0]["prompt"]
    system_prompt = selected.calls[0]["system_prompt"]
    assert "不能从禁忌推断" in system_prompt
    assert "禁止联网检索" in system_prompt and "外部药品知识" in system_prompt
    assert "JSON schema" in system_prompt and "evidence_ids" in system_prompt
    assert generated["workflow"]["current_step"] == 2
    assert generated["workflow"]["version"] == project["workflow"]["version"] + 1
    assert generated["audit_events"][-1]["action"] == "generate_dimensions"
    assert "kimi（openai_chat_completion）" in generated["audit_events"][-1]["comment"]
    assert original_other == [
        item
        for item in generated["dimensions"]
        if item["dimension_id"] not in {"ingredients", "audience"}
    ]
    for dimension in generated["dimensions"]:
        if dimension["dimension_id"] in {"ingredients", "audience"}:
            for item in dimension["items"]:
                if item["source_type"] != "model_generated":
                    continue
                assert item["confirmed"]
                assert item["model_provider"] == "kimi（openai_chat_completion）"
                assert (
                    item["evidence_ids"]
                    and item["source_text"] == item["evidence"][0]["source_text"]
                )
                assert item["page_no"] == 1
    with pytest.raises(PharmaTranslatorError, match="无权访问"):
        await service.generate_dimensions("another-user", project["project_id"])


class _ExternalDimensionProvider:
    """按输入证据构造含主治功能/现有渠道/品牌名和产品名的模型输出。"""

    def __init__(self):
        self.provider_config = {"id": "kimi", "type": "openai_chat_completion"}
        self.calls = []

    async def text_chat(self, **kwargs):
        self.calls.append(kwargs)
        payload = json.loads(kwargs["prompt"])
        evidence = payload["evidence"]
        ref = {item["dimension_id"]: item["evidence_id"] for item in evidence}
        kb, web = ref["knowledge_base"], ref["web_search"]
        result = {
            "ingredients": [
                {"text": item["text"], "evidence_ids": [item["evidence_id"]]}
                for item in evidence
                if item["dimension_id"] == "ingredients"
            ],
            "audience": [],
            "efficacy": [
                {"text": "用于失眠、健忘", "evidence_ids": [kb]},
                {"text": "根治失眠", "evidence_ids": [kb]},
            ],
            "channels": [
                {"text": "连锁药店", "evidence_ids": [kb]},
                {"text": "京东大药房", "evidence_ids": [web]},
                {"text": "医院处方渠道", "evidence_ids": [web]},
            ],
            "brand_product": [
                {"text": "安神补脑液", "evidence_ids": [web]},
                {"text": "鹿茸", "evidence_ids": [kb]},
            ],
        }
        return SimpleNamespace(completion_text=json.dumps(result, ensure_ascii=False))


@pytest.mark.asyncio
async def test_dimension_generation_uses_drug_name_kb_and_search(tmp_path, monkeypatch):
    from astrbot.dashboard.services import pharma_competitor

    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    provider = _ExternalDimensionProvider()
    _attach_models(service, [provider])
    kb_calls, search_calls = [], []

    async def fake_kb(claims, *, kb_ids, kb_names, product_name):
        kb_calls.append((kb_ids, product_name))
        return (
            [
                {
                    "text": "安神补脑液功能主治：用于失眠、健忘。主要在连锁药店销售。",
                    "source_label": "知识库·药企资料/产品手册",
                }
            ],
            "",
        )

    async def fake_opencli(platforms, keywords, *, per_keyword):
        search_calls.append((platforms, keywords))
        return (
            [
                {
                    "platform": "ecommerce",
                    "title": "安神补脑液 京东大药房",
                    "text": "安神补脑液在京东大药房有售",
                    "url": "https://example.com/item",
                }
            ],
            [],
        )

    monkeypatch.setattr(service, "_retrieve_kb_corpus", fake_kb)
    monkeypatch.setattr(
        pharma_competitor,
        "capabilities",
        lambda: {"tikhub_configured": False, "opencli_available": True},
    )
    monkeypatch.setattr(pharma_competitor, "collect_opencli", fake_opencli)

    generated = await service.generate_dimensions(
        "workflow-user", project["project_id"], kb_ids=["kb1"]
    )
    assert kb_calls == [(["kb1"], "安神补脑液")]
    assert search_calls and search_calls[0][1] == ["安神补脑液"]
    assert json.loads(provider.calls[0]["prompt"])["drug_name"] == "安神补脑液"
    dimensions = {item["dimension_id"]: item for item in generated["dimensions"]}
    assert dimensions["efficacy"]["label"] == "主治功能"
    assert dimensions["audience"]["label"] == "对症人群"

    def model_texts(code):
        return [
            item["text"]
            for item in dimensions[code]["items"]
            if item["source_type"] == "model_generated"
        ]

    assert model_texts("efficacy") == ["用于失眠、健忘"]
    # 渠道归入五类标准渠道：医院/药店/诊所/药品零售商/药品批发商
    assert model_texts("channels") == ["药店", "药品零售商"]
    # 药品名称已由上传资料预填并确认，模型同名条目被去重
    assert model_texts("brand_product") == []
    assert any(
        item["text"] == "安神补脑液" for item in dimensions["brand_product"]["items"]
    )
    channel = next(
        item for item in dimensions["channels"]["items"] if item["text"] == "药品零售商"
    )
    assert (
        channel["is_external"] and channel["source_url"] == "https://example.com/item"
    )
    assert "待人工确认" in channel["derivation"]
    assert channel["source_label"].startswith("搜索内容")
    meta = generated["dimension_generation"]
    assert meta["kb_hits"] == 1 and meta["search_hits"] == 1
    assert meta["dropped"] == 3
    assert "本地药企知识库" in generated["audit_events"][-1]["comment"]


@pytest.mark.asyncio
async def test_dimension_generation_degrades_without_kb_or_search(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    _attach_models(service, [FakeChatProvider()])
    generated = await service.generate_dimensions(
        "workflow-user", project["project_id"]
    )
    warnings = generated["dimension_generation"]["warnings"]
    assert any("未选择本地药企知识库" in item for item in warnings)
    assert any("未配置搜索采集" in item for item in warnings)
    with pytest.raises(PharmaTranslatorError, match="搜索方式无效"):
        await service.generate_dimensions(
            "workflow-user", project["project_id"], search_mode="bad"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_id,provider_type,api_base",
    [
        ("kimi", "openai_chat_completion", "https://api.moonshot.cn/v1"),
        ("fuse", "anthropic_chat_completion", "https://www.fusecode.cc"),
    ],
)
async def test_enabled_cloud_providers_are_used_for_generation(
    tmp_path, provider_id, provider_type, api_base
):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    provider = FakeChatProvider(
        provider_id=provider_id, provider_type=provider_type, api_base=api_base
    )
    _attach_models(service, [provider])
    generated = await service.generate_dimensions(
        "workflow-user", project["project_id"]
    )
    assert len(provider.calls) == 1
    label = f"{provider_id}（{provider_type}）"
    assert label in generated["audit_events"][-1]["comment"]
    for dimension in generated["dimensions"]:
        if dimension["dimension_id"] in {"ingredients", "audience"}:
            assert dimension["items"]
            assert all(
                item["model_provider"] == label
                for item in dimension["items"]
                if item["source_type"] == "model_generated"
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("attach", ["empty", "no_manager"])
async def test_missing_generation_provider_is_visible_error_without_writes(
    tmp_path, attach
):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    providers = []
    if attach == "empty":
        _attach_models(service, providers)
    else:
        service.core_lifecycle = SimpleNamespace(provider_manager=None)
    with pytest.raises(
        PharmaTranslatorError,
        match="未配置可用的生成模型，请在模型提供商启用当前对话模型或支持的OpenAI兼容provider",
    ):
        await service.generate_dimensions("workflow-user", project["project_id"])
    assert service.get_project("workflow-user", project["project_id"]) == project
    assert all(not provider.calls for provider in providers)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "output",
    [
        {
            "ingredients": [{"text": "鹿茸", "evidence_ids": ["unknown"]}],
            "audience": [],
        },
        {"ingredients": [{"text": "鹿茸", "evidence_ids": []}], "audience": []},
        {"ingredients": [], "audience": [{"text": "儿童", "evidence_ids": ["e1"]}]},
        {"ingredients": [], "audience": [{"text": "孕妇禁用", "evidence_ids": ["e2"]}]},
        {"ingredients": [], "audience": []},
    ],
)
async def test_invalid_model_citations_leave_dimensions_untouched(tmp_path, output):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    _attach_models(service, [FakeChatProvider(output=output)])
    with pytest.raises(PharmaTranslatorError, match="来源引用无效"):
        await service.generate_dimensions("workflow-user", project["project_id"])
    assert service.get_project("workflow-user", project["project_id"]) == project


@pytest.mark.asyncio
async def test_model_audience_heading_junk_is_rejected_without_writes(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    evidence = service._dimension_evidence(project, full_context=True)
    audience_ref = next(
        source["evidence_id"]
        for source in evidence
        if source["dimension_id"] == "audience"
    )
    _attach_models(
        service,
        [
            FakeChatProvider(
                output={
                    "ingredients": [],
                    "audience": [{"text": "解决方案", "evidence_ids": [audience_ref]}],
                }
            )
        ],
    )
    with pytest.raises(PharmaTranslatorError, match="来源引用无效"):
        await service.generate_dimensions("workflow-user", project["project_id"])
    assert service.get_project("workflow-user", project["project_id"]) == project


def test_audience_heading_junk_is_not_extracted_as_audience(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    text = "【药品名称】安神补脑液\n【适用人群】解决方案\n【功能主治】用于头痛。\n【用法用量】一次一袋。"
    fields = {field["field_code"]: field for field in service.extract_fields(text)}
    assert fields["audience"]["value"] == ""
    assert fields["indications"]["value"] == "用于头痛。"
    evidence = service._dimension_evidence({"pages": service._pages_from_text(text)})
    assert not [item for item in evidence if item["dimension_id"] == "audience"]
    good = {
        field["field_code"]: field
        for field in service.extract_fields("【适宜人群】成年气血不足人群。")
    }
    assert "成年气血不足" in good["audience"]["value"]


@pytest.mark.asyncio
async def test_regeneration_removes_sourceless_junk_but_keeps_confirmed_items(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    project_dir, data = service._read_owned_project_with_dir(
        "workflow-user", project["project_id"]
    )
    audience = next(
        item for item in data["dimensions"] if item["dimension_id"] == "audience"
    )
    valid_unconfirmed = dict(audience["items"][0])
    junk = {
        "item_id": "dimension-audience-legacy-junk",
        "label": "适用人群",
        "text": "解决方案",
        "source_text": "",
        "confirmed": False,
    }
    confirmed = dict(
        valid_unconfirmed,
        item_id="dimension-audience-confirmed",
        text="成年人",
        confirmed=True,
    )
    audience["items"] = [junk, valid_unconfirmed, confirmed]
    service._write_project(project_dir, data)
    evidence = service._dimension_evidence(data, full_context=True)
    ingredients_ref = next(
        source["evidence_id"]
        for source in evidence
        if source["dimension_id"] == "ingredients"
    )
    _attach_models(
        service,
        [
            FakeChatProvider(
                output={
                    "ingredients": [
                        {"text": "鹿茸", "evidence_ids": [ingredients_ref]}
                    ],
                    "audience": [],
                }
            )
        ],
    )
    generated = await service.generate_dimensions(
        "workflow-user", project["project_id"]
    )
    items = next(
        dimension["items"]
        for dimension in generated["dimensions"]
        if dimension["dimension_id"] == "audience"
    )
    texts = [item["text"] for item in items]
    assert "解决方案" not in texts
    assert valid_unconfirmed["text"] in texts
    assert next(item for item in items if item["text"] == "成年人")["confirmed"] is True


@pytest.mark.asyncio
async def test_model_failure_is_safe_visible_and_does_not_write(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    _attach_models(service, [FakeChatProvider(failure=RuntimeError("secret-token"))])
    with pytest.raises(PharmaTranslatorError, match="模型服务错误") as error:
        await service.generate_dimensions("workflow-user", project["project_id"])
    assert "secret-token" not in str(error.value)
    assert service.get_project("workflow-user", project["project_id"]) == project


@pytest.mark.asyncio
async def test_generation_checks_workflow_before_call_and_after_model_wait(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    project = await _new_project(service)
    provider = FakeChatProvider()
    _attach_models(service, [provider])
    with pytest.raises(PharmaTranslatorError, match="只能在第 2 步"):
        await service.generate_dimensions("workflow-user", project["project_id"])
    project = _workflow_action(
        service,
        project,
        "confirm_profile",
        {
            "fields": _confirm_all_fields(project),
            "user_notes": [{"text": DIMENSION_TEXT}],
        },
    )
    original_chat = provider.text_chat

    async def terminate_during_generation(**kwargs):
        result = await original_chat(**kwargs)
        _workflow_action(service, project, "terminate", comment="停止")
        return result

    provider.text_chat = terminate_during_generation
    with pytest.raises(PharmaTranslatorError, match="已终止"):
        await service.generate_dimensions("workflow-user", project["project_id"])
    assert (
        service.get_project("workflow-user", project["project_id"])["workflow"][
            "status"
        ]
        == "terminated"
    )


@pytest.mark.asyncio
async def test_approved_and_later_steps_reject_dimension_generation(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    _attach_models(service, [FakeChatProvider()])
    for status, step, message in [
        ("approved", 2, "已终审"),
        ("active", 3, "只能在第 2 步"),
    ]:
        project_dir, data = service._read_owned_project_with_dir(
            "workflow-user", project["project_id"]
        )
        data["workflow"].update(status=status, current_step=step)
        service._write_project(project_dir, data)
        with pytest.raises(PharmaTranslatorError, match=message):
            await service.generate_dimensions("workflow-user", project["project_id"])


@pytest.mark.asyncio
async def test_long_notes_and_cross_page_ingredients_are_not_truncated(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    long_ingredients = "鹿茸、" * 900 + "干姜。"
    project = await _new_project(service)
    project = _workflow_action(
        service,
        project,
        "confirm_profile",
        {
            "fields": _confirm_all_fields(project),
            "user_notes": [{"title": "成分", "text": long_ingredients}],
        },
    )
    ingredients = next(
        item for item in project["dimensions"] if item["dimension_id"] == "ingredients"
    )
    assert ingredients["items"][0]["text"] == long_ingredients
    assert project["user_notes"][0]["text"] == long_ingredients
    with pytest.raises(PharmaTranslatorError, match="不会截断"):
        service._normalize_user_notes([{"text": "药" * 30001}], "workflow-user")
    pages = service._pages_from_text("【成分】鹿茸、\f干姜。\n【适用人群】成年人。")
    evidence = service._dimension_evidence({"pages": pages})
    assert "干姜" in evidence[0]["text"] and evidence[0]["page_no"] == 1
    assert evidence[1]["page_no"] == 2
    repeated = service._dimension_evidence(
        {
            "pages": service._pages_from_text(
                "成分：鹿茸。\n【成分】干姜。\n【适用人群】成年人。"
            )
        }
    )
    assert [
        item["text"] for item in repeated if item["dimension_id"] == "ingredients"
    ] == ["鹿茸。", "干姜。"]


@pytest.mark.asyncio
async def test_generation_with_no_evidence_or_version_conflict_does_not_write(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service, LEAFLET_TEXT)
    provider = FakeChatProvider()
    _attach_models(service, [provider])
    project_dir, empty = service._read_owned_project_with_dir(
        "workflow-user", project["project_id"]
    )
    empty["pages"] = []
    empty["fields"] = []
    service._write_project(project_dir, empty)
    with pytest.raises(PharmaTranslatorError, match="没有可检索"):
        await service.generate_dimensions("workflow-user", project["project_id"])
    assert not provider.calls
    project = await _dimension_project(service)
    original_chat = provider.text_chat

    async def change_during_generation(**kwargs):
        result = await original_chat(**kwargs)
        project_dir, data = service._read_owned_project_with_dir(
            "workflow-user", project["project_id"]
        )
        data["workflow"]["version"] += 1
        service._write_project(project_dir, data)
        return result

    provider.text_chat = change_during_generation
    with pytest.raises(PharmaTranslatorError, match="生成期间项目已变更"):
        await service.generate_dimensions("workflow-user", project["project_id"])
    assert (
        service.get_project("workflow-user", project["project_id"])["dimensions"]
        == project["dimensions"]
    )


@pytest.mark.asyncio
async def test_old_project_fulltext_generation_and_derived_audience(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    text = (
        LEAFLET_TEXT
        + "\n【成 份】麻黄、\n桂枝。\n【功能主治】用于风寒感冒，头痛、鼻塞。"
    )
    project = await _dimension_project(service, text)
    project_dir, data = service._read_owned_project_with_dir(
        "workflow-user", project["project_id"]
    )
    data["fields"] = [
        field
        for field in data["fields"]
        if field["field_code"] not in {"ingredients", "audience"}
    ]
    data["dimensions"] = [
        dict(dimension, items=[])
        if dimension["dimension_id"] in {"ingredients", "audience"}
        else dimension
        for dimension in data["dimensions"]
    ]
    service._write_project(project_dir, data)
    provider = FakeChatProvider()

    async def from_fulltext(**kwargs):
        provider.calls.append(kwargs)
        evidence = json.loads(kwargs["prompt"])["evidence"]
        fulltext = next(
            source
            for source in evidence
            if source["dimension_id"] == "uploaded_fulltext"
        )
        assert "【成 份】麻黄" in fulltext["text"]
        assert fulltext["page_no"] == 1
        return SimpleNamespace(
            completion_text=json.dumps(
                {
                    "ingredients": [
                        {
                            "text": "麻黄、桂枝。",
                            "evidence_ids": [fulltext["evidence_id"]],
                            "source_text": "伪造原文",
                        }
                    ],
                    "audience": [
                        {
                            "text": "有风寒感冒相关症状者",
                            "evidence_ids": [fulltext["evidence_id"]],
                            "is_inferred": False,
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )

    provider.text_chat = from_fulltext
    _attach_models(service, [provider])
    generated = await service.generate_dimensions(
        "workflow-user", project["project_id"]
    )
    dimensions = {
        dimension["dimension_id"]: dimension["items"]
        for dimension in generated["dimensions"]
    }
    assert dimensions["ingredients"][0]["source_text"] == text.strip()
    audience = dimensions["audience"][0]
    assert audience["is_inferred"] is True
    assert audience["derivation"] == "依据功能主治整理，待人工确认"
    assert audience["confirmed"]
    assert "伪造原文" not in dimensions["ingredients"][0]["source_text"]


@pytest.mark.asyncio
async def test_empty_model_dimension_and_confirmed_items_are_preserved(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    project_dir, data = service._read_owned_project_with_dir(
        "workflow-user", project["project_id"]
    )
    ingredients = next(
        dimension
        for dimension in data["dimensions"]
        if dimension["dimension_id"] == "ingredients"
    )
    ingredients["items"][0]["confirmed"] = True
    confirmed = ingredients["items"][0].copy()
    service._write_project(project_dir, data)
    evidence = service._dimension_evidence(data, full_context=True)
    ref = next(
        source["evidence_id"]
        for source in evidence
        if source["dimension_id"] == "ingredients"
    )
    _attach_models(
        service,
        [
            FakeChatProvider(
                output={
                    "ingredients": [{"text": "鹿茸", "evidence_ids": [ref]}],
                    "audience": [],
                }
            )
        ],
    )
    generated = await service.generate_dimensions(
        "workflow-user", project["project_id"]
    )
    dimensions = {
        dimension["dimension_id"]: dimension["items"]
        for dimension in generated["dimensions"]
    }
    assert confirmed in dimensions["ingredients"]
    assert dimensions["audience"] == next(
        dimension["items"]
        for dimension in data["dimensions"]
        if dimension["dimension_id"] == "audience"
    )
    audience_ref = next(
        source["evidence_id"]
        for source in evidence
        if source["dimension_id"] == "audience"
    )
    before_ingredients = dimensions["ingredients"]
    _attach_models(
        service,
        [
            FakeChatProvider(
                output={
                    "ingredients": [],
                    "audience": [
                        {"text": "成年气血不足人群。", "evidence_ids": [audience_ref]}
                    ],
                }
            )
        ],
    )
    regenerated = await service.generate_dimensions(
        "workflow-user", project["project_id"]
    )
    assert (
        next(
            dimension["items"]
            for dimension in regenerated["dimensions"]
            if dimension["dimension_id"] == "ingredients"
        )
        == before_ingredients
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code,text,source_kind",
    [
        ("ingredients", "鹿茸", "indications"),
        ("ingredients", "不存在的药材", "uploaded_fulltext"),
        ("audience", "风寒感冒儿童安全适用", "indications"),
        ("audience", "过敏者适用", "uploaded_fulltext"),
        ("audience", "糖尿病患者", "indications"),
    ],
)
async def test_fulltext_and_field_citations_reject_unsupported_candidates(
    tmp_path, code, text, source_kind
):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    evidence = service._dimension_evidence(project, full_context=True)
    ref = next(
        source["evidence_id"]
        for source in evidence
        if source["dimension_id"] == source_kind
    )
    output = {"ingredients": [], "audience": []}
    output[code] = [{"text": text, "evidence_ids": [ref]}]
    _attach_models(service, [FakeChatProvider(output=output)])
    with pytest.raises(PharmaTranslatorError, match="来源引用无效"):
        await service.generate_dimensions("workflow-user", project["project_id"])
    assert service.get_project("workflow-user", project["project_id"]) == project


@pytest.mark.asyncio
async def test_indications_evidence_is_derived_without_audience_heading(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service, LEAFLET_TEXT)
    ref = next(
        source["evidence_id"]
        for source in service._dimension_evidence(project, full_context=True)
        if source["dimension_id"] == "indications"
    )
    _attach_models(
        service,
        [
            FakeChatProvider(
                output={
                    "ingredients": [],
                    "audience": [
                        {"text": "有头晕、乏力、失眠症状者", "evidence_ids": [ref]}
                    ],
                }
            )
        ],
    )
    generated = await service.generate_dimensions(
        "workflow-user", project["project_id"]
    )
    audience = next(
        dimension
        for dimension in generated["dimensions"]
        if dimension["dimension_id"] == "audience"
    )["items"][0]
    assert (
        audience["is_inferred"]
        and audience["derivation"] == "依据功能主治整理，待人工确认"
    )


def test_spaced_and_crossline_ingredient_heading_does_not_consume_other_fields(
    tmp_path,
):
    service = PharmaTranslatorService(tmp_path)
    fields = {
        field["field_code"]: field
        for field in service.extract_fields(
            "【成\n份】麻黄、\n\n桂枝。\n【功能主治】用于风寒感冒。\n【用法用量】一次一袋。"
        )
    }
    assert fields["ingredients"]["value"] == "麻黄、\n\n桂枝。"
    assert fields["indications"]["value"] == "用于风寒感冒。"
    assert fields["dosage"]["value"] == "一次一袋。"


@pytest.mark.asyncio
async def test_full_context_limit_rejects_without_truncating_or_model_call(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    project = await _dimension_project(service)
    project_dir, data = service._read_owned_project_with_dir(
        "workflow-user", project["project_id"]
    )
    data["pages"] = service._pages_from_text("【成 份】" + "鹿茸、" * 10001 + "桂枝。")
    service._write_project(project_dir, data)
    provider = FakeChatProvider()
    _attach_models(service, [provider])
    with pytest.raises(PharmaTranslatorError, match="不会截断成分"):
        await service.generate_dimensions("workflow-user", project["project_id"])
    assert not provider.calls
    assert service._read_owned_project("workflow-user", project["project_id"]) == data


@pytest.mark.asyncio
async def test_rx_public_content_is_persisted_as_compliance_block(
    tmp_path: Path, monkeypatch
):
    service = PharmaTranslatorService(tmp_path)
    rx_text = LEAFLET_TEXT.replace("OTC", "处方药")
    project = await _new_project(service, rx_text)
    project = _workflow_action(
        service,
        project,
        "confirm_profile",
        {"fields": _confirm_all_fields(project)},
    )
    dimensions, constraints = _confirm_dimensions(project)
    project = _workflow_action(
        service,
        project,
        "confirm_dimensions",
        {"dimensions": dimensions, "safety_constraints": constraints},
    )
    project = await _pass_literature(service, project)
    project = _workflow_action(
        service,
        project,
        "confirm_scenes",
        {"scenes": project["scenes"]},
    )
    project = await _pass_competitor(service, project, monkeypatch)
    project = await _pass_compliance_filter(service, project)

    project = _workflow_action(
        service,
        project,
        "generate_contents",
        {"platforms": ["小红书"]},
    )
    assert project["contents"] == []
    assert project["compliance"]["status"] == "blocked"
    assert project["compliance"]["risks"][0]["rule_id"] == "rule_rx_public_001"
    with pytest.raises(PharmaTranslatorError, match="先生成内容"):
        _workflow_action(service, project, "market_confirm")


def test_manual_review_source_and_ocr_polygon_are_preserved(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    manual_fields = service.extract_fields(
        LEAFLET_TEXT,
        pages=service._pages_from_text(LEAFLET_TEXT),
        source_mode="manual_review",
    )
    assert all(
        field["source_type"] == "manual_review"
        for field in manual_fields
        if field["value"]
    )

    text = "【规格】每支装10毫升"
    fields = service.extract_fields(
        text,
        pages=[
            {
                "page_no": 1,
                "text": text,
                "confidence": 0.91,
                "start_offset": 0,
                "end_offset": len(text),
                "blocks": [
                    {
                        "text": "每支装10毫升",
                        "confidence": 0.96,
                        "polygon": [[1, 2], [10, 2], [10, 8], [1, 8]],
                    }
                ],
            }
        ],
    )
    specification = next(
        field for field in fields if field["field_code"] == "specification"
    )
    assert specification["polygon"] == [[1, 2], [10, 2], [10, 8], [1, 8]]
    assert specification["confidence"] > 0.9


def test_workflow_action_request_accepts_data_and_legacy_payload():
    request = WorkflowActionRequest.model_validate(
        {"action": "confirm_profile", "data": {"fields": []}}
    )
    assert request.data == {"fields": []}
    legacy = WorkflowActionRequest.model_validate(
        {"action": "confirm_profile", "payload": {"fields": []}}
    )
    assert legacy.payload == {"fields": []}


@pytest.mark.asyncio
async def test_invalid_numeric_workflow_payloads_return_business_errors(
    tmp_path: Path, monkeypatch
):
    service = PharmaTranslatorService(tmp_path)
    project = await _new_project(service)

    with pytest.raises(PharmaTranslatorError, match="返工目标步骤必须为整数"):
        _workflow_action(
            service,
            project,
            "rework",
            {"target_step": "not-a-number"},
            "退回重做",
        )

    project = _workflow_action(
        service,
        project,
        "confirm_profile",
        {"fields": _confirm_all_fields(project)},
    )
    dimensions, constraints = _confirm_dimensions(project)
    project = _workflow_action(
        service,
        project,
        "confirm_dimensions",
        {"dimensions": dimensions, "safety_constraints": constraints},
    )
    project = await _pass_literature(service, project)
    project = _workflow_action(
        service,
        project,
        "confirm_scenes",
        {"scenes": project["scenes"]},
    )
    project = await _pass_competitor(service, project, monkeypatch)
    project = await _pass_compliance_filter(service, project)
    with pytest.raises(PharmaTranslatorError, match="内容数量必须为整数"):
        _workflow_action(
            service,
            project,
            "generate_contents",
            {"platforms": ["公众号"], "count": {"invalid": True}},
        )


@pytest.mark.asyncio
async def test_project_summary_exposes_workflow_progress(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _new_project(service)
    project = _workflow_action(
        service,
        project,
        "confirm_profile",
        {"fields": _confirm_all_fields(project)},
    )

    summary = service.list_projects("workflow-user")[0]
    assert summary["project_id"] == project["project_id"]
    assert summary["workflow_step"] == 2
    assert summary["workflow_status"] == "active"


@pytest.mark.asyncio
async def test_confirm_profile_allows_empty_approval_fields(tmp_path: Path):
    """批文字段未识别时允许留空跳过。"""
    text_without_approval = """
【药品名称】安神补脑液
【功能主治】生精补髓，益气养血，强脑安神。
【规格】每支装10毫升
【用法用量】口服。一次10毫升，一日2次。
【不良反应】尚不明确。
"""
    service = PharmaTranslatorService(tmp_path)
    project = await _new_project(service, text_without_approval)
    fields = _confirm_all_fields(project)
    for field in fields:
        if field["field_code"] in {"approval_number", "approval_type"}:
            field["value"] = ""
            field["source_text"] = ""
            field["confirmed"] = False
        elif field["field_code"] == "product_type" and not field["value"].strip():
            field["value"] = "保健食品"
            field["source_type"] = "manual_input"
            field["confirmed"] = True

    project = _workflow_action(service, project, "confirm_profile", {"fields": fields})
    assert project["workflow"]["current_step"] == 2


@pytest.mark.asyncio
async def test_confirm_profile_accepts_manual_input_without_source(tmp_path: Path):
    """用户手动补充批文字段时，仅需 confirmed 不要求原文证据。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _new_project(service, LEAFLET_TEXT.replace("国药准字Z22000001", ""))
    fields = _confirm_all_fields(project)
    for field in fields:
        if field["field_code"] == "approval_number":
            field["value"] = "国药准字Z99999999"
            field["source_text"] = ""
            field["source_type"] = "manual_input"
            field["confirmed"] = True

    project = _workflow_action(service, project, "confirm_profile", {"fields": fields})
    assert project["workflow"]["current_step"] == 2
    approval = next(
        item for item in project["fields"] if item["field_code"] == "approval_number"
    )
    assert approval["value"] == "国药准字Z99999999"
    assert approval["source_type"] == "manual_input"


@pytest.mark.asyncio
async def test_confirm_profile_persists_user_notes(tmp_path: Path):
    """确认档案时提交的 user_notes 应被持久化。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _new_project(service)
    fields = _confirm_all_fields(project)
    project = _workflow_action(
        service,
        project,
        "confirm_profile",
        {
            "fields": fields,
            "user_notes": [
                {"title": "厂家补充", "text": "该药品近期更换了外包装。"},
                {"text": ""},
            ],
        },
    )
    assert len(project["user_notes"]) == 1
    note = project["user_notes"][0]
    assert note["title"] == "厂家补充"
    assert note["text"].startswith("该药品近期")
    assert note["created_by"] == "workflow-user"


@pytest.mark.asyncio
async def test_confirm_profile_still_blocks_other_critical_missing(tmp_path: Path):
    """非批文的关键字段缺失仍然阻断，防止误放行。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _new_project(service)
    fields = _confirm_all_fields(project)
    for field in fields:
        if field["field_code"] == "drug_name":
            field["value"] = ""
            field["source_text"] = ""
            field["confirmed"] = False
    with pytest.raises(PharmaTranslatorError, match="缺失、无来源"):
        _workflow_action(service, project, "confirm_profile", {"fields": fields})


# ---- 第 3 步：企业商品文献验证 ----


async def _literature_ready_project(
    service: PharmaTranslatorService, text: str = LEAFLET_TEXT
) -> dict:
    """推进到第 3 步（文献验证）的项目。"""
    project = await _new_project(service, text)
    project = _workflow_action(
        service, project, "confirm_profile", {"fields": _confirm_all_fields(project)}
    )
    dimensions, constraints = _confirm_dimensions(project)
    return _workflow_action(
        service,
        project,
        "confirm_dimensions",
        {"dimensions": dimensions, "safety_constraints": constraints},
    )


def _pdf_bytes(text: str) -> bytes:
    """生成带文本层的单页 PDF（UniGB-UCS2-H 编码，供 extract_text 还原中文）。"""
    from pypdf import PdfWriter
    from pypdf.generic import (
        ArrayObject,
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
        NumberObject,
        TextStringObject,
    )

    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    hex_text = text.encode("utf-16-be").hex().upper()
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 50 800 Td <{hex_text}> Tj ET".encode("ascii"))
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type0"),
            NameObject("/BaseFont"): NameObject("/STSong-Light"),
            NameObject("/Encoding"): NameObject("/UniGB-UCS2-H"),
            NameObject("/DescendantFonts"): ArrayObject(
                [
                    DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/CIDFontType0"),
                            NameObject("/BaseFont"): NameObject("/STSong-Light"),
                            NameObject("/CIDSystemInfo"): DictionaryObject(
                                {
                                    NameObject("/Registry"): TextStringObject("Adobe"),
                                    NameObject("/Ordering"): TextStringObject("GB1"),
                                    NameObject("/Supplement"): NumberObject(5),
                                }
                            ),
                        }
                    )
                ]
            ),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    page[NameObject("/Contents")] = stream
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _docx_bytes(text: str) -> bytes:
    """生成最小 DOCX（仅测试用）。"""
    import zipfile
    from xml.sax.saxutils import escape

    paragraphs = "".join(
        f"<w:p><w:r><w:t>{escape(line)}</w:t></w:r></w:p>"
        for line in text.split("\n")
        if line.strip()
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraphs}</w:body></w:document>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document)
    return output.getvalue()


@pytest.mark.asyncio
async def test_literature_claims_extracted_from_confirmed_dimensions(tmp_path: Path):
    """第一层：卖点清单按成分/功效/人群/背书从已确认多维卡片抽取并编号。"""
    service = PharmaTranslatorService(tmp_path)
    text = LEAFLET_TEXT + "\n【主要成份】鹿茸、干姜。\n【适宜人群】成年气血不足人群。"
    project = await _literature_ready_project(service, text)

    claims = project["literature_claims"]
    assert project["workflow"]["current_step"] == 3
    assert project["scenes"] == []
    by_type: dict[str, list[dict]] = {}
    for claim in claims:
        by_type.setdefault(claim["claim_type"], []).append(claim)
    assert {item["text"] for item in by_type["ingredients"]} == {"鹿茸", "干姜"}
    assert any(item["text"].startswith("生精补髓") for item in by_type["efficacy"])
    assert by_type["audience"][0]["text"] == "成年气血不足人群"
    assert any("国药准字" in item["text"] for item in by_type["endorsement"])
    assert [claim["claim_no"] for claim in claims] == [
        f"F{index:02d}" for index in range(1, len(claims) + 1)
    ]
    assert all(claim["match_status"] == "pending" for claim in claims)
    assert all(claim["triple_card"]["compliant_copy"] for claim in claims)
    assert all(claim["triple_card"]["disclaimer"] for claim in claims)


@pytest.mark.asyncio
async def test_literature_upload_pdf_docx_and_validation(tmp_path: Path):
    """文献上传：PDF/DOCX 提取切片，格式与步骤门禁校验。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _new_project(service)

    with pytest.raises(PharmaTranslatorError, match="只能在第 3 步"):
        await service.add_literature(
            username="workflow-user",
            project_id=project["project_id"],
            files=[("a.pdf", _pdf_bytes("任意内容"))],
            doc_kind="clinical",
        )

    project = await _literature_ready_project(service)
    with pytest.raises(PharmaTranslatorError, match="仅支持 PDF 和 DOCX"):
        await service.add_literature(
            username="workflow-user",
            project_id=project["project_id"],
            files=[("a.png", b"\x89PNG\r\n\x1a\nxxxx")],
            doc_kind="clinical",
        )
    with pytest.raises(PharmaTranslatorError, match="文献类型无效"):
        await service.add_literature(
            username="workflow-user",
            project_id=project["project_id"],
            files=[("a.pdf", _pdf_bytes("任意内容"))],
            doc_kind="unknown",
        )

    project = await service.add_literature(
        username="workflow-user",
        project_id=project["project_id"],
        files=[
            ("临床研究报告.pdf", _pdf_bytes("安神补脑液用于头晕乏力的随机对照试验。")),
            ("药典标准.docx", _docx_bytes("鹿茸\n补肾壮阳，益精血。")),
        ],
        doc_kind="clinical",
    )
    documents = project["literature"]["documents"]
    assert len(documents) == 2
    assert documents[0]["doc_kind"] == "clinical"
    assert documents[0]["chunk_count"] >= 1
    assert all("stored_filename" not in doc for doc in documents)
    assert project["literature"]["matched_at"] is None

    project = service.remove_literature(
        username="workflow-user",
        project_id=project["project_id"],
        doc_id=documents[1]["doc_id"],
    )
    assert len(project["literature"]["documents"]) == 1


@pytest.mark.asyncio
async def test_literature_match_three_color_labels(tmp_path: Path):
    """第二层：优先文献源命中评强证据，说明书人工校对最高弱证据，无引用为无证据。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _literature_ready_project(service)

    project = await service.run_literature_match(
        username="workflow-user", project_id=project["project_id"]
    )
    claims = {claim["claim_no"]: claim for claim in project["literature_claims"]}
    assert project["literature"]["matched_at"]
    efficacy = next(
        claim for claim in claims.values() if claim["claim_type"] == "efficacy"
    )
    # 说明书为人工校对来源：即使有直接命中也只能是弱证据
    assert efficacy["evidence_level"] == "weak"
    assert efficacy["citations"][0]["source_channel"] == "leaflet"
    # “药品批准文号”在说明书中没有原文，评为无证据
    approval_type_claim = next(
        claim for claim in claims.values() if claim["text"] == "药品批准文号"
    )
    assert approval_type_claim["evidence_level"] == "none"
    assert approval_type_claim["citations"] == []

    # 上传临床研究文献后重新匹配，功效卖点升级为强证据
    await service.add_literature(
        username="workflow-user",
        project_id=project["project_id"],
        files=[
            (
                "RCT研究.pdf",
                _pdf_bytes(
                    "随机双盲对照试验证实：安神补脑液生精补髓，益气养血，强脑安神。"
                ),
            )
        ],
        doc_kind="clinical",
    )
    project = await service.run_literature_match(
        username="workflow-user", project_id=project["project_id"]
    )
    efficacy = next(
        claim
        for claim in project["literature_claims"]
        if claim["claim_type"] == "efficacy" and claim["text"].startswith("生精补髓")
    )
    assert efficacy["evidence_level"] == "strong"
    assert any(
        citation["source_kind"] == "clinical" for citation in efficacy["citations"]
    )

    # 输出按 🟢强 → 🟡弱 → 🔴无 排序；三联卡带文献来源汇总行
    levels = [claim["evidence_level"] for claim in project["literature_claims"]]
    order = {"strong": 0, "weak": 1, "none": 2}
    assert levels == sorted(levels, key=lambda level: order[level])
    assert levels[0] == "strong" and levels[-1] == "none"
    assert efficacy["triple_card"]["citation_summary"]
    assert "RCT研究.pdf" in efficacy["triple_card"]["citation_summary"]
    red = project["literature_claims"][-1]
    assert red["triple_card"]["citation_summary"] == "无文献来源"


@pytest.mark.asyncio
async def test_confirm_literature_gates_and_unusable_library(tmp_path: Path):
    """第三层：确认门禁、红线清单、场景仅引用通过验证的卖点。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _literature_ready_project(service)

    # 未执行匹配直接确认 → 阻断
    with pytest.raises(PharmaTranslatorError, match="请先执行文献匹配"):
        _workflow_action(service, project, "confirm_literature", {"claims": []})

    project = await service.run_literature_match(
        username="workflow-user", project_id=project["project_id"]
    )
    red_claim = next(
        claim
        for claim in project["literature_claims"]
        if claim["evidence_level"] == "none"
    )
    # 接受无证据卖点 → 阻断
    with pytest.raises(PharmaTranslatorError, match="无证据卖点，不能标记为可用"):
        _workflow_action(
            service,
            project,
            "confirm_literature",
            {
                "claims": [{**red_claim, "accepted": True}],
                "signoff": LITERATURE_SIGNOFF,
            },
        )
    # 全部不接受 → 阻断
    with pytest.raises(PharmaTranslatorError, match="至少需要一条有文献证据"):
        _workflow_action(
            service,
            project,
            "confirm_literature",
            {
                "claims": [
                    {**claim, "accepted": False}
                    for claim in project["literature_claims"]
                ],
                "signoff": LITERATURE_SIGNOFF,
            },
        )

    claims = [
        {
            **claim,
            "accepted": claim["evidence_level"] in {"strong", "weak"}
            and bool(claim["citations"]),
        }
        for claim in project["literature_claims"]
    ]
    # 未签字 → 阻断（确认节点必须有签字人）
    with pytest.raises(PharmaTranslatorError, match="签字人姓名与职务"):
        _workflow_action(service, project, "confirm_literature", {"claims": claims})
    # 非医学部/学术部 → 阻断
    with pytest.raises(PharmaTranslatorError, match="医学部/学术部"):
        _workflow_action(
            service,
            project,
            "confirm_literature",
            {
                "claims": claims,
                "signoff": {**LITERATURE_SIGNOFF, "signer_title": "市场部经理"},
            },
        )
    # 代签 → 阻断
    with pytest.raises(PharmaTranslatorError, match="不可代签"):
        _workflow_action(
            service,
            project,
            "confirm_literature",
            {
                "claims": claims,
                "signoff": {**LITERATURE_SIGNOFF, "signer_name": "王五代签"},
            },
        )
    # 确认清单未逐项勾选 → 阻断
    with pytest.raises(PharmaTranslatorError, match="三色标签准确"):
        _workflow_action(
            service,
            project,
            "confirm_literature",
            {
                "claims": claims,
                "signoff": {
                    **LITERATURE_SIGNOFF,
                    "checklist": {
                        **LITERATURE_SIGNOFF["checklist"],
                        "levels_accurate": False,
                    },
                },
            },
        )
    project = _workflow_action(
        service,
        project,
        "confirm_literature",
        {"claims": claims, "signoff": LITERATURE_SIGNOFF},
    )
    assert project["workflow"]["current_step"] == 4
    assert project["scenes"]
    assert project["unusable_claims"]
    assert all(
        item["evidence_level"] == "none"
        or item["reason"] in {"人工排除，不进入内容生成", "弱证据且未确认，禁止使用"}
        for item in project["unusable_claims"]
    )
    # 不可用卖点库携带处置建议（对齐企业红线清单 2.4 表）
    assert all(item["disposal"] for item in project["unusable_claims"])
    signoff = project["literature_signoff"]
    assert signoff["signer_name"] == "李医学"
    assert signoff["signer_qualified"] is True
    assert signoff["accepted_count"] == len(project["claims"])
    assert len(signoff["triple_table"]) == len(project["literature_claims"])
    valid_ids = {claim["claim_id"] for claim in project["claims"]}
    assert red_claim["claim_id"] not in valid_ids
    for scene in project["scenes"]:
        assert set(scene["allowed_claim_ids"]) <= valid_ids


async def _signed_literature_project(service: PharmaTranslatorService) -> dict:
    project = await _literature_ready_project(service)
    project = await service.run_literature_match(
        username="workflow-user", project_id=project["project_id"]
    )
    claims = [
        {
            **claim,
            "accepted": claim["evidence_level"] in {"strong", "weak"}
            and bool(claim["citations"]),
        }
        for claim in project["literature_claims"]
    ]
    return _workflow_action(
        service,
        project,
        "confirm_literature",
        {"claims": claims, "signoff": LITERATURE_SIGNOFF},
    )


@pytest.mark.asyncio
async def test_literature_redlines_archive_and_sku_reuse(tmp_path: Path):
    """红线清单归档；同 SKU 复投载入历史复核结论预填，仍需重新签字。"""
    service = PharmaTranslatorService(tmp_path)
    signed = await _signed_literature_project(service)

    redlines = service.list_literature_redlines(
        "workflow-user", project_id=signed["project_id"]
    )
    assert redlines["total"] == len(redlines["items"]) > 0
    assert all(
        item["verdict"] in {"人工排除", "弱化后可用", "禁用"}
        for item in redlines["items"]
    )
    assert all(item["signer"] for item in redlines["items"])

    record = service.get_literature_sku_archive("workflow-user", signed["project_id"])
    assert record["signoff"]["signer_name"] == "李医学"
    assert record["triple_table"]
    assert record["reviews"]

    # 新建同 SKU 项目：归档可复用
    project = await _literature_ready_project(service)
    project = service.reuse_literature_archive("workflow-user", project["project_id"])
    assert project["literature"]["reused_from"]["project_id"] == signed["project_id"]
    project = await service.run_literature_match(
        username="workflow-user", project_id=project["project_id"]
    )
    assert "仍需重新签字" in project["literature"]["tier_notice"]
    reused = [
        claim for claim in project["literature_claims"] if claim.get("prior_review")
    ]
    assert reused
    assert any(claim["accepted"] for claim in reused)
    assert not any(
        claim["accepted"]
        for claim in project["literature_claims"]
        if claim["evidence_level"] == "none"
    )


@pytest.mark.asyncio
async def test_literature_reuse_requires_archive(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _literature_ready_project(service)
    with pytest.raises(PharmaTranslatorError, match="暂无已签字"):
        service.reuse_literature_archive("workflow-user", project["project_id"])


@pytest.mark.asyncio
async def test_literature_triple_csv_export(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _literature_ready_project(service)
    project = await service.run_literature_match(
        username="workflow-user", project_id=project["project_id"]
    )
    filename, content = service.export_literature_triple_csv(
        "workflow-user", project["project_id"]
    )
    text = content.decode("utf-8-sig")
    assert filename.endswith("卖点文献话术三联表.csv")
    assert "证据等级" in text and "合规话术示范" in text
    assert "未签字" in text

    signed = await _signed_literature_project(service)
    _, content = service.export_literature_triple_csv(
        "workflow-user", signed["project_id"]
    )
    text = content.decode("utf-8-sig")
    assert "确认签字" in text and "李医学" in text


def test_content_footnotes_dedupe_and_url():
    claims = [
        {
            "claim_id": "c1",
            "claim_no": "F01",
            "citations": [
                {"source_label": "RCT研究.pdf", "page_no": 2, "url": ""},
                {
                    "source_label": "PubMed PMID 123",
                    "page_no": None,
                    "url": "https://pubmed.ncbi.nlm.nih.gov/123/",
                },
            ],
        },
        {
            "claim_id": "c2",
            "claim_no": "F02",
            "citations": [{"source_label": "RCT研究.pdf", "page_no": 2, "url": ""}],
        },
        {"claim_id": "c3", "claim_no": "F03", "source_label": "说明书", "page_no": 1},
    ]
    footnotes = PharmaTranslatorService._content_footnotes(claims)
    assert [item["index"] for item in footnotes] == [1, 2, 3]
    assert footnotes[0]["text"] == "RCT研究.pdf，第2页"
    assert footnotes[1]["text"].endswith("https://pubmed.ncbi.nlm.nih.gov/123/")
    assert footnotes[2]["claim_no"] == "F03"


@pytest.mark.asyncio
async def test_literature_match_tiers(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _literature_ready_project(service)
    with pytest.raises(PharmaTranslatorError, match="档位无效"):
        await service.run_literature_match(
            username="workflow-user", project_id=project["project_id"], tier="bad"
        )
    project = await service.run_literature_match(
        username="workflow-user", project_id=project["project_id"], tier="standard"
    )
    notice = project["literature"]["tier_notice"]
    assert "PubMed 补证未执行" in notice
    assert "CNKI" in notice
    assert project["literature"]["tier"] == "standard"


@pytest.mark.asyncio
async def test_literature_match_uses_local_knowledge_base(tmp_path: Path):
    """知识库证据：检索命中作为引用，按命名推断文献类型参与优先级。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _literature_ready_project(service)

    async def fake_retrieve(query, kb_ids, kb_names, top_m_final, **_kwargs):
        assert query
        return {
            "results": [
                {
                    "chunk_id": "c1",
                    "doc_id": "d1",
                    "kb_id": kb_ids[0],
                    "kb_name": "企业药典库",
                    "doc_name": "安神补脑液质量标准研究",
                    "content": "安神补脑液：生精补髓，益气养血，强脑安神。",
                    "score": 0.91,
                    "metadata": {},
                }
            ]
        }

    service.core_lifecycle = SimpleNamespace(
        kb_manager=SimpleNamespace(retrieve=fake_retrieve)
    )
    project = await service.run_literature_match(
        username="workflow-user",
        project_id=project["project_id"],
        kb_ids=["kb-1"],
    )
    assert project["literature"]["kb_ids"] == ["kb-1"]
    efficacy = next(
        claim
        for claim in project["literature_claims"]
        if claim["claim_type"] == "efficacy"
    )
    kb_citations = [
        citation
        for citation in efficacy["citations"]
        if citation["source_channel"] == "knowledge_base"
    ]
    # 药典/标准不是功效卖点的优先文献源；有命中即至少为弱证据
    assert kb_citations
    assert kb_citations[0]["source_kind"] == "pharmacopoeia"
    assert "企业药典库" in kb_citations[0]["source_label"]
    assert efficacy["evidence_level"] == "weak"


@pytest.mark.asyncio
async def test_rework_to_literature_step_resets_validation(tmp_path: Path):
    """返工到第 3 步：清空下游卖点与红线清单，保留文献文件，可重新验证。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _literature_ready_project(service)
    project = await _pass_literature(service, project)
    assert project["claims"]

    project = _workflow_action(
        service, project, "rework", {"target_step": 3}, "医学部要求补充文献"
    )
    assert project["workflow"]["current_step"] == 3
    assert project["claims"] == []
    assert project["unusable_claims"] == []
    assert all(not claim["accepted"] for claim in project["literature_claims"])
    project = await _pass_literature(service, project)
    assert project["workflow"]["current_step"] == 4


@pytest.mark.asyncio
async def test_literature_match_ai_analysis_applies_guardrails(tmp_path: Path):
    """本地 AI 分析：只依据召回引用给出建议；上调封顶、下调可至 none、伪造引用被忽略。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _literature_ready_project(service)

    # 先跑一遍确定性匹配拿到 claim_no 与 citation_id
    project = await service.run_literature_match(
        username="workflow-user", project_id=project["project_id"]
    )
    claims = project["literature_claims"]
    efficacy = next(c for c in claims if c["claim_type"] == "efficacy")
    otc = next(c for c in claims if c["text"] == "OTC")
    approval = next(c for c in claims if "国药准字" in c["text"])
    efficacy_cite = efficacy["citations"][0]["citation_id"]

    ai_output = {
        "claims": [
            {
                "claim_no": efficacy["claim_no"],
                "level": "strong",
                "citation_ids": [efficacy_cite],
                "reason": "说明书直接支撑该功效表述",
                "verdict_note": "说明书原文直接引用",
                "expression_rule": "仅按说明书功效表述，禁延伸具体病症",
            },
            {
                "claim_no": otc["claim_no"],
                "level": "none",
                "citation_ids": [],
                "reason": "引用仅为产品分类信息，不构成卖点证据",
                "verdict_note": "所给引用均不支撑该卖点",
                "disposal": "永久禁用",
            },
            {
                "claim_no": approval["claim_no"],
                "level": "strong",
                "citation_ids": ["claim-bogus-cite-99"],
                "reason": "引用不存在，应被忽略",
            },
        ]
    }
    _attach_models(service, [_JsonChatProvider(ai_output)])
    project = await service.run_literature_match(
        username="workflow-user", project_id=project["project_id"]
    )
    claims = {c["claim_no"]: c for c in project["literature_claims"]}

    efficacy_after = claims[efficacy["claim_no"]]
    # 说明书为人工校对来源，确定性等级为 weak；AI 建议 strong 不得上调
    assert efficacy_after["evidence_level"] == "weak"
    assert not efficacy_after.get("ai_adjusted")
    assert efficacy_after["ai_analysis"]["suggested_level"] == "strong"
    assert "kimi" in efficacy_after["ai_analysis"]["model_provider"]
    # 模型建议文案覆盖判定说明与表述边界（不动等级）
    assert efficacy_after["verdict_note"] == "说明书原文直接引用"
    assert efficacy_after["expression_rule"] == "仅按说明书功效表述，禁延伸具体病症"
    assert efficacy_after["triple_card"]["verdict_note"] == "说明书原文直接引用"

    otc_after = claims[otc["claim_no"]]
    # AI 判为引用不支撑 → 下调至 none
    assert otc_after["evidence_level"] == "none"
    assert otc_after["ai_adjusted"] is True
    assert otc_after["ai_analysis"]["suggested_level"] == "none"
    # 🔴 卖点：模型判定说明 + 处置（永久禁用为加严，允许采纳）
    assert otc_after["verdict_note"] == "所给引用均不支撑该卖点"
    assert otc_after["disposal"] == "进入不可用卖点库，永久禁用"

    approval_after = claims[approval["claim_no"]]
    # 模型引用了不存在的 citation_id → 建议整体忽略
    assert "ai_analysis" not in approval_after
    assert approval_after["evidence_level"] == "weak"
    # 未获模型建议的卖点回退为确定性判定说明
    assert approval_after["verdict_note"] == (
        "有引用但非优先源或覆盖度不足，可用但需弱化表述"
    )
    # 每条卖点匹配后都有判定说明与表述边界（对齐三色标签表）
    assert all(c["verdict_note"] and c["expression_rule"] for c in claims.values())

    assert "kimi" in project["literature"]["ai_notice"]

    # AI 下调为 none 的卖点不允许接受；人工可对误杀带理由恢复（有引用）
    with pytest.raises(PharmaTranslatorError, match="无证据卖点，不能标记为可用"):
        _workflow_action(
            service,
            project,
            "confirm_literature",
            {
                "claims": [
                    {**c, "accepted": True} if c["claim_no"] == otc["claim_no"] else c
                    for c in project["literature_claims"]
                ],
                "signoff": LITERATURE_SIGNOFF,
            },
        )
    restored = _workflow_action(
        service,
        project,
        "confirm_literature",
        {
            "claims": [
                (
                    {
                        **c,
                        "accepted": True,
                        "evidence_level": "weak",
                        "adjust_reason": "医学部复核：分类信息可作弱证据使用",
                    }
                    if c["claim_no"] == otc["claim_no"]
                    else {
                        **c,
                        "accepted": c["evidence_level"] in {"strong", "weak"}
                        and bool(c["citations"]),
                    }
                )
                for c in project["literature_claims"]
            ],
            "signoff": LITERATURE_SIGNOFF,
        },
    )
    assert restored["workflow"]["current_step"] == 4
    otc_final = next(c for c in restored["claims"] if c["claim_id"] == otc["claim_id"])
    assert otc_final["evidence_level"] == "weak"
    # 人工恢复为弱证据后：判定说明按新等级确定性重算，处置清空
    otc_lit = next(
        c for c in restored["literature_claims"] if c["claim_id"] == otc["claim_id"]
    )
    assert otc_lit["verdict_note"] == ("有引用但非优先源或覆盖度不足，可用但需弱化表述")
    assert otc_lit["disposal"] == ""
    assert "disposal" not in otc_final["triple_card"]


@pytest.mark.asyncio
async def test_literature_match_ai_failure_keeps_deterministic_results(tmp_path: Path):
    """模型调用失败：保留确定性匹配结果并如实提示，不伪装 AI 结论。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _literature_ready_project(service)
    _attach_models(service, [FakeChatProvider(failure=TimeoutError("timeout"))])
    project = await service.run_literature_match(
        username="workflow-user", project_id=project["project_id"]
    )
    assert "模型分析未完成" in project["literature"]["ai_notice"]
    assert project["literature"]["matched_at"]
    efficacy = next(
        c for c in project["literature_claims"] if c["claim_type"] == "efficacy"
    )
    assert efficacy["evidence_level"] == "weak"
    assert "ai_analysis" not in efficacy
    # 模型不可用时仍输出确定性判定说明/表述边界
    assert efficacy["verdict_note"] == "有引用但非优先源或覆盖度不足，可用但需弱化表述"
    assert efficacy["expression_rule"]


@pytest.mark.asyncio
async def test_literature_match_ai_writes_triple_card_copies(tmp_path: Path):
    """本地模型生成三联卡话术：合规话术过红线词护栏，🔴 卖点不生成话术。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _literature_ready_project(service)
    project = await service.run_literature_match(
        username="workflow-user", project_id=project["project_id"]
    )
    claims = {c["claim_no"]: c for c in project["literature_claims"]}
    efficacy = next(c for c in claims.values() if c["claim_type"] == "efficacy")
    approval = next(c for c in claims.values() if "国药准字" in c["text"])
    assert efficacy["triple_card"]["copy_source"] == "template"

    copy_output = {
        "cards": [
            {
                "claim_no": efficacy["claim_no"],
                "compliant_copy": "批准功效写得明明白白，状态调理看这里 ✅",
                "violation_copy": "喝了三天头不晕了/贫血喝它 ❌",
            },
            {
                "claim_no": approval["claim_no"],
                "compliant_copy": "治疗失眠效果显著，见效快",  # 红线词 → 回退模板
                "violation_copy": "国家批准的特效药 ❌",
            },
        ]
    }
    provider = _SeqChatProvider([{"claims": []}, copy_output])
    _attach_models(service, [provider])
    project = await service.run_literature_match(
        username="workflow-user", project_id=project["project_id"]
    )
    claims = {c["claim_no"]: c for c in project["literature_claims"]}

    efficacy_after = claims[efficacy["claim_no"]]
    assert efficacy_after["triple_card"]["compliant_copy"] == (
        "批准功效写得明明白白，状态调理看这里 ✅"
    )
    assert efficacy_after["triple_card"]["violation_copy"] == (
        "喝了三天头不晕了/贫血喝它 ❌"
    )
    assert efficacy_after["triple_card"]["copy_source"] == "ai"

    approval_after = claims[approval["claim_no"]]
    # 合规话术命中红线词 → 保留确定性模板；违规警示仍可采用
    assert approval_after["triple_card"]["compliant_copy"].startswith("国药准字")
    assert approval_after["triple_card"]["copy_source"] == "template"
    assert approval_after["triple_card"]["violation_copy"] == "国家批准的特效药 ❌"
    assert "三联卡话术 1 条由本地模型生成" in project["literature"]["ai_notice"]


@pytest.mark.asyncio
async def test_kb_retrieval_query_includes_recognized_product_name(tmp_path: Path):
    """知识库检索必须带入第 1 步图片识别出的药品名。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _literature_ready_project(service)
    queries: list[str] = []

    async def fake_retrieve(query, kb_ids, kb_names, top_m_final, **_kwargs):
        queries.append(query)
        return {"results": []}

    service.core_lifecycle = SimpleNamespace(
        kb_manager=SimpleNamespace(retrieve=fake_retrieve)
    )
    project = await service.run_literature_match(
        username="workflow-user",
        project_id=project["project_id"],
        kb_ids=["kb-1"],
    )
    assert queries
    assert all("安神补脑液" in query for query in queries)
    # 未配置生成模型时如实降级提示
    assert "未配置可用的生成模型" in project["literature"]["ai_notice"]


@pytest.mark.asyncio
async def test_confirm_dimensions_drops_manually_filled_unsourced_items(
    tmp_path: Path,
):
    """手工补录的字段没有原文来源：前端按口径过滤这些条目，
    后端不得再要求确认它们（否则第 2 步死锁）。"""
    service = PharmaTranslatorService(tmp_path)
    # 说明书缺批准文号、批文类型与适用人群
    text = """
OTC
【药品名称】安神补脑液
【功能主治】生精补髓，益气养血，强脑安神。用于肾精不足、气血两亏所致的头晕、乏力、健忘、失眠。
【规格】每支装10毫升
【用法用量】口服。一次10毫升，一日2次。
【不良反应】尚不明确。
"""
    project = await _new_project(service, text)
    fields = _confirm_all_fields(project)
    manual_values = {
        "approval_number": "国药准字Z22000001",
        "approval_type": "药品批准文号",
        "audience": "成年气血不足人群",
    }
    for field in fields:
        if field["field_code"] in manual_values:
            field["value"] = manual_values[field["field_code"]]
            field["confirmed"] = True
            field["source_type"] = "manual_input"
            field["source_text"] = ""
    project = _workflow_action(service, project, "confirm_profile", {"fields": fields})
    assert project["workflow"]["current_step"] == 2
    # 多维卡片中三个手工条目存在但无原文来源
    unsourced_labels = {
        item["label"]
        for dimension in project["dimensions"]
        for item in dimension["items"]
        if not str(item.get("source_text") or "").strip()
    }
    assert unsourced_labels == {"适用人群", "批准文号", "批文类型"}

    # 模拟前端 confirmDimensions 的提交口径：过滤无来源条目，其余全部确认
    submitted_dimensions = [
        {
            **dimension,
            "items": [
                {**item, "confirmed": True}
                for item in dimension["items"]
                if str(item.get("source_text") or "").strip()
            ],
        }
        for dimension in project["dimensions"]
    ]
    submitted_constraints = [
        {**item, "confirmed": True}
        for item in project["safety_constraints"]
        if str(item.get("source_text") or "").strip()
    ]
    project = _workflow_action(
        service,
        project,
        "confirm_dimensions",
        {
            "dimensions": submitted_dimensions,
            "safety_constraints": submitted_constraints,
        },
    )
    assert project["workflow"]["current_step"] == 3
    # 无来源条目已移出多维卡片，不再阻塞也不会进入卖点候选
    remaining_labels = {
        item["label"]
        for dimension in project["dimensions"]
        for item in dimension["items"]
    }
    assert "适用人群" not in remaining_labels
    assert "批准文号" not in remaining_labels
    assert all(
        str(item.get("source_text") or "").strip()
        for dimension in project["dimensions"]
        for item in dimension["items"]
    )


async def _drive_to_step3(service: PharmaTranslatorService) -> dict:
    project = await _new_project(service)
    project = _workflow_action(
        service,
        project,
        "confirm_profile",
        {"fields": _confirm_all_fields(project)},
    )
    dimensions, constraints = _confirm_dimensions(project)
    return _workflow_action(
        service,
        project,
        "confirm_dimensions",
        {"dimensions": dimensions, "safety_constraints": constraints},
    )


@pytest.mark.asyncio
async def test_scene_engine_generates_standard_template_candidates(tmp_path: Path):
    """场景翻译引擎：四层流程 + 标准模板，仅使用已验证（🟢/🟡）卖点。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _drive_to_step3(service)
    assert project["scenes"] == []

    project = await _pass_literature(service, project)
    assert project["workflow"]["current_step"] == 4
    scenes = project["scenes"]
    assert 8 <= len(scenes) <= 12
    assert [scene["scene_no"] for scene in scenes] == [
        f"S{index:02d}" for index in range(1, len(scenes) + 1)
    ]
    assert sum(1 for scene in scenes if scene["selected"]) <= 5

    valid_claim_ids = {claim["claim_id"] for claim in project["claims"]}
    for scene in scenes:
        # 标准模板字段完整
        for key in (
            "target_audience",
            "time_of_day",
            "location",
            "trigger_event",
            "core_pain",
            "inner_monologue",
            "content_hook",
            "keywords_notice",
        ):
            assert scene[key], (scene["scene_no"], key)
        assert scene["search_keywords"]
        assert scene["trust_anchors"]
        assert scene["generation_mode"] == "deterministic_rules"
        # 关联卖点全部来自已验证卖点，且只含 🟢/🟡
        assert scene["linked_claims"]
        for linked in scene["linked_claims"]:
            assert linked["claim_id"] in valid_claim_ids
            assert linked["evidence_level"] in {"strong", "weak"}
            assert linked["marker"] in {"🟢", "🟡"}
            assert linked["claim_no"].startswith("F")
        # 未导入用户原话时如实提示，不伪造评论
        assert scene["user_voices"] == []
        assert "未导入平台真实用户原话" in scene["user_voices_notice"]

    # 第一层症状解构：说明书“失眠”翻译成睡眠场景簇的生活化关键词
    sleep_scenes = [scene for scene in scenes if scene["cluster"] == "sleep"]
    assert sleep_scenes
    assert "睡不着" in sleep_scenes[0]["symptom_keywords"]
    assert sleep_scenes[0]["inner_monologue"]
    # 人群画像标注说明书人群锚点（本例说明书无适用人群字段，锚点为空）
    assert sleep_scenes[0]["audience_scope"]["claim_nos"] == []


@pytest.mark.asyncio
async def test_scene_confirmation_records_priority_note_and_deleted(tmp_path: Path):
    """Step 3 人工确认节点：输出选定清单+强打/弱打/删除批注凭证。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _drive_to_step3(service)
    project = await _pass_literature(service, project)
    scenes = project["scenes"]

    payload = []
    for index, scene in enumerate(scenes):
        payload.append(
            {
                "scene_id": scene["scene_id"],
                "selected": index < 2,
                "priority": "strong" if index == 0 else "",
                "note": "重点投放" if index == 0 else "",
                "deleted": index == len(scenes) - 1,
            }
        )
    project = _workflow_action(
        service, project, "confirm_scenes", {"scenes": payload}, comment="市场勾选"
    )
    assert project["workflow"]["current_step"] == 5
    first, last = project["scenes"][0], project["scenes"][-1]
    assert first["status"] == "confirmed"
    assert first["priority"] == "strong" and first["note"] == "重点投放"
    assert last["status"] == "deleted" and last["deleted"]
    receipt = project["audit_events"][-1]["comment"]
    assert "场景选定" in receipt and "强打" in receipt and "删除" in receipt
    assert scenes[0]["scene_no"] in receipt


@pytest.mark.asyncio
async def test_scene_confirmation_rejects_selected_deleted(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _drive_to_step3(service)
    project = await _pass_literature(service, project)
    scenes = project["scenes"]
    payload = [
        {
            "scene_id": scene["scene_id"],
            "selected": True,
            "deleted": index == 0,
        }
        for index, scene in enumerate(scenes)
    ]
    with pytest.raises(PharmaTranslatorError, match="已标记删除，不能同时被选定"):
        _workflow_action(service, project, "confirm_scenes", {"scenes": payload})


@pytest.mark.asyncio
async def test_user_voices_import_anchor_refresh_and_step_gate(
    tmp_path: Path, monkeypatch
):
    """用户原话：带来源声明导入、场景锚点挂载、步骤门禁与去重。"""
    service = PharmaTranslatorService(tmp_path)
    project = await _new_project(service)
    with pytest.raises(PharmaTranslatorError, match="请先完成档案与多维拆解确认"):
        service.add_user_voices(
            username="workflow-user",
            project_id=project["project_id"],
            voices=[
                {"text": "又到3点了还睡不着", "source": "小红书评论抽样（已获授权）"}
            ],
        )

    project = await _drive_to_step3(service)
    with pytest.raises(PharmaTranslatorError, match="来源声明"):
        service.add_user_voices(
            username="workflow-user",
            project_id=project["project_id"],
            voices=[{"text": "又到3点了还睡不着", "source": ""}],
        )
    project = service.add_user_voices(
        username="workflow-user",
        project_id=project["project_id"],
        voices=[
            {
                "text": "又到3点了还睡不着，脑子停不下来",
                "source": "小红书评论抽样（已获授权）",
            },
            {"text": "一换季办公室感冒就有我", "source": "小红书评论抽样（已获授权）"},
            {"text": "站起来头晕要扶桌子", "source": "电商评论导出（已授权）"},
        ],
    )
    assert len(project["user_voices_pool"]) == 3
    with pytest.raises(PharmaTranslatorError, match="没有新增用户原话"):
        service.add_user_voices(
            username="workflow-user",
            project_id=project["project_id"],
            voices=[
                {
                    "text": "又到3点了还睡不着，脑子停不下来",
                    "source": "小红书评论抽样（已获授权）",
                }
            ],
        )

    project = await _pass_literature(service, project)
    for scene in project["scenes"]:
        assert 1 <= len(scene["user_voices"]) <= 3
        assert scene["user_voices_notice"] == ""
        assert all(voice["source"] for voice in scene["user_voices"])
    # 症状重叠度高的原话优先挂载到睡眠场景
    sleep_scene = next(
        scene for scene in project["scenes"] if scene["cluster"] == "sleep"
    )
    assert any("睡不着" in voice["text"] for voice in sleep_scene["user_voices"])

    # 第 4 步删除一条原话后，场景锚点同步刷新
    voice_id = project["user_voices_pool"][0]["voice_id"]
    project = service.remove_user_voice(
        username="workflow-user",
        project_id=project["project_id"],
        voice_id=voice_id,
    )
    assert len(project["user_voices_pool"]) == 2
    assert all(
        voice["voice_id"] != voice_id
        for scene in project["scenes"]
        for voice in scene["user_voices"]
    )

    # 场景确认后进入第 5 步竞品扫描，仍可补充原话；竞品确认后禁止再修改样本池
    project = _workflow_action(
        service, project, "confirm_scenes", {"scenes": project["scenes"]}
    )
    project = service.add_user_voices(
        username="workflow-user",
        project_id=project["project_id"],
        voices=[{"text": "竞品阶段补充一条", "source": "知乎回答抽样（已授权）"}],
    )
    project = await _pass_competitor(service, project, monkeypatch)
    with pytest.raises(PharmaTranslatorError, match="竞品扫描已确认"):
        service.add_user_voices(
            username="workflow-user",
            project_id=project["project_id"],
            voices=[{"text": "新增一条试试看", "source": "知乎回答抽样（已授权）"}],
        )


# ---------------- 合规过滤引擎（中睿知识库 + 三层规则 + 合规部签字） ----------------

SAFE_TAIL = "效果因个体差异而不同；使用前请阅读完整说明书，如有疑问请咨询医师或药师。"


def _content(body: str, platform: str = "公众号", content_id: str = "c-1") -> dict:
    return {
        "content_id": content_id,
        "platform": platform,
        "title": "健康信息卡",
        "body": body,
        "fact_sentences": [{"claim_id": "claim-1", "text": "说明书事实"}],
        "claim_ids": ["claim-1"],
    }


def _scan(service, body, *, product_type="OTC", platform="公众号"):
    return service._scan_content_compliance(
        _content(body, platform),
        product_type=product_type,
        valid_claim_ids={"claim-1"},
    )


def _levels(risks: list[dict]) -> dict[str, str]:
    return {risk["rule_id"]: risk["level"] for risk in risks}


def test_compliance_three_tier_rules_and_labels(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    # ✅ 合规：带免责声明与个体差异
    assert _scan(service, "有助于睡眠。" + SAFE_TAIL) == []

    # 🔴 一级红线：OTC 绝对化疗效
    risks = _scan(service, "药到病除，立竿见影。" + SAFE_TAIL)
    assert _levels(risks)["rule_cure_001"] == "block"
    assert {r["matched_text"] for r in risks if r["rule_id"] == "rule_cure_001"} >= {
        "药到病除",
        "立竿见影",
    }
    # 保健品禁用治疗/预防疾病，OTC 不适用该条
    assert (
        _levels(_scan(service, "可治疗失眠" + SAFE_TAIL, product_type="保健食品"))[
            "rule_health_food_001"
        ]
        == "block"
    )
    assert "rule_health_food_001" not in _levels(
        _scan(service, "可治疗失眠" + SAFE_TAIL)
    )
    assert "rule_device_001" in _levels(
        _scan(service, "保证永不复发" + SAFE_TAIL, product_type="医疗器械")
    )
    assert "rule_non_medical_001" in _levels(
        _scan(service, "专业消炎" + SAFE_TAIL, product_type="消字号")
    )

    # 🟡 二级谨慎：缺免责声明 / 个体差异 / 疑问句 / 医师出镜
    levels = _levels(_scan(service, "专治失眠，医生推荐。"))
    assert levels["caution_disclaimer_001"] == "caution"
    assert levels["caution_individual_001"] == "caution"
    assert levels["caution_question_001"] == "caution"
    assert levels["caution_doctor_001"] == "caution"

    # 平台规则分平台维护：小红书禁止站外导流，公众号不命中该条
    assert "platform_xhs_001" in _levels(
        _scan(service, "私信我" + SAFE_TAIL, platform="小红书")
    )
    assert "platform_xhs_001" not in _levels(_scan(service, "私信我" + SAFE_TAIL))

    # 🟢 三级替换不影响三色标签
    risks = _scan(service, "对睡眠有效。" + SAFE_TAIL)
    assert [(r["level"], r["replacement"]) for r in risks] == [
        ("replace", "可能有帮助")
    ]
    contents = [_content("x", content_id="c-1"), _content("y", content_id="c-2")]
    summary = service._apply_compliance_labels(
        contents,
        risks + [{**risks[0], "content_id": "c-2", "level": "block", "risk_id": "r2"}],
    )
    assert summary == {"pass": 1, "caution": 0, "blocked": 1}
    assert contents[0]["compliance_label_text"].startswith("✅")
    assert contents[1]["status"] == "blocked"

    # RX 大众平台直接拦截，只走患者管理路径
    report = service._rx_block_report(["小红书"])
    assert report["status"] == "blocked"
    assert report["patient_management_only"] is True


def _review_data(service, body: str) -> dict:
    content = _content(body)
    data = {
        "product_type": "OTC",
        "claims": [{"claim_id": "claim-1", "medical_confirmed": True}],
        "contents": [content],
    }
    data["compliance"] = service._scan_compliance(data)
    return data


def _review_payload(data: dict, decision: str = "keep", **extra) -> dict:
    return {
        "signer_name": "张合规",
        "signer_title": "合规部经理",
        "citation_covered": True,
        "reviews": {
            risk["risk_id"]: {"decision": decision, "note": "已逐条复核"}
            for risk in data["compliance"]["risks"]
        },
        **extra,
    }


def test_compliance_confirmation_gates_and_signed_record(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)

    def confirm(data, payload):
        return service._confirm_compliance_review(
            data, username="u", payload=payload, comment=""
        )

    # 违规拦截不能绕过
    blocked = _review_data(service, "根治失眠。" + SAFE_TAIL)
    with pytest.raises(PharmaTranslatorError, match="不能绕过"):
        confirm(blocked, _review_payload(blocked))

    data = _review_data(service, "对睡眠有效，治失眠。" + SAFE_TAIL)
    assert data["compliance"]["status"] == "caution"
    with pytest.raises(PharmaTranslatorError, match="不可代签"):
        confirm(data, _review_payload(data, on_behalf=True))
    with pytest.raises(PharmaTranslatorError, match="合规部"):
        confirm(data, {**_review_payload(data), "signer_title": "市场部"})
    with pytest.raises(PharmaTranslatorError, match="文献引证"):
        confirm(data, {**_review_payload(data), "citation_covered": False})
    with pytest.raises(PharmaTranslatorError, match="未逐条处理"):
        confirm(data, {**_review_payload(data), "reviews": {}})
    caution_without_note = _review_payload(data)
    for review in caution_without_note["reviews"].values():
        review["note"] = ""
    with pytest.raises(PharmaTranslatorError, match="未逐条处理"):
        confirm(data, caution_without_note)
    stale = json.loads(json.dumps(data))
    stale["compliance"]["kb_version"] = "zr-compliance-kb-2020.01"
    with pytest.raises(PharmaTranslatorError, match="未同步"):
        confirm(stale, _review_payload(stale))

    approval = confirm(data, _review_payload(data, decision="adopt"))
    record = approval["record"]
    assert record["record_id"].startswith("ZR-CR-")
    assert record["kb_version"] == data["compliance"]["kb_version"]
    assert record["retrieval_date"] == data["compliance"]["scanned_at"]
    assert record["signer_name"] == "张合规"
    assert record["replace_adopted"] == 1
    assert record["caution_reviewed"] == 1
    assert "中睿" in record["kb_builder"]
    # 采纳的替换建议已写回正文
    assert "可能有帮助" in data["contents"][0]["body"]


async def _content_ready_project(service, body: str, product_type="OTC") -> dict:
    project = await _new_project(service)
    project_dir, data = service._read_owned_project_with_dir(
        "workflow-user", project["project_id"]
    )
    data["product_type"] = product_type
    data["workflow"]["current_step"] = 9
    data["workflow"]["state"] = "COMPLIANCE_CONFIRMATION"
    data["claims"] = [{"claim_id": "claim-1", "medical_confirmed": True}]
    data["contents"] = [_content(body)]
    data["compliance"] = service._scan_compliance(data)
    service._write_project(project_dir, data)
    return service.get_project("workflow-user", project["project_id"])


@pytest.mark.asyncio
async def test_compliance_review_with_kb_and_model_only_adds_risks(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _content_ready_project(service, "对睡眠有帮助。" + SAFE_TAIL)
    assert project["compliance"]["status"] == "clear"

    queries = []

    async def fake_retrieve(query, kb_ids, kb_names, top_m_final, **_kwargs):
        queries.append(query)
        return {
            "results": [
                {
                    "kb_name": "企业合规库",
                    "doc_name": "OTC 广告禁用语清单",
                    "content": "OTC 广告不得暗示对睡眠有帮助以外的功效。",
                    "score": 0.8,
                }
            ]
        }

    provider = _JsonChatProvider(
        {
            "findings": [
                {
                    "content_id": "c-1",
                    "level": "caution",
                    "matched_text": "对睡眠有帮助",
                    "message": "功效暗示需人工复核",
                    "legal_basis": "《药品广告审查发布标准》",
                    "suggestion": "改为说明书原文",
                    "kb_refs": ["kb-1", "kb-404"],
                },
                {
                    "content_id": "c-1",
                    "level": "block",
                    "matched_text": "原文中不存在的片段",
                },
                {"content_id": "c-404", "level": "block", "matched_text": "对睡眠"},
                {"content_id": "c-1", "level": "pass", "matched_text": "对睡眠"},
            ]
        }
    )
    _attach_models(service, [provider])
    service.core_lifecycle.kb_manager = SimpleNamespace(retrieve=fake_retrieve)
    project = await service.run_compliance_review(
        username="workflow-user",
        project_id=project["project_id"],
        kb_ids=["kb-a"],
    )
    assert queries
    prompt = json.loads(provider.calls[0]["prompt"])
    assert prompt["knowledge_base"][0]["kb_ref"] == "kb-1"
    compliance = project["compliance"]
    assert compliance["status"] == "caution"
    ai_risks = [r for r in compliance["risks"] if r["source"] == "ai"]
    assert len(ai_risks) == 1
    assert "企业合规库/OTC 广告禁用语清单" in ai_risks[0]["legal_basis"]
    assert compliance["ai_review"]["kb_hits"][0]["kb_name"] == "企业合规库"
    assert compliance["ai_review"]["finding_count"] == 1
    assert project["contents"][0]["compliance_label"] == "caution"

    # 签字凭证的检索日期取自本次知识库检索
    project = _workflow_action(service, project, "market_confirm")
    project = _workflow_action(
        service, project, "compliance_confirm", _compliance_payload(project)
    )
    record = project["approvals"]["compliance"]["record"]
    assert record["retrieval_date"] == compliance["ai_review"]["retrieved_at"]


@pytest.mark.asyncio
async def test_compliance_review_keeps_rule_hits_when_model_missing(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _content_ready_project(service, "根治失眠")
    _attach_models(service, [])
    project = await service.run_compliance_review(
        username="workflow-user", project_id=project["project_id"]
    )
    assert project["compliance"]["status"] == "blocked"
    assert "未配置" in project["compliance"]["ai_review"]["notice"]
    assert project["workflow"]["step_status"]["9"] == "blocked"
    cross = project["compliance"]["cross_validation"]
    assert "中睿" in cross["baseline"]
    assert cross["engine"] == ""
    assert "未配置可用的 AI 搜索" in cross["notice"]
    assert cross["summary"]["rule_only"] >= 1
    assert cross["conclusion"] == "AI 搜索未完成，结果以中睿合规底座为准"


@pytest.mark.asyncio
async def test_compliance_review_auto_kb_and_rule_fallback(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _content_ready_project(service, "根治失眠")
    used_ids: list = []

    async def fake_retrieve(**kwargs):
        used_ids.append(kwargs.get("kb_ids"))
        return {
            "results": [
                {
                    "content": "广告禁用语：根治、治愈",
                    "kb_name": "企业合规库",
                    "doc_name": "禁用语清单",
                    "score": 0.9,
                }
            ]
        }

    class DeadProvider:
        provider_config = {"id": "dead", "type": "openai"}

        async def text_chat(self, **_):
            raise asyncio.TimeoutError()

    _attach_models(service, [DeadProvider()])
    service.core_lifecycle.kb_manager = SimpleNamespace(
        retrieve=fake_retrieve, kb_insts={"kb-auto": SimpleNamespace(init_error=None)}
    )
    project = await service.run_compliance_review(
        username="workflow-user", project_id=project["project_id"], ai_search=False
    )
    review = project["compliance"]["ai_review"]
    assert used_ids and used_ids[0] == ["kb-auto"]
    assert review["kb_auto"] is True
    assert "结合规则引擎重新生成" in review["notice"]
    assert any(
        "企业合规库/禁用语清单" in r["legal_basis"]
        for r in project["compliance"]["risks"]
    )


class _SeqChatProvider(_JsonChatProvider):
    """按调用顺序返回不同 JSON。"""

    def __init__(self, outputs):
        super().__init__(outputs[0])
        self.outputs = list(outputs)

    async def text_chat(self, **kwargs):
        self.calls.append(kwargs)
        output = self.outputs[min(len(self.calls), len(self.outputs)) - 1]
        return SimpleNamespace(completion_text=json.dumps(output, ensure_ascii=False))


_SEARCH_ROWS = [
    {
        "title": "广告法第十六条",
        "url": "https://www.samr.gov.cn/ad16",
        "snippet": "药品广告不得含有表示功效、安全性的断言或者保证，不得使用根治等用语",
        "query": "q1",
    },
    {
        "title": "药品广告审查发布标准",
        "url": "https://www.nmpa.gov.cn/std",
        "snippet": "不得含有暗示功效的表述",
        "query": "q2",
    },
    {
        "title": "重复",
        "url": "https://www.samr.gov.cn/ad16",
        "snippet": "",
        "query": "q3",
    },
    {"title": "无效链接", "url": "javascript:alert(1)", "snippet": "", "query": "q4"},
]


@pytest.mark.asyncio
async def test_compliance_cross_validation_with_ai_search(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _content_ready_project(
        service, "根治失眠。对睡眠有帮助。" + SAFE_TAIL
    )
    rule_risk = next(
        r for r in project["compliance"]["risks"] if r["matched_text"] == "根治"
    )
    provider = _SeqChatProvider(
        [
            {"findings": []},
            {
                "confirmations": [
                    {
                        "risk_id": rule_risk["risk_id"],
                        "refs": ["web-1", "web-99"],
                        "note": "广告法佐证",
                    },
                    {"risk_id": "unknown", "refs": ["web-1"]},
                ],
                "new_findings": [
                    {
                        "content_id": "c-1",
                        "level": "caution",
                        "matched_text": "对睡眠有帮助",
                        "message": "功效暗示",
                        "legal_basis": "《药品广告审查发布标准》",
                        "suggestion": "改为说明书原文",
                        "refs": ["web-2"],
                    },
                    {
                        "content_id": "c-1",
                        "level": "block",
                        "matched_text": "对睡眠有帮助",
                    },
                    {
                        "content_id": "c-1",
                        "level": "block",
                        "matched_text": "不存在",
                        "refs": ["web-1"],
                    },
                ],
            },
        ]
    )
    _attach_models(service, [provider])
    searched = []

    async def fake_search(queries):
        searched.extend(queries)
        return list(_SEARCH_ROWS), "Tavily", ""

    service._run_configured_web_search = fake_search
    project = await service.run_compliance_review(
        username="workflow-user", project_id=project["project_id"]
    )
    assert searched and len(searched) <= 5
    cross = project["compliance"]["cross_validation"]
    assert cross["engine"] == "Tavily" and cross["engine_type"] == "web_search"
    assert [s["ref"] for s in cross["sources"]] == ["web-1", "web-2"]
    by_risk = {item["risk_id"]: item for item in cross["items"]}
    assert by_risk[rule_risk["risk_id"]]["verdict"] == "consistent"
    assert by_risk[rule_risk["risk_id"]]["search_refs"] == ["web-1"]
    ai_only = [i for i in cross["items"] if i["verdict"] == "ai_only"]
    assert len(ai_only) == 1 and ai_only[0]["matched_text"] == "对睡眠有帮助"
    search_risks = [
        r for r in project["compliance"]["risks"] if r["source"] == "ai_search"
    ]
    assert len(search_risks) == 1
    assert "AI搜索·药品广告审查发布标准" in search_risks[0]["legal_basis"]
    # 中睿底座的红线不被撤销
    assert project["compliance"]["status"] == "blocked"
    assert "双方一致 1 项" in cross["conclusion"]


@pytest.mark.asyncio
async def test_compliance_cross_validation_keyword_fallback_and_switch_off(
    tmp_path: Path,
):
    service = PharmaTranslatorService(tmp_path)
    project = await _content_ready_project(service, "根治失眠。" + SAFE_TAIL)
    _attach_models(service, [])

    async def fake_search(_queries):
        return list(_SEARCH_ROWS), "博查 AI 搜索", ""

    service._run_configured_web_search = fake_search
    result = await service.run_compliance_review(
        username="workflow-user", project_id=project["project_id"]
    )
    cross = result["compliance"]["cross_validation"]
    item = next(i for i in cross["items"] if i["matched_text"] == "根治")
    assert item["verdict"] == "consistent"
    assert item["note"] == "关键词比对佐证"

    result = await service.run_compliance_review(
        username="workflow-user", project_id=project["project_id"], ai_search=False
    )
    assert result["compliance"]["cross_validation"] is None


@pytest.mark.asyncio
async def test_compliance_expert_ticket_sla_and_answer(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _content_ready_project(service, "治失眠。" + SAFE_TAIL)
    risk_id = project["compliance"]["risks"][0]["risk_id"]
    with pytest.raises(PharmaTranslatorError, match="请填写"):
        await service.create_compliance_expert_ticket(
            username="workflow-user", project_id=project["project_id"], question=""
        )
    project = await service.create_compliance_expert_ticket(
        username="workflow-user",
        project_id=project["project_id"],
        question="“治失眠”改疑问句是否足够？",
        risk_ids=[risk_id, "unknown"],
    )
    ticket = project["compliance_tickets"][0]
    assert ticket["status"] == "open"
    assert ticket["risk_ids"] == [risk_id]
    from datetime import datetime

    created = datetime.fromisoformat(ticket["created_at"])
    due = datetime.fromisoformat(ticket["due_at"])
    assert (due - created).total_seconds() == 24 * 3600

    with pytest.raises(PharmaTranslatorError, match="不存在"):
        await service.answer_compliance_expert_ticket(
            username="workflow-user",
            project_id=project["project_id"],
            ticket_id="ZR-Q-NONE",
            answer="x",
            expert_name="y",
        )
    project = await service.answer_compliance_expert_ticket(
        username="workflow-user",
        project_id=project["project_id"],
        ticket_id=ticket["ticket_id"],
        answer="建议改为“失眠能用吗？”并补充说明书指引",
        expert_name="中睿王专家",
    )
    assert project["compliance_tickets"][0]["status"] == "answered"

    project = _workflow_action(service, project, "market_confirm")
    project = _workflow_action(
        service, project, "compliance_confirm", _compliance_payload(project)
    )
    record = project["approvals"]["compliance"]["record"]
    assert record["expert_ticket_ids"] == [ticket["ticket_id"]]


def test_compliance_knowledge_base_catalog(tmp_path: Path):
    catalog = PharmaTranslatorService(tmp_path).get_compliance_knowledge_base()
    assert "中睿" in catalog["builder"]
    assert len(catalog["layers"]) >= 5
    assert catalog["expert_sla_hours"] == 24
    assert {"original": "根治", "replacement": "改善"} in catalog["replacements"]
    assert "小红书" in catalog["platforms"]
    assert catalog["filter_rule_version"] == "zr-otc-filter-1.0"
    assert "广告法" in catalog["filter_basis"]
    assert {r["category"] for r in catalog["filter_redline_rules"]} >= {
        "off_label",
        "disparage",
        "silver_fear",
        "fake_data",
    }
    assert {"original": "提高血氧", "replacement": ""} in catalog["filter_replacements"]
    assert catalog["filter_notice"] == "请按药品说明书或者在药师指导下购买和使用"
    assert catalog["disposal_actions"]["takedown"] == "联系渠道下架"


# ---------------- Step 6 合规过滤引擎（竞品样本 + 品牌存量内容） ----------------

FILTER_NOTICE = "请按药品说明书或者在药师指导下购买和使用。OTC 国药准字Z22000001"
FILTER_INVENTORY = [
    {
        "inventory_id": "inv-00000000a1",
        "platform": "腾讯新闻",
        "channel": "腾讯新闻、抖音好物",
        "date": "2026-04-12",
        "title": "软文",
        "body": "每天一支，提高血氧，改善认知。",
    },
    {
        "inventory_id": "inv-00000000a2",
        "platform": "小红书",
        "date": "2026-09-02",
        "title": "素人帖",
        "body": "妈妈最近健忘，认不出人了。" + FILTER_NOTICE,
    },
    {
        "inventory_id": "inv-00000000a3",
        "platform": "抖音",
        "title": "大药房账号",
        "body": "口感酸甜。" + FILTER_NOTICE,
        "is_brand_matrix": True,
    },
    {
        "inventory_id": "inv-00000000a4",
        "platform": "小红书",
        "title": "KOC 分享",
        "body": "日常调理分享。" + FILTER_NOTICE,
        "is_koc": True,
    },
]


async def _filter_ready_project(service) -> dict:
    project = await _new_project(service)
    project_dir, data = service._read_owned_project_with_dir(
        "workflow-user", project["project_id"]
    )
    data["product_type"] = "OTC"
    data["workflow"]["current_step"] = 6
    data["workflow"]["state"] = "COMPLIANCE_FILTER"
    service._write_project(project_dir, data)
    return service.get_project("workflow-user", project["project_id"])


async def _run_filter(service, project, inventory=FILTER_INVENTORY) -> dict:
    _attach_models(service, [])
    return await service.run_compliance_filter(
        username="workflow-user",
        project_id=project["project_id"],
        ai_search=False,
        inventory=[dict(item) for item in inventory],
    )


@pytest.mark.asyncio
async def test_compliance_filter_three_tier_disposal_and_mandatory(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _filter_ready_project(service)
    with pytest.raises(PharmaTranslatorError, match="没有可过滤"):
        await _run_filter(service, project, inventory=[])

    project = await _run_filter(service, project)
    state = project["compliance_filter"]
    assert state["status"] == "blocked"
    assert state["filter_rule_version"] == "zr-otc-filter-1.0"
    assert project["workflow"]["step_status"]["6"] == "blocked"
    risks = state["risks"]
    by_item = {}
    for risk in risks:
        by_item.setdefault(risk["content_id"], []).append(risk)

    # 🔴 超说明书功效 + 🟢 删除型替换
    soft = by_item["inv-00000000a1"]
    assert {"提高血氧", "改善认知"} <= {
        r["matched_text"] for r in soft if r["category"] == "off_label"
    }
    assert any(r["level"] == "replace" and r["delete_only"] for r in soft)
    # 🔴 银发恐惧营销
    assert any(r["category"] == "silver_fear" for r in by_item["inv-00000000a2"])

    # 5.2 存量处置清单
    actions = {d["inventory_id"]: d["action"] for d in state["disposals"]}
    assert actions == {
        "inv-00000000a1": "takedown",
        "inv-00000000a2": "stop_promotion",
        "inv-00000000a3": "full_review",
        "inv-00000000a4": "revise",
    }
    takedown = next(d for d in state["disposals"] if d["action"] == "takedown")
    assert takedown["location"] == "腾讯新闻、抖音好物（2026-04-12）"

    # 5.3 每篇强制要素
    mandatory = {m["inventory_id"]: m for m in state["mandatory_elements"]}
    assert mandatory["inv-00000000a1"]["passed"] is False
    assert mandatory["inv-00000000a3"]["passed"] is True
    koc = {c["code"]: c["passed"] for c in mandatory["inv-00000000a4"]["checks"]}
    assert koc["koc_real"] is False and koc["notice"] is True
    assert state["category_summary"]["off_label"]["block"] >= 2
    assert state["category_summary"]["mandatory"]["block"] >= 2
    labels = {i["inventory_id"]: i["label"] for i in state["inventory"]}
    assert labels["inv-00000000a1"] == "blocked"
    assert labels["inv-00000000a3"] == "pass"


@pytest.mark.asyncio
async def test_compliance_filter_off_label_exempts_leaflet_indications(tmp_path):
    service = PharmaTranslatorService(tmp_path)
    project = await _filter_ready_project(service)
    project = await _run_filter(
        service,
        project,
        inventory=[{"title": "说明书内", "body": "治失眠。" + FILTER_NOTICE}],
    )
    assert not [
        r for r in project["compliance_filter"]["risks"] if r["category"] == "off_label"
    ]


@pytest.mark.asyncio
async def test_compliance_filter_confirmation_gates_and_receipt(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _filter_ready_project(service)
    project = await _run_filter(service, project)

    def confirm(payload):
        return _workflow_action(service, project, "confirm_compliance_filter", payload)

    good = _compliance_filter_payload(project, decision="adopt")
    with pytest.raises(PharmaTranslatorError, match="不可代签"):
        confirm({**good, "on_behalf": True})
    with pytest.raises(PharmaTranslatorError, match="合规部"):
        confirm({**good, "signer_title": "市场部"})
    with pytest.raises(PharmaTranslatorError, match="未逐条处理"):
        confirm({**good, "reviews": {}})
    with pytest.raises(PharmaTranslatorError, match="广审"):
        confirm({**good, "ad_review_schedule": {"apply_date": "2026/12/01"}})

    # 存量被修改 / 规则版本未同步 → 强制返工
    project_dir, data = service._read_owned_project_with_dir(
        "workflow-user", project["project_id"]
    )
    snapshot = json.loads(json.dumps(data))
    data["compliance_filter"]["inventory"][0]["body"] += "改过"
    service._write_project(project_dir, data)
    project = service.get_project("workflow-user", project["project_id"])
    with pytest.raises(PharmaTranslatorError, match="被修改"):
        confirm(good)
    data = json.loads(json.dumps(snapshot))
    data["compliance_filter"]["filter_rule_version"] = "zr-otc-filter-0.1"
    service._write_project(project_dir, data)
    project = service.get_project("workflow-user", project["project_id"])
    with pytest.raises(PharmaTranslatorError, match="未同步"):
        confirm(good)
    service._write_project(project_dir, snapshot)
    project = service.get_project("workflow-user", project["project_id"])

    # 疑难表述发起中睿专家答疑（Step 6 范围）
    risk_id = project["compliance_filter"]["risks"][0]["risk_id"]
    project = await service.create_compliance_expert_ticket(
        username="workflow-user",
        project_id=project["project_id"],
        question="“改善认知”删除后能否保留成分描述？",
        risk_ids=[risk_id],
    )
    ticket = project["compliance_tickets"][0]
    assert ticket["scope"] == "compliance_filter"

    project = confirm(good)
    assert project["workflow"]["current_step"] == 9
    state = project["compliance_filter"]
    assert state["status"] == "confirmed"
    record = state["record"]
    assert record["record_id"].startswith("ZR-CF-")
    assert record["kb_version"] and record["retrieval_date"]
    assert "中睿" in record["kb_builder"]
    assert record["ad_review_schedule"]["apply_date"] == "2026-12-01"
    assert record["disposal_count"] == 4
    assert record["expert_ticket_ids"] == [ticket["ticket_id"]]
    assert record["replace_adopted"] >= 1
    # 采纳的删除型替换写回存量内容
    soft = next(i for i in state["inventory"] if i["inventory_id"] == "inv-00000000a1")
    assert "提高血氧" not in soft["body"]
    assert soft["disposal_status"] == "done"
    assert all(d["status"] == "done" for d in state["disposals"])


@pytest.mark.asyncio
async def test_compliance_filter_local_model_and_kb_only_add_risks(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _filter_ready_project(service)
    provider = _JsonChatProvider(
        {
            "findings": [
                {
                    "content_id": "inv-00000000a3",
                    "level": "caution",
                    "matched_text": "口感酸甜",
                    "message": "口感描述需避免暗示功效",
                    "legal_basis": "《药品广告审查发布标准》",
                    "suggestion": "保持体验描述",
                    "kb_refs": ["kb-1"],
                },
                {
                    "content_id": "inv-00000000a3",
                    "level": "block",
                    "matched_text": "原文不存在",
                },
            ]
        }
    )
    _attach_models(service, [provider])

    async def fake_retrieve(query, kb_ids, kb_names, top_m_final, **_kwargs):
        return {
            "results": [
                {
                    "kb_name": "中睿合规库",
                    "doc_name": "OTC 平台规则",
                    "content": "OTC 内容须展示批准文号",
                    "score": 0.9,
                }
            ]
        }

    service.core_lifecycle.kb_manager = SimpleNamespace(retrieve=fake_retrieve)
    project = await service.run_compliance_filter(
        username="workflow-user",
        project_id=project["project_id"],
        kb_ids=["kb-a"],
        ai_search=False,
        inventory=[dict(item) for item in FILTER_INVENTORY],
    )
    state = project["compliance_filter"]
    ai_risks = [r for r in state["risks"] if r["source"] == "ai"]
    assert len(ai_risks) == 1 and ai_risks[0]["category"] == "ai"
    assert state["ai_review"]["finding_count"] == 1
    assert state["kb_hits"][0]["kb_name"] == "中睿合规库"
    # 模型不能撤销规则命中
    assert any(r["category"] == "off_label" for r in state["risks"])
    assert state["status"] == "blocked"


@pytest.mark.asyncio
async def test_compliance_filter_requires_step_six(tmp_path: Path):
    service = PharmaTranslatorService(tmp_path)
    project = await _new_project(service)
    with pytest.raises(PharmaTranslatorError, match="第 6 步"):
        await _run_filter(service, project)
