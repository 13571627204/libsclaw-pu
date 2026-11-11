# 译言·药企 C 端内容翻译器：七步确定性 MVP 操作与验收

文档日期：2026-11-02。

完整的七步企业版目标、系统架构、数据模型、接口、权限、安全和分期开发计划见 [《译言·药企 C 端内容翻译器开发需求与系统设计文档》](./pharma-translator-development-design.md)。本文仅描述当前仓库中已经实现并可自动化验收的七步确定性 MVP。

本模块实现一个可追溯、不可跳步的七步 MVP：说明书上传与字段确认、四维拆解、企业商品文献验证、场景确认、关键词确认、卖点证据确认、内容生成与合规审批。当前内容、场景、文献匹配和合规判断均为确定性规则结果，不把模型预测伪装成真实搜索数据、医学证据或正式法规结论。

> 重要边界：本系统是内容生产、证据追溯和合规辅助工具，不替代医学部、合规部、法务部门或行政广告审查。只有完成市场确认、合规确认和终审的项目才能导出“可发布内容包”。

## 1. 启动与入口

在仓库根目录运行：

```powershell
.\scripts\dev.ps1
```

脚本会输出实际前后端端口。默认情况下：

- 前端工作台：`http://localhost:3007/#/pharma-translator`
- 后端 API：`http://localhost:6185/api/v1/pharma-translator`

如果端口已占用，脚本会选择后续可用端口，应以控制台输出为准。

## 2. OCR 与文件处理范围

支持 JPG、JPEG、PNG、WEBP 和单个 PDF：

- 单张图片最大 20 MB。
- PDF 最大 100 MB、100 页。
- 后端检查扩展名、文件魔数、图片可解码性和 WEBP 标识。
- 图片质量检查包括分辨率、可能模糊和可能反光提示。

文字来源按以下顺序选择：

1. 用户在页面粘贴的“识别文本校对”，来源标记为 `manual_review`；
2. PDF 自带文本层；
3. `PHARMA_OCR_ENDPOINT` 配置的企业 OCR Provider；
4. 本地 RapidOCR；
5. 可选 Tesseract 回退。

人工校对文本不会被标记成文档直接证据，只能形成弱证据候选。OCR Provider 或本地 OCR 返回块坐标时，系统会尽量将字段关联到对应 `polygon`，并融合 OCR 块/页面置信度。

### 2.1 企业 OCR Provider

```powershell
$env:PHARMA_OCR_ENDPOINT = 'https://ocr.example.com/v1/recognize'
$env:PHARMA_OCR_API_KEY = 'replace-with-secret'
```

Provider 接收 `multipart/form-data` 的 `file` 字段，响应示例：

```json
{
  "pages": [
    {
      "page_no": 1,
      "confidence": 0.96,
      "text": "可选的整页文字",
      "blocks": [
        {
          "text": "【功能主治】……",
          "confidence": 0.97,
          "polygon": [[10, 20], [500, 20], [500, 80], [10, 80]]
        }
      ]
    }
  ]
}
```

生产环境只能配置企业批准的私有化或合规云服务。

## 3. 七步用户操作

### 第 1 步：品名、说明书与产品档案

1. 输入药品名称，或留空让系统从说明书识别。
2. 选择产品类型，或保留“自动识别”。
3. 上传文件，点击“开始识别并生成表”。
4. 核对 8 个关键字段：药品名称、批文类型、产品类型、规格、用法用量、不良反应、功能主治、批准文号。
5. 每个字段检查机器值、正式值、来源类型、页码、原文、置信度和坐标。
6. 对所有关键字段勾选人工确认，执行 `confirm_profile`。

关键字段为空、没有来源或未确认时，后端阻断通过，不允许只靠前端修改绕过。

### 第 2 步：四维拆解与安全约束

系统从已确认字段确定性生成：

- 成分：当前 8 字段中没有成分资料时保持空，不推断。
- 主治功能：仅使用已确认的功能主治/适应内容。
- 对症人群：没有直接原文时保持空，不从功效反推人群。
- 背书：批准文号、批文类型和产品类型。
- 现有渠道、品牌名和产品名：由下方"按药品名称检索生成"补充；品牌名和产品名默认预填上传资料识别的药品名称。
- 安全约束：用法用量、不良反应，独立于营销卖点保存。

#### 按药品名称检索生成（`POST /projects/{id}/dimensions/generate`）

请求体（均可选）：`kb_ids`/`kb_names`（本地药企知识库，最多 8 个）、`search_mode`（`auto`/`standard`/`deep`/`none`，`auto` 优先 TikHub，其次 opencli）、`search_platforms`（默认电商、知乎、小红书）。

流程：从上传资料识别药品名称 → 以药品名称检索本地药企知识库与搜索采集（同时复用第 5 步已采集且包含药品名称的内容）→ 与上传 OCR 全文一起编号成证据交给已配置的生成模型 → 校验后合并为待确认候选。

约束：

- 模型本身禁止联网、禁止凭记忆补写，每条候选必须引用证据编号；成分只能引用上传资料。
- 现有渠道固定为五类：医院、药店、诊所、药品零售商、药品批发商。模型输出先归类（电商/网上药店→药品零售商，经销/配送→药品批发商），所引证据原文须出现该类渠道关键词，否则丢弃；同类去重。页面以五个标签显示命中情况。
- 品牌名和产品名须与证据原文高度吻合（≥80%），主治功能拦截"治愈/根治/无副作用"等绝对化表述，对症人群拦截年龄、孕哺、禁忌等风险推断；不合格条目丢弃并计入 `dropped`。
- 外部来源条目标注 `is_external`、来源标签与 `source_url`，页面展示"查看原文"。
- 未识别药品名称、未选知识库、未配置搜索或采集失败时降级并记入 `dimension_generation.warnings`，不阻断生成。
- 已确认的品牌名和产品名、现有渠道会写入第 4 步场景卡片（`brand_product`、`existing_channels`），非处方场景的首个品牌名加入搜索词。

用户逐项确认四维卡片与安全信息后执行 `confirm_dimensions`。有原文来源但未确认的项目会被阻断；没有原文来源的条目（例如第 1 步手工补录的字段）不参与确认，在确认时由后端统一移出四维卡片，字段值仍保留在产品档案中，但不会进入卖点候选。确认后系统从已确认四维卡片抽取候选卖点（成分/功效/人群/背书四类，编号 F01 起，上限 20 条），进入文献验证。

### 第 3 步：企业商品文献验证（卖点—文献双向验证）

强制关卡：没有文献支撑的卖点不进入场景与内容生成。

1. 文献来源（可并用）：
   - 上传企业文献（PDF/DOCX，单份 ≤100 MB，每项目 ≤20 份），上传时声明文献类型：说明书/药典国家标准/临床研究/检测报告/专利批文/其他；系统提取文本并按段落切片（保留页码）。扫描版 PDF 无文字层时拒绝并提示先 OCR 或转 DOCX。
   - 选择本地知识库（药企知识内容），匹配时调用 `kb_manager.retrieve` 检索；知识库证据按库名/文档名推断文献类型并如实标注。
   - 说明书原文始终作为内置语料参与匹配。
2. 执行 `POST .../literature/match`（或页面上“开始文献匹配”）：对每条卖点做确定性关键词覆盖度匹配，知识库检索自动带入第 1 步识别/确认的药品名。召回引用后调用本地生成模型做语义级辅助分析（可选增强）：
   - 模型只依据召回的引用片段判定，禁止编造文献；未配置模型或调用失败时保留确定性结果并如实提示（`literature.ai_notice`），不把模型输出伪装成医学证据；
   - 模型建议上调证据等级时封顶于确定性规则等级（禁用联想推论）；判为“引用不支撑”时可下调至 🔴，人工确认环节可带理由恢复；
   - 模型引用的 citation_id 必须真实存在于召回结果中，否则该条建议整体忽略；
   - 每条卖点的模型建议与依据保存在 `ai_analysis`（含模型来源标识），供人工复核。
   三色标签：
   - 🟢 强证据：命中该卖点类型的优先文献源（成分→药典/检测报告且含量可追溯；功效→说明书原文或临床研究；人群→必须有说明书原文引用且覆盖度 ≥0.6，与说明书口径一致；背书→专利批文或说明书，卖点或引文中必须含可核验编号），覆盖度 ≥0.6。说明书为人工校对来源时最高只评 🟡。
   - 🟡 弱证据：有引用但非优先源或覆盖度不足，可用但需弱化表述。
   - 🔴 无证据：无任何引用，禁止使用（即使“业内都这么说”）。
   匹配完成后卖点列表按 🟢 强证据 → 🟡 弱证据 → 🔴 无证据 排序输出。
3. 每条卖点输出「卖点—场景—话术」三联卡：卖点编号、卖点原文、证据等级、文献来源（多来源以 “ + ” 连接，含页码）、可用场景、禁用场景、合规话术示范 ✅、违规话术警示 ❌、需加注说明（按批文类型区分 RX/OTC/保健食品）。卖点按 🧪 成分 / 🎯 功效 / 👥 人群 / 🏆 背书 分类展示；抽取少于 10 条时页面提示补充产品档案。
4. 人工逐条勾选后执行 `confirm_literature`：至少一条 🟢/🟡 卖点被接受；🔴 卖点不能被接受；调整证据等级必须填写理由；无引用卖点禁止上调等级。
   🔍 人工确认节点（`signoff`）：
   - 确认人必须为企业医学部/学术部人员（`signer_title` 须含“医学”或“学术”），不可代签（姓名/职务含“代签/代为/委托”等字样或 `on_behalf` 时拒绝）；
   - `signoff.checklist` 四项须全部为 true：`claims_complete` 卖点清单完整、`matches_valid` 文献匹配成立、`levels_accurate` 三色标签准确、`redlines_complete` 禁用卖点无遗漏；
   - 输出凭证：卖点—文献—话术三联表 + 医学部签字，可导出 CSV；
   - 返工：弱证据被标为强证据、关键文献遗漏、禁用卖点未纳入红线 → 补充文献或下调证据等级后重新签字。
5. 未被接受的卖点全部进入 `unusable_claims`（不可用卖点库/红线清单），随项目归档并可在版本快照中追溯。

确认通过后，场景候选仅引用通过验证的卖点，进入第 4 步。

### 第 4 步：消费者场景（场景翻译引擎）

系统只使用第 3 步通过文献验证（🟢 强证据/🟡 弱证据）的卖点作为翻译素材，按四层确定性流程把说明书术语翻译成生活场景；🔴 无证据卖点已进入不可用卖点库，不参与场景构建。

四层处理流程：

1. 症状关键词解构：命中内置词典（如“虚烦不眠/失眠”→【睡不着/睡前烦躁/脑子停不下来】）并归入场景簇（睡眠困扰/情绪内耗/精力透支/记性变差/胃口差/身体信号/抵抗力焦虑/气色焦虑）；关键词只锚定已验证功效卖点原文，不超出说明书范围，未命中词条回退到卖点原文。
2. 人群画像推演：按场景簇输出人群画像（如 25-35 岁一线城市职场女性、熬夜程序员、更年期女性、备考学生），并展示锚定的人群卖点编号与原文（`audience_scope`）供确认人核对。
3. 场景三要素映射：时间（凌晨3点）+ 地点（卧室）+ 触发事件（刷手机到2点）。
4. 语言翻译：医学术语 → 用户内心独白（如“虚烦不眠”→“明明很累却睡不着，脑子停不下来”）。

每个场景输出标准模板字段：场景编号（S01 起）、场景名称、目标人群、核心痛点、搜索关键词（标注“内部估算，不代表平台真实搜索量”）、用户内心独白、内容钩子、推荐信任锚（由关联卖点类型映射：成分/说明书主治/真实用户经历/医师背书）、关联已验证卖点（含卖点编号与 🟢/🟡 标记）、禁用话题、建议平台、证据覆盖率。

- 典型产出：自动生成至多 12 个场景候选（默认预选前 3 个），用户勾选 1—5 个作为重点打透。
- 场景真实度锚点：可通过 `POST .../user-voices` 导入经授权的平台用户原话（每条必须填写来源声明，4—200 字，上限 50 条，仅第 3—4 步可导入/删除）；场景生成或样本变更时按症状关键词重叠度自动挂载至多 3 条原话。未导入样本时场景如实提示锚点缺失，系统不生成任何模拟评论。
- 人工确认（市场部/品牌经理）：每个场景支持勾选、强打/弱打标注、批注与删除；已删除场景不能被选定。执行 `confirm_scenes` 后审计评论自动记录“场景选定 S01（强打）…；删除 S12”凭证。
- RX 只生成企业内部或专业人员医学教育场景；RX 场景出现大众营销平台时强制阻断。
- 场景总览（页面顶部）：按"输入·说明书原文 → AI 先拆出四个维度（主治功能/对症人群/现有渠道/品牌名和产品名）→ AI 翻译 → 客群卡片"展示。客群卡片包含人群、内心独白、"TA 搜的是：首个搜索词"和【内容钩子】。
- 场景优先级矩阵：每个未删除场景给出市场规模、竞品饱和度、内容可做度三项 ★ 星级（高/中/低），以及推荐优先级 P0 首打 / P1 重点 / P2 差异化。
  - 市场规模：依据搜索词数与用户原话数估算。
  - 竞品饱和度：取自竞品分析的 `scene_saturation`，未采集时显示"未采集"。
  - 内容可做度：依据证据覆盖率估算。
  - 推荐优先级：按综合分三等分；强打标注加分、弱打标注减分；竞品缺口中已人工确认的 P0/P1 优先采用。
  - 所有指标均为前端估算，标注"待人工确认"，不代表平台真实热度。

### 第 5 步：关键词与优先级

关键词只来自已确认字段，不使用用法用量、不良反应等安全字段作为营销词。执行 `confirm_keywords` 前至少选择一个非空关键词。

当前关键词来源为 `document_extracted`、`manual_review` 或人工输入，优先级是内部估算值。响应明确包含：

- `is_estimate: true`
- `source_observed: false`
- 来源字段、原文、页码和证据覆盖情况

它们不代表平台真实搜索量或真实热度。

### 第 6 步：卖点与证据确认

系统使用第 3 步通过文献验证的卖点作为 Claim，并保留：

- `claim_id` 与卖点编号 `claim_no`（F01…）
- 卖点文字和类型
- 来源字段、页码和原文
- 文献引用（说明书/企业文献/知识库）与 `strong`、`weak` 证据等级
- 弱证据卖点的弱化话术（`allowed_expression`），内容生成时使用弱化表达
- 医学确认状态

说明书直接抽取可评为强证据候选；人工校对文本最高只能作为弱证据候选。医学确认人员执行 `confirm_evidence`。至少一条卖点必须有原文证据、证据等级为强/弱并完成医学确认，才能进入第 7 步。

### 第 7 步：内容、合规、审批与交付

1. 选择平台、数量和语气，执行 `generate_contents`。
2. 内容仅组装医学确认的 Claim，每个事实句保存 `claim_id`。
3. 合规过滤引擎（规则底座由中睿医药商学院知识库萃取，带知识库版本号与规则版本号）对每条内容按三级规则扫描并贴标：
   - 🔴 一级红线（`block`，标记 ❌ 违规）：RX 禁止大众媒体广告，社媒内容直接拒绝生成、只能走患者管理路径；OTC 绝对化用语（治愈/根治/见效快/最有效/药到病除/立竿见影）；保健品“治疗/预防疾病”；医疗器械绝对化与疗效承诺；消字号/食字号医疗效果宣称。
   - 🟡 二级谨慎（`caution`，标记 ⚠️ 谨慎）：需免责声明、建议改疑问句、需加“个体差异”、医师出镜身份标注。
   - 🟢 三级替换（`replace`）：治疗失眠→睡眠困扰、降血压→血压管理期、缓解疼痛→不适时、有效→可能有帮助、根治→改善、见效快→感受明显、无副作用→温和配方。
   - 平台规则（小红书/抖音/视频号/公众号/电商/知乎）分平台维护。
4. 合规部可执行“知识库检索 + 模型复核”：从中睿合规知识库与所选本地药企知识库检索条文，由已配置模型复核并补充 `source=ai` 风险，结果写入 `compliance.ai_review`。
5. 疑难问题可发起中睿合规专家答疑工单（24 小时响应），答复留痕。
6. 合规确认（`compliance_confirm`）必须由合规部本人签字，不可代签：
   - 签字人必填，职务须含“合规”，`on_behalf`/`proxy_sign` 被拒绝；
   - 谨慎项和替换项须逐条选择采纳/保留，谨慎项须填写批注；采纳的替换会写回内容；
   - 必须勾选“文献引证已完整覆盖所有合规风险点”（`citation_covered`）；
   - 存在违规拦截或规则/知识库版本落后时强制返工重跑；
   - 输出合规审查记录：中睿知识库版本号、规则版本、检索日期、签字人、复核时长、专家工单。
7. 依次执行 `market_confirm`、`compliance_confirm`、`final_approve`。
8. 终审后导出 `delivery.json` 内容交付包。

合规接口：`GET /api/v1/pharma-translator/compliance/knowledge-base`、`POST .../projects/{id}/compliance/review`、`POST .../projects/{id}/compliance/expert-tickets`、`POST .../projects/{id}/compliance/expert-tickets/{ticket_id}/answer`。

当前生成物是待人工审核草稿，不会自动发布到外部平台。

## 4. 工作流状态、版本和动作

项目响应包含：

```json
{
  "workflow": {
    "current_step": 1,
    "state": "PRODUCT_CONFIRMATION",
    "status": "active",
    "version": 1,
    "step_status": {
      "1": "pending",
      "2": "locked",
      "3": "locked",
      "4": "locked",
      "5": "locked",
      "6": "locked",
      "7": "locked"
    }
  }
}
```

步骤状态由后端维护，不能通过切换页面 Tab 跳过。工作流状态依次为：

```text
PRODUCT_CONFIRMATION
→ DIMENSION_CONFIRMATION
→ LITERATURE_VALIDATION
→ SCENE_CONFIRMATION
→ KEYWORD_CONFIRMATION
→ MEDICAL_CONFIRMATION
→ CONTENT_GENERATION / COMPLIANCE_CONFIRMATION
→ MARKET_CONFIRMATION
→ FINAL_APPROVAL
→ APPROVED
```

每个成功动作都会：

- 将旧项目写入 `versions/vNNNN_<action>.json`；
- 将版本号递增；
- 在 `version_history` 记录快照；
- 在 `audit_events` 追加操作人、时间、批注、步骤和版本。

`rework` 必须填写批注并指定当前或前置步骤。`terminate` 必须填写终止原因；终止后项目只读。

## 5. API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/pharma-translator/analyze` | 上传并识别说明书 |
| GET | `/api/v1/pharma-translator/projects` | 当前用户项目列表 |
| GET | `/api/v1/pharma-translator/projects/{id}` | 项目详情和七步状态 |
| POST | `/api/v1/pharma-translator/projects/{id}/workflow/actions` | 执行工作流动作 |
| POST | `/api/v1/pharma-translator/projects/{id}/confirm` | 旧版字段＋关键词确认兼容接口 |
| POST | `/api/v1/pharma-translator/projects/{id}/literature` | 上传企业文献（PDF/DOCX，`doc_kind` 声明类型，单次 ≤5 份） |
| DELETE | `/api/v1/pharma-translator/projects/{id}/literature/{doc_id}` | 移除文献（仅第 3 步） |
| POST | `/api/v1/pharma-translator/projects/{id}/literature/match` | 执行卖点—文献匹配（可传 `kb_ids`/`kb_names` 选用本地知识库） |
| GET | `/api/v1/pharma-translator/projects/{id}/literature/triple-table.csv` | 导出卖点—文献—话术三联表（含医学部签字） |
| GET | `/api/v1/pharma-translator/literature/redlines` | 企业不可用卖点库 / 红线清单 |
| GET | `/api/v1/pharma-translator/projects/{id}/literature/archive` | 查询同 SKU 历史验证归档 |
| POST | `/api/v1/pharma-translator/projects/{id}/literature/archive/reuse` | 复用同 SKU 历史验证记录 |
| POST | `/api/v1/pharma-translator/projects/{id}/user-voices` | 导入平台真实用户原话（评论抽样，每条须带来源声明，仅第 3—4 步） |
| DELETE | `/api/v1/pharma-translator/projects/{id}/user-voices/{voice_id}` | 移除一条用户原话并刷新场景锚点 |
| GET | `/api/v1/pharma-translator/projects/{id}/source` | 获取原始文件 |
| GET | `/api/v1/pharma-translator/projects/{id}/keywords.csv` | 导出关键词草稿表 |
| GET | `/api/v1/pharma-translator/projects/{id}/delivery.json` | 导出终审内容交付包 |

接口使用现有 Dashboard JWT 或具有 `data` scope 的 API Key。

工作流请求推荐使用 `data`：

```json
{
  "action": "generate_contents",
  "data": {
    "platforms": ["公众号"],
    "count": 2,
    "tone": "专业、克制、易懂"
  },
  "comment": "生成第一轮审核草稿"
}
```

为兼容早期客户端，后端也接受同结构的 `payload` 字段；新代码应统一使用 `data`，避免表单契约不一致造成 HTTP 422。

动作名称：

```text
confirm_profile
confirm_dimensions
confirm_literature
confirm_scenes
confirm_keywords
confirm_evidence
generate_contents
market_confirm
compliance_confirm
final_approve
rework
terminate
```

返工示例：

```json
{
  "action": "rework",
  "data": {"target_step": 3},
  "comment": "场景范围需要重新确认"
}
```

## 6. 主要硬阻断

以下校验在后端执行：

- 关键字段为空、无来源或未人工确认；
- 试图跳过或逆序执行工作流；
- 四维/安全信息有值但未确认；
- 未执行文献匹配就确认文献验证；
- 接受无文献证据（🔴）的卖点，或不填写理由调整证据等级；
- 没有任何一条被接受的强/弱证据卖点；
- 在非第 3 步上传、删除文献或执行文献匹配；
- 场景选择少于 1 个或超过 5 个，或已删除场景被同时选定；
- 第 3—4 步之外导入/删除用户原话，或原话缺少来源声明；
- RX 进入大众平台营销路径；
- 没有选中的有效关键词；
- 没有原文证据或未经医学确认的 Claim；
- 内容事实没有绑定已确认 Claim ID；
- 命中绝对化、治愈/根治、无副作用规则；
- 未完成市场确认就提交合规确认；
- 未完成市场和合规确认就提交终审；
- 未终审通过就导出可发布内容包；
- 返工或终止没有填写原因；
- 终止项目继续写入。

## 7. 自动化验收

后端核心回归：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pharma_translator.py tests/test_pharma_workflow.py tests/test_pharma_translator_api.py -q
```

代码质量：

```powershell
.venv\Scripts\python.exe -m ruff check astrbot/dashboard/api/pharma_translator.py astrbot/dashboard/services/pharma_translator_service.py tests/test_pharma_translator.py tests/test_pharma_workflow.py tests/test_pharma_translator_api.py
.venv\Scripts\python.exe -m ruff format --check astrbot/dashboard/api/pharma_translator.py astrbot/dashboard/services/pharma_translator_service.py tests/test_pharma_translator.py tests/test_pharma_workflow.py tests/test_pharma_translator_api.py
git diff --check
```

前端类型和构建：

```powershell
pnpm --dir dashboard run typecheck
pnpm --dir dashboard run build
```

当前后端测试覆盖：字段抽取和来源追溯、关键字段确认、租户隔离、文件魔数、CSV、完整七步主路径、严格步骤顺序、终止只读、RX 平台阻断、版本快照、人工校对来源、OCR 坐标关联、`data`/`payload` 请求兼容、卖点四类抽取与编号、文献 PDF/DOCX 上传与段落切片、三色证据标签、文献确认门禁、不可用卖点库、本地知识库检索接入（带入药品名）、本地模型辅助分析护栏（上调封顶/下调恢复/伪造引用忽略/失败降级）、文献步骤返工重置和无来源条目确认口径、场景翻译引擎标准模板与已验证卖点白名单（8—12 候选/🟢🟡 标记/症状解构/人群锚点）、场景选定清单与强打/弱打/删除批注凭证、已删除场景不可选定、用户原话导入/删除/去重/步骤门禁与场景锚点刷新。

## 8. 人工 UAT 主路径

1. 上传一份清晰的 OTC 说明书图片，确认生成 8 个字段且每个字段显示来源。
2. 不确认任一关键字段直接通过，验证被阻断。
3. 确认全部关键字段，进入四维拆解。
4. 检查成分/人群无直接原文时保持空白；确认功效、背书和安全约束。
5. 进入文献验证：上传一份 PDF 或 DOCX 企业文献并声明类型，或选择一个本地知识库，执行文献匹配。
6. 核对每条卖点的三色标签与三联卡；确认无引用卖点标红且不可勾选。
7. 不执行匹配直接确认、或尝试接受红色卖点，验证被阻断。
8. 接受至少一条有证据卖点后确认，检查红色卖点进入「不可用卖点库」、场景候选只引用通过验证的卖点。
9. 核对场景候选的标准模板字段（编号/人群/三要素/痛点/独白/钩子/信任锚/关联卖点标记），可导入带来源声明的用户原话并查看场景锚点刷新；勾选 1—5 个重点场景，标注强打/弱打或删除；
10. 选择关键词，确认页面没有把估算值显示为平台真实搜索量。
11. 将至少一条有来源的 Claim 标记为强/弱证据并医学确认。
12. 选择“公众号”、数量 2，生成内容草稿；弱证据卖点应使用弱化话术。
13. 检查每条事实均可回到 Claim、文献引用和说明书原文。
14. 依次完成市场确认、合规确认和终审，导出 JSON 内容包。
15. 另建 RX 项目并选择“小红书”，验证产生 `rule_rx_public_001` 阻断记录且不能继续审批。
16. 发起返工到第 3 步，检查版本递增、卖点与红线清单清空、文献文件保留，可重新匹配与确认。
17. 终止项目，检查后续写操作被拒绝。

## 9. 当前未实现的企业化边界

以下能力尚未在当前确定性 MVP 中实现，不能按生产能力验收：

- 多张图片上传、拖拽排序、重复页检测和 HEIC 转换；
- OCR/内容生成异步任务队列、`job_id`、进度轮询和幂等键；
- 扫描 PDF 在本机逐页渲染后执行 OCR；当前扫描 PDF 需要企业 OCR Provider 或人工校对文本；
- 文献的版权/密级/版本/生效失效管理、向量索引、CNKI/万方公开库对接、医学知识图谱推理及文献撤回/失效联动；当前为 PDF/DOCX 上传、段落切片、确定性关键词匹配、本地知识库检索和 PubMed 公开文献拉取；
- 同 SKU 验证记录已支持归档复用与企业红线清单聚合，尚未支持跨企业/品牌的数据范围隔离；
- 平台官方接口、已授权搜索量、合法竞品数据连接器及真实内容缺口分析；
- 企业/部门/品牌数据范围、完整 RBAC、医学/市场/合规/终审账号隔离和电子签名；
- 病毒扫描、S3/企业对象存储、静态加密、保留期、等待期删除和灾备；
- 经法务维护的正式法规/平台规则库、规则审批、生效失效、法规自动更新和历史内容回扫；
- 飞书、CMS、SSO、企业微信、正式发布和效果数据回传；
- 行政广告审查或任何医学、法务、合规部门的最终判断替代。

这些能力应在企业版后续阶段按数据许可、部署方式、角色责任和合规规则书面确认后开发。
