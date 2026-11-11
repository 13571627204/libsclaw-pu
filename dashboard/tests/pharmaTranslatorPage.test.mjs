import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import ts from "typescript";

const pageSource = await readFile(
  new URL("../src/views/PharmaTranslatorPage.vue", import.meta.url),
  "utf8",
);
const apiSource = await readFile(
  new URL("../src/api/pharmaTranslator.ts", import.meta.url),
  "utf8",
);

test("renders the nine required workflow steps", () => {
  for (const title of [
    "品名与说明书",
    "多维拆解",
    "文献验证",
    "场景生成",
    "竞品扫描",
    "合规过滤",
    "搜索词与优先级",
    "医学确认",
    "内容与审批",
  ]) {
    assert.match(pageSource, new RegExp(`title: "${title}"`));
  }
  const stepsBody = pageSource.slice(
    pageSource.indexOf("const workflowSteps = ["),
    pageSource.indexOf("const productTypes"),
  );
  assert.equal((stepsBody.match(/\btitle: "/g) || []).length, 9);
  assert.ok(
    stepsBody.indexOf('title: "竞品扫描"') <
      stepsBody.indexOf('title: "合规过滤"') &&
      stepsBody.indexOf('title: "合规过滤"') <
        stepsBody.indexOf('title: "搜索词与优先级"'),
  );
  assert.match(pageSource, /七步工作流/);
  assert.match(
    pageSource,
    /\{\{ displayStepNo\(currentStep\) \}\}\/\{\{ visibleWorkflowSteps\.length \}\}/,
  );
  assert.doesNotMatch(pageSource, /\}\}\/8 /);
  assert.match(pageSource, /Math\.min\(9,/);
  assert.doesNotMatch(pageSource, /Math\.min\(8,/);
  for (const step of [6, 7, 8, 9]) {
    assert.match(pageSource, new RegExp(`activeStep === ${step}"`));
  }
  assert.match(
    pageSource,
    /currentStep\.value === 9 &&\s*approvalDone\("market"\)/,
  );
  assert.match(pageSource, /project\.value\?\.workflow\?\.current_step/);
  assert.doesNotMatch(pageSource, /activeTab\.value === 'keywords'/);
});

test("step 6 compliance filter runs three-tier filtering and compliance sign-off", () => {
  assert.match(apiSource, /runComplianceFilter/);
  assert.match(
    apiSource,
    /\/pharma-translator\/projects\/\$\{projectId\}\/compliance-filter\/run/,
  );
  assert.match(apiSource, /["']confirm_compliance_filter["']/);
  assert.match(apiSource, /compliance_filter\?: ComplianceFilterState/);
  assert.match(
    pageSource,
    /pharmaTranslatorApi\.runComplianceFilter\(projectId, \{/,
  );
  assert.match(pageSource, /"confirm_compliance_filter"/);
  for (const marker of [
    "合规过滤",
    "🔴 一级 红线拦截",
    "🟡 二级 谨慎标记",
    "🟢 三级 建议替换",
    "❌ 删除，无替换",
    "品牌存量",
    "竞品样本",
    "处方药禁止大众媒体广告，只能走患者管理路径",
    "合规部确认并进入下一步",
    "AI 搜索交叉验证",
    "省级药品监督管理部门",
  ]) {
    assert.ok(pageSource.includes(marker), marker);
  }
  const confirmBody = pageSource.slice(
    pageSource.indexOf("function confirmComplianceFilter"),
    pageSource.indexOf("function ticketAnswerDraft"),
  );
  for (const key of [
    "signer_name",
    "signer_title",
    "reviews",
    "disposals",
    "ad_review_schedule",
    "apply_date",
  ]) {
    assert.match(confirmBody, new RegExp(key));
  }
  assert.match(confirmBody, /includes\("合规"\)/);
  assert.match(confirmBody, /filterPendingReviewCount/);
  assert.match(pageSource, /ticket\.scope === "compliance_filter"/);
  assert.match(pageSource, /ticket\.scope !== "compliance_filter"/);
  assert.match(pageSource, /step === 6 \|\| step === 9/);
});

test("competitor scan step exposes three collection tiers and P0/P1 gap confirmation", () => {
  assert.match(pageSource, /竞品内容扫描（基于真实数据）/);
  assert.match(pageSource, /confirm_competitor/);
  assert.match(apiSource, /scanCompetitors/);
  assert.match(apiSource, /analyzeCompetitors/);
  for (const marker of [
    "P0",
    "P1",
    "gap_map",
    "user_voices",
    "platform_strategy",
  ]) {
    assert.match(pageSource, new RegExp(marker));
  }
});

test("workflow API sends action data and comment to the backend contract", () => {
  assert.match(
    apiSource,
    /\/pharma-translator\/projects\/\$\{projectId\}\/workflow\/actions/,
  );
  assert.match(apiSource, /\{ action, data, comment \}/);
  for (const action of [
    "confirm_profile",
    "confirm_dimensions",
    "confirm_scenes",
    "confirm_keywords",
    "confirm_evidence",
    "generate_contents",
    "market_confirm",
    "compliance_confirm",
    "final_approve",
    "rework",
    "terminate",
  ]) {
    assert.match(apiSource, new RegExp(`["']${action}["']`));
  }
});

test("client checks supported extensions and image/PDF size before upload", () => {
  for (const extension of ["jpg", "jpeg", "png", "webp", "pdf"]) {
    assert.ok(
      pageSource.includes(`"${extension}"`) ||
        pageSource.includes(`'${extension}'`),
    );
  }
  assert.ok(pageSource.includes("100 * 1024 * 1024"));
  assert.ok(pageSource.includes("20 * 1024 * 1024"));
  assert.ok(pageSource.includes("上传文件为空"));
});

test("evidence and content steps remain gated by confirmed source data", () => {
  assert.ok(pageSource.includes("claim.evidence_level"));
  assert.ok(pageSource.includes("claim.medical_confirmed"));
  assert.match(pageSource, /claims\.value\.some\(/);
  assert.match(pageSource, /无证据卖点不能进入内容白名单/);
  assert.match(pageSource, /hasBlockingRisk/);
  assert.match(pageSource, /RX 禁止大众媒体广告/);
  assert.match(pageSource, /只能走患者管理路径/);
});

test("compliance filter exposes KB, model review, expert tickets and non-proxy sign-off", () => {
  assert.match(apiSource, /\/compliance\/knowledge-base/);
  assert.match(apiSource, /\/compliance\/review/);
  assert.match(apiSource, /expert-tickets/);
  assert.match(pageSource, /signer_name/);
  assert.match(pageSource, /citation_covered: true/);
  assert.match(pageSource, /不可代签/);
  assert.match(pageSource, /中睿/);
  assert.match(pageSource, /pendingReviewCount/);
  for (const label of ["✅ 合规", "⚠️ 谨慎", "❌ 违规"]) {
    assert.ok(pageSource.includes(label), label);
  }
});

test("profile confirmation blocks empty, sourceless, and unconfirmed critical fields", () => {
  assert.ok(pageSource.includes("!field.value.trim()"));
  assert.ok(pageSource.includes("!field.source_text.trim()"));
  assert.ok(pageSource.includes("!field.confirmed"));
});

test("rework and termination require a non-empty comment", () => {
  assert.match(pageSource, /返工必须填写批注/);
  assert.match(pageSource, /终止必须填写原因/);
  assert.match(pageSource, /target_step: reworkTarget\.value/);
  assert.match(pageSource, /v-if="false" class="workflow-controls"/);
  assert.match(pageSource, /v-if="!isApproved"\s+color="error"/);
});

test("project switching resets platform selections and preserves manual keyword provenance", () => {
  const openProjectBody = pageSource.slice(
    pageSource.indexOf("async function openProject"),
    pageSource.indexOf("async function runAction"),
  );
  assert.match(openProjectBody, /selectedPlatforms\.value = \[\]/);
  assert.match(pageSource, /manual_input: "人工输入"/);
  assert.match(pageSource, /manual_review: "人工校对"/);
  assert.match(apiSource, /\| "manual_input"/);
  assert.match(apiSource, /\| "manual_review"/);
});

test("dimension generation exposes loading, errors and evidence without auto-confirming", () => {
  assert.match(apiSource, /\/dimensions\/generate/);
  assert.match(apiSource, /timeout: 240000/);
  assert.match(apiSource, /search_mode: payload\.searchMode/);
  assert.match(pageSource, /:loading="dimensionsLoading"/);
  assert.match(pageSource, /v-if="dimensionsError"/);
  assert.match(pageSource, /按药品名称检索并生成多维/);
  assert.match(
    pageSource,
    /品牌名和产品名、主治功能、成分、批号、对症人群、现有渠道/,
  );
  assert.match(pageSource, /channels: "现有渠道"/);
  assert.match(pageSource, /brand_product: "品牌名和产品名"/);
  assert.match(pageSource, /v-model="dimensionKbIds"/);
  assert.match(pageSource, /v-if="item\.is_external"/);
  assert.match(pageSource, /item\.source_url/);
  assert.match(pageSource, /dimensionGeneration\.warnings/);
  assert.doesNotMatch(pageSource, /本地模型|本地 AI/);
  assert.match(pageSource, /模型生成/);
  assert.match(pageSource, /item\.model_provider/);
  assert.match(pageSource, /待人工确认/);
  assert.match(pageSource, /source\.evidence_id/);
  assert.match(pageSource, /source\.source_label/);
  assert.match(pageSource, /project\.value\?\.project_id !== projectId/);
  const generateBody = pageSource.slice(
    pageSource.indexOf("async function generateDimensions"),
    pageSource.indexOf("async function generateDimensions") + 1600,
  );
  assert.match(
    generateBody,
    /pharmaTranslatorApi\.generateDimensions\(projectId, \{/,
  );
  assert.doesNotMatch(generateBody, /confirmed\s*=\s*true/);
});

test("literature step requires medical-department signoff with four-item checklist", () => {
  assert.match(pageSource, /人工确认节点 · 医学部签字/);
  assert.match(pageSource, /不可代签/);
  for (const key of [
    "claims_complete",
    "matches_valid",
    "levels_accurate",
    "redlines_complete",
  ]) {
    assert.match(pageSource, new RegExp(`key: "${key}"`));
  }
  assert.match(pageSource, /checklist: \{ \.\.\.literatureChecklist\.value \}/);
  assert.match(
    pageSource,
    /literatureSignerQualified\.value &&\s*literatureChecklistDone\.value/,
  );
  assert.match(pageSource, /🟢 强证据/);
  assert.match(pageSource, /ingredients: "🧪"/);
  assert.match(apiSource, /checklist\?: Record<string, boolean>/);
});

test("scene step shows dimension-to-persona flow and estimated priority matrix", () => {
  assert.match(pageSource, /输入 · 说明书原文/);
  assert.match(pageSource, /AI 先拆出四个维度/);
  assert.match(pageSource, /AI 翻译/);
  assert.match(pageSource, /TA 搜的是：\{\{ scene\.search_keywords\[0\] \}\}/);
  assert.match(pageSource, /【\{\{ scene\.content_hook \}\}】/);
  assert.match(pageSource, /场景优先级矩阵/);
  assert.match(pageSource, /估算值，待人工确认/);
  for (const label of ["市场规模", "内容可做度", "推荐优先级"]) {
    assert.match(pageSource, new RegExp(`<th>${label}</th>`));
  }
  assert.match(pageSource, /P0: "首打", P1: "重点", P2: "差异化"/);
  assert.match(
    pageSource,
    /channelCategories = \["医院", "药店", "诊所", "药品零售商", "药品批发商"\]/,
  );
});

test("automatic generation is explicit after confirmation/open and never watched", () => {
  assert.match(
    pageSource,
    /confirmedProfile = action === "confirm_profile" && currentStep.value === 2/,
  );
  assert.match(pageSource, /await autoGenerateDimensions\(true\)/);
  assert.match(pageSource, /await autoGenerateDimensions\(\)/);
  assert.match(pageSource, /正在用已配置的生成模型检索当前上传资料/);
  assert.match(pageSource, /v-if="item.is_inferred"/);
  assert.match(pageSource, /不是原文人群事实/);
  assert.match(pageSource, /context !== projectContext/);
  assert.doesNotMatch(pageSource, /watch\([\s\S]{0,200}autoGenerateDimensions/);
});

function dimensionHarness(generate) {
  const start = pageSource.indexOf("async function autoGenerateDimensions");
  const end = pageSource.indexOf("async function confirmDimensions", start);
  const body = ts.transpileModule(pageSource.slice(start, end), {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const data = {
    project_id: "p1",
    workflow: { version: 2 },
    dimensions: [
      { dimension_id: "ingredients", items: [] },
      { dimension_id: "audience", items: [] },
    ],
  };
  const context = {
    project: { value: data },
    readOnly: { value: false },
    currentStep: { value: 2 },
    actionLoading: { value: false },
    dimensionsLoading: { value: false },
    openingProjectId: { value: "" },
    analyzing: { value: false },
    dimensionsError: { value: "" },
    dimensions: { value: data.dimensions },
    dimensionAutoAttempts: new Set(),
    dimensionRequests: new Set(),
    actionRequests: new Set(),
    projectContext: 0,
    dimensionKbIds: { value: [] },
    dimensionSearchMode: { value: "auto" },
    dimensionKey: (dimension) => dimension.dimension_id,
    pharmaTranslatorApi: { generateDimensions: generate },
    normalizeProject: (project) => project,
    notify: () => {},
    loadHistory: async () => {},
    extractError: (error) => error.message,
  };
  vm.createContext(context);
  vm.runInContext(body, context);
  return context;
}

test("failed automatic attempt is once per project/version while retry stays callable", async () => {
  let calls = 0;
  const context = dimensionHarness(async () => {
    calls++;
    throw new Error("local unavailable");
  });
  await context.autoGenerateDimensions(true);
  await context.autoGenerateDimensions();
  await context.autoGenerateDimensions(true);
  assert.equal(calls, 1);
  assert.equal(context.dimensionsError.value, "local unavailable");
  assert.equal(context.dimensionsLoading.value, false);
  await context.generateDimensions();
  assert.equal(calls, 2);
  context.project.value.workflow.version = 3;
  await context.autoGenerateDimensions();
  assert.equal(calls, 3);
});

test("loaded populated projects do not auto-generate, confirmation still triggers once", async () => {
  let calls = 0;
  const context = dimensionHarness(async () => {
    calls++;
    throw new Error("offline");
  });
  context.dimensions.value.forEach((dimension) =>
    dimension.items.push({ text: "原文" }),
  );
  await context.autoGenerateDimensions();
  assert.equal(calls, 0);
  await context.autoGenerateDimensions(true);
  assert.equal(calls, 1);
});

test("switching project during generation cannot replace new project or clear its loading", async () => {
  let resolve;
  const context = dimensionHarness(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  const pending = context.autoGenerateDimensions(true);
  assert.equal(context.dimensionsLoading.value, true);
  context.projectContext++;
  const next = { project_id: "p2", workflow: { version: 9 }, dimensions: [] };
  context.project.value = next;
  context.dimensionsLoading.value = true;
  resolve({
    data: {
      data: {
        project_id: "p1",
        workflow: { version: 3 },
        dimensions: [{ items: [] }],
      },
    },
  });
  await pending;
  assert.equal(context.project.value, next);
  assert.equal(context.dimensionsLoading.value, true);
  assert.equal(context.dimensionRequests.size, 0);
});

test("successful empty dimension response does not automatically retry the new version", async () => {
  let calls = 0;
  const context = dimensionHarness(async () => {
    calls++;
    return {
      data: {
        data: { project_id: "p1", workflow: { version: 3 }, dimensions: [] },
      },
    };
  });
  await context.autoGenerateDimensions(true);
  await context.autoGenerateDimensions();
  assert.equal(calls, 1);
  assert.equal(context.dimensionsLoading.value, false);
});

test("delivery export is separate from draft keyword export", () => {
  assert.match(apiSource, /delivery\.json/);
  assert.match(pageSource, /导出草稿关键词 CSV/);
  assert.match(pageSource, /:disabled="!isApproved"/);
});
