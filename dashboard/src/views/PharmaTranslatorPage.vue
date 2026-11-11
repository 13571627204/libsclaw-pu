<template>
  <div class="pharma-page">
    <section class="hero-panel">
      <div class="hero-decor" aria-hidden="true">
        <span class="hero-orb hero-orb--a" />
        <span class="hero-orb hero-orb--b" />
        <svg class="hero-molecule" viewBox="0 0 240 240" fill="none">
          <g stroke="currentColor" stroke-width="1.4">
            <polygon points="120,40 155,60 155,100 120,120 85,100 85,60" />
            <polygon points="155,100 190,120 190,160 155,180 120,160 120,120" />
            <polygon points="85,100 120,120 120,160 85,180 50,160 50,120" />
            <line x1="120" y1="40" x2="120" y2="12" />
            <line x1="190" y1="160" x2="222" y2="178" />
            <line x1="50" y1="160" x2="18" y2="178" />
          </g>
          <g fill="currentColor">
            <circle cx="120" cy="12" r="5" />
            <circle cx="222" cy="178" r="5" />
            <circle cx="18" cy="178" r="5" />
            <circle cx="155" cy="100" r="3.5" />
            <circle cx="85" cy="100" r="3.5" />
            <circle cx="120" cy="160" r="3.5" />
          </g>
        </svg>
      </div>
      <div class="hero-main">
        <div class="hero-eyebrow">
          <v-icon icon="mdi-shield-check-outline" size="16" />
          原文追溯 · 七步工作流 · 人工审批后交付
        </div>
        <h1>药译言<em>·</em>药企 C 端内容翻译器</h1>
        <p>
          从说明书
          OCR、多维拆解、文献来源、消费者场景、竞品内容扫描、合规过滤到内容与合规审批，
          每个产品事实均须关联原文或已确认 Claim,系统不会补写无证据事实。
        </p>
        <ul class="hero-pillars">
          <li><v-icon icon="mdi-file-search-outline" size="16" />原文可追溯</li>
          <li><v-icon icon="mdi-flask-outline" size="16" />证据三色分级</li>
          <li><v-icon icon="mdi-scale-balance" size="16" />广告法合规过滤</li>
          <li><v-icon icon="mdi-account-check-outline" size="16" />多级人工审批</li>
        </ul>
      </div>
      <div class="hero-state">
        <span class="hero-state-label">{{
          project
            ? `项目 ${project.project_id.slice(0, 8).toUpperCase()}`
            : "新建项目"
        }}</span>
        <strong>{{ workflowStateLabel }}</strong>
        <div class="hero-state-step">
          <b>{{ String(displayStepNo(currentStep)).padStart(2, "0") }}</b>
          <span>/ {{ String(visibleWorkflowSteps.length).padStart(2, "0") }}</span>
        </div>
        <div class="hero-progress">
          <i
            :style="{
              width: `${Math.round((displayStepNo(currentStep) / visibleWorkflowSteps.length) * 100)}%`,
            }"
          />
        </div>
        <small>当前步骤 · {{ currentStepMeta.title }}</small>
      </div>
    </section>

    <nav class="workflow-strip" aria-label="七步业务流程">
      <button
        v-for="(step, index) in visibleWorkflowSteps"
        :key="step.title"
        type="button"
        :disabled="!canVisitStep(step.step)"
        :class="[
          'workflow-step',
          {
            active: activeStep === step.step,
            done: isStepDone(step.step),
            locked: !canVisitStep(step.step),
          },
        ]"
        @click="selectStep(step.step)"
      >
        <span>{{ isStepDone(step.step) ? "✓" : index + 1 }}</span>
        <div>
          <strong>{{ step.title }}</strong>
          <small>{{ step.subtitle }}</small>
        </div>
      </button>
    </nav>

    <section class="workspace-grid">
      <v-card class="surface-card upload-card" variant="flat">
        <div class="section-heading">
          <div>
            <span class="section-kicker">STEP 01</span>
            <h2>品名与说明书</h2>
            <p>
              支持 JPG、PNG、WEBP 和 PDF；客户端与服务端都会检查格式及大小。
            </p>
          </div>
          <v-chip color="primary" variant="tonal" size="small"
            >8 项关键字段强制复核</v-chip
          >
        </div>

        <div class="form-grid">
          <v-text-field
            v-model="productName"
            label="药品名称（可选）"
            placeholder="可留空，由图片自动识别"
            variant="outlined"
            prepend-inner-icon="mdi-pill"
            hide-details="auto"
          />
          <v-select
            v-model="productType"
            :items="productTypes"
            label="产品类型"
            variant="outlined"
            prepend-inner-icon="mdi-shape-outline"
            hide-details="auto"
          />
        </div>

        <div
          :class="[
            'drop-zone',
            {
              'drop-zone--active': dragging,
              'drop-zone--filled': selectedFile,
            },
          ]"
          @dragover.prevent="dragging = true"
          @dragleave.prevent="dragging = false"
          @drop.prevent="handleDrop"
          @click="fileInput?.click()"
        >
          <input
            ref="fileInput"
            type="file"
            accept=".jpg,.jpeg,.png,.webp,.pdf"
            hidden
            @change="handleFileInput"
          />
          <div class="drop-icon">
            <v-icon
              :icon="
                selectedFile
                  ? 'mdi-file-check-outline'
                  : 'mdi-cloud-upload-outline'
              "
              size="34"
            />
          </div>
          <template v-if="selectedFile">
            <strong>{{ selectedFile.name }}</strong>
            <span>{{ formatBytes(selectedFile.size) }} · 点击重新选择</span>
          </template>
          <template v-else>
            <strong>拖入说明书，或点击选择文件</strong>
            <span>建议页面完整、镜头垂直、光线均匀、文字清晰</span>
          </template>
        </div>

        <div class="upload-actions">
          <div class="privacy-note">
            <v-icon icon="mdi-lock-outline" size="18" />
            文件按当前登录用户隔离保存；不会用于公共模型训练。
          </div>
          <v-btn
            color="primary"
            size="large"
            variant="flat"
            prepend-icon="mdi-text-box-search-outline"
            :loading="analyzing"
            :disabled="!canAnalyze"
            @click="analyze"
          >
            开始识别并建立项目
          </v-btn>
        </div>
      </v-card>

      <v-card class="surface-card preview-card" variant="flat">
        <div class="section-heading section-heading--compact">
          <div>
            <span class="section-kicker">SOURCE</span>
            <h2>原始文件预览</h2>
          </div>
          <v-chip v-if="project" size="small" variant="tonal">
            {{ providerLabel(project.ocr_provider) }}
          </v-chip>
        </div>
        <div class="preview-stage">
          <template v-if="previewUrl">
            <iframe v-if="isPdf" :src="previewUrl" title="PDF 预览" />
            <img v-else :src="previewUrl" alt="说明书预览" />
          </template>
          <div v-else class="preview-empty">
            <v-icon icon="mdi-file-image-outline" size="54" />
            <strong>等待上传</strong>
            <span>识别后可在字段中查看页码、原文片段及置信度</span>
          </div>
        </div>
        <div v-if="project?.quality.warnings.length" class="quality-warnings">
          <div v-for="warning in project.quality.warnings" :key="warning.code">
            <v-icon icon="mdi-alert-outline" color="warning" size="18" />
            {{ warning.message }}
          </div>
        </div>
        <div v-else-if="project" class="quality-ok">
          <v-icon icon="mdi-check-circle-outline" color="success" size="18" />
          文件质量检查未发现已定义的明显问题
        </div>
      </v-card>
    </section>

    <section v-if="project" id="result-section-top" class="result-section">
      <v-btn
        v-show="showBackToTop"
        class="back-to-top-btn"
        icon="mdi-arrow-up"
        color="primary"
        size="small"
        aria-label="回到开头"
        title="回到开头"
        @click="scrollToAnchor('result-section-top')"
      />
      <div class="result-toolbar">
        <div class="result-toolbar-step" aria-hidden="true">
          <small>STEP</small>
          <b>{{ String(displayStepNo(activeStep)).padStart(2, "0") }}</b>
        </div>
        <div class="result-toolbar-main">
          <span class="section-kicker"
            >WORKFLOW V{{ project.workflow?.version || 1 }}</span
          >
          <h2>{{ project.product_name }} · {{ activeStepMeta.title }}</h2>
          <p>{{ activeStepMeta.description }}</p>
        </div>
        <div class="result-stats">
          <div>
            <strong>{{ filledFieldCount }}</strong
            ><span>已识别字段</span>
          </div>
          <div>
            <strong>{{ selectedKeywordCount }}</strong
            ><span>已选关键词</span>
          </div>
          <div>
            <strong>{{ confirmedClaimCount }}/{{ claims.length }}</strong
            ><span>医学确认卖点</span>
          </div>
        </div>
      </div>

      <v-alert
        v-if="isTerminated"
        class="status-alert"
        type="error"
        variant="tonal"
        title="项目已终止"
        text="历史记录与原始证据仍可查看，但不能继续生成或审批。"
      />
      <v-alert
        v-else-if="isApproved"
        class="status-alert"
        type="success"
        variant="tonal"
        title="项目已终审通过"
        text="可以导出交付包；任何上游事实变更均应重新进入审核。"
      />

      <v-alert
        v-if="viewingDoneStep && !isTerminated"
        class="status-alert"
        type="info"
        variant="tonal"
        title="已完成步骤 · 查看模式"
      >
        该步骤已完成，生成/提交等操作已锁定。如需重新执行。
        <template v-if="!readOnly" #append>
          <v-btn
            color="warning"
            variant="tonal"
            :loading="actionLoading"
            @click="openRetryDialog"
            >重试此步骤</v-btn
          >
        </template>
      </v-alert>

      <div
        :class="{ 'step-view-only': stepViewOnly }"
        @mousedown.capture="guardViewOnly"
        @click.capture="guardViewOnly"
        @beforeinput.capture="guardViewOnly"
      >
        <div v-if="activeStep === 1" class="step-panel">
          <div class="step-intro">
            <div>
              <h3>产品档案与关键字段确认</h3>
              <p>
                人工修改不会覆盖机器原始值；关键字段缺失、无来源或未确认均会阻断。
              </p>
            </div>
            <v-chip color="error" variant="tonal"
              >{{ criticalConfirmedCount }}/{{
                criticalWithValueCount
              }}
              已确认</v-chip
            >
            <v-checkbox
              v-if="confirmableFields.length"
              v-model="allFieldsConfirmed"
              :indeterminate="someFieldsConfirmed && !allFieldsConfirmed"
              :disabled="readOnly"
              label="全部确认"
              color="primary"
              density="compact"
              hide-details
              @update:model-value="onToggleAllFieldsConfirmed"
            />
          </div>
          <div class="field-groups">
            <div
              v-for="group in fieldGroups"
              :key="group.key"
              :class="[
                'field-group',
                { 'field-group--single': group.fields.length === 1 },
              ]"
            >
              <div class="field-group-title">
                <v-icon :icon="group.icon" :color="group.color" size="20" />
                <div>
                  <strong>{{ group.title }}</strong
                  ><small>{{ group.subtitle }}</small>
                </div>
              </div>
              <div class="field-card-grid">
                <div
                  v-for="field in group.fields"
                  :key="field.field_code"
                  class="field-card"
                >
                  <div class="field-card-head">
                    <div>
                      <strong>{{ field.label }}</strong>
                      <v-chip
                        v-if="field.critical"
                        color="error"
                        size="x-small"
                        variant="tonal"
                        >关键</v-chip
                      >
                      <v-chip
                        v-if="isSkippableField(field) && !field.value.trim()"
                        color="grey"
                        size="x-small"
                        variant="tonal"
                        >可跳过</v-chip
                      >
                      <v-chip
                        v-else-if="isManualSource(field)"
                        color="warning"
                        size="x-small"
                        variant="tonal"
                        >手动补充</v-chip
                      >
                    </div>
                    <v-chip
                      :color="confidenceColor(field.confidence)"
                      size="x-small"
                      variant="tonal"
                    >
                      {{ confidenceText(field.confidence, field.source_text) }}
                    </v-chip>
                  </div>
                  <v-textarea
                    v-model="field.value"
                    :disabled="readOnly"
                    variant="outlined"
                    auto-grow
                    rows="1"
                    density="comfortable"
                    :placeholder="fieldPlaceholder(field)"
                    hide-details
                    @update:model-value="onFieldValueChange(field)"
                  />
                  <div class="evidence-line">
                    <span
                      ><v-icon icon="mdi-file-document-outline" size="15" />{{
                        field.page_no ? `第 ${field.page_no} 页` : "无页码"
                      }}</span
                    >
                    <span :title="field.source_text">{{
                      field.source_text ||
                      (isManualSource(field)
                        ? "手动补充（无原文证据）"
                        : "无原文证据")
                    }}</span>
                  </div>
                  <v-checkbox
                    v-if="field.value"
                    v-model="field.confirmed"
                    :disabled="readOnly"
                    :label="
                      isManualSource(field) && !field.source_text
                        ? '我已核实并手动补充'
                        : '我已对照原文确认'
                    "
                    color="primary"
                    density="compact"
                    hide-details
                  />
                </div>
              </div>
            </div>
          </div>
          <div class="user-notes-panel">
            <div class="field-group-title">
              <v-icon icon="mdi-note-plus-outline" color="indigo" size="20" />
              <div>
                <strong>用户手动填写信息</strong>
                <small>字段未识别或需要补充说明时，可在此添加备注</small>
              </div>
            </div>
            <div v-if="userNotes.length" class="user-notes-list">
              <div
                v-for="(note, index) in userNotes"
                :key="note.note_id"
                class="user-note-item"
              >
                <v-text-field
                  v-model="note.title"
                  :disabled="readOnly"
                  label="标题（可选）"
                  variant="outlined"
                  density="compact"
                  hide-details
                  maxlength="120"
                />
                <v-textarea
                  v-model="note.text"
                  :disabled="readOnly"
                  label="内容"
                  variant="outlined"
                  auto-grow
                  rows="2"
                  density="comfortable"
                  hide-details
                  maxlength="30000"
                />
                <v-btn
                  v-if="!readOnly"
                  variant="text"
                  color="error"
                  size="small"
                  prepend-icon="mdi-delete-outline"
                  @click="removeUserNote(index)"
                  >删除</v-btn
                >
              </div>
            </div>
            <v-btn
              v-if="!readOnly"
              variant="tonal"
              color="indigo"
              size="small"
              prepend-icon="mdi-plus"
              @click="addUserNote"
              >添加手动信息</v-btn
            >
          </div>
          <div id="profile-step-actions" class="step-actions">
            <v-btn
              color="primary"
              :loading="actionLoading"
              :disabled="readOnly || currentStep !== 1"
              @click="confirmProfile"
            >
              通过产品档案，进入多维拆解
            </v-btn>
          </div>
        </div>

        <div v-else-if="activeStep === 2" class="step-panel">
          <div class="step-intro">
            <div>
              <h3>品牌名和产品名、主治功能、成分、批号、对症人群、现有渠道</h3>
              <p>
                以上传资料识别的药品名称为检索词，结合上传 OCR
                全文、所选本地药企知识库与搜索采集内容，由已配置的生成模型整理品牌名和产品名、主治功能、成分、批号、对症人群、现有渠道（医院、药店、诊所、药品零售商、药品批发商）。模型本身不联网、不凭记忆补写；每条候选附来源，须人工确认，不从禁忌推断适用人群。
              </p>
            </div>
            <v-btn
              color="primary"
              variant="tonal"
              :loading="dimensionsLoading"
              :disabled="readOnly || currentStep !== 2 || actionLoading"
              @click="generateDimensions"
            >
              按药品名称检索并生成多维
            </v-btn>
          </div>
          <div class="dimension-source-bar">
            <v-select
              v-model="dimensionKbIds"
              :items="kbOptions"
              :loading="kbLoading"
              :disabled="readOnly || currentStep !== 2 || dimensionsLoading"
              label="本地药企知识库（可多选）"
              multiple
              chips
              closable-chips
              clearable
              density="compact"
              variant="outlined"
              hide-details
            />
            <v-select
              v-model="dimensionSearchMode"
              :items="dimensionSearchModeOptions"
              :disabled="readOnly || currentStep !== 2 || dimensionsLoading"
              label="搜索方式"
              density="compact"
              variant="outlined"
              hide-details
            />
          </div>
          <v-alert
            v-if="dimensionsLoading"
            type="info"
            variant="tonal"
            class="status-alert"
          >
            正在用已配置的生成模型检索当前上传资料、本地药企知识库与搜索内容，生成多维候选，请稍候；模型仅使用传入资料。
          </v-alert>
          <v-alert
            v-if="dimensionGeneration && !dimensionsLoading"
            type="info"
            variant="tonal"
            density="compact"
            class="status-alert ui-hidden"
          >
            药品名称：{{ dimensionGeneration.drug_name || "未识别" }} ·
            知识库命中 {{ dimensionGeneration.kb_hits || 0 }} 条 · 搜索命中
            {{ dimensionGeneration.search_hits || 0 }} 条 · 丢弃无依据条目
            {{ dimensionGeneration.dropped || 0 }} 条
            <div
              v-for="(warning, index) in dimensionGeneration.warnings || []"
              :key="index"
              class="text-warning"
            >
              {{ warning }}
            </div>
          </v-alert>
          <v-alert
            v-if="dimensionsError"
            type="error"
            variant="tonal"
            class="status-alert"
          >
            {{ dimensionsError }}
          </v-alert>
          <div v-if="dimensions.length" class="dimension-toolbar">
            <span class="dimension-progress">
              已确认 {{ confirmedReviewCount }}/{{ reviewItemTotal }}
              条（含安全约束）
            </span>
            <v-btn
              size="small"
              color="primary"
              :variant="allReviewConfirmed ? 'outlined' : 'tonal'"
              prepend-icon="mdi-check-all"
              :disabled="readOnly || currentStep !== 2 || dimensionsLoading"
              @click="toggleAllReviewConfirmed"
            >
              {{ allReviewConfirmed ? "取消全选" : "全部确认" }}
            </v-btn>
          </div>
          <div v-if="dimensions.length" class="dimension-grid">
            <article
              v-for="dimension in orderedDimensions"
              :key="dimensionKey(dimension)"
              class="dimension-card"
              :data-dimension="dimensionKey(dimension)"
            >
              <header>
                <v-icon
                  :icon="dimensionIcon(dimensionKey(dimension))"
                  size="22"
                />
                <strong>{{ dimensionLabel(dimension) }}</strong>
              </header>
              <div
                v-if="dimensionKey(dimension) === 'channels'"
                class="channel-category-row"
              >
                <v-chip
                  v-for="category in channelCategories"
                  :key="category"
                  size="x-small"
                  :color="
                    channelHit(dimension, category) ? 'primary' : undefined
                  "
                  :variant="
                    channelHit(dimension, category) ? 'flat' : 'outlined'
                  "
                >
                  {{ category }}
                </v-chip>
              </div>
              <div v-if="dimension.items.length" class="dimension-items">
                <div
                  v-for="(item, index) in dimension.items"
                  :key="item.item_id || index"
                >
                  <p>{{ item.text || item.value }}</p>
                  <small
                    v-if="item.source_type || item.source_label"
                    class="ui-hidden"
                  >
                    {{
                      item.source_type === "model_generated" ||
                      item.source_type === "local_model"
                        ? `模型生成${
                            item.model_provider
                              ? ` · ${item.model_provider}`
                              : ""
                          } · 待人工确认`
                        : "资料提取"
                    }}
                    {{ item.source_label ? ` · ${item.source_label}` : "" }}
                  </small>
                  <small v-if="item.is_external" class="text-info">
                    外部来源 ·
                    {{
                      item.derivation ||
                      "依据本地药企知识库/搜索内容整理，待人工确认"
                    }}
                    <a
                      v-if="item.source_url"
                      :href="webUrl(item.source_url)"
                      target="_blank"
                      rel="noopener noreferrer"
                      >查看原文</a
                    >
                  </small>
                  <small v-if="item.is_inferred" class="text-warning ui-hidden">
                    推导 ·
                    {{
                      item.derivation || "依据功能主治整理，待人工确认"
                    }}（不是原文人群事实）
                  </small>
                  <small
                    >{{ item.page_no ? `P${item.page_no} · ` : ""
                    }}{{ uniqueSourceText(item.source_text) || "无原文片段" }}</small
                  >
                  <small
                    v-for="source in uniqueEvidenceSources(item.evidence)"
                    :key="source.evidence_id"
                  >
                    [{{ source.evidence_id }}] {{ source.source_label }}
                    {{ source.page_no ? ` · P${source.page_no}` : "" }}
                  </small>
                  <v-checkbox
                    v-model="item.confirmed"
                    :disabled="
                      readOnly || currentStep !== 2 || dimensionsLoading
                    "
                    label="已对照来源确认"
                    color="primary"
                    density="compact"
                    hide-details
                  />
                </div>
              </div>
              <div v-else class="empty-state compact">
                当前确认资料没有可用内容，不进行推断。
              </div>
            </article>
          </div>
          <div v-else class="empty-state">
            多维候选尚未生成。请先完成第 1 步，或刷新项目数据。
          </div>

          <div class="safety-panel">
            <div class="field-group-title">
              <v-icon icon="mdi-shield-alert-outline" color="error" size="22" />
              <div>
                <strong>安全与使用约束</strong
                ><small>不会作为营销卖点，内容生成时作为硬约束</small>
              </div>
            </div>
            <div v-if="safetyConstraints.length" class="safety-grid">
              <article
                v-for="item in safetyConstraints"
                :key="item.constraint_id || item.field_code || item.label"
              >
                <strong>{{ item.label }}</strong>
                <p>{{ item.text || item.value || "未识别到原文" }}</p>
                <small>{{ item.source_text || "无原文证据" }}</small>
                <v-checkbox
                  v-model="item.confirmed"
                  :disabled="readOnly || currentStep !== 2"
                  label="已确认安全约束"
                  color="error"
                  density="compact"
                  hide-details
                />
              </article>
            </div>
            <div v-else class="empty-state compact">尚无已确认的安全约束。</div>
          </div>
          <div id="dimension-step-actions" class="step-actions">
            <v-btn
              color="primary"
              :loading="actionLoading"
              :disabled="
                readOnly ||
                currentStep !== 2 ||
                dimensionsLoading ||
                !dimensions.length
              "
              @click="confirmDimensions"
            >
              通过多维拆解，文献来源
            </v-btn>
          </div>
        </div>

        <div
          v-else-if="activeStep === 3"
          id="literature-step"
          class="step-panel"
        >
          <div class="step-intro">
            <div>
              <h3>企业商品文献来源</h3>
              <p>
                每个卖点必须能从企业文献或权威资料中找到支撑；无证据卖点进入不可用卖点库，不进入内容生成。
              </p>
            </div>
            <v-chip
              :color="literatureMatched ? 'primary' : 'warning'"
              variant="tonal"
            >
              {{
                literatureMatched
                  ? `已匹配 · ${acceptedLiteratureCount}/${literatureClaims.length} 条可用`
                  : "待执行文献匹配"
              }}
            </v-chip>
          </div>

          <div class="literature-sources">
            <section class="literature-upload">
              <h4>企业文献库（PDF / DOCX）</h4>
              <div class="upload-row">
                <v-select
                  v-model="literatureDocKind"
                  :items="literatureDocKindOptions"
                  label="文献类型"
                  density="compact"
                  variant="outlined"
                  hide-details
                  class="doc-kind-select"
                />
                <v-file-input
                  v-model="literatureFiles"
                  label="选择文献文件（可多选）"
                  multiple
                  density="compact"
                  variant="outlined"
                  hide-details
                  prepend-icon="mdi-file-upload-outline"
                  accept=".pdf,.docx"
                />
                <v-btn
                  variant="tonal"
                  :loading="literatureUploading"
                  :disabled="
                    readOnly || currentStep !== 3 || !literatureFiles.length
                  "
                  @click="uploadLiterature"
                  >上传文献</v-btn
                >
              </div>
              <div
                v-if="literatureDocuments.length"
                class="literature-doc-list"
              >
                <article
                  v-for="doc in literatureDocuments"
                  :key="doc.doc_id"
                  class="literature-doc"
                >
                  <v-icon icon="mdi-file-document-outline" size="18" />
                  <div>
                    <strong>{{ doc.filename }}</strong>
                    <small
                      >{{ doc.doc_kind_label || doc.doc_kind }} ·
                      {{ doc.chunk_count || 0 }} 个切片 ·
                      {{
                        doc.uploaded_at ? formatDate(doc.uploaded_at) : ""
                      }}</small
                    >
                  </div>
                  <v-btn
                    icon="mdi-delete-outline"
                    size="x-small"
                    variant="text"
                    color="error"
                    :disabled="readOnly || currentStep !== 3"
                    @click="removeLiterature(doc.doc_id)"
                  />
                </article>
              </div>
              <p v-else class="literature-hint">
                未上传文献时仅使用说明书原文验证；成分、背书类卖点可能被评为弱证据。
              </p>
            </section>
            <section class="literature-kb">
              <h4>
                本地知识库(知识库需开通对应服务后使用，支持本地/企业专属云部署且数据不上传，保障数据安全)
              </h4>
              <v-select
                v-model="selectedKbIds"
                :items="kbOptions"
                label="选择知识库（可多选）"
                multiple
                chips
                density="compact"
                variant="outlined"
                hide-details
                :loading="kbLoading"
                :disabled="readOnly || currentStep !== 3"
              />
            </section>
          </div>
          <div class="step-actions">
            <v-select
              v-model="literatureTier"
              :items="literatureTierOptions"
              label="技术档位"
              density="compact"
              variant="outlined"
              hide-details
              class="tier-select"
              :disabled="readOnly || currentStep !== 3 || literatureMatching"
            />
            <v-btn
              color="primary"
              variant="tonal"
              prepend-icon="mdi-book-search-outline"
              :loading="literatureMatching"
              :disabled="
                readOnly || currentStep !== 3 || !literatureClaims.length
              "
              @click="runLiteratureMatch"
            >
              {{ literatureMatched ? "重新执行文献匹配" : "开始文献匹配" }}
            </v-btn>
          </div>
          <v-alert
            v-if="literature.ai_notice"
            type="info"
            variant="tonal"
            density="compact"
            class="status-alert ui-hidden"
            icon="mdi-robot-outline"
          >
            {{ literature.ai_notice }}
          </v-alert>
          <v-alert
            v-if="literature.tier_notice"
            type="info"
            variant="tonal"
            density="compact"
            class="status-alert"
            icon="mdi-layers-outline"
          >
            {{ literature.tier_notice }}
          </v-alert>
          <v-alert
            v-if="literature.reused_from"
            type="warning"
            variant="tonal"
            density="compact"
            class="status-alert"
            icon="mdi-history"
          >
            已复用同 SKU 历史验证（签字：{{
              literature.reused_from.signer || "-"
            }}<template v-if="literature.reused_from.signed_at">
              · {{ formatDate(literature.reused_from.signed_at) }}</template
            >），请逐条复核后重新签字确认。
          </v-alert>
          <div v-if="literature.knowledge_graph?.length" class="unusable-box">
            <h4>成分—靶点—适应症三元组（仅提示，不改变证据等级）</h4>
            <div
              v-for="(triple, index) in literature.knowledge_graph"
              :key="`${triple.claim_no}-${index}`"
              class="unusable-item"
            >
              <v-icon icon="mdi-graph-outline" size="18" color="primary" />
              <span
                >{{ triple.claim_no }} · {{ triple.ingredient }} →
                {{ triple.target }} → {{ triple.indication }}</span
              >
              <small
                >依据引用 {{ triple.basis_citation_ids?.length || 0 }} 条</small
              >
            </div>
          </div>

          <v-alert
            v-if="literatureClaims.length && literatureClaims.length < 10"
            type="info"
            variant="tonal"
            density="compact"
            class="status-alert"
          >
            当前抽取 {{ literatureClaims.length }} 条卖点，建议 10-20
            条；可回到第 2 步补充产品档案后重新抽取。
          </v-alert>
          <div v-if="literatureClaims.length" class="claim-groups">
            <h4>卖点清单抽取（{{ literatureClaims.length }} 条）</h4>
            <section
              v-for="group in literatureClaimGroups"
              :key="`claim-group-${group.type}`"
              class="claim-group"
            >
              <h5>
                {{ group.icon }} {{ group.label }}（{{ group.items.length }}）
              </h5>
              <ul>
                <li v-for="item in group.items" :key="`group-${item.claim_id}`">
                  <b>{{ item.claim_no }}</b> {{ item.text }}
                  <v-chip
                    v-if="literatureMatched"
                    :color="evidenceColor(effectiveLevel(item))"
                    size="x-small"
                    variant="tonal"
                    >{{ evidenceLabel(effectiveLevel(item)) }}</v-chip
                  >
                </li>
              </ul>
            </section>
          </div>

          <div
            v-if="literatureMatched && literatureClaims.length"
            class="literature-summary"
          >
            <h4>文献匹配与三色标签</h4>
            <table class="literature-summary-table">
              <thead>
                <tr>
                  <th>编号</th>
                  <th>卖点</th>
                  <th>文献来源</th>
                  <th>证据等级</th>
                  <th>判定说明</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="claim in literatureClaims"
                  :key="`summary-${claim.claim_id}`"
                >
                  <td class="nowrap">{{ claim.claim_no }}</td>
                  <td>{{ claim.text }}</td>
                  <td>
                    {{ claim.triple_card?.citation_summary || "无文献来源" }}
                  </td>
                  <td class="nowrap">
                    <v-chip
                      :color="evidenceColor(effectiveLevel(claim))"
                      size="small"
                      variant="tonal"
                      >{{ evidenceLabel(effectiveLevel(claim)) }}</v-chip
                    >
                  </td>
                  <td>
                    {{ claim.verdict_note || "-"
                    }}<template v-if="claim.disposal"
                      >；{{ claim.disposal }}</template
                    >
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="literatureClaims.length" class="claim-list-head">
            <h4 class="claim-list-title">逐条复核与确认</h4>
            <v-btn
              v-if="!readOnly && currentStep === 3"
              size="small"
              variant="tonal"
              color="primary"
              prepend-icon="mdi-checkbox-multiple-marked-outline"
              :disabled="!acceptableClaims.length"
              @click="toggleAllClaimsAccepted"
            >
              {{ allClaimsAccepted ? "取消全选（逐条单选）" : "一键全选" }}
            </v-btn>
          </div>
          <div v-if="literatureClaims.length" class="claim-list">
            <article
              v-for="claim in literatureClaims"
              :key="claim.claim_id"
              class="claim-card"
            >
              <header>
                <div>
                  <strong>{{ claim.claim_no }} · {{ claim.text }}</strong
                  ><small
                    >{{ claimTypeIcon(claim.claim_type) }}
                    {{ claim.claim_type_label || claim.claim_type }} · Claim
                    ID：{{ claim.claim_id }}</small
                  >
                </div>
                <div class="claim-chips">
                  <v-chip
                    v-if="claim.prior_review"
                    size="small"
                    variant="outlined"
                    color="info"
                    :title="claim.prior_review.adjust_reason || ''"
                    >历史复核：{{
                      claim.prior_review.accepted ? "可用" : "不可用"
                    }}</v-chip
                  >
                  <v-chip
                    :color="evidenceColor(effectiveLevel(claim))"
                    size="small"
                    variant="tonal"
                    >{{ evidenceLabel(effectiveLevel(claim)) }}</v-chip
                  >
                </div>
              </header>
              <div
                v-if="claim.match_status === 'matched' && claim.verdict_note"
                class="verdict-note"
              >
                <v-icon icon="mdi-gavel" size="16" />
                <div>
                  <p>
                    判定说明：{{ claim.verdict_note
                    }}<template v-if="claim.adjusted_by_human"
                      >（人工已调级）</template
                    >
                  </p>
                  <small v-if="claim.expression_rule"
                    >表述边界：{{ claim.expression_rule }}</small
                  >
                  <small v-if="claim.disposal" class="disposal-text"
                    >处置：{{ claim.disposal }}</small
                  >
                </div>
              </div>
              <div v-if="claim.citations?.length" class="citation-list">
                <div
                  v-for="citation in claim.citations"
                  :key="citation.citation_id"
                  class="claim-evidence"
                >
                  <v-icon
                    :icon="citationIcon(citation.source_channel)"
                    size="18"
                  />
                  <div>
                    <p>{{ citation.excerpt }}</p>
                    <small
                      >{{ citation.source_label }} ·
                      {{ citation.source_kind_label || citation.source_kind
                      }}<template v-if="citation.page_no">
                        · 第 {{ citation.page_no }} 页</template
                      >
                      · 覆盖度 {{ Math.round(citation.score * 100) }}%<template
                        v-if="citation.url"
                      >
                        ·
                        <a
                          :href="citation.url"
                          target="_blank"
                          rel="noopener noreferrer"
                          >核验链接</a
                        ></template
                      ></small
                    >
                  </div>
                </div>
              </div>
              <v-alert
                v-else-if="claim.match_status === 'matched'"
                type="error"
                variant="tonal"
                density="compact"
                class="status-alert"
              >
                未找到任何文献支撑，禁止使用（即使“业内都这么说”）。
              </v-alert>
              <p v-else class="literature-hint">尚未执行文献匹配。</p>
              <div
                v-if="claim.ai_analysis"
                class="ai-analysis"
                :class="{ adjusted: claim.ai_adjusted }"
              >
                <v-icon icon="mdi-robot-outline" size="18" />
                <div>
                  <p>
                    模型建议：{{
                      evidenceLabel(claim.ai_analysis.suggested_level || "none")
                    }}
                    <template v-if="claim.ai_adjusted">（已采纳下调）</template>
                    <template
                      v-else-if="
                        claim.ai_analysis.suggested_level !==
                        claim.evidence_level
                      "
                      >（上调建议未采纳，以确定性规则为准）</template
                    >
                  </p>
                  <small>{{ claim.ai_analysis.reason || "无判定依据" }}</small>
                  <small
                    v-if="claim.ai_analysis.verdict_note"
                    class="ai-note-line"
                    >判定说明（模型建议）：{{
                      claim.ai_analysis.verdict_note
                    }}</small
                  >
                  <small
                    v-if="claim.ai_analysis.expression_rule"
                    class="ai-note-line"
                    >表述边界（模型建议）：{{
                      claim.ai_analysis.expression_rule
                    }}</small
                  >
                  <small
                    v-if="claim.ai_analysis.disposal"
                    class="ai-note-line disposal-text"
                    >处置建议（模型建议）：{{
                      claim.ai_analysis.disposal
                    }}</small
                  >
                </div>
              </div>
              <v-expansion-panels
                v-if="claim.triple_card"
                class="triple-card-panels"
                variant="accordion"
              >
                <v-expansion-panel>
                  <v-expansion-panel-title
                    >卖点—场景—话术三联卡</v-expansion-panel-title
                  >
                  <v-expansion-panel-text>
                    <dl class="triple-card-grid">
                      <dt>卖点编号</dt>
                      <dd>{{ claim.claim_no }}</dd>
                      <dt>卖点原文</dt>
                      <dd>{{ claim.text }}</dd>
                      <dt>证据等级</dt>
                      <dd>{{ evidenceLabel(effectiveLevel(claim)) }}</dd>
                      <dt>判定说明</dt>
                      <dd>
                        {{
                          claim.triple_card.verdict_note ||
                          claim.verdict_note ||
                          "待文献匹配"
                        }}
                      </dd>
                      <dt>表述边界</dt>
                      <dd>
                        {{
                          claim.triple_card.expression_rule ||
                          claim.expression_rule ||
                          "-"
                        }}
                      </dd>
                      <template
                        v-if="claim.triple_card.disposal || claim.disposal"
                      >
                        <dt>处置</dt>
                        <dd class="violation-copy">
                          {{ claim.triple_card.disposal || claim.disposal }}
                        </dd>
                      </template>
                      <dt>文献来源</dt>
                      <dd>
                        {{ claim.triple_card.citation_summary || "无文献来源" }}
                      </dd>
                      <dt>文献证据</dt>
                      <dd>{{ claim.triple_card.usable_scenes.join("、") }}</dd>
                      <dt>禁用场景</dt>
                      <dd>{{ claim.triple_card.blocked_scenes.join("、") }}</dd>
                      <dt>合规话术示范</dt>
                      <dd>
                        {{ claim.triple_card.compliant_copy }} ✅
                        <v-chip
                          v-if="claim.triple_card.copy_source === 'ai'"
                          size="x-small"
                          color="primary"
                          variant="tonal"
                          >模型生成</v-chip
                        >
                      </dd>
                      <dt>违规话术警示</dt>
                      <dd class="violation-copy">
                        {{ claim.triple_card.violation_copy }} ❌
                      </dd>
                      <dt>需加注说明</dt>
                      <dd>{{ claim.triple_card.disclaimer }}</dd>
                    </dl>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
              <div
                v-if="literatureMatched && claim.match_status === 'matched'"
                class="upload-row"
              >
                <v-select
                  :model-value="effectiveLevel(claim)"
                  :items="evidenceLevelOptions"
                  label="人工复核证据等级"
                  density="compact"
                  variant="outlined"
                  hide-details
                  class="doc-kind-select"
                  :disabled="readOnly || currentStep !== 3"
                  @update:model-value="(value) => setClaimLevel(claim, value)"
                />
                <v-text-field
                  v-if="effectiveLevel(claim) !== claim.evidence_level"
                  :model-value="
                    literatureLevelDrafts[claim.claim_id]?.reason || ''
                  "
                  label="调级理由（必填，将写入审计）"
                  density="compact"
                  variant="outlined"
                  hide-details
                  :error="
                    !literatureLevelDrafts[claim.claim_id]?.reason?.trim()
                  "
                  :disabled="readOnly || currentStep !== 3"
                  @update:model-value="
                    (value) => (levelDraft(claim).reason = value)
                  "
                />
              </div>
              <v-checkbox
                v-model="claim.accepted"
                :disabled="
                  readOnly ||
                  currentStep !== 3 ||
                  effectiveLevel(claim) === 'none' ||
                  !claim.citations?.length
                "
                color="primary"
                label="已核对文献证据，确认该卖点可用于内容生成"
                hide-details
              />
            </article>
          </div>
          <div v-else class="empty-state">
            尚无卖点候选；请先在第 2 步完成多维拆解确认。
          </div>

          <div v-if="unusableClaims.length" class="unusable-box">
            <h4>不可用卖点库（企业红线清单）</h4>
            <div
              v-for="item in unusableClaims"
              :key="item.claim_id"
              class="unusable-item"
            >
              <v-icon icon="mdi-cancel" size="18" color="error" />
              <span>{{ item.claim_no }} · {{ item.text }}</span>
              <small
                >{{ item.reason
                }}<template v-if="item.disposal">
                  · {{ item.disposal }}</template
                ></small
              >
            </div>
          </div>

          <div v-if="literatureSignoff" class="literature-signoff-done">
            <v-icon icon="mdi-draw-pen" size="18" color="success" />
            <span
              >已签字确认：{{ literatureSignoff.signer_name }}（{{
                literatureSignoff.signer_title
              }}）<template v-if="literatureSignoff.signed_at">
                · {{ formatDate(literatureSignoff.signed_at) }}</template
              >
              · 可用 {{ literatureSignoff.accepted_count ?? 0 }} 条 / 卡断
              {{ literatureSignoff.blocked_count ?? 0 }} 条</span
            >
            <v-chip
              v-if="literatureSignoff.signer_qualified === false"
              size="x-small"
              color="warning"
              variant="tonal"
              >签字人非医学/学术背景</v-chip
            >
          </div>
          <div
            v-if="literatureMatched && currentStep === 3 && !readOnly"
            id="literature-signoff"
            class="literature-signoff"
          >
            <h4>🔍 人工确认节点 · 医学部签字</h4>
            <p class="literature-hint">
              确认人必须为企业医学部/学术部人员，不可代签；签字后输出卖点—文献—话术三联表并归档。铁律：无文献支撑的卖点不得进入下一步，系统强制卡断。
            </p>
            <div class="literature-checklist">
              <v-checkbox
                v-for="item in literatureChecklistItems"
                :key="item.key"
                v-model="literatureChecklist[item.key]"
                :label="item.label"
                color="primary"
                density="compact"
                hide-details
              />
            </div>
            <div class="upload-row">
              <v-text-field
                v-model="literatureSigner.name"
                label="签字人姓名（本人签字）"
                density="compact"
                variant="outlined"
                hide-details
              />
              <v-text-field
                v-model="literatureSigner.title"
                label="部门 / 职务（须含 医学部 或 学术部）"
                density="compact"
                variant="outlined"
                hide-details
                :error="
                  !!literatureSigner.title.trim() && !literatureSignerQualified
                "
              />
            </div>
            <p
              v-if="literatureSigner.title.trim() && !literatureSignerQualified"
              class="literature-hint error-text"
            >
              确认人必须为企业医学部/学术部人员。
            </p>
          </div>

          <div class="step-actions">
            <v-btn
              variant="text"
              prepend-icon="mdi-shield-alert-outline"
              @click="loadLiteratureRedlines"
              >查看企业红线清单</v-btn
            >
            <v-btn
              variant="text"
              prepend-icon="mdi-table-arrow-down"
              :loading="exporting"
              :disabled="!literatureMatched"
              @click="exportLiteratureTripleTable"
              >导出三联表 CSV</v-btn
            >
            <v-btn
              color="primary"
              :loading="actionLoading"
              :disabled="readOnly || currentStep !== 3 || !canConfirmLiterature"
              @click="confirmLiterature"
            >
              签字确认卖点验证，进入场景生成
            </v-btn>
          </div>

          <v-dialog v-model="literatureRedlineDialog" max-width="860">
            <v-card>
              <v-card-title>不可用卖点库 · 企业红线清单</v-card-title>
              <v-card-text>
                <v-progress-linear
                  v-if="literatureRedlineLoading"
                  indeterminate
                  color="primary"
                />
                <div v-else-if="!literatureRedlines.length" class="empty-state">
                  暂无红线记录；文献来源签字后，弱证据/无证据卖点会自动归入。
                </div>
                <div
                  v-for="(item, index) in literatureRedlines"
                  :key="`${item.sku_key}-${item.claim_no}-${index}`"
                  class="unusable-item"
                >
                  <v-chip
                    size="x-small"
                    :color="
                      item.evidence_level === 'weak' ? 'warning' : 'error'
                    "
                    variant="tonal"
                    >{{
                      item.verdict ||
                      (item.evidence_level === "weak" ? "弱证据" : "无证据")
                    }}</v-chip
                  >
                  <span
                    >{{ item.product_name ? `${item.product_name} · ` : ""
                    }}{{ item.claim_no }} · {{ item.text }}</span
                  >
                  <small
                    >{{ item.reason
                    }}<template v-if="item.disposal">
                      · {{ item.disposal }}</template
                    ><template v-if="item.signer">
                      · 签字：{{ item.signer }}</template
                    ><template v-if="item.archived_at">
                      · {{ formatDate(item.archived_at) }}</template
                    ></small
                  >
                </div>
              </v-card-text>
              <v-card-actions>
                <v-spacer />
                <v-btn variant="text" @click="literatureRedlineDialog = false"
                  >关闭</v-btn
                >
              </v-card-actions>
            </v-card>
          </v-dialog>
        </div>

        <div v-else-if="activeStep === 4" id="scene-step" class="step-panel">
          <div class="step-intro">
            <div>
              <h3>场景翻译引擎 · 场景候选确认</h3>
              <p>
                仅由已验证（🟢/🟡）卖点翻译生成；勾选 1—5
                个重点场景，可标注强打/弱打/删除并填写批注。
              </p>
            </div>
            <v-chip
              :color="project.product_type === 'RX' ? 'error' : 'primary'"
              variant="tonal"
            >
              {{
                project.product_type === "RX"
                  ? "RX 专用路径"
                  : `${selectedSceneCount} 个已选场景`
              }}
            </v-chip>
          </div>
          <v-alert
            v-if="project.product_type === 'RX'"
            type="warning"
            variant="tonal"
            class="status-alert"
          >
            处方药不会进入普通大众平台营销路径，仅允许企业批准的患者服务或专业医学教育场景。
          </v-alert>

          <section v-if="scenes.length" class="scene-flow">
            <h4>
              {{ dimensionDrugName || "当前药品" }}：从「{{
                dimensionFlowHeadline
              }}」到多种客群
            </h4>
            <div class="scene-flow-body">
              <div class="scene-flow-input">
                <strong>输入 · 说明书原文</strong>
                <p>{{ dimensionSourceText || "未识别到主治功能原文" }}</p>
                <strong>AI 先拆出四个维度</strong>
                <dl>
                  <div
                    v-for="row in dimensionFlowRows"
                    :key="row.code"
                    class="flow-dim-card"
                  >
                    <dt>{{ row.label }}</dt>
                    <dd>{{ row.text || "待生成" }}</dd>
                  </div>
                </dl>
              </div>
              <div class="scene-flow-arrow">
                <span>AI 翻译</span>
                <v-icon icon="mdi-arrow-right-bold-outline" />
              </div>
              <div class="scene-persona-row">
                <article
                  v-for="scene in activeScenes.slice(0, 6)"
                  :key="scene.scene_id"
                  class="scene-persona"
                >
                  <strong>{{
                    scene.target_audience ||
                    audienceText(scene.audience) ||
                    scene.name
                  }}</strong>
                  <p>
                    {{
                      scene.inner_monologue || scene.core_pain || "独白未生成"
                    }}
                  </p>
                  <small v-if="scene.search_keywords?.length">
                    TA 搜的是：{{ scene.search_keywords[0] }}
                  </small>
                  <em v-if="scene.content_hook"
                    >【{{ scene.content_hook }}】</em
                  >
                </article>
              </div>
            </div>

            <div class="scene-matrix">
              <div class="scene-matrix-head">
                <strong>场景优先级矩阵</strong>
                <small>
                  估算值，待人工确认：市场规模依据搜索词数量；内容可做度依据已验证卖点证据覆盖率。
                </small>
              </div>
              <v-table density="compact">
                <thead>
                  <tr>
                    <th>场景</th>
                    <th>市场规模</th>
                    <th>内容可做度</th>
                    <th>推荐优先级</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in scenePriorityMatrix" :key="row.scene_id">
                    <td>{{ row.scene_no }} {{ row.name }}</td>
                    <td>
                      {{ starText(row.market) }} {{ levelText(row.market) }}
                    </td>
                    <td>
                      {{ starText(row.doability) }}
                      {{ levelText(row.doability) }}
                    </td>
                    <td>
                      <v-chip
                        size="x-small"
                        variant="tonal"
                        :color="
                          row.priority === 'P0'
                            ? 'error'
                            : row.priority === 'P1'
                            ? 'warning'
                            : 'default'
                        "
                      >
                        {{ row.priority }} {{ priorityTierText(row.priority) }}
                      </v-chip>
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </div>
          </section>

          <div
            v-if="scenes.length && !readOnly && currentStep === 4"
            class="scene-toolbar"
          >
            <small
              >已选 {{ selectedSceneCount }}/5 个重点场景（确认提交限 1—5
              个，可逐张单选）</small
            >
            <v-btn
              size="small"
              variant="tonal"
              color="primary"
              prepend-icon="mdi-checkbox-multiple-marked-outline"
              :disabled="!selectableScenes.length"
              @click="toggleAllScenesSelected"
            >
              {{ allScenesSelected ? "取消全选（逐张单选）" : "一键全选" }}
            </v-btn>
          </div>
          <div v-if="scenes.length" class="scene-grid">
            <article
              v-for="scene in scenes"
              :key="scene.scene_id"
              :class="[
                'scene-card',
                { selected: scene.selected, deleted: scene.deleted },
              ]"
            >
              <header>
                <v-checkbox
                  v-model="scene.selected"
                  :disabled="readOnly || currentStep !== 4 || scene.deleted"
                  hide-details
                  color="primary"
                  @update:model-value="onSceneCheckboxChange"
                />
                <div>
                  <strong>{{ scene.scene_no }} {{ scene.name }}</strong>
                  <small>
                    {{ scene.cluster_label }} · 证据覆盖
                    {{ Math.round(scene.evidence_coverage * 100) }}%
                  </small>
                </div>
                <v-btn
                  v-if="!readOnly && currentStep === 4"
                  size="x-small"
                  :color="scene.deleted ? 'error' : 'default'"
                  variant="text"
                  @click="toggleSceneDeleted(scene)"
                >
                  {{ scene.deleted ? "恢复" : "删除" }}
                </v-btn>
              </header>
              <dl>
                <dt>目标人群</dt>
                <dd>
                  {{
                    scene.target_audience ||
                    audienceText(scene.audience) ||
                    "未定义"
                  }}
                  <small
                    v-if="
                      scene.audience_scope &&
                      scene.audience_scope.claim_nos.length
                    "
                    class="scope-note"
                  >
                    锚定人群卖点：{{
                      scene.audience_scope.claim_nos.join("、")
                    }}（{{ scene.audience_scope.texts.join("；") }}）
                  </small>
                </dd>
                <dt>场景三要素</dt>
                <dd>
                  {{ scene.time_of_day || "待定" }} ·
                  {{ scene.location || "待定" }} ·
                  {{ scene.trigger_event || scene.trigger || "待定" }}
                </dd>
                <dt>核心痛点</dt>
                <dd>{{ scene.core_pain || "未定义" }}</dd>
                <dt>用户内心独白</dt>
                <dd>
                  <blockquote v-if="scene.inner_monologue" class="monologue">
                    {{ scene.inner_monologue }}
                  </blockquote>
                  <span v-else>未生成</span>
                </dd>
                <dt>内容钩子</dt>
                <dd>{{ scene.content_hook || "未生成" }}</dd>
                <dt>推荐信任锚</dt>
                <dd>
                  {{ (scene.trust_anchors || []).join(" + ") || "待确认" }}
                </dd>
                <template v-if="scene.brand_product?.length">
                  <dt>品牌名和产品名</dt>
                  <dd>{{ scene.brand_product.join("、") }}</dd>
                </template>
                <template v-if="scene.existing_channels?.length">
                  <dt>现有渠道</dt>
                  <dd>{{ scene.existing_channels.join("、") }}</dd>
                </template>
                <dt>建议平台</dt>
                <dd>
                  {{ scene.recommended_platforms.join("、") || "待确认" }}
                </dd>
              </dl>
              <div class="tag-row">
                <v-chip
                  v-for="keyword in scene.search_keywords || []"
                  :key="keyword"
                  size="x-small"
                  color="primary"
                  variant="tonal"
                  >{{ keyword }}</v-chip
                >
              </div>
              <small v-if="scene.keywords_notice" class="keywords-notice">
                {{ scene.keywords_notice }}
              </small>
              <div class="linked-claims">
                <span class="linked-label">关联已验证卖点：</span>
                <v-chip
                  v-for="linked in scene.linked_claims || []"
                  :key="linked.claim_id"
                  size="x-small"
                  :color="
                    linked.evidence_level === 'strong'
                      ? 'success'
                      : linked.evidence_level === 'weak'
                      ? 'warning'
                      : 'error'
                  "
                  variant="tonal"
                >
                  {{ linked.claim_no }}（{{ linked.text }}{{ linked.marker }}）
                </v-chip>
              </div>
              <div v-if="scene.user_voices?.length" class="voice-anchor">
                <span class="linked-label">用户原话锚点：</span>
                <ul>
                  <li v-for="voice in scene.user_voices" :key="voice.voice_id">
                    「{{ voice.text }}」<small>— {{ voice.source }}</small>
                  </li>
                </ul>
              </div>
              <div class="tag-row">
                <v-chip
                  v-for="topic in scene.blocked_topics"
                  :key="topic"
                  size="x-small"
                  color="error"
                  variant="tonal"
                  >禁用：{{ topic }}</v-chip
                >
              </div>
              <div
                v-if="!readOnly && currentStep === 4 && !scene.deleted"
                class="scene-review"
              >
                <v-btn-toggle
                  v-model="scene.priority"
                  density="compact"
                  color="primary"
                  divided
                >
                  <v-btn value="strong" size="x-small">强打</v-btn>
                  <v-btn value="weak" size="x-small">弱打</v-btn>
                </v-btn-toggle>
                <v-text-field
                  v-model="scene.note"
                  label="批注（可选）"
                  density="compact"
                  hide-details
                  maxlength="200"
                />
              </div>
            </article>
          </div>
          <div v-else class="empty-state">
            后端尚未生成场景，不能进入下一步。
          </div>
          <div id="scene-step-actions" class="step-actions">
            <v-btn
              color="primary"
              :loading="actionLoading"
              :disabled="
                readOnly ||
                currentStep !== 4 ||
                selectedSceneCount < 1 ||
                selectedSceneCount > 5
              "
              @click="confirmScenes"
            >
              确认场景选定清单，进入竞品扫描
            </v-btn>
          </div>
        </div>

        <div
          v-else-if="activeStep === 5"
          id="competitor-step"
          class="step-panel competitor-step-panel"
        >
          <div class="step-intro">
            <div>
              <h3>竞品内容扫描（基于真实数据）</h3>
              <p>
                实时采集小红书 / 抖音 / 知乎 /
                电商的竞品内容，由已配置的生成模型基于采集样本输出“内容缺口地图”。所有结论均引用真实样本，不编造数据。
              </p>
            </div>
            <v-chip color="primary" variant="tonal"
              >确认人：市场部 + 运营</v-chip
            >
          </div>

          <v-alert
            v-if="competitor?.legacy_skipped"
            type="info"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            该项目创建于竞品扫描功能上线前，已跳过此步骤。
          </v-alert>
          <v-alert
            v-if="project.product_type === 'RX'"
            type="warning"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            RX 产品仅做竞品研究参考，分析结果不会用于大众平台投放。
          </v-alert>
          <section class="competitor-form">
            <div class="step-actions">
              <v-btn
                color="primary"
                variant="tonal"
                :loading="competitorScanning"
                :disabled="readOnly || currentStep !== 5 || competitorAnalyzing"
                @click="scanCompetitors"
              >
                {{ competitor?.items?.length ? "补采" : "开始实时采集" }}
              </v-btn>
              <v-btn
                color="primary"
                :loading="competitorAnalyzing"
                :disabled="
                  readOnly ||
                  currentStep !== 5 ||
                  competitorScanning ||
                  !competitor?.items?.length
                "
                @click="analyzeCompetitors"
              >
                {{
                  competitorAnalysis?.gap_map?.length
                    ? "重新分析"
                    : "分析内容缺口"
                }}
              </v-btn>
            </div>
          </section>

          <div
            v-if="competitor?.scans?.length || competitor?.items?.length"
            class="competitor-group"
          >
            <span class="competitor-group-no">0</span>
            <span class="competitor-group-title">采集过程</span>
            <span class="competitor-group-desc">采集记录与原始样本</span>
          </div>
          <section
            v-if="competitor?.scans?.length"
            class="competitor-section sec-raw"
          >
            <h4>采集记录</h4>
            <ul class="competitor-list">
              <li v-for="scan in competitor.scans" :key="scan.scan_id">
                {{ scan.time }} · {{ scan.mode_label }} ·
                {{
                  scan.platforms.map(competitorPlatformLabel).join("、") ||
                  "公开链接"
                }}
                <template v-if="scan.per_keyword">
                  · 每词 {{ scan.per_keyword }} 条</template
                >
                · 获取 {{ scan.fetched }} 条 / 新增 {{ scan.added }} 条 ·
                {{ scan.operator }}
                <div v-if="scan.keyword_counts?.length" class="tag-row">
                  <v-chip
                    v-for="row in scan.keyword_counts"
                    :key="row.platform + row.keyword"
                    size="x-small"
                    variant="tonal"
                  >
                    {{ competitorPlatformLabel(row.platform) }}「{{
                      row.keyword
                    }}」{{ row.count }} 条
                  </v-chip>
                </div>
              </li>
            </ul>
          </section>

          <section
            v-if="competitor?.items?.length"
            class="competitor-section sec-raw"
          >
            <h4>
              采集样本<small class="sec-sub"
                >{{ competitor.items.length }} 条</small
              >
            </h4>
            <v-table density="compact" class="competitor-table">
              <thead>
                <tr>
                  <th>平台</th>
                  <th>标题 / 内容</th>
                  <th>互动</th>
                  <th>来源</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in competitor.items.slice(0, 100)"
                  :key="item.item_id"
                >
                  <td>{{ competitorPlatformLabel(item.platform) }}</td>
                  <td class="competitor-text">{{ item.title || item.text }}</td>
                  <td>
                    {{ item.likes ?? item.heat ?? "-" }}
                  </td>
                  <td>
                    <a
                      v-if="item.url"
                      :href="webUrl(item.url)"
                      target="_blank"
                      rel="noopener"
                      >链接</a
                    >
                    <span v-else>-</span>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </section>

          <template v-if="competitorAnalysis && competitor?.analyzed_at">
            <v-alert
              v-if="competitor.analysis_stale"
              type="warning"
              variant="tonal"
              density="compact"
              class="mb-3"
            >
              已补采新样本，当前分析已过期，请重新分析后再确认。
            </v-alert>
            <div class="competitor-report-head">
              <div class="competitor-report-kicker">竞品分析报告</div>
              <h3>
                竞品内容扫描
                <span class="competitor-report-date"
                  >{{
                    (competitor.analyzed_at || "").slice(0, 10)
                  }}
                  实时采集</span
                >
              </h3>
              <p
                v-if="competitorCollectionSummary"
                class="competitor-report-source"
              >
                采集方式：{{ competitorCollectionSummary }}
              </p>
              <p class="competitor-report-meta">
                分析模型：{{ competitor.provider_label || "已配置模型" }} ·
                {{ competitor.analyzed_at }}
              </p>
            </div>
            <v-alert
              v-if="sampleAssessment && !sampleAssessment.sufficient"
              type="warning"
              variant="tonal"
              density="compact"
              class="mb-3"
            >
              <div>
                <strong>样本不足</strong>
                <span v-if="sampleAssessment.post_count != null">
                  （内容样本 {{ sampleAssessment.post_count }} 条<template
                    v-if="sampleAssessment.price_count != null"
                    >，含价格 {{ sampleAssessment.price_count }} 条</template
                  ><template v-if="samplePlatformSummary"
                    >；{{ samplePlatformSummary }}</template
                  >）
                </span>
                ：{{ sampleAssessment.note || "缺口判断可能偏激进" }}
              </div>
              <div v-if="sampleAssessment.missing?.length" class="tag-row mt-2">
                <span>缺少：</span>
                <v-chip
                  v-for="item in sampleAssessment.missing"
                  :key="item"
                  size="x-small"
                  color="warning"
                  variant="outlined"
                >
                  {{ item }}
                </v-chip>
              </div>
              <div
                v-if="sampleAssessment.suggested_keywords?.length"
                class="tag-row mt-1"
              >
                <span>建议补采关键词：</span>
                <v-chip
                  v-for="keyword in sampleAssessment.suggested_keywords"
                  :key="keyword"
                  size="x-small"
                  variant="tonal"
                >
                  {{ keyword }}
                </v-chip>
              </div>
              <div
                v-if="sampleAssessment.suggested_platforms?.length"
                class="tag-row mt-1"
              >
                <span>建议补采平台：</span>
                <v-chip
                  v-for="platform in sampleAssessment.suggested_platforms"
                  :key="platform"
                  size="x-small"
                  variant="tonal"
                >
                  {{ competitorPlatformLabel(platform) }}
                </v-chip>
              </div>
              <div class="step-actions mt-2">
                <v-btn
                  size="small"
                  variant="tonal"
                  :disabled="
                    readOnly ||
                    currentStep !== 5 ||
                    competitorScanning ||
                    competitorAnalyzing
                  "
                  @click="applySampleSuggestions(false)"
                >
                  填入补采参数
                </v-btn>
                <v-btn
                  size="small"
                  color="primary"
                  :loading="competitorScanning"
                  :disabled="
                    readOnly || currentStep !== 5 || competitorAnalyzing
                  "
                  @click="applySampleSuggestions(true)"
                >
                  一键补采
                </v-btn>
              </div>
            </v-alert>

            <div id="competitor-market-group" class="competitor-group">
              <span class="competitor-group-no">1</span>
              <span class="competitor-group-title">市场格局</span>
              <span class="competitor-group-desc">内容热度 · 竞品价格带</span>
            </div>
            <section
              v-if="competitorAnalysis.content_heatmap?.length"
              class="competitor-section sec-heat"
            >
              <h4>
                <span class="sec-no">4.1</span>品类内容热度地图<small
                  class="sec-sub"
                  >本轮实证</small
                >
              </h4>
              <v-table density="compact" class="competitor-table">
                <thead>
                  <tr>
                    <th>内容主题</th>
                    <th>代表笔记</th>
                    <th>互动量</th>
                    <th>信号</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in competitorAnalysis.content_heatmap"
                    :key="row.theme"
                  >
                    <td>
                      <strong>{{ row.theme }}</strong>
                    </td>
                    <td class="competitor-text">
                      <template v-for="(id, index) in row.item_ids" :key="id">
                        <span v-if="index">、</span>
                        <a
                          v-if="competitorItemMap.get(id)?.url"
                          :href="webUrl(competitorItemMap.get(id)?.url)"
                          target="_blank"
                          rel="noopener"
                          >《{{ competitorItemTitle(id) }}》</a
                        >
                        <span v-else>《{{ competitorItemTitle(id) }}》</span>
                      </template>
                    </td>
                    <td>
                      {{
                        heatEngagementText(
                          row.item_ids,
                          row.commercial_item_ids,
                        )
                      }}
                    </td>
                    <td>
                      {{ heatSignalLabel(row.signal) }}
                      <span v-if="row.note"> {{ row.note }}</span>
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </section>

            <section
              v-if="
                competitorAnalysis.price_tiers?.length ||
                competitorAnalysis.our_position?.price
              "
              class="competitor-section sec-price"
            >
              <h4>
                <span class="sec-no">4.2</span>竞品价格带<small class="sec-sub"
                  >电商实证</small
                >
              </h4>
              <v-table density="compact" class="competitor-table">
                <thead>
                  <tr>
                    <th>层级</th>
                    <th>竞品</th>
                    <th>规格</th>
                    <th>实证价格</th>
                    <th>日服成本</th>
                    <th>定位</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, index) in competitorAnalysis.price_tiers"
                    :key="row.tier + row.brand + index"
                  >
                    <td>{{ row.tier }} {{ row.tier_label }}</td>
                    <td>
                      <a
                        v-if="
                          row.item_ids[0] &&
                          competitorItemMap.get(row.item_ids[0])?.url
                        "
                        :href="
                          webUrl(competitorItemMap.get(row.item_ids[0])?.url)
                        "
                        target="_blank"
                        rel="noopener"
                        >{{ row.brand }}</a
                      >
                      <span v-else>{{ row.brand }}</span>
                    </td>
                    <td>{{ row.spec || "-" }}</td>
                    <td>{{ row.price || "-" }}</td>
                    <td>{{ row.daily_cost || "-" }}</td>
                    <td>{{ row.positioning || "-" }}</td>
                  </tr>
                  <tr
                    v-if="competitorAnalysis.our_position?.price"
                    class="competitor-our-row"
                  >
                    <td><strong>本品</strong></td>
                    <td>
                      <strong>{{ project.product_name }}</strong>
                    </td>
                    <td>
                      <strong>{{
                        competitorAnalysis.our_position.spec || "-"
                      }}</strong>
                    </td>
                    <td>
                      <strong>{{
                        competitorAnalysis.our_position.price
                      }}</strong>
                    </td>
                    <td>
                      <strong>{{
                        competitorAnalysis.our_position.daily_cost || "-"
                      }}</strong>
                    </td>
                    <td>
                      <strong>{{
                        competitorAnalysis.our_position.note || "待重构"
                      }}</strong>
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </section>

            <div class="competitor-group">
              <span class="competitor-group-no">2</span>
              <span class="competitor-group-title">机会洞察</span>
              <span class="competitor-group-desc">内容缺口 · 信任锚</span>
            </div>
            <section class="competitor-section sec-gap competitor-gap-map">
              <h4>
                <span class="sec-no">4.3</span>内容缺口地图<small
                  class="sec-sub sec-sub-key"
                  >核心产出</small
                >
              </h4>
              <div v-if="competitorGaps.length" class="competitor-bulk-bar">
                <v-btn
                  size="small"
                  variant="tonal"
                  prepend-icon="mdi-checkbox-multiple-marked-outline"
                  :disabled="readOnly || currentStep !== 5"
                  @click="selectGapsAndScroll('all')"
                >
                  全选（按建议优先级）
                </v-btn>
                <v-btn
                  size="small"
                  variant="tonal"
                  :disabled="readOnly || currentStep !== 5"
                  @click="selectGaps('P0')"
                >
                  仅选建议 P0
                </v-btn>
                <v-btn
                  size="small"
                  variant="tonal"
                  :disabled="readOnly || currentStep !== 5"
                  @click="selectGaps('invert')"
                >
                  反选
                </v-btn>
                <v-btn
                  size="small"
                  variant="text"
                  :disabled="readOnly || currentStep !== 5 || !selectedGapCount"
                  @click="selectGaps('none')"
                >
                  清空
                </v-btn>
                <v-divider vertical class="mx-1" />
                <span class="competitor-meta">已选批量设为</span>
                <v-btn
                  size="small"
                  variant="outlined"
                  :disabled="readOnly || currentStep !== 5 || !selectedGapCount"
                  @click="setSelectedGapPriority('P0')"
                >
                  P0
                </v-btn>
                <v-btn
                  size="small"
                  variant="outlined"
                  :disabled="readOnly || currentStep !== 5 || !selectedGapCount"
                  @click="setSelectedGapPriority('P1')"
                >
                  P1
                </v-btn>
              </div>
              <v-table
                v-if="competitorGaps.length"
                density="compact"
                class="competitor-table"
              >
                <thead>
                  <tr>
                    <th>缺口</th>
                    <th>证据</th>
                    <th>{{ project.product_name || "本品" }}动作</th>
                    <th>蓝海切口选定</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="gap in competitorGaps"
                    :key="gap.gap_id"
                    :class="{ 'competitor-gap-selected': gap.selected }"
                  >
                    <td>
                      <strong>{{ gap.gap_id }} {{ gap.scene }}</strong>
                      <div v-if="gap.opportunity">
                        <small>{{ gap.opportunity }}</small>
                      </div>
                    </td>
                    <td class="competitor-text">
                      {{ gap.evidence || "-" }}
                      <div v-if="gap.item_ids.length" class="competitor-refs">
                        <template v-for="(id, index) in gap.item_ids" :key="id">
                          <span v-if="index">、</span>
                          <a
                            v-if="competitorItemMap.get(id)?.url"
                            :href="webUrl(competitorItemMap.get(id)?.url)"
                            target="_blank"
                            rel="noopener"
                            >《{{ competitorItemTitle(id) }}》</a
                          >
                          <span v-else>《{{ competitorItemTitle(id) }}》</span>
                        </template>
                      </div>
                    </td>
                    <td>
                      {{ gap.action || gap.entry_angle || "-" }}
                      <div v-if="gap.our_scene_no">
                        <small>对应场景 {{ gap.our_scene_no }}</small>
                      </div>
                    </td>
                    <td>
                      <v-checkbox
                        :model-value="gap.selected"
                        :label="`建议 ${gap.suggested_priority}`"
                        @update:model-value="toggleGap(gap, !!$event)"
                        density="compact"
                        hide-details
                        :disabled="readOnly || currentStep !== 5"
                      />
                      <v-btn-toggle
                        v-if="gap.selected"
                        v-model="gap.priority"
                        density="compact"
                        color="primary"
                        divided
                        :disabled="readOnly || currentStep !== 5"
                      >
                        <v-btn value="P0" size="x-small">P0</v-btn>
                        <v-btn value="P1" size="x-small">P1</v-btn>
                      </v-btn-toggle>
                    </td>
                  </tr>
                </tbody>
              </v-table>
              <div v-else class="empty-state">
                样本不足以判断内容缺口，请补采后重新分析。
              </div>
            </section>

            <section
              v-if="competitorAnalysis.trust_anchors?.length"
              class="competitor-section sec-trust"
            >
              <h4><span class="sec-no">4.4</span>信任锚类型分析</h4>
              <v-table density="compact" class="competitor-table">
                <thead>
                  <tr>
                    <th>信任锚</th>
                    <th>使用现状</th>
                    <th>{{ project.product_name || "本品" }}建议</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="anchor in competitorAnalysis.trust_anchors"
                    :key="anchor.type + anchor.label"
                    :class="{
                      'competitor-anchor-lead': anchor.stance === 'lead',
                    }"
                  >
                    <td>{{ anchor.label }}</td>
                    <td>
                      {{
                        anchor.usage_status ||
                        `竞品使用 ${anchor.usage_count} 次`
                      }}
                    </td>
                    <td>
                      <template v-if="anchor.stance">{{
                        anchorStanceLabel(anchor.stance)
                      }}</template>
                      <template v-if="anchor.stance && anchor.suggestion"
                        >（{{ anchor.suggestion }}）</template
                      >
                      <template v-else>{{ anchor.suggestion }}</template>
                    </td>
                  </tr>
                </tbody>
              </v-table>
            </section>

            <div class="competitor-group">
              <span class="competitor-group-no">3</span>
              <span class="competitor-group-title">内容策略</span>
              <span class="competitor-group-desc">内容公式 · 竞品入场信号</span>
            </div>
            <section class="competitor-section sec-formula">
              <h4>
                <span class="sec-no">4.5</span>内容公式<small class="sec-sub"
                  >可参考模板库</small
                >
              </h4>
              <div class="competitor-grid">
                <article
                  v-for="tpl in competitorAnalysis.formula_templates"
                  :key="tpl.template_id"
                  class="competitor-card formula-card"
                >
                  <span class="formula-platform">{{
                    competitorPlatformLabel(tpl.platform)
                  }}</span>
                  <div class="formula-step formula-open">
                    <span class="formula-label">开头</span>
                    <span>{{ tpl.opening || "-" }}</span>
                  </div>
                  <div class="formula-step formula-middle">
                    <span class="formula-label">中间</span>
                    <span>{{ tpl.middle || "-" }}</span>
                  </div>
                  <div class="formula-step formula-end">
                    <span class="formula-label">结尾</span>
                    <span>{{ tpl.ending || "-" }}</span>
                  </div>
                </article>
              </div>
            </section>

            <section
              v-if="competitorAnalysis.competitor_signals?.length"
              class="competitor-section sec-signal"
            >
              <h4><span class="sec-no">4.6</span>竞品入场信号</h4>
              <div class="signal-list">
                <div
                  v-for="sig in competitorAnalysis.competitor_signals"
                  :key="sig.signal_id"
                  class="signal-item"
                >
                  <div class="signal-brand">
                    <v-icon size="16" color="error">mdi-alert-outline</v-icon>
                    {{ sig.brand || sig.signal_id }}
                  </div>
                  <div class="signal-text">{{ sig.signal }}</div>
                  <div v-if="sig.item_ids.length" class="signal-refs">
                    来源：{{ sig.item_ids.map(competitorItemTitle).join("、") }}
                  </div>
                </div>
              </div>
            </section>

            <div id="competitor-user-platform-group" class="competitor-group">
              <span class="competitor-group-no">4</span>
              <span class="competitor-group-title">用户与平台</span>
              <span class="competitor-group-desc">用户原话 · 平台调性</span>
            </div>
            <section class="competitor-section sec-voice">
              <h4>
                <span class="sec-no">4.7</span>用户真实评论<small
                  class="sec-sub"
                  >勾选后导入场景用户原话</small
                >
              </h4>
              <div
                v-if="competitorAnalysis.user_voices.length"
                class="competitor-bulk-bar"
              >
                <v-btn
                  size="small"
                  variant="tonal"
                  prepend-icon="mdi-checkbox-multiple-marked-outline"
                  :disabled="readOnly || currentStep !== 5"
                  @click="
                    competitorVoiceImports = competitorAnalysis.user_voices.map(
                      (v) => v.item_id,
                    )
                  "
                >
                  全选
                </v-btn>
                <v-btn
                  size="small"
                  variant="text"
                  :disabled="
                    readOnly ||
                    currentStep !== 5 ||
                    !competitorVoiceImports.length
                  "
                  @click="competitorVoiceImports = []"
                >
                  清空
                </v-btn>
                <span class="competitor-meta">
                  已选 {{ competitorVoiceImports.length }} /
                  {{ competitorAnalysis.user_voices.length }} 条
                </span>
              </div>
              <div
                v-for="voice in competitorAnalysis.user_voices"
                :key="voice.item_id"
                class="competitor-voice"
              >
                <v-checkbox
                  v-model="competitorVoiceImports"
                  :value="voice.item_id"
                  density="compact"
                  hide-details
                  :disabled="readOnly || currentStep !== 5"
                />
                <div>
                  <blockquote class="monologue">
                    「{{ voice.quote }}」
                  </blockquote>
                  <small class="voice-meta">
                    {{ competitorPlatformLabel(voice.platform) }}
                    <template v-if="voice.likes != null">
                      · 赞 {{ voice.likes }}</template
                    >
                    <span v-if="voice.pain_point" class="voice-pain">
                      · 痛点：{{ voice.pain_point }}</span
                    >
                  </small>
                </div>
              </div>
              <div
                v-if="!competitorAnalysis.user_voices.length"
                class="empty-state"
              >
                用户原话样本不足，请补采评论。
              </div>
            </section>

            <section class="competitor-section sec-platform">
              <h4>
                <span class="sec-no">4.8</span>平台调性<small class="sec-sub"
                  >分平台策略</small
                >
              </h4>
              <div class="competitor-grid">
                <article
                  v-for="row in competitorAnalysis.platform_strategy"
                  :key="row.platform"
                  class="competitor-card"
                >
                  <div class="platform-name">{{ row.platform_label }}</div>
                  <div v-if="row.tone" class="platform-tone">
                    调性：{{ row.tone }}
                  </div>
                  <div class="platform-strategy">{{ row.strategy }}</div>
                </article>
              </div>
            </section>

            <v-alert
              v-if="competitorAnalysis.compliance_note"
              type="info"
              variant="tonal"
              density="compact"
              class="mb-3"
            >
              {{ competitorAnalysis.compliance_note }}
            </v-alert>
          </template>

          <div id="competitor-step-actions" class="step-actions">
            <span class="competitor-meta">
              已选蓝海切口 {{ selectedGapCount }} 个（P0
              {{ selectedP0Count }} 个） · 导入原话
              {{ competitorVoiceImports.length }} 条 · 返工：遗漏头部品牌 /
              缺口过于激进 / 样本不足 → 补采或重新分析
            </span>
            <v-btn
              color="primary"
              :loading="actionLoading"
              :disabled="readOnly || currentStep !== 5 || !canConfirmCompetitor"
              @click="confirmCompetitor"
            >
              {{
                currentStep > 5
                  ? "竞品地图已确认（如需修改请发起返工）"
                  : "确认竞品地图与蓝海切口，进入合规过滤"
              }}
            </v-btn>
          </div>
        </div>

        <div
          v-else-if="activeStep === 6"
          class="step-panel compliance-step-panel"
        >
          <div class="step-intro">
            <div>
              <h3>合规过滤引擎</h3>
              <p>
                竞品样本与品牌存量内容（软文 / 素人帖 /
                账号矩阵）执行中睿三级规则过滤： 🔴 一级红线拦截 / 🟡
                二级谨慎标记 / 🟢 三级建议替换；规则命中不可被模型或搜索撤销，
                合规部逐条复核、确认存量处置清单与广审文号申请排期后方可进入搜索词排序。
              </p>
            </div>
            <v-chip
              :color="
                complianceFilter?.label
                  ? complianceLabelColor(
                      complianceFilter.label as ComplianceLabel,
                    )
                  : 'default'
              "
              variant="tonal"
            >
              {{
                complianceFilter?.label_text ||
                (filterScanned ? "已初筛" : "尚未初筛")
              }}
            </v-chip>
          </div>
          <v-alert
            v-if="
              complianceFilter?.rx_patient_only || project.product_type === 'RX'
            "
            type="error"
            variant="tonal"
            class="status-alert"
          >
            处方药禁止大众媒体广告，只能走患者管理路径。
          </v-alert>
          <v-alert
            v-if="complianceFilter?.legacy_skipped"
            type="info"
            variant="tonal"
            density="compact"
            class="status-alert"
          >
            该项目创建于合规过滤引擎上线前.已按历史版本跳过。
          </v-alert>
          <v-expansion-panels class="compliance-kb-panel" variant="accordion">
            <v-expansion-panel value="filter-kb">
              <v-expansion-panel-title>
                <v-icon icon="mdi-shield-star-outline" class="mr-2" size="18" />
                过滤底座 · {{ complianceKb?.builder || "中睿医药商学院" }}
                <v-chip
                  v-if="complianceKb"
                  size="x-small"
                  variant="tonal"
                  class="ml-2"
                  >{{ complianceKb.kb_version }} · 规则 V{{
                    complianceKb.rule_version
                  }}
                  · 过滤规则
                  {{ complianceKb.filter_rule_version || "—" }}</v-chip
                >
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <div v-if="complianceKb" class="compliance-kb">
                  <p>
                    {{ complianceKb.builder_profile }} ·
                    {{ complianceKb.endorsement }}
                  </p>
                  <p v-if="complianceKb.filter_basis">
                    <b>依据口径：</b>{{ complianceKb.filter_basis }}
                  </p>
                  <p v-if="complianceKb.filter_notice">
                    {{ complianceKb.filter_notice }}
                  </p>
                  <template v-if="complianceKb.filter_categories">
                    <h4>违规分类</h4>
                    <div class="tag-row">
                      <v-chip
                        v-for="(label, code) in complianceKb.filter_categories"
                        :key="code"
                        size="small"
                        variant="tonal"
                        >{{ label }}</v-chip
                      >
                    </div>
                  </template>
                  <template v-if="complianceKb.filter_replacements?.length">
                    <h4>三级建议替换</h4>
                    <div class="tag-row">
                      <v-chip
                        v-for="row in complianceKb.filter_replacements"
                        :key="row.original"
                        size="small"
                        variant="tonal"
                        :color="row.replacement ? 'success' : 'error'"
                        >{{ row.original }} →
                        {{ row.replacement || "❌ 删除，无替换" }}</v-chip
                      >
                    </div>
                  </template>
                  <template v-if="complianceKb.disposal_actions">
                    <h4>存量处置动作</h4>
                    <div class="tag-row">
                      <v-chip
                        v-for="(label, code) in complianceKb.disposal_actions"
                        :key="code"
                        size="small"
                        variant="outlined"
                        >{{ label }}</v-chip
                      >
                    </div>
                  </template>
                </div>
                <div v-else class="empty-state">合规知识库目录加载中…</div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>

          <section class="compliance-section compliance-run-section">
            <header>
              <h4>运行合规过滤（规则初筛 + 本地知识库 + 模型复核）</h4>
            </header>
            <div class="platform-picker">
              <v-select
                v-model="filterKbIds"
                :items="kbOptions"
                :loading="kbLoading"
                label="选择本地药企知识库（可多选，留空仅规则 + 模型复核）"
                multiple
                chips
                closable-chips
                variant="outlined"
                hide-details
                :disabled="!canEditFilter"
              />
              <v-btn
                color="primary"
                prepend-icon="mdi-shield-search"
                :loading="filterRunning"
                :disabled="!canEditFilter"
                @click="runComplianceFilter"
                >{{
                  filterScanned ? "重新运行合规过滤" : "运行合规过滤"
                }}</v-btn
              >
            </div>
            <v-checkbox
              v-model="filterAiSearch"
              label="AI 搜索交叉验证（联网检索监管口径，只能追加风险）"
              density="compact"
              hide-details
              :disabled="!canEditFilter"
            />
          </section>

          <template v-if="complianceFilter && filterScanned">
            <section class="compliance-section compliance-results-section">
              <header>
                <h4>5.1 三级过滤结果</h4>
                <div class="tag-row">
                  <v-chip
                    size="small"
                    variant="tonal"
                    :color="
                      complianceLabelColor(
                        complianceFilter.label as ComplianceLabel,
                      )
                    "
                    >{{ complianceFilter.label_text }}</v-chip
                  >
                  <v-chip size="small" color="success" variant="tonal"
                    >✅ 合规 {{ complianceFilter.summary?.pass || 0 }}</v-chip
                  >
                  <v-chip size="small" color="warning" variant="tonal"
                    >⚠️ 谨慎
                    {{ complianceFilter.summary?.caution || 0 }}</v-chip
                  >
                  <v-chip size="small" color="error" variant="tonal"
                    >❌ 违规
                    {{ complianceFilter.summary?.blocked || 0 }}</v-chip
                  >
                  <v-chip size="small" variant="outlined"
                    >{{ complianceFilter.kb_version }} · 规则 V{{
                      complianceFilter.rule_version
                    }}
                    · 过滤规则
                    {{ complianceFilter.filter_rule_version }}</v-chip
                  >
                </div>
              </header>
              <small
                >初筛时间：{{ formatDateTime(complianceFilter.scanned_at) }}
                <template v-if="complianceFilter.basis">
                  · 依据：{{ complianceFilter.basis }}</template
                ></small
              >
              <div
                v-if="
                  Object.keys(complianceFilter.category_summary || {}).length
                "
                class="keyword-table-wrap"
              >
                <table class="keyword-table">
                  <thead>
                    <tr>
                      <th>违规分类</th>
                      <th>🔴 拦截</th>
                      <th>🟡 谨慎</th>
                      <th>🟢 替换</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(row, code) in complianceFilter.category_summary"
                      :key="code"
                    >
                      <td>{{ row.label }}</td>
                      <td>{{ row.block }}</td>
                      <td>{{ row.caution }}</td>
                      <td>{{ row.replace }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-if="complianceFilter.samples?.length" class="tag-row">
                <v-chip
                  v-for="sample in complianceFilter.samples"
                  :key="sample.content_id"
                  size="small"
                  variant="tonal"
                  :color="complianceLabelColor(sample.label as ComplianceLabel)"
                  >{{ sampleSourceLabel(sample.source) }} ·
                  {{ sample.platform || "—" }} ·
                  {{ (sample.title || "无标题").slice(0, 18) }} ·
                  {{ sample.label_text }}</v-chip
                >
              </div>
              <div
                v-for="group in filterRiskGroups"
                :key="group.level"
                class="filter-risk-group"
              >
                <h5>{{ group.title }}（{{ group.risks.length }}）</h5>
                <div v-if="group.risks.length" class="risk-list">
                  <div
                    v-for="(risk, index) in group.risks"
                    :key="risk.risk_id || `${group.level}-${index}`"
                    class="risk-item"
                    :class="riskClass(risk.level)"
                  >
                    <div class="risk-item-head">
                      <strong>{{ riskLevelLabel(risk.level) }}</strong>
                      <span>{{ risk.message }}</span>
                      <small
                        >{{ sampleSourceLabel(risk.sample_source) }} ·
                        {{ risk.platform || "全部平台" }} ·
                        {{ riskSourceLabel(risk.source) }}
                        <template v-if="risk.rule_id">
                          · {{ risk.rule_id }}</template
                        ></small
                      >
                    </div>
                    <div
                      v-if="filterSampleTitle(risk.content_id)"
                      class="risk-item-line"
                    >
                      所属内容：{{ filterSampleTitle(risk.content_id) }}
                    </div>
                    <div
                      v-if="risk.level === 'replace' && risk.matched_text"
                      class="risk-item-line"
                    >
                      <mark>{{ risk.matched_text }}</mark> →
                      <b>{{ risk.replacement || "❌ 删除，无替换" }}</b>
                    </div>
                    <div v-else-if="risk.matched_text" class="risk-item-line">
                      命中原文：<mark>{{ risk.matched_text }}</mark>
                    </div>
                    <div v-if="risk.legal_basis" class="risk-item-line">
                      依据：{{ risk.legal_basis }}
                    </div>
                    <div v-if="risk.suggestion" class="risk-item-line">
                      修改建议：{{ risk.suggestion }}
                    </div>
                    <div
                      v-if="
                        risk.risk_id &&
                        (risk.level === 'caution' || risk.level === 'replace')
                      "
                      class="risk-review"
                    >
                      <v-btn-toggle
                        v-model="filterReviewDraft(risk.risk_id).decision"
                        density="compact"
                        divided
                        color="primary"
                        :disabled="!canEditFilter"
                      >
                        <v-btn value="adopt" size="x-small">采纳建议</v-btn>
                        <v-btn value="keep" size="x-small">保留原文</v-btn>
                      </v-btn-toggle>
                      <v-text-field
                        v-model="filterReviewDraft(risk.risk_id).note"
                        density="compact"
                        variant="outlined"
                        hide-details
                        :disabled="!canEditFilter"
                        :label="
                          risk.level === 'caution'
                            ? '合规批注（谨慎项必填）'
                            : '合规批注（可选）'
                        "
                      />
                    </div>
                  </div>
                </div>
                <div v-else class="empty-state compact">无</div>
              </div>
              <v-alert
                v-if="complianceFilter.ai_review?.notice"
                type="info"
                variant="tonal"
                density="compact"
                class="ui-hidden"
              >
                {{ complianceFilter.ai_review.notice }}
                <template v-if="complianceFilter.ai_review.kb_warning">
                  （{{ complianceFilter.ai_review.kb_warning }}）</template
                >
              </v-alert>
              <ul
                v-if="complianceFilter.kb_hits?.length"
                class="competitor-list"
              >
                <li
                  v-for="(hit, index) in complianceFilter.kb_hits"
                  :key="`filter-kb-hit-${index}`"
                >
                  <strong>{{ hit.kb_name || "知识库" }}</strong>
                  <span v-if="hit.doc_name"> / {{ hit.doc_name }}</span>
                  <small> · 相关度 {{ hit.score }}</small>
                  <p>{{ hit.excerpt }}</p>
                </li>
              </ul>
              <v-alert
                v-if="complianceFilter.cross_validation?.conclusion"
                :type="
                  complianceFilter.cross_validation.warning?.includes(
                    '已自动重试',
                  )
                    ? 'error'
                    : complianceFilter.cross_validation.warning
                    ? 'warning'
                    : 'info'
                "
                variant="tonal"
                density="compact"
                class="ui-hidden"
              >
                AI 搜索交叉验证：{{
                  complianceFilter.cross_validation.conclusion
                }}
                <template v-if="complianceFilter.cross_validation.warning">
                  （{{ complianceFilter.cross_validation.warning }}）</template
                >
              </v-alert>
            </section>
          </template>

          <section class="compliance-section compliance-signoff-section">
            <header>
              <h4>
                🔍 人工确认节点（最关键）· 合规部签字（必须本人，不可代签）
              </h4>
              <v-chip
                size="small"
                variant="tonal"
                :color="filterPendingReviewCount ? 'warning' : 'success'"
                >待批注 {{ filterPendingReviewCount }} /
                {{ filterReviewableRisks.length }}</v-chip
              >
            </header>
            <div v-if="filterRecord" class="compliance-record">
              <div><b>确认记录</b>{{ filterRecord.record_id }}</div>
              <div>
                <b>签字</b>{{ filterRecord.signer_name }}（{{
                  filterRecord.signer_title
                }}） · {{ formatDateTime(filterRecord.signed_at) }}
              </div>
              <div>
                <b>知识库版本</b>{{ filterRecord.kb_builder }} ·
                {{ filterRecord.kb_version }} · 规则 V{{
                  filterRecord.rule_version
                }}
                · 过滤规则 {{ filterRecord.filter_rule_version }}
              </div>
              <div>
                <b>检索日期</b
                >{{ formatDateTime(filterRecord.retrieval_date) }} · 初筛
                {{ formatDateTime(filterRecord.scanned_at) }}
              </div>
              <div v-if="filterRecord.basis">
                <b>依据</b>{{ filterRecord.basis }}
              </div>
              <div>
                <b>过滤结论</b>✅{{ filterRecord.summary?.pass || 0 }} / ⚠️{{
                  filterRecord.summary?.caution || 0
                }}
                / ❌{{ filterRecord.summary?.blocked || 0 }} · 风险
                {{ filterRecord.risk_count || 0 }} 项
              </div>
              <div>
                <b>处理情况</b>谨慎项批注 {{ filterRecord.caution_reviewed }} 条
                · 采纳替换 {{ filterRecord.replace_adopted }} 条 · 存量处置
                {{ filterRecord.disposal_count }} 项 · 答疑工单
                {{ filterRecord.expert_ticket_ids?.length || 0 }} 个
              </div>
              <div v-if="filterRecord.ad_review_schedule">
                <b>广审排期</b
                >{{ filterRecord.ad_review_schedule.apply_date }} ·
                {{ filterRecord.ad_review_schedule.authority }}
                <template v-if="filterRecord.ad_review_schedule.note">
                  · {{ filterRecord.ad_review_schedule.note }}</template
                >
              </div>
              <div><b>操作人</b>{{ filterRecord.operator || "—" }}</div>
              <div v-if="filterRecord.confirm_checks?.length">
                <b>确认内容</b>
                <span class="tag-row">
                  <v-chip
                    v-for="label in filterRecord.confirm_checks"
                    :key="label"
                    size="x-small"
                    color="success"
                    variant="tonal"
                    prepend-icon="mdi-check"
                    >{{ label }}</v-chip
                  >
                </span>
              </div>
              <div v-if="filterRecord.comment">
                <b>备注</b>{{ filterRecord.comment }}
              </div>
              <div v-if="filterRecord.endorsement">
                <b>背书</b>{{ filterRecord.endorsement }}
              </div>
            </div>
            <template v-else>
              <div
                v-if="filterReviewableRisks.length"
                class="zr-confirm-checks"
              >
                <b
                  >谨慎/替换项逐条复核（待处理 {{ filterPendingReviewCount }} /
                  {{ filterReviewableRisks.length }}，须逐条选择「采纳建议 /
                  保留原文」，谨慎项须填写批注）</b
                >
                <div id="filter-adopt-all">
                  <v-btn
                    size="small"
                    variant="tonal"
                    color="primary"
                    prepend-icon="mdi-check-all"
                    :disabled="!canEditFilter || !filterPendingReviewCount"
                    @click="adoptAllFilterReviews"
                    >一键全部采纳建议</v-btn
                  >
                </div>
                <div
                  v-for="risk in filterReviewableRisks"
                  :key="`pending-${risk.risk_id}`"
                  class="risk-item"
                  :class="riskClass(risk.level)"
                >
                  <div class="risk-item-head">
                    <strong>{{ riskLevelLabel(risk.level) }}</strong>
                    <span>{{ risk.message }}</span>
                    <v-chip
                      size="x-small"
                      variant="tonal"
                      :color="
                        filterPendingReviewRisks.includes(risk)
                          ? 'warning'
                          : 'success'
                      "
                      >{{
                        filterPendingReviewRisks.includes(risk)
                          ? "待处理"
                          : "已处理"
                      }}</v-chip
                    >
                    <small>{{ risk.platform || "全部平台" }}</small>
                  </div>
                  <div v-if="risk.matched_text" class="risk-item-line">
                    命中原文：<mark>{{ risk.matched_text }}</mark>
                    <template v-if="risk.level === 'replace'">
                      →
                      <b>{{
                        risk.replacement || "❌ 删除，无替换"
                      }}</b></template
                    >
                  </div>
                  <div class="risk-review">
                    <v-btn-toggle
                      v-model="
                        filterReviewDraft(risk.risk_id as string).decision
                      "
                      density="compact"
                      divided
                      color="primary"
                      :disabled="!canEditFilter"
                    >
                      <v-btn value="adopt" size="x-small">采纳建议</v-btn>
                      <v-btn value="keep" size="x-small">保留原文</v-btn>
                    </v-btn-toggle>
                    <v-text-field
                      v-model="filterReviewDraft(risk.risk_id as string).note"
                      density="compact"
                      variant="outlined"
                      hide-details
                      :disabled="!canEditFilter"
                      :label="
                        risk.level === 'caution'
                          ? '合规批注（谨慎项必填）'
                          : '合规批注（可选）'
                      "
                    />
                  </div>
                </div>
              </div>
              <div class="zr-confirm-checks">
                <b>确认内容（合规部须逐项勾选）</b>
                <div class="zr-confirm-checks-grid">
                  <v-checkbox
                    v-for="item in ZR_CONFIRM_CHECKS"
                    :key="item.value"
                    v-model="filterConfirmChecks"
                    :value="item.value"
                    :label="item.label"
                    density="compact"
                    hide-details
                    color="primary"
                    :disabled="!canEditFilter"
                  />
                </div>
                <small
                  v-if="!filterConfirmChecksComplete"
                  class="zr-confirm-hint"
                  >尚有
                  {{ ZR_CONFIRM_CHECKS.length - filterConfirmChecks.length }}
                  项未勾选，全部确认后方可签字提交。</small
                >
              </div>
              <div class="compliance-sign-form">
                <v-text-field
                  v-model="filterSignerTitle"
                  label="部门/职务（须含“合规”）"
                  density="compact"
                  variant="outlined"
                  hide-details
                  :disabled="!canEditFilter"
                />
                <v-text-field
                  v-model="filterApplyDate"
                  type="date"
                  label="广审文号申请排期（YYYY-MM-DD）"
                  density="compact"
                  variant="outlined"
                  hide-details
                  :disabled="!canEditFilter"
                />
                <v-text-field
                  v-model="filterAuthority"
                  label="广审受理机关"
                  density="compact"
                  variant="outlined"
                  hide-details
                  :disabled="!canEditFilter"
                />
                <v-text-field
                  v-model="filterAdNote"
                  label="广审排期备注"
                  density="compact"
                  variant="outlined"
                  hide-details
                  :disabled="!canEditFilter"
                />
                <v-text-field
                  v-model="filterComment"
                  label="确认意见（写入审计记录）"
                  density="compact"
                  variant="outlined"
                  hide-details
                  :disabled="!canEditFilter"
                />
              </div>
            </template>
          </section>

          <div class="step-actions split">
            <span class="compliance-boundary"
              >内部合规过滤不等同于行政广告审查，发布前仍须取得广告审查批准文号。</span
            >
            <v-btn
              color="primary"
              :loading="actionLoading"
              :disabled="
                !canEditFilter ||
                !filterScanned ||
                filterInventoryDirty ||
                Boolean(filterRecord) ||
                !filterConfirmChecksComplete
              "
              @click="confirmComplianceFilter"
            >
              合规部确认并进入下一步
            </v-btn>
          </div>
        </div>

        <div v-else-if="activeStep === 7" class="step-panel">
          <div class="step-intro">
            <div>
              <h3>搜索词与内容优先级</h3>
              <p>来源标签必须如实显示；模型建议词不代表真实平台搜索量。</p>
            </div>
            <div class="keyword-actions">
              <v-text-field
                v-model="keywordSearch"
                prepend-inner-icon="mdi-magnify"
                placeholder="搜索关键词或来源"
                density="compact"
                variant="outlined"
                hide-details
                clearable
              />
              <v-btn
                variant="tonal"
                :disabled="readOnly"
                @click="selectRecommended"
                >选择高置信度</v-btn
              >
              <v-btn
                variant="text"
                :disabled="readOnly"
                @click="clearKeywordSelection"
                >清空</v-btn
              >
            </div>
          </div>
          <div class="keyword-table-wrap">
            <table class="keyword-table">
              <thead>
                <tr>
                  <th class="check-col">采用</th>
                  <th>关键词</th>
                  <th>来源</th>
                  <th>平台/时间</th>
                  <th>页码</th>
                  <th>置信度</th>
                  <th>优先级</th>
                  <th>原文证据</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="keyword in filteredKeywords"
                  :key="keyword.keyword_id"
                  :class="{ selected: keyword.selected }"
                >
                  <td class="check-col">
                    <v-checkbox
                      v-model="keyword.selected"
                      :disabled="readOnly || currentStep !== 7"
                      color="primary"
                      hide-details
                      density="compact"
                    />
                  </td>
                  <td>
                    <v-text-field
                      v-model="keyword.keyword"
                      :disabled="readOnly || currentStep !== 7"
                      variant="plain"
                      density="compact"
                      hide-details
                    />
                  </td>
                  <td>
                    <v-chip size="small" variant="tonal">{{
                      keywordSourceLabel(keyword.source_type)
                    }}</v-chip>
                  </td>
                  <td>
                    {{ keyword.platform || "—"
                    }}<small class="table-subtext">{{
                      keyword.observed_at
                        ? formatDate(keyword.observed_at)
                        : "无观测时间"
                    }}</small>
                  </td>
                  <td>{{ keyword.page_no ? `P${keyword.page_no}` : "—" }}</td>
                  <td>
                    <span
                      :class="[
                        'score-dot',
                        confidenceClass(keyword.confidence),
                      ]"
                    />{{ Math.round(keyword.confidence * 100) }}%
                  </td>
                  <td>
                    <strong>{{ keyword.priority_score.toFixed(1) }}</strong>
                  </td>
                  <td>
                    <div class="source-cell" :title="keyword.source_text">
                      {{ keyword.source_text }}
                    </div>
                  </td>
                </tr>
                <tr v-if="filteredKeywords.length === 0">
                  <td colspan="8" class="empty-row">没有匹配的关键词</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="step-actions split">
            <v-btn
              variant="tonal"
              prepend-icon="mdi-download-outline"
              :loading="exporting"
              @click="exportKeywords"
              >导出草稿关键词 CSV</v-btn
            >
            <v-btn
              color="primary"
              :loading="actionLoading"
              :disabled="readOnly || currentStep !== 7 || !selectedKeywordCount"
              @click="confirmKeywords"
            >
              确认搜索词，进入医学证据
            </v-btn>
          </div>
        </div>

        <div v-else-if="activeStep === 8" class="step-panel">
          <div class="step-intro">
            <div>
              <h3>卖点—证据映射与医学确认</h3>
              <p>无证据卖点不能进入内容白名单；弱证据只能使用弱化表达。</p>
            </div>
            <v-chip
              :color="
                confirmedClaimCount === claims.length && claims.length
                  ? 'success'
                  : 'warning'
              "
              variant="tonal"
            >
              {{ confirmedClaimCount }}/{{ claims.length }} 已确认
            </v-chip>
          </div>
          <div v-if="claims.length" class="claim-list">
            <article
              v-for="claim in claims"
              :key="claim.claim_id"
              class="claim-card"
            >
              <header>
                <div>
                  <strong>{{ claimText(claim) }}</strong
                  ><small>Claim ID：{{ claim.claim_id }}</small>
                </div>
                <v-chip
                  :color="evidenceColor(claim.evidence_level)"
                  size="small"
                  variant="tonal"
                  >{{ evidenceLabel(claim.evidence_level) }}</v-chip
                >
              </header>
              <div class="claim-evidence">
                <v-icon icon="mdi-book-open-page-variant-outline" size="18" />
                <div>
                  <p>
                    {{
                      claim.source_text ||
                      claim.evidence?.[0]?.source_text ||
                      "无证据片段"
                    }}
                  </p>
                  <small
                    >{{ claim.page_no ? `第 ${claim.page_no} 页` : "无页码" }} ·
                    {{ claim.source_field || "来源未标记" }}</small
                  >
                </div>
              </div>
              <v-checkbox
                v-model="claim.medical_confirmed"
                :disabled="
                  readOnly ||
                  currentStep !== 8 ||
                  claim.evidence_level === 'none'
                "
                color="primary"
                label="医学人员已核对证据并确认可用"
                hide-details
              />
            </article>
          </div>
          <div v-else class="empty-state">
            尚无卖点—证据映射；第 8 步保持锁定。
          </div>
          <div class="step-actions">
            <v-btn
              color="primary"
              :loading="actionLoading"
              :disabled="readOnly || currentStep !== 8 || !canConfirmEvidence"
              @click="confirmEvidence"
            >
              医学确认，进入内容工厂
            </v-btn>
          </div>
        </div>

        <div v-else-if="activeStep === 9" id="approval-step" class="step-panel">
          <div class="step-intro">
            <div>
              <h3>多平台内容、合规过滤与终审</h3>
              <p>
                内容只能使用已确认 Claim；三层合规规则（🔴红线拦截 / 🟡谨慎标记
                / 🟢建议替换）自动贴标，❌ 违规项未返工前不能确认。
              </p>
            </div>
            <v-chip
              :color="
                hasBlockingRisk
                  ? 'error'
                  : complianceReport?.label === 'caution'
                  ? 'warning'
                  : contents.length
                  ? 'success'
                  : 'warning'
              "
              variant="tonal"
            >
              {{
                complianceReport?.label_text ||
                (hasBlockingRisk
                  ? "存在阻断风险"
                  : contents.length
                  ? "已生成待审内容"
                  : "尚未生成")
              }}
            </v-chip>
          </div>
          <v-alert
            v-if="project.product_type === 'RX'"
            type="error"
            variant="tonal"
            class="status-alert"
          >
            RX 禁止大众媒体广告：社媒内容直接拒绝生成，只能走患者管理路径。
          </v-alert>
          <v-expansion-panels class="compliance-kb-panel" variant="accordion">
            <v-expansion-panel value="kb">
              <v-expansion-panel-title>
                <v-icon icon="mdi-shield-star-outline" class="mr-2" size="18" />
                合规知识库底座 · {{ complianceKb?.builder || "中睿医药商学院" }}
                <v-chip
                  v-if="complianceKb"
                  size="x-small"
                  variant="tonal"
                  class="ml-2"
                  >{{ complianceKb.kb_version }} · 规则 V{{
                    complianceKb.rule_version
                  }}</v-chip
                >
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <div v-if="complianceKb" class="compliance-kb">
                  <p>
                    {{ complianceKb.builder_profile }} ·
                    {{ complianceKb.endorsement }}
                  </p>
                  <div class="compliance-kb-layers">
                    <article
                      v-for="layer in complianceKb.layers"
                      :key="layer.layer_id"
                    >
                      <strong>{{ layer.name }}</strong>
                      <ul>
                        <li v-for="item in layer.items" :key="item">
                          {{ item }}
                        </li>
                      </ul>
                    </article>
                  </div>
                  <h4>更新与解读机制</h4>
                  <ul>
                    <li
                      v-for="item in complianceKb.update_mechanism"
                      :key="item"
                    >
                      {{ item }}
                    </li>
                  </ul>
                  <h4>三级建议替换</h4>
                  <div class="tag-row">
                    <v-chip
                      v-for="row in complianceKb.replacements"
                      :key="row.original"
                      size="small"
                      variant="tonal"
                      color="success"
                      >{{ row.original }} → {{ row.replacement }}</v-chip
                    >
                  </div>
                </div>
                <div v-else class="empty-state">合规知识库目录加载中…</div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>

          <div class="platform-picker batch-generator-panel">
            <v-select
              v-model="batchChannels"
              :items="batchChannelOptions"
              label="批量内容生产 · 分平台渠道（一次输入，多平台产出）"
              multiple
              chips
              closable-chips
              variant="outlined"
              :disabled="readOnly || currentStep !== 9 || batchGenerating"
              hide-details
            />
            <v-text-field
              v-model.number="batchTotal"
              type="number"
              min="10"
              max="50"
              label="选题总数"
              variant="outlined"
              hide-details
              style="max-width: 120px"
              :disabled="readOnly || currentStep !== 9 || batchGenerating"
            />
            <v-btn
              color="primary"
              variant="flat"
              prepend-icon="mdi-layers-triple-outline"
              :loading="batchGenerating"
              :disabled="
                readOnly ||
                currentStep !== 9 ||
                actionLoading ||
                !batchChannels.length
              "
              @click="generateContentBatch"
            >
              批量生成（AI 模型）
            </v-btn>
          </div>

          <section
            v-if="contentBatch"
            id="batch-report-top"
            class="batch-report"
          >
            <header class="batch-report-hero">
              <div class="batch-report-kicker">CONTENT PRODUCTION PLAN</div>
              <h3>批量内容生产规划</h3>
              <blockquote class="competitor-report-source">
                 {{ contentBatch.scene_count }}
                {{ contentBatch.gap_count }} 产出
                {{ contentBatch.topic_count }} 选题矩阵<template
                  v-if="batchSampleContents.length"
                >
                  + {{ batchSampleContents.length }} 条完整示范内容</template
                >，一次输入跨 {{ batchContentGroups.length }} 个平台产出
                {{ batchFullContents.length }}
                条内容，覆盖一个月分发量。全量内容在选题矩阵确认后按勾选与排期分发。
              </blockquote>
              <p class="competitor-meta">
                分析模型：{{ contentBatch.provider_label }} ·
                {{ contentBatch.generated_at }} · 渠道
                {{ contentBatch.channels.join("、") }}
              </p>
            </header>
            <v-alert
              v-if="contentBatch.failed_groups?.length"
              type="warning"
              variant="tonal"
              density="compact"
              class="mb-3"
            >
              {{ contentBatch.failed_groups.join("、") }}
              未完成，可在 6.2 对应平台点击「分平台返工」重新生成。
            </v-alert>

            <h4 class="batch-section-title">
              <span class="batch-section-no">6.1</span>
              {{ contentBatch.topic_count }} 选题矩阵（{{
                contentBatch.channels.includes("小红书图文")
                  ? "小红书为主战场"
                  : "分平台"
              }}）
            </h4>
            <div
              v-for="group in contentBatch.topic_matrix"
              :key="group.group + group.group_name"
              class="batch-group batch-topic-group"
            >
              <h5>
                {{ group.scene_no || group.group }}
                {{
                  group.group_name !== group.group ? group.group_name : ""
                }}（{{ group.topics.length }}条）
              </h5>
              <ol :start="group.topics[0]?.no || 1">
                <li v-for="topic in group.topics" :key="topic.no">
                  <input
                    v-if="topicDrafts[topic.no]"
                    v-model="topicDrafts[topic.no].selected"
                    type="checkbox"
                    class="topic-check"
                    :disabled="!topicsEditable"
                    :aria-label="`勾选选题 ${topic.no}`"
                  />
                  <span
                    :class="{
                      'topic-off':
                        topicDrafts[topic.no] &&
                        !topicDrafts[topic.no].selected,
                    }"
                    >{{ topic.title }}</span
                  >
                  <v-chip size="x-small" variant="tonal" class="ml-1">{{
                    topic.channel
                  }}</v-chip>
                  <small v-if="topic.claim_nos.length" class="ml-1"
                    >卖点 {{ topic.claim_nos.join("/") }}</small
                  >
                  <input
                    v-if="topicDrafts[topic.no]"
                    v-model="topicDrafts[topic.no].publish_time"
                    class="topic-time ml-1"
                    maxlength="60"
                    placeholder="排期，如 第1周周二 20:00"
                    :disabled="!topicsEditable"
                  />
                  <v-chip
                    v-if="topic.redline"
                    size="x-small"
                    color="error"
                    variant="tonal"
                    class="ml-1"
                    >🔴 命中「{{ topic.redline }}」</v-chip
                  >
                </li>
              </ol>
            </div>
            <div
              id="batch-topic-actions"
              class="batch-channel-head batch-topic-actions"
            >
              <span class="competitor-meta">
                确认①选题勾选与排期：已选 {{ selectedTopicDraftCount }}/{{
                  contentBatch.topic_count
                }}
                条<template v-if="contentBatch.topics_scheduled_at"
                  >（上次保存 {{ contentBatch.topics_scheduled_at }}）</template
                >
              </span>
              <v-btn
                size="small"
                variant="tonal"
                color="primary"
                prepend-icon="mdi-calendar-check"
                :disabled="!topicsEditable || !selectedTopicDraftCount"
                :loading="topicsSaving"
                @click="saveContentTopics"
                >保存选题勾选与排期</v-btn
              >
            </div>

            <template v-if="batchSampleContents.length">
              <div class="batch-channel-head batch-section-heading">
                <h4 class="batch-section-title">
                  <span class="batch-section-no">6.2</span>
                  完整示范内容 {{ batchSampleContents.length }} 条
                </h4>
              </div>
              <p class="competitor-meta">
                配图按每条素材清单逐张生成，画幅：小红书/抖音 3:4 · 视频号封面
                6:7 · 公众号头图 2.35:1。
              </p>
              <div
                v-for="sample in batchSampleContents"
                :key="`demo-${sample.content_id}`"
                class="batch-sample batch-demo"
              >
                <h5>
                  【示范{{ sample.sample_no
                  }}{{ sample.scene_no ? `·${sample.scene_no}` : "" }}
                  {{ sceneNameOf(sample.scene_no) || sample.channel }}】
                  <v-chip size="x-small" variant="tonal" class="ml-1">{{
                    sample.channel
                  }}</v-chip>
                  <v-chip
                    v-if="sample.compliance_label"
                    size="x-small"
                    variant="tonal"
                    :color="complianceLabelColor(sample.compliance_label)"
                    >{{ sample.compliance_label_text }}</v-chip
                  >
                </h5>
                <blockquote class="batch-demo-body">
                  <p v-if="sample.title">标题：{{ sample.title }}</p>
                  <template
                    v-for="(block, blockIndex) in demoBlocks(
                      sample.body || sample.content || '',
                    )"
                    :key="`${sample.content_id}-b${blockIndex}`"
                  >
                    <ul v-if="block.type === 'ul'">
                      <li
                        v-for="(line, lineIndex) in block.lines"
                        :key="lineIndex"
                      >
                        <template
                          v-for="(part, partIndex) in boldParts(line)"
                          :key="partIndex"
                          ><b v-if="part.bold">{{ part.text }}</b
                          ><template v-else>{{ part.text }}</template></template
                        >
                      </li>
                    </ul>
                    <p v-else>
                      <template
                        v-for="(line, lineIndex) in block.lines"
                        :key="lineIndex"
                        ><br v-if="lineIndex" /><template
                          v-for="(part, partIndex) in boldParts(line)"
                          :key="partIndex"
                          ><b v-if="part.bold">{{ part.text }}</b
                          ><template v-else>{{ part.text }}</template></template
                        ></template
                      >
                    </p>
                  </template>
                  <p v-if="sample.hashtags?.length">
                    {{
                      sample.hashtags
                        .map((tag) => `#${tag.replace(/^#/, "")}`)
                        .join(" ")
                    }}
                  </p>
                </blockquote>
                <div v-if="sample.images?.length" class="content-image-grid">
                  <figure
                    v-for="image in sample.images"
                    :key="`demo-${image.filename}`"
                    class="content-image"
                  >
                    <img
                      v-if="imageUrls[image.filename]"
                      :src="imageUrls[image.filename]"
                      :alt="image.asset"
                      :title="image.prompt"
                      :style="
                        aspectStyle(
                          image.aspect || channelAspect(sample.channel),
                        )
                      "
                      class="content-image-clickable"
                      @click="
                        openImagePreview(imageUrls[image.filename], image.asset)
                      "
                    />
                    <div
                      v-else
                      class="content-image-loading"
                      :style="
                        aspectStyle(
                          image.aspect || channelAspect(sample.channel),
                        )
                      "
                    >
                      加载中…
                    </div>
                    <figcaption>
                      <span class="content-image-caption" :title="image.asset">
                        图{{ image.index }}（{{
                          image.aspect || channelAspect(sample.channel)
                        }}）：{{ image.asset }}
                      </span>
                      <div class="content-image-actions">
                      <v-btn
                        size="x-small"
                        variant="text"
                        icon="mdi-refresh"
                        :disabled="
                          !canRegenerateContentImages || Boolean(imageLoading)
                        "
                        :aria-label="`重新生成图${image.index}`"
                        title="单张重新生成"
                        @click="generateContentImages(sample, [image.index])"
                      />
                      <v-btn
                        v-if="imageUrls[image.filename]"
                        size="x-small"
                        variant="text"
                        icon="mdi-magnify-plus-outline"
                        :aria-label="`放大图${image.index}`"
                        title="放大查看"
                        @click="
                          openImagePreview(
                            imageUrls[image.filename],
                            image.asset,
                          )
                        "
                      />
                      <v-btn
                        v-if="imageUrls[image.filename]"
                        size="x-small"
                        variant="text"
                        icon="mdi-download"
                        :href="imageUrls[image.filename]"
                        :download="image.filename.split('/').pop()"
                        :aria-label="`下载图${image.index}`"
                        title="下载图片"
                      />
                      </div>
                    </figcaption>
                  </figure>
                </div>
                <v-btn
                  v-else-if="sample.assets?.length"
                  size="x-small"
                  variant="tonal"
                  color="secondary"
                  prepend-icon="mdi-image-multiple"
                  :disabled="
                    !canRegenerateContentImages ||
                    batchGenerating ||
                    Boolean(imageLoading)
                  "
                  :loading="imageLoading === sample.content_id"
                  @click="generateContentImages(sample)"
                  >按素材清单生成配图（{{
                    channelAspect(sample.channel)
                  }}）</v-btn
                >
              </div>
            </template>

            <h4 class="batch-section-title">
              <span class="batch-section-no">{{
                batchSampleContents.length ? "6.2.1" : "6.2"
              }}</span>
              分平台内容（{{ batchContentGroups.length }} 个平台 ·
              {{ batchFullContents.length }} 条）
            </h4>
            <p class="competitor-meta">
              正文全文与逐条合规风险见下方内容卡片；不符合项请按平台返工。
            </p>
            <div
              v-for="group in batchContentGroups"
              :key="group.channel"
              :id="batchGroupAnchor(group.channel)"
              class="batch-group batch-platform-group"
            >
              <h5 class="batch-channel-head batch-platform-head">
                <span
                  >{{ group.channel }}（{{ group.items.length }}/{{
                    group.quota || group.items.length
                  }}条）</span
                >
                <v-chip
                  v-if="group.blocked"
                  size="x-small"
                  color="error"
                  variant="tonal"
                  >含阻断项</v-chip
                >
                <v-chip v-if="group.reworkCount" size="x-small" variant="tonal"
                  >已返工 {{ group.reworkCount }} 次</v-chip
                >
                <v-btn
                  size="x-small"
                  variant="tonal"
                  color="warning"
                  prepend-icon="mdi-restore"
                  :disabled="readOnly || currentStep !== 9 || batchGenerating"
                  :loading="reworkLoading === group.channel"
                  @click="openRework(group.channel)"
                  >分平台返工</v-btn
                >
                <v-btn
                  size="x-small"
                  variant="text"
                  prepend-icon="mdi-arrow-down"
                  @click="jumpToContent(group.channel)"
                  >查看正文与合规</v-btn
                >
              </h5>
              <div
                v-for="(sample, index) in group.items"
                :key="sample.content_id"
                class="batch-sample"
              >
                <h5>
                  {{ index + 1 }}. {{ sample.title || sample.channel }}（{{
                    sample.content_type
                  }}
                  · {{ sample.length_spec }}）
                </h5>
                <v-chip
                  v-if="sample.sample_no"
                  size="x-small"
                  color="primary"
                  variant="flat"
                  class="mr-1"
                  >示范{{ sample.sample_no
                  }}{{ sample.scene_no ? `·${sample.scene_no}` : "" }}</v-chip
                >
                <v-chip
                  v-if="sample.compliance_label"
                  size="x-small"
                  variant="tonal"
                  :color="complianceLabelColor(sample.compliance_label)"
                  >{{ sample.compliance_label_text }}</v-chip
                >
                <v-chip
                  v-for="claimRef in sample.unverified_claim_refs || []"
                  :key="claimRef"
                  size="x-small"
                  color="error"
                  variant="tonal"
                  class="ml-1"
                  >未验证卖点 {{ claimRef }}</v-chip
                >
                <v-chip
                  v-if="sample.claim_nos?.length"
                  size="x-small"
                  variant="tonal"
                  class="ml-1"
                  >卖点 {{ sample.claim_nos.join("/") }}</v-chip
                >
                <ul>
                  <li v-if="sample.quality_issues?.length" class="text-warning">
                    调性/结构提示：{{ sample.quality_issues.join("；") }}
                  </li>
                  <li v-if="sample.segments?.length">
                    分段结构：
                    <ol>
                      <li
                        v-for="(seg, segIndex) in sample.segments"
                        :key="segIndex"
                      >
                        <b>{{ seg.label }}</b> {{ seg.text }}
                        <small v-if="seg.note">（{{ seg.note }}）</small>
                      </li>
                    </ol>
                  </li>
                  <li v-if="sample.title_options?.length">
                    标题备选：{{ sample.title_options.join(" ｜ ") }}
                  </li>
                  <li v-if="sample.hashtags?.length">
                    话题：{{
                      sample.hashtags.map((tag) => `#${tag}`).join(" ")
                    }}
                  </li>
                  <li v-if="sample.publish_time?.slot">
                    建议发布时间：{{ sample.publish_time.slot }}
                    <template v-if="sample.publish_time.reason"
                      >（{{ sample.publish_time.reason }}）</template
                    >
                  </li>
                  <li v-if="sample.assets?.length">
                    配图/视频素材：
                    <ol>
                      <li
                        v-for="(asset, assetIndex) in sample.assets"
                        :key="asset"
                      >
                        {{ asset }}
                        <v-btn
                          size="x-small"
                          variant="text"
                          color="secondary"
                          prepend-icon="mdi-image-plus"
                          class="ml-1"
                          :disabled="
                            !canRegenerateContentImages ||
                            batchGenerating ||
                            Boolean(imageLoading)
                          "
                          :loading="
                            imageLoading ===
                            `${sample.content_id}#${assetIndex + 1}`
                          "
                          @click="
                            generateContentImages(sample, [assetIndex + 1])
                          "
                          >{{
                            sample.images?.some(
                              (image) => image.index === assetIndex + 1,
                            )
                              ? "重新生成此图"
                              : "生成此图"
                          }}</v-btn
                        >
                      </li>
                    </ol>
                    <v-btn
                      size="small"
                      variant="tonal"
                      color="secondary"
                      prepend-icon="mdi-image-multiple"
                      class="current-content-image-action mt-2"
                      :disabled="
                        !canRegenerateContentImages ||
                        batchGenerating ||
                        Boolean(imageLoading)
                      "
                      :loading="imageLoading === sample.content_id"
                      @click="generateContentImages(sample)"
                      >{{
                        sample.images?.length
                          ? "重新生成当前内容配图"
                          : "生成当前内容配图"
                      }}</v-btn
                    >
                    <div
                      v-if="sample.image_errors?.length"
                      class="text-warning"
                    >
                      配图失败：{{ sample.image_errors.join("；") }}
                    </div>
                    <div
                      v-if="sample.images?.length"
                      class="content-image-grid content-image-grid--current"
                    >
                      <figure
                        v-for="image in sample.images"
                        :key="image.filename"
                        class="content-image"
                      >
                        <img
                          v-if="imageUrls[image.filename]"
                          :src="imageUrls[image.filename]"
                          :alt="image.asset"
                          :title="image.prompt"
                          :style="
                            aspectStyle(
                              image.aspect || channelAspect(sample.channel),
                            )
                          "
                          class="content-image-clickable"
                          @click="
                            openImagePreview(
                              imageUrls[image.filename],
                              image.asset,
                            )
                          "
                        />
                        <div
                          v-else
                          class="content-image-loading"
                          :style="
                            aspectStyle(
                              image.aspect || channelAspect(sample.channel),
                            )
                          "
                        >
                          加载中…
                        </div>
                        <figcaption>
                          <span class="content-image-caption" :title="image.asset">
                            图{{ image.index }}（{{
                              image.aspect || channelAspect(sample.channel)
                            }}）：{{ image.asset }}
                            <small v-if="image.model"
                              >（{{ image.model }}）</small
                            >
                          </span>
                          <div class="content-image-actions">
                          <v-btn
                            size="x-small"
                            variant="text"
                            icon="mdi-refresh"
                            :disabled="
                              !canRegenerateContentImages || Boolean(imageLoading)
                            "
                            :aria-label="`重新生成图${image.index}`"
                            @click="
                              generateContentImages(sample, [image.index])
                            "
                          />
                          <v-btn
                            v-if="imageUrls[image.filename]"
                            size="x-small"
                            variant="text"
                            icon="mdi-magnify-plus-outline"
                            :aria-label="`放大图${image.index}`"
                            title="放大查看"
                            @click="
                              openImagePreview(
                                imageUrls[image.filename],
                                image.asset,
                              )
                            "
                          />
                          <v-btn
                            v-if="imageUrls[image.filename]"
                            size="x-small"
                            variant="text"
                            icon="mdi-download"
                            :href="imageUrls[image.filename]"
                            :download="image.filename.split('/').pop()"
                            :aria-label="`下载图${image.index}`"
                            title="下载图片"
                          />
                          </div>
                        </figcaption>
                      </figure>
                    </div>
                  </li>
                  <li v-if="sample.faq?.length">
                    评论区可能被问到：
                    <ol>
                      <li v-for="row in sample.faq" :key="row.q">
                        <b>{{ row.q }}</b> → {{ row.a }}
                      </li>
                    </ol>
                  </li>
                  <li v-if="sample.ad_review_tips?.length">
                    平台广审规避要点：{{ sample.ad_review_tips.join("；") }}
                  </li>
                </ul>
              </div>
            </div>

            <template v-if="contentBatch.comment_replies.length">
              <h4>
                6.3 评论区预埋话术（{{
                  contentBatch.comment_replies.length
                }}条标准回复）
              </h4>
              <ol>
                <li v-for="row in contentBatch.comment_replies" :key="row.q">
                  <b>"{{ row.q }}"</b> → "{{ row.a }}"
                </li>
              </ol>
            </template>

            <div id="batch-checklist-section" class="batch-checklist">
              <div class="d-flex align-center justify-space-between">
                <strong>确认内容（市场确认前须全部勾选）</strong>
                <v-btn
                  size="small"
                  variant="tonal"
                  color="primary"
                  prepend-icon="mdi-check-all"
                  :disabled="readOnly || approvalDone('market')"
                  @click="selectAllBatchChecklist"
                  >一键全选</v-btn
                >
              </div>
              <v-checkbox
                v-for="item in batchChecklistOptions"
                :key="item.key"
                v-model="batchChecklist"
                :value="item.key"
                :label="item.text"
                density="compact"
                hide-details
                :disabled="readOnly || approvalDone('market')"
              />
            </div>
          </section>

          <v-dialog v-model="reworkDialog" max-width="520">
            <v-card :title="`分平台返工 · ${reworkChannel}`">
              <v-card-text>
                <v-select
                  v-model="reworkReason"
                  :items="reworkReasonOptions"
                  item-title="text"
                  item-value="key"
                  label="返工原因"
                  variant="outlined"
                  density="compact"
                />
                <v-textarea
                  v-model="reworkComment"
                  label="返工批注（必填，将作为重写要求）"
                  variant="outlined"
                  rows="3"
                  counter="500"
                  maxlength="500"
                />
                <small>返工仅重写该平台内容，并重置市场/合规/终审签字。</small>
              </v-card-text>
              <v-card-actions>
                <v-spacer />
                <v-btn variant="text" @click="reworkDialog = false">取消</v-btn>
                <v-btn
                  color="warning"
                  variant="flat"
                  :disabled="
                    !!reworkLoading || !reworkReason || !reworkComment.trim()
                  "
                  @click="submitRework"
                  >确认返工</v-btn
                >
              </v-card-actions>
            </v-card>
          </v-dialog>

          <div v-if="contents.length" class="content-list">
            <article
              v-for="content in contents"
              :key="content.content_id"
              :id="contentAnchor(content.content_id)"
              class="content-card"
            >
              <header>
                <div>
                  <v-chip size="small" color="primary" variant="tonal">{{
                    content.channel || content.platform
                  }}</v-chip
                  ><strong>{{ content.title || "内容草稿" }}</strong>
                </div>
                <small>引用 {{ content.claim_ids.length }} 个 Claim</small>
                <v-chip
                  v-if="content.compliance_label"
                  size="small"
                  variant="tonal"
                  :color="complianceLabelColor(content.compliance_label)"
                  >{{ content.compliance_label_text }}</v-chip
                >
                <v-btn
                  size="small"
                  variant="text"
                  prepend-icon="mdi-content-copy"
                  @click="copyContent(content)"
                  >{{
                    content.footnotes?.length ? "复制（含脚注）" : "复制"
                  }}</v-btn
                >
                <v-btn
                  v-if="contentBatch"
                  size="small"
                  variant="text"
                  prepend-icon="mdi-arrow-up-left"
                  @click="backToBatch(content)"
                  >回到批量规划</v-btn
                >
              </header>
              <pre>{{ content.body || content.content }}</pre>
              <ol v-if="content.footnotes?.length" class="content-footnotes">
                <li v-for="note in content.footnotes" :key="note.index">
                  [{{ note.index }}] {{ note.text }}
                  <a
                    v-if="note.url"
                    :href="note.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    >核验</a
                  >
                </li>
              </ol>
              <div
                v-if="contentRisks(content.content_id).length"
                class="risk-list"
              >
                <div
                  v-for="(risk, index) in contentRisks(content.content_id)"
                  :key="risk.risk_id || `${content.content_id}-${index}`"
                  class="risk-item"
                  :class="riskClass(risk.level)"
                >
                  <div class="risk-item-head">
                    <strong>{{ riskLevelLabel(risk.level) }}</strong>
                    <span>{{ risk.message }}</span>
                    <small
                      >{{ risk.source === "ai" ? "模型复核" : "规则引擎" }}
                      <template v-if="risk.rule_id">
                        · {{ risk.rule_id }} · V{{
                          risk.rule_version || 1
                        }}</template
                      ></small
                    >
                  </div>
                  <div v-if="risk.matched_text" class="risk-item-line">
                    命中原文：<mark>{{ risk.matched_text }}</mark>
                    <template v-if="risk.replacement">
                      → 建议替换为 <b>{{ risk.replacement }}</b></template
                    >
                  </div>
                  <div v-if="risk.legal_basis" class="risk-item-line">
                    依据：{{ risk.legal_basis }}
                  </div>
                  <div v-if="risk.suggestion" class="risk-item-line">
                    修改建议：{{ risk.suggestion }}
                  </div>
                  <div
                    v-if="risk.risk_id && isReviewableRisk(risk)"
                    class="risk-review"
                  >
                    <v-btn-toggle
                      v-model="reviewDraft(risk.risk_id).decision"
                      density="compact"
                      divided
                      color="primary"
                      :disabled="!canReviewCompliance"
                    >
                      <v-btn value="adopt" size="x-small">采纳建议</v-btn>
                      <v-btn value="keep" size="x-small">保留原文</v-btn>
                    </v-btn-toggle>
                    <v-text-field
                      v-model="reviewDraft(risk.risk_id).note"
                      density="compact"
                      variant="outlined"
                      hide-details
                      :disabled="!canReviewCompliance"
                      :label="
                        risk.level === 'caution'
                          ? '合规批注（谨慎项必填）'
                          : '合规批注（可选）'
                      "
                    />
                  </div>
                </div>
              </div>
              <div v-else class="quality-ok">
                <v-icon
                  icon="mdi-check-circle-outline"
                  size="18"
                />未命中三层合规规则，仍需合规部人工确认。
              </div>
            </article>
          </div>
          <div v-else class="empty-state">
            完成合规过滤后选择平台生成内容。系统不会自动发布。
          </div>

          <div v-if="projectLevelRisks.length" class="risk-list">
            <div
              v-for="(risk, index) in projectLevelRisks"
              :key="risk.risk_id || `project-risk-${index}`"
              class="risk-item"
              :class="riskClass(risk.level)"
            >
              <div class="risk-item-head">
                <strong>{{ riskLevelLabel(risk.level) }}</strong>
                <span>{{ risk.message }}</span>
                <small>{{ risk.platform || "全部平台" }}</small>
              </div>
              <div v-if="risk.suggestion" class="risk-item-line">
                修改建议：{{ risk.suggestion }}
              </div>
            </div>
          </div>

          <section v-if="complianceReport" class="compliance-section">
            <header>
              <h4>合规过滤结果</h4>
              <div class="tag-row">
                <v-chip size="small" color="success" variant="tonal"
                  >✅ 合规 {{ complianceReport.summary?.pass || 0 }}</v-chip
                >
                <v-chip size="small" color="warning" variant="tonal"
                  >⚠️ 谨慎 {{ complianceReport.summary?.caution || 0 }}</v-chip
                >
                <v-chip size="small" color="error" variant="tonal"
                  >❌ 违规 {{ complianceReport.summary?.blocked || 0 }}</v-chip
                >
                <v-chip size="small" variant="outlined"
                  >{{ complianceReport.kb_builder || "中睿医药商学院" }} ·
                  {{ complianceReport.kb_version }} · 规则 V{{
                    complianceReport.rule_version
                  }}</v-chip
                >
              </div>
            </header>
            <small v-if="complianceReport.scanned_at"
              >扫描时间：{{
                formatDateTime(complianceReport.scanned_at)
              }}</small
            >
          </section>

          <section
            v-if="contents.length"
            id="kb-review-section"
            class="compliance-section"
          >
            <header>
              <h4>本地药企知识库检索 + 模型复核</h4>
              <small
                >模型只能追加风险，不能撤销规则命中；命中原文必须真实出现在内容中。</small
              >
            </header>
            <div class="platform-picker">
              <v-select
                v-model="complianceKbIds"
                :items="kbOptions"
                :loading="kbLoading"
                label="选择本地药企知识库（可多选，留空自动检索全部本地知识库）"
                multiple
                chips
                closable-chips
                variant="outlined"
                hide-details
                :disabled="readOnly || currentStep !== 9"
              />
              <v-btn
                color="primary"
                variant="tonal"
                prepend-icon="mdi-shield-search"
                :loading="complianceReviewing"
                :disabled="
                  readOnly || currentStep !== 9 || approvalDone('compliance')
                "
                @click="runComplianceReview"
                >检索知识库并复核</v-btn
              >
            </div>
            <div v-if="complianceReviewing" class="review-progress">
              <div class="review-progress__head">
                <v-progress-circular indeterminate size="16" width="2" color="primary" />
                <span>正在检索知识库并调用模型复核… 已用 {{ reviewElapsed }}s</span>
              </div>
              <ul class="review-progress__logs auto-bottom">
                <li v-if="!reviewProgress?.logs?.length">任务已提交，等待服务端响应…</li>
                <li v-for="(item, i) in reviewProgress?.logs || []" :key="i">
                  {{ item.message }}
                </li>
              </ul>
              <div
                v-for="(text, label) in reviewProgress?.streams || {}"
                :key="label"
                class="review-progress__stream"
              >
                <div class="review-progress__label">{{ label }}</div>
                <pre class="auto-bottom">{{ text || "等待模型输出…" }}</pre>
              </div>
            </div>
            <template v-if="complianceReport?.ai_review">
              <v-alert
                type="info"
                variant="tonal"
                density="compact"
                class="status-alert"
              >
                {{ complianceReport.ai_review.notice || "已完成复核" }}
                <template v-if="complianceReport.ai_review.kb_warning">
                  （{{ complianceReport.ai_review.kb_warning }}）</template
                >
                <template v-if="complianceReport.ai_review.retrieved_at">
                  · 检索日期
                  {{
                    formatDateTime(complianceReport.ai_review.retrieved_at)
                  }}</template
                >
              </v-alert>
              <ul
                v-if="complianceReport.ai_review.kb_hits?.length"
                class="competitor-list"
              >
                <li
                  v-for="(hit, index) in complianceReport.ai_review.kb_hits"
                  :key="`kb-hit-${index}`"
                >
                  <strong>{{ hit.kb_name || "知识库" }}</strong>
                  <span v-if="hit.doc_name"> / {{ hit.doc_name }}</span>
                  <small> · 相关度 {{ hit.score }}</small>
                  <p>{{ hit.excerpt }}</p>
                </li>
              </ul>
            </template>
          </section>

          <section v-if="contents.length" class="compliance-section">
            <header>
              <h4>
                中睿合规专家在线答疑（{{
                  complianceKb?.expert_sla_hours || 24
                }}小时响应）
              </h4>
            </header>
            <div class="platform-picker">
              <v-btn
                variant="tonal"
                color="primary"
                prepend-icon="mdi-face-agent"
                @click="customerServiceDialog = true"
                >人工服务</v-btn
              >
            </div>
            <v-dialog v-model="customerServiceDialog" max-width="360">
              <v-card>
                <v-card-title class="d-flex align-center">
                  人工服务
                  <v-spacer />
                  <v-btn
                    icon="mdi-close"
                    size="small"
                    variant="text"
                    aria-label="关闭"
                    @click="customerServiceDialog = false"
                  />
                </v-card-title>
                <v-card-text class="text-center">
                  <img
                    :src="customerServiceQr"
                    alt="客服二维码"
                    style="width: 100%; max-width: 280px"
                  />
                  <p class="mt-2">微信扫码添加客服，获取人工服务</p>
                </v-card-text>
              </v-card>
            </v-dialog>
            <article
              v-for="ticket in complianceTickets"
              :key="ticket.ticket_id"
              class="compliance-ticket"
            >
              <header>
                <strong>{{ ticket.ticket_id }}</strong>
                <v-chip
                  size="x-small"
                  variant="tonal"
                  :color="ticket.status === 'answered' ? 'success' : 'warning'"
                  >{{
                    ticket.status === "answered" ? "已答复" : "待答复"
                  }}</v-chip
                >
                <small
                  >{{ ticket.expert_team }} · 截止
                  {{ formatDateTime(ticket.due_at) }}</small
                >
              </header>
              <p>{{ ticket.question }}</p>
              <p v-if="ticket.status === 'answered'" class="ticket-answer">
                <b>{{ ticket.answered_by }}：</b>{{ ticket.answer }}
              </p>
              <div v-else class="platform-picker">
                <v-text-field
                  v-model="ticketAnswerDraft(ticket.ticket_id).answer"
                  label="登记专家答复"
                  density="compact"
                  variant="outlined"
                  hide-details
                  :disabled="readOnly"
                />
                <v-text-field
                  v-model="ticketAnswerDraft(ticket.ticket_id).expertName"
                  label="答复专家"
                  density="compact"
                  variant="outlined"
                  hide-details
                  :disabled="readOnly"
                />
                <v-btn
                  size="small"
                  variant="tonal"
                  :loading="ticketSubmitting"
                  :disabled="readOnly"
                  @click="answerComplianceTicket(ticket.ticket_id)"
                  >登记</v-btn
                >
              </div>
            </article>
          </section>

          <section v-if="contents.length" class="compliance-section">
            <header>
              <h4>合规部人工确认（勾选后点击确认即可）</h4>
              <v-chip
                size="small"
                variant="tonal"
                :color="pendingReviewCount ? 'warning' : 'success'"
                >待批注 {{ pendingReviewCount }} /
                {{ reviewableRisks.length }}</v-chip
              >
              <v-btn
                v-if="!complianceRecord"
                size="small"
                variant="tonal"
                color="primary"
                prepend-icon="mdi-check-all"
                :disabled="!canReviewCompliance || !pendingReviewCount"
                @click="adoptAllComplianceReviews"
                >一键批注全部（采纳建议）</v-btn
              >
            </header>
            <template v-if="complianceRecord">
              <div class="compliance-record">
                <div><b>审查记录</b>{{ complianceRecord.record_id }}</div>
                <div>
                  <b>签字</b>{{ complianceRecord.signer_name }}（{{
                    complianceRecord.signer_title
                  }}）
                </div>
                <div>
                  <b>知识库版本</b>{{ complianceRecord.kb_builder }} ·
                  {{ complianceRecord.kb_version }} · 规则 V{{
                    complianceRecord.rule_version
                  }}
                </div>
                <div>
                  <b>检索日期</b
                  >{{ formatDateTime(complianceRecord.retrieval_date) }}
                </div>
                <div>
                  <b>处理情况</b>谨慎项批注
                  {{ complianceRecord.caution_reviewed }} 条 · 采纳替换
                  {{ complianceRecord.replace_adopted }} 条 · 答疑工单
                  {{ complianceRecord.expert_ticket_ids?.length || 0 }} 个
                </div>
                <div v-if="complianceRecord.endorsement">
                  <b>背书</b>{{ complianceRecord.endorsement }}
                </div>
              </div>
            </template>
            <div v-else class="compliance-sign-form">
              <v-checkbox
                v-model="citationCovered"
                label="已确认文献引证完整覆盖所有合规风险点"
                density="compact"
                hide-details
                :disabled="!canReviewCompliance"
              />
            </div>
          </section>

          <div class="approval-grid">
            <article :class="{ done: approvalDone('market') }">
              <v-icon icon="mdi-account-tie-outline" /><strong>市场确认</strong
              ><span>{{ approvalDone("market") ? "已签字" : "待签字" }}</span
              ><v-btn
                size="small"
                variant="tonal"
                :disabled="
                  readOnly || !contents.length || approvalDone('market')
                "
                :loading="actionLoading"
                @click="approve('market_confirm')"
                >确认</v-btn
              >
            </article>
            <article :class="{ done: approvalDone('compliance') }">
              <v-icon icon="mdi-shield-check-outline" /><strong>合规确认</strong
              ><span>{{
                approvalDone("compliance") ? "已确认" : "待确认"
              }}</span
              ><v-btn
                size="small"
                variant="tonal"
                :disabled="
                  readOnly ||
                  !approvalDone('market') ||
                  hasBlockingRisk ||
                  approvalDone('compliance')
                "
                :loading="actionLoading"
                @click="approve('compliance_confirm')"
                >确认</v-btn
              >
            </article>
            <article :class="{ done: approvalDone('final') }">
              <v-icon icon="mdi-check-decagram-outline" /><strong
                >品牌终审</strong
              ><span>{{ approvalDone("final") ? "已通过" : "待终审" }}</span
              ><v-btn
                size="small"
                color="primary"
                :disabled="
                  readOnly ||
                  !approvalDone('compliance') ||
                  hasBlockingRisk ||
                  approvalDone('final')
                "
                :loading="actionLoading"
                @click="submitFinalApprove"
                >终审</v-btn
              >
            </article>
          </div>
          <div
            v-if="contents.length && !approvalDone('final') && !readOnly"
            class="d-flex justify-end mb-3"
          >
            <v-btn
              color="primary"
              prepend-icon="mdi-lightning-bolt"
              :loading="oneClickApproving"
              :disabled="actionLoading || !!reworkLoading"
              @click="oneClickApprove"
              >一键审批进入下一步</v-btn
            >
          </div>
          <v-alert
            v-if="reworkLoading"
            type="info"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            <div class="d-flex align-center ga-2">
              <v-progress-circular indeterminate size="16" width="2" />
              <template v-if="reworkLoading === AUTO_FIX_LABEL">
                一键修复中（仅改写违规片段，多条并行），已用时
                {{ reworkElapsedText }}（3
                分钟内完成），完成后自动刷新并重新自检
              </template>
              <template v-else>
                「{{ reworkLoading }}」返工重写中，已用时
                {{ reworkElapsedText }}（通常 2-5 分钟），完成后自动刷新内容
              </template>
            </div>
          </v-alert>
          <v-alert
            v-if="contents.length && approvalBlockers.length"
            type="warning"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            <div><b>当前无法进入下一步的原因：</b></div>
            <ul class="approval-blockers">
              <li v-for="item in approvalBlockers" :key="item.text">
                {{ item.text }}
                <v-btn
                  v-if="item.fixable"
                  size="x-small"
                  variant="flat"
                  color="primary"
                  class="ml-1"
                  prepend-icon="mdi-auto-fix"
                  :disabled="
                    readOnly ||
                    (!!reworkLoading && reworkLoading !== AUTO_FIX_LABEL)
                  "
                  :loading="reworkLoading === AUTO_FIX_LABEL"
                  @click="autoFixAll"
                  >一键修复（约 3 分钟）</v-btn
                >
                <v-btn
                  v-if="item.fixable"
                  size="x-small"
                  variant="flat"
                  color="error"
                  class="ml-1"
                  prepend-icon="mdi-shield-check"
                  :disabled="
                    readOnly ||
                    (!!reworkLoading && reworkLoading !== FIX_ALL_LABEL)
                  "
                  :loading="reworkLoading === FIX_ALL_LABEL"
                  @click="fixAllViolations"
                  >{{ FIX_ALL_LABEL }}</v-btn
                >
                <v-btn
                  v-for="channel in item.channels || []"
                  :key="channel"
                  size="x-small"
                  variant="tonal"
                  color="warning"
                  class="ml-1"
                  prepend-icon="mdi-wrench"
                  :disabled="
                    readOnly || (!!reworkLoading && reworkLoading !== channel)
                  "
                  :loading="reworkLoading === channel"
                  @click="fixChannelViolations(channel)"
                  >修复「{{ channel }}」</v-btn
                >
              </li>
            </ul>
          </v-alert>
          <section
            v-if="contents.length"
            class="compliance-section final-review-section"
          >
            <header>
              <h4>品牌终审（品牌总监 / 业务负责人，典型 30-60 分钟）</h4>
              <v-chip
                size="small"
                variant="tonal"
                :color="auditChainGaps.length ? 'warning' : 'success'"
                >{{
                  auditChainGaps.length
                    ? `审计链缺环：${auditChainGaps.join("、")}`
                    : "审计链齐备"
                }}</v-chip
              >
            </header>
            <div v-if="finalRecord" class="compliance-record">
              <div><b>终审凭证</b>{{ finalRecord.record_id }}</div>
              <div>
                <b>签字</b>{{ finalRecord.signer_name }}（{{
                  finalRecord.signer_title
                }}）
              </div>
              <div><b>确认时长</b>{{ finalRecord.duration_minutes }} 分钟</div>
              <div v-if="finalRecord.business_goal_note">
                <b>业务目标</b>{{ finalRecord.business_goal_note }}
              </div>
              <div>
                <b>发布授权</b
                >{{
                  finalRecord.publish_authorization?.authorized
                    ? "已授权"
                    : "未授权"
                }}
                · 渠道
                {{
                  (finalRecord.publish_authorization?.channels || []).join(
                    "、",
                  ) || "全部"
                }}
                <template v-if="finalRecord.publish_authorization?.start_date">
                  · 自
                  {{ finalRecord.publish_authorization.start_date }}
                  起</template
                >
              </div>
              <div><b>审计链归档</b>{{ auditChain.length }} 环已归档</div>
            </div>
            <div v-else class="final-sign-form">
              <v-alert
                v-if="finalLockReason"
                type="info"
                variant="tonal"
                density="compact"
                icon="mdi-lock-outline"
                >{{ finalLockReason }}</v-alert
              >
              <div class="final-sign-fields">
                <v-combobox
                  v-model="finalSignerTitle"
                  :items="finalTitleOptions"
                  label="职务（品牌总监/业务负责人）"
                  density="compact"
                  variant="outlined"
                  hide-details="auto"
                  :error-messages="
                    finalTouched && !finalTitleValid
                      ? '须为品牌总监或业务负责人，不可代签'
                      : ''
                  "
                  :disabled="finalFormLocked"
                />
                <v-text-field
                  v-model.number="finalDuration"
                  type="number"
                  min="1"
                  label="确认时长（分钟）"
                  density="compact"
                  variant="outlined"
                  hide-details="auto"
                  :messages="finalDurationHint"
                  :disabled="finalFormLocked"
                />
                <v-text-field
                  v-model="finalStartDate"
                  type="date"
                  :min="todayStr"
                  label="发布开始日期"
                  density="compact"
                  variant="outlined"
                  hide-details
                  :disabled="finalFormLocked || !finalAuthorized"
                />
              </div>
              <v-textarea
                v-model="finalGoalNote"
                label="业务目标达成度说明"
                rows="2"
                auto-grow
                counter="500"
                maxlength="500"
                density="compact"
                variant="outlined"
                hide-details="auto"
                :disabled="finalFormLocked"
              />
              <div class="final-checklist-head">
                <span
                  >终审清单（{{ finalChecklist.length }}/{{
                    finalChecklistOptions.length
                  }}）</span
                >
                <v-btn
                  size="small"
                  variant="tonal"
                  :prepend-icon="
                    finalChecklistAllChecked
                      ? 'mdi-checkbox-blank-outline'
                      : 'mdi-checkbox-multiple-marked-outline'
                  "
                  :disabled="finalFormLocked"
                  @click="toggleFinalChecklistAll"
                  >{{
                    finalChecklistAllChecked ? "取消全选" : "一键全选"
                  }}</v-btn
                >
              </div>
              <div class="final-checklist">
                <v-checkbox
                  v-for="item in finalChecklistOptions"
                  :key="item.key"
                  v-model="finalChecklist"
                  :value="item.key"
                  :label="item.text"
                  density="compact"
                  hide-details="auto"
                  :messages="finalChecklistItemLockReason(item.key)"
                  :disabled="
                    finalFormLocked ||
                    Boolean(finalChecklistItemLockReason(item.key))
                  "
                />
              </div>
              <div class="compliance-sign-form">
                <v-switch
                  v-model="finalAuthorized"
                  label="授权进入发布"
                  color="primary"
                  density="compact"
                  hide-details
                  :disabled="finalFormLocked"
                />
                <v-select
                  v-model="finalChannels"
                  :items="contentChannels"
                  label="授权渠道（不选为全部）"
                  multiple
                  chips
                  closable-chips
                  density="compact"
                  variant="outlined"
                  hide-details
                  :disabled="finalFormLocked || !finalAuthorized"
                />
              </div>
              <div class="final-submit-bar">
                <span
                  v-if="!finalFormLocked && finalMissing.length"
                  class="final-missing"
                >
                  还差 {{ finalMissing.length }} 项：{{
                    finalMissing.join("；")
                  }}
                </span>
                <span v-else-if="!finalFormLocked" class="final-ready">
                  <v-icon icon="mdi-check-circle-outline" size="small" />
                  终审条件已满足
                </span>
                <v-btn
                  color="primary"
                  prepend-icon="mdi-check-decagram-outline"
                  :disabled="finalFormLocked || hasBlockingRisk"
                  :loading="actionLoading"
                  @click="submitFinalApprove"
                  >签字并终审通过</v-btn
                >
              </div>
            </div>
          </section>

          <section v-if="auditChain.length" class="compliance-section">
            <header>
              <h4>7.1 七步确认留痕表（本报告审计链）</h4>
            </header>
            <div class="audit-chain-table">
              <table>
                <thead>
                  <tr>
                    <th>步骤</th>
                    <th>产出物</th>
                    <th>确认人</th>
                    <th>留痕</th>
                    <th>状态</th>
                    <th>确认时间</th>
                    <th>签字</th>
                    <th>批注</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in auditChain"
                    :key="row.step"
                    :class="{ gap: row.step < 7 && row.status !== 'confirmed' }"
                  >
                    <td>{{ row.step_label }}</td>
                    <td>{{ row.output }}</td>
                    <td>{{ row.confirmer }}</td>
                    <td>{{ row.trace }}</td>
                    <td>
                      <v-chip
                        size="x-small"
                        variant="tonal"
                        :color="row.status === 'confirmed' ? 'success' : 'grey'"
                        >{{ row.status_text }}</v-chip
                      >
                    </td>
                    <td>
                      {{
                        row.confirmed_at ? formatDateTime(row.confirmed_at) : ""
                      }}
                    </td>
                    <td>{{ row.signer || "" }}</td>
                    <td>{{ row.comment || "" }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="export-meta">
              <div>
                <h5>7.2 导出物清单</h5>
                <ul>
                  <li v-for="item in exportChecklist" :key="item.text">
                    <v-icon
                      size="18"
                      :color="item.done ? 'success' : 'grey'"
                      :icon="
                        item.done
                          ? 'mdi-checkbox-marked'
                          : 'mdi-checkbox-blank-outline'
                      "
                    />{{ item.text }}
                  </li>
                </ul>
              </div>
              <!-- <div>
                <h5>7.3 复用机制</h5>
                <p>
                  同 SKU 复投时 Step 1-4
                  可直接复用本次确认结论；法规/平台规则变化时仅需重跑 Step 5。
                </p>
                <p v-if="skuReuse?.available" class="reuse-hint">
                  该 SKU 已有终审归档（{{
                    formatDateTime(skuReuse.archived_at || "")
                  }}），可复用 Step
                  {{ (skuReuse.reusable_steps || [1, 2, 3, 4]).join("、") }}
                  <template v-if="skuReuse.rule_changed"
                    >；检测到合规规则已变化，需重跑 Step 5。</template
                  >
                </p>
              </div> -->
            </div>
          </section>

          <div class="step-actions split">
            <span class="compliance-boundary"
              >内部审核不等同于行政广告审查，发布前仍须按企业制度复核.</span
            >
            <div class="export-buttons">
              <v-btn
                color="primary"
                variant="flat"
                prepend-icon="mdi-file-eye-outline"
                :loading="reportPreview.loading"
                @click="openReportPreview"
                >全流程报告预览</v-btn
              >
              <v-btn
                variant="tonal"
                prepend-icon="mdi-file-document-outline"
                :loading="exporting"
                @click="exportApproval('approval-report.md')"
                >飞书文档</v-btn
              >
              <v-btn
                variant="tonal"
                prepend-icon="mdi-table-large"
                :loading="exporting"
                @click="exportApproval('feishu-bitable.xlsx')"
                >飞书多维表格</v-btn
              >
              <v-btn
                variant="tonal"
                prepend-icon="mdi-microsoft-excel"
                :loading="exporting"
                @click="exportApproval('approval.xlsx')"
                >Excel 审批包</v-btn
              >
              <v-btn
                variant="tonal"
                prepend-icon="mdi-code-json"
                :loading="exporting"
                @click="exportApproval('full-report.json')"
                >JSON（内容管理系统）</v-btn
              >
              <v-btn
                variant="tonal"
                prepend-icon="mdi-package-down"
                :loading="exporting"
                :disabled="!isApproved"
                @click="exportDelivery"
                >发布交付包</v-btn
              >
            </div>
          </div>
        </div>
      </div>

      <v-dialog v-model="retryDialog" max-width="480">
        <v-card title="重试此步骤">
          <v-card-text>
            <p class="mb-3">
              将返工到「{{
                activeStepMeta.title
              }}」并重新执行，后续已完成步骤需要重新确认。
            </p>
            <v-text-field
              v-model="retryComment"
              label="重试原因（必填）"
              variant="outlined"
              hide-details
              autofocus
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="retryDialog = false">取消</v-btn>
            <v-btn
              color="warning"
              variant="tonal"
              :loading="actionLoading"
              :disabled="!retryComment.trim()"
              @click="confirmRetryStep"
              >确认重试</v-btn
            >
          </v-card-actions>
        </v-card>
      </v-dialog>

      <v-expansion-panels class="source-audit-panels" multiple>
        <v-expansion-panel value="source">
          <v-expansion-panel-title>识别原文与页码</v-expansion-panel-title>
          <v-expansion-panel-text
            ><div class="ocr-pages">
              <article v-for="page in project.pages" :key="page.page_no">
                <header>
                  <strong>第 {{ page.page_no }} 页</strong
                  ><v-chip size="x-small" variant="tonal"
                    >OCR {{ Math.round(page.confidence * 100) }}%</v-chip
                  >
                </header>
                <pre>{{ page.text }}</pre>
              </article>
            </div></v-expansion-panel-text
          >
        </v-expansion-panel>
        <v-expansion-panel value="audit">
          <v-expansion-panel-title>审计记录与版本</v-expansion-panel-title>
          <v-expansion-panel-text
            ><div class="audit-list">
              <div
                v-for="(event, index) in project.audit_events"
                :key="index"
                class="audit-item"
              >
                <span><v-icon icon="mdi-check" size="16" /></span>
                <div>
                  <strong>{{ auditAction(String(event.action || "")) }}</strong>
                  <p>
                    {{ event.operator }} ·
                    {{ formatDate(String(event.time || "")) }}
                  </p>
                  <small v-if="event.comment">{{ event.comment }}</small>
                </div>
              </div>
            </div></v-expansion-panel-text
          >
        </v-expansion-panel>
      </v-expansion-panels>

      <div v-if="false" class="workflow-controls">
        <div>
          <v-text-field
            v-model="workflowComment"
            label="返工/终止批注"
            placeholder="执行返工或终止时必填"
            variant="outlined"
            hide-details
          />
          <v-select
            v-model="reworkTarget"
            :items="reworkOptions"
            label="返工到步骤"
            variant="outlined"
            hide-details
          />
          <v-select
            v-if="isApproved || approvalDone('compliance')"
            v-model="finalReworkReason"
            :items="finalReworkReasons"
            label="终审返工原因"
            variant="outlined"
            hide-details
          />
        </div>
        <div v-if="project?.final_reviews?.length" class="final-reviews">
          <strong>整体复盘记录</strong>
          <p v-for="review in project?.final_reviews" :key="review.review_id">
            {{ formatDateTime(review.time) }} · {{ review.operator }} ·
            {{ review.reason_text }} → 返工至 Step
            {{ displayStepNo(review.target_step) }}
            <template v-if="review.was_approved">（终审后撤回）</template>：{{
              review.comment
            }}
          </p>
        </div>
        <div>
          <v-btn
            color="warning"
            variant="tonal"
            :loading="actionLoading"
            @click="reworkProject"
            >返工</v-btn
          >
          <v-btn
            v-if="!isApproved"
            color="error"
            variant="tonal"
            :loading="actionLoading"
            @click="terminateProject"
            >终止项目</v-btn
          >
        </div>
      </div>
    </section>

    <section class="history-section">
      <div class="section-heading section-heading--compact">
        <div>
          <span class="section-kicker">HISTORY</span>
          <h2>最近项目</h2>
        </div>
        <div class="history-heading-actions">
          <v-btn
            color="primary"
            variant="tonal"
            prepend-icon="mdi-plus"
            @click="startNewProject"
            >新增项目</v-btn
          >
          <v-btn
            icon="mdi-refresh"
            variant="text"
            aria-label="刷新最近项目"
            :loading="loadingHistory"
            @click="loadHistory"
          />
        </div>
      </div>
      <div v-if="history.length" class="history-grid">
        <div
          v-for="item in history"
          :key="item.project_id"
          class="history-card"
        >
          <button
            type="button"
            class="history-card-main"
            :disabled="
              openingProjectId === item.project_id ||
              deletingProjectId === item.project_id
            "
            @click="openProject(item.project_id)"
          >
            <div>
              <v-icon icon="mdi-file-document-check-outline" size="22" /><v-chip
                :color="historyStatusColor(item)"
                size="x-small"
                variant="tonal"
                >{{ historyStatusLabel(item) }}</v-chip
              >
            </div>
            <strong>{{ item.product_name }}</strong>
            <span>{{ item.filename }}</span>
            <small
              >步骤 {{ displayStepNo(item.workflow_step || 1) }}/{{
                visibleWorkflowSteps.length
              }}
              · {{ item.field_count }} 个字段 ·
              {{ item.keyword_count }} 个关键词 ·
              {{ formatDate(item.updated_at) }}</small
            >
          </button>
          <div class="history-card-actions">
            <v-btn
              size="small"
              variant="tonal"
              color="primary"
              prepend-icon="mdi-pencil-outline"
              :loading="openingProjectId === item.project_id"
              :disabled="!!deletingProjectId"
              @click="openProject(item.project_id)"
              >修改</v-btn
            >
            <v-btn
              size="small"
              variant="tonal"
              color="error"
              prepend-icon="mdi-delete-outline"
              :loading="deletingProjectId === item.project_id"
              :disabled="
                !!openingProjectId ||
                (!!deletingProjectId && deletingProjectId !== item.project_id)
              "
              @click="confirmDeleteProject(item)"
              >删除</v-btn
            >
          </div>
        </div>
      </div>
      <div v-else class="history-empty">
        暂无历史项目，完成首次识别后会显示在这里。
      </div>
    </section>

    <v-dialog v-model="deleteDialog" max-width="420">
      <v-card title="确认删除项目">
        <v-card-text
          >确定删除「{{
            projectToDelete?.product_name
          }}」吗？原始文件和项目记录将一并删除，且无法恢复。</v-card-text
        >
        <v-card-actions>
          <v-spacer />
          <v-btn
            variant="text"
            :disabled="!!deletingProjectId"
            @click="deleteDialog = false"
            >取消</v-btn
          >
          <v-btn
            color="error"
            variant="tonal"
            :loading="!!deletingProjectId"
            @click="deleteProject"
            >确认删除</v-btn
          >
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="previewImage.show" max-width="1100">
      <v-card>
        <v-card-title class="d-flex align-center">
          <span class="text-truncate">{{ previewImage.title }}</span>
          <v-spacer />
          <v-btn
            icon="mdi-close"
            size="small"
            variant="text"
            aria-label="关闭"
            @click="previewImage.show = false"
          />
        </v-card-title>
        <v-card-text class="text-center">
          <img
            :src="previewImage.src"
            :alt="previewImage.title"
            style="max-width: 100%; max-height: 80vh; object-fit: contain"
          />
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-dialog v-model="reportPreview.show" max-width="1000" scrollable>
      <v-card>
        <v-card-title class="d-flex align-center flex-wrap ga-2">
          <span>全流程报告预览</span>
          <v-chip v-if="isApproved" size="small" color="success" variant="tonal"
            >已终审</v-chip
          >
          <v-chip v-else size="small" color="warning" variant="tonal"
            >未终审（草稿）</v-chip
          >
          <v-spacer />
          <v-btn
            size="small"
            variant="tonal"
            prepend-icon="mdi-language-markdown-outline"
            :disabled="!reportPreview.markdown"
            @click="downloadReport('md')"
            >下载 Markdown</v-btn
          >
          <v-btn
            size="small"
            variant="tonal"
            prepend-icon="mdi-language-html5"
            :disabled="!reportPreview.html"
            @click="downloadReport('html')"
            >下载 HTML</v-btn
          >
          <v-btn
            size="small"
            color="primary"
            variant="flat"
            prepend-icon="mdi-printer-outline"
            :disabled="!reportPreview.html"
            @click="printReport"
            >打印 / 另存为 PDF</v-btn
          >
          <v-btn
            icon="mdi-close"
            variant="text"
            size="small"
            @click="reportPreview.show = false"
          />
        </v-card-title>
        <div class="d-flex align-center flex-wrap ga-2 px-4 pb-3">
          <span class="text-caption text-medium-emphasis">一键导出：</span>
          <v-btn
            size="small"
            variant="tonal"
            prepend-icon="mdi-file-document-outline"
            :loading="exporting"
            @click="exportApproval('approval-report.md')"
            >飞书文档</v-btn
          >
          <v-btn
            size="small"
            variant="tonal"
            prepend-icon="mdi-table-large"
            :loading="exporting"
            @click="exportApproval('feishu-bitable.xlsx')"
            >飞书多维表格</v-btn
          >
          <v-btn
            size="small"
            variant="tonal"
            prepend-icon="mdi-microsoft-excel"
            :loading="exporting"
            @click="exportApproval('approval.xlsx')"
            >Excel 审批包</v-btn
          >
          <v-btn
            size="small"
            variant="tonal"
            prepend-icon="mdi-code-json"
            :loading="exporting"
            @click="exportApproval('full-report.json')"
            >JSON</v-btn
          >
        </div>
        <v-divider />
        <v-card-text style="max-height: 75vh">
          <div v-if="reportPreview.loading" class="text-center pa-6">
            <v-progress-circular indeterminate color="primary" />
          </div>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <article
            v-else
            class="report-preview-body"
            v-html="reportPreview.html"
          />
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      location="top center"
      :timeout="5000"
      >{{ snackbar.message }}</v-snackbar
    >
  </div>
</template>

<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import type { AxiosError } from "axios";
import {
  pharmaTranslatorApi,
  type ComplianceKnowledgeBase,
  type ComplianceExpertTicket,
  type ComplianceAiAnswer,
  type ComplianceFilterState,
  type FilterDisposal,
  type FilterInventoryItem,
  type ComplianceLabel,
  type ComplianceReviewDecision,
  type ComplianceRisk,
  type CompetitorCapabilities,
  type CompetitorGap,
  type CompetitorMode,
  type CompetitorPlatform,
  type PharmaClaim,
  type PharmaContent,
  type PharmaDimension,
  type PharmaField,
  type PharmaLiteratureClaim,
  type PharmaLiteratureRedline,
  type PharmaProject,
  type PharmaProjectSummary,
  type PharmaScene,
  type PharmaWorkflowAction,
  type LiteratureTier,
  type AuditChainRow,
  type PharmaApprovalExportKind,
  type SkuReuseStatus,
} from "@/api/pharmaTranslator";
import { knowledgeApi } from "@/api/v1";
import { copyToClipboard } from "@/utils/clipboard";
import customerServiceQr from "@/assets/customer-service-qr.png";
import MarkdownIt from "markdown-it";
import DOMPurify from "dompurify";

const workflowSteps = [
  {
    title: "品名与说明书",
    subtitle: "OCR / 字段确认",
    description: "核对 8 项关键字段及原文证据，确认后冻结产品档案版本。",
  },
  {
    title: "多维拆解",
    subtitle: "事实 / 安全约束",
    description: "核对成分、功效、人群、背书多维候选及独立安全约束。",
  },
  {
    title: "文献来源",
    subtitle: "卖点 / 三色证据",
    description:
      "上传企业文献或选择本地知识库，完成卖点—文献双向验证；无证据卖点不进入内容生成。",
  },
  {
    title: "场景生成",
    subtitle: "场景翻译引擎",
    description:
      "由已验证卖点翻译生成场景候选，勾选 1—5 个重点场景并标注强打/弱打/删除。",
  },
  {
    title: "竞品扫描",
    subtitle: "真实采集 / 缺口地图",
    description:
      "实时采集小红书/抖音/电商/知乎竞品内容，由已配置的生成模型分析内容缺口与机会优先级，市场部+运营选定 P0/P1 蓝海切口。",
  },
  {
    title: "合规过滤",
    subtitle: "三级规则 / 存量处置",
    description:
      "对竞品样本与品牌存量内容执行中睿三级过滤，合规部逐条复核、确认存量处置清单与广审排期。",
  },
  {
    title: "搜索词与优先级",
    subtitle: "来源 / 评分",
    description: "确认关键词来源、观测时间和可解释优先级，不伪装真实热度。",
    hidden: true,
  },
  {
    title: "医学确认",
    subtitle: "Claim / 证据等级",
    description: "逐条确认卖点和证据等级；无证据卖点不能进入内容生成。",
    hidden: true,
  },
  {
    title: "内容与审批",
    subtitle: "合规 / 终审 / 导出",
    description: "分平台生成、确定性合规扫描、市场与合规确认、品牌终审。",
  },
];
// 第 7/8 步已从流程移除（后端自动通过），内部步骤编号保持不变
const visibleWorkflowSteps = workflowSteps
  .map((step, index) => ({ ...step, step: index + 1 }))
  .filter((step) => !step.hidden);
function displayStepNo(step: number) {
  const index = visibleWorkflowSteps.findIndex((item) => item.step >= step);
  return index === -1 ? visibleWorkflowSteps.length : index + 1;
}
// 证据摘录展示去重：同一行原文只显示一次，同一来源同一页只列一次
function uniqueSourceText(text?: string | null) {
  const seen = new Set<string>();
  return String(text || "")
    .split("\n")
    .filter((line) => {
      const key = line.replace(/[\s\p{P}]/gu, "");
      if (key.length < 4) return true;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .join("\n")
    .trim();
}
function uniqueEvidenceSources<
  T extends { source_label?: string; page_no?: number | null },
>(evidence?: T[] | null) {
  const seen = new Set<string>();
  return (evidence || []).filter((source) => {
    const key = `${source.source_label || ""}|${source.page_no ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
const productTypes = [
  "自动识别",
  "OTC",
  "RX",
  "医疗器械",
  "保健食品",
  "消字号",
  "食字号",
];

const productName = ref("");
const productType = ref("自动识别");
const selectedFile = ref<File | null>(null);
const previewUrl = ref("");
const dragging = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);
const analyzing = ref(false);
const actionLoading = ref(false);
const dimensionsLoading = ref(false);
const dimensionsError = ref("");
const dimensionAutoAttempts = new Set<string>();
const dimensionRequests = new Set<string>();
const actionRequests = new Set<string>();
let projectContext = 0;
function resetProjectContext() {
  projectContext += 1;
  dimensionsLoading.value = false;
  dimensionsError.value = "";
  actionLoading.value = false;
  return projectContext;
}
const exporting = ref(false);
const loadingHistory = ref(false);
const openingProjectId = ref("");
const deletingProjectId = ref("");
const deleteDialog = ref(false);
const projectToDelete = ref<PharmaProjectSummary | null>(null);
const project = ref<PharmaProject | null>(null);
const history = ref<PharmaProjectSummary[]>([]);
const activeStep = ref(1);
const keywordSearch = ref("");
const workflowComment = ref("");
const reworkTarget = ref(1);
const finalReworkReason = ref("");
const finalReworkReasons = [
  { title: "常规返工（非终审）", value: "" },
  { title: "业务目标偏离 → 整体复盘", value: "business_deviation" },
  { title: "预算超限 → 整体复盘", value: "budget_overrun" },
  { title: "风险未提示 → 整体复盘", value: "risk_unflagged" },
  { title: "审计链缺环 → 整体复盘", value: "audit_gap" },
];
const finalChecklistOptions = [
  { key: "completeness", text: "全流程产出完整性（Step 1-6 产出物齐备）" },
  { key: "business_goal", text: "业务目标达成度已评估" },
  { key: "publish_ready", text: "内容可进入发布" },
  { key: "audit_chain", text: "文献引证链 + 合规审计链齐备" },
];
const finalSigner = ref("");
const finalSignerTitle = ref("品牌总监");
const finalChecklist = ref<string[]>([]);
const finalChecklistAllChecked = computed(() => {
  const selectable = finalChecklistOptions.filter(
    (item) => !finalChecklistItemLockReason(item.key),
  );
  return (
    selectable.length > 0 &&
    selectable.every((item) => finalChecklist.value.includes(item.key))
  );
});
function toggleFinalChecklistAll() {
  finalChecklist.value = finalChecklistAllChecked.value
    ? []
    : finalChecklistOptions
        .filter((item) => !finalChecklistItemLockReason(item.key))
        .map((item) => item.key);
}
const finalDuration = ref(45);
const finalGoalNote = ref("");
const finalAuthorized = ref(false);
const finalChannels = ref<string[]>([]);
const todayStr = (() => {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 10);
})();
const finalStartDate = ref(todayStr);
const finalTouched = ref(false);
const finalTitleOptions = ["品牌总监", "业务负责人", "品牌负责人"];
const finalTitleValid = computed(() =>
  /品牌|总监|负责人/.test((finalSignerTitle.value || "").trim()),
);
const finalDurationHint = computed(() => {
  const minutes = Number(finalDuration.value) || 0;
  if (minutes <= 0) return "请填写确认时长";
  if (minutes < 30) return "低于典型 30 分钟，请确认已完整审阅";
  if (minutes > 60) return "超过典型 60 分钟";
  return "";
});
const skuReuse = ref<SkuReuseStatus | null>(null);
const snackbar = ref({ show: false, message: "", color: "success" });

const literatureDocKindOptions = [
  { value: "pharmacopoeia", title: "药典/国家标准" },
  { value: "clinical", title: "临床研究/RCT/Meta" },
  { value: "testing", title: "原料/第三方检测报告" },
  { value: "patent", title: "专利/批文/官方公示" },
  { value: "leaflet", title: "说明书/标签" },
  { value: "other", title: "其他资料" },
];
const literatureDocKind = ref("pharmacopoeia");
const literatureFiles = ref<File[]>([]);
const literatureUploading = ref(false);
const literatureMatching = ref(false);
const literatureTier = ref<LiteratureTier>("light");
const literatureTierOptions = [
  { value: "light", title: "轻量档：上传文献 + 段落索引 + 关键词匹配" },
  { value: "standard", title: "标准档：加接 PubMed 公开文献自动补证" },
  { value: "deep", title: "深度档：标准档 + 成分-靶点-适应症三元组推理" },
];
const evidenceLevelOptions = [
  { value: "strong", title: "🟢 强证据" },
  { value: "weak", title: "🟡 弱证据" },
  { value: "none", title: "🔴 无证据" },
];
// 人工调整证据等级：仅在提交确认时随卖点一起提交，后端校验理由与引用
const literatureLevelDrafts = ref<
  Record<
    string,
    { level: PharmaLiteratureClaim["evidence_level"]; reason: string }
  >
>({});
const literatureSigner = ref({ name: "", title: "" });
// 医学部/学术部确认清单四项，须全部勾选方可签字
const literatureChecklistItems = [
  { key: "claims_complete", label: "卖点清单完整" },
  { key: "matches_valid", label: "文献匹配成立" },
  { key: "levels_accurate", label: "三色标签准确" },
  { key: "redlines_complete", label: "禁用卖点无遗漏（已纳入红线清单）" },
] as const;
function emptyLiteratureChecklist(value = false): Record<string, boolean> {
  return Object.fromEntries(
    literatureChecklistItems.map((item) => [item.key, value]),
  );
}
const literatureChecklist = ref<Record<string, boolean>>(
  emptyLiteratureChecklist(),
);
const literatureChecklistDone = computed(() =>
  literatureChecklistItems.every((item) => literatureChecklist.value[item.key]),
);
const literatureSignerQualified = computed(() => {
  const signer = `${literatureSigner.value.name}${literatureSigner.value.title}`;
  return (
    /医学|学术/.test(literatureSigner.value.title) &&
    !/代签|代为|代替|代理|委托|on\s*behalf/i.test(signer)
  );
});
const literatureRedlines = ref<PharmaLiteratureRedline[]>([]);
const literatureRedlineDialog = ref(false);
const literatureRedlineLoading = ref(false);
const selectedKbIds = ref<string[]>([]);
const kbOptions = ref<Array<{ title: string; value: string }>>([]);
const kbLoading = ref(false);
const dimensionKbIds = ref<string[]>([]);
const dimensionSearchMode = ref<"auto" | "none" | "standard" | "deep">("auto");
const dimensionSearchModeOptions = [
  { title: "自动（优先深度采集）", value: "auto" },
  { title: "标准采集（opencli）", value: "standard" },
  { title: "深度采集（TikHub）", value: "deep" },
  { title: "不搜索，仅用资料与知识库", value: "none" },
];
const competitorCaps = ref<CompetitorCapabilities | null>(null);
const competitorMode = ref<CompetitorMode>("light");
const competitorPlatforms = ref<CompetitorPlatform[]>([
  "douyin",
  "xiaohongshu",
]);
const competitorKeywords = ref("");
const competitorBrands = ref("");
const competitorUrls = ref("");
const competitorPerKeyword = ref(20);
const competitorScanning = ref(false);
const competitorAnalyzing = ref(false);
const competitorVoiceImports = ref<string[]>([]);
const competitorOurPrice = ref("");
const competitorRadarBrands = ref<string[]>([]);
const competitorSignalResponses = ref<Record<string, string>>({});
const complianceKb = ref<ComplianceKnowledgeBase | null>(null);
const complianceKbIds = ref<string[]>([]);
const complianceReviewing = ref(false);
const reviewProgress = ref<{
  running: boolean;
  started_at: number | null;
  logs: { t: number; message: string }[];
  streams: Record<string, string>;
} | null>(null);
const reviewElapsed = ref(0);
let reviewTimer: number | undefined;
const ticketSubmitting = ref(false);
const customerServiceDialog = ref(false);
const previewImage = ref({ show: false, src: "", title: "" });
const reportPreview = ref({
  show: false,
  loading: false,
  markdown: "",
  html: "",
});
const reportMarkdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
});
function openImagePreview(src: string, title: string) {
  previewImage.value = { show: true, src, title };
}
const complianceDuration = ref<number | null>(null);
const citationCovered = ref(false);
type ReviewDraft = {
  decision: ComplianceReviewDecision["decision"] | null;
  note: string;
};
const reviewDrafts = ref<Record<string, ReviewDraft>>({});
const ticketAnswerDrafts = ref<
  Record<string, { answer: string; expertName: string }>
>({});

type FilterInventoryDraft = FilterInventoryItem & { draft_key: string };
type FilterDisposalDraft = {
  status: "done" | "scheduled" | null;
  scheduled_date: string;
  note: string;
};
const filterInventoryDrafts = ref<FilterInventoryDraft[]>([]);
const filterReviewDrafts = ref<Record<string, ReviewDraft>>({});
const filterDisposalDrafts = ref<Record<string, FilterDisposalDraft>>({});
const filterKbIds = ref<string[]>([]);
const filterAiSearch = ref(true);
const filterRunning = ref(false);
const filterTicketQuestion = ref("");
const filterTicketRiskIds = ref<string[]>([]);
const filterSignerName = ref("");
const filterSignerTitle = ref("合规部");
const filterApplyDate = ref("");
const filterAuthority = ref("省级药品监督管理部门");
const filterAdNote = ref("");
const filterComment = ref("");
const filterConfirmChecks = ref<string[]>([]);
const filterConfirmChecksComplete = computed(() =>
  ZR_CONFIRM_CHECKS.every((item) =>
    filterConfirmChecks.value.includes(item.value),
  ),
);
const consultDialog = ref(false);
const consultQrBroken = ref(false);
const aiAskQuestion = ref("");
const aiAskLoading = ref(false);
const aiAskResult = ref<ComplianceAiAnswer | null>(null);
const ZR_CONSULT_QR_URL = `${
  import.meta.env.BASE_URL
}zhongrui-consult-qrcode.png`;
const ZR_CONFIRM_CHECKS = [
  { value: "label_review", label: "三色标签复核" },
  { value: "caution_notes", label: "谨慎项逐条批注" },
  { value: "violation_adoption", label: "违规修改建议采纳情况" },
  {
    value: "evidence_coverage",
    label: "文献引证是否完整覆盖所有合规风险点",
  },
];
let forceFilterInventorySync = false;
let filterDraftCounter = 0;
function nextFilterDraftKey() {
  filterDraftCounter += 1;
  return `inv-draft-${Date.now().toString(36)}-${filterDraftCounter}`;
}
function emptyFilterInventory(): FilterInventoryItem {
  return {
    platform: "",
    channel: "",
    date: "",
    url: "",
    account: "",
    title: "",
    body: "",
    is_brand_matrix: false,
    is_koc: false,
    koc_verified: false,
  };
}
function filterInventoryPayload(): FilterInventoryItem[] {
  return filterInventoryDrafts.value.map((item) => ({
    ...(item.inventory_id ? { inventory_id: item.inventory_id } : {}),
    platform: (item.platform || "").trim(),
    channel: (item.channel || "").trim(),
    date: (item.date || "").trim(),
    url: (item.url || "").trim(),
    account: (item.account || "").trim(),
    title: (item.title || "").trim(),
    body: (item.body || "").trim(),
    is_brand_matrix: Boolean(item.is_brand_matrix),
    is_koc: Boolean(item.is_koc),
    koc_verified: Boolean(item.is_koc && item.koc_verified),
  }));
}
function filterInventoryFingerprint(items: FilterInventoryItem[]) {
  return JSON.stringify(
    items
      .filter((item) => (item.title || "").trim() || (item.body || "").trim())
      .map((item) => [
        (item.platform || "").trim(),
        (item.channel || "").trim(),
        (item.date || "").trim(),
        (item.url || "").trim(),
        (item.account || "").trim(),
        (item.title || "").trim(),
        (item.body || "").trim(),
        Boolean(item.is_brand_matrix),
        Boolean(item.is_koc),
        Boolean(item.is_koc && item.koc_verified),
      ]),
  );
}

interface UserNoteDraft {
  note_id: string;
  title: string;
  text: string;
}
const userNotes = ref<UserNoteDraft[]>([]);
let noteCounter = 0;
function nextNoteId() {
  noteCounter += 1;
  return `note-draft-${Date.now().toString(36)}-${noteCounter}`;
}
function addUserNote() {
  userNotes.value.push({ note_id: nextNoteId(), title: "", text: "" });
}
function removeUserNote(index: number) {
  userNotes.value.splice(index, 1);
}

const isPdf = computed(
  () =>
    selectedFile.value?.type === "application/pdf" ||
    selectedFile.value?.name.toLowerCase().endsWith(".pdf"),
);
const canAnalyze = computed(
  () =>
    Boolean(selectedFile.value) &&
    !analyzing.value &&
    !openingProjectId.value &&
    !actionLoading.value &&
    !dimensionsLoading.value,
);
const currentStep = computed(() =>
  Math.min(9, Math.max(1, Number(project.value?.workflow?.current_step || 1))),
);
const workflowStatus = computed(() =>
  String(
    project.value?.workflow?.status || project.value?.status || "draft",
  ).toLowerCase(),
);
const isTerminated = computed(() => workflowStatus.value.includes("terminat"));
const isApproved = computed(
  () => workflowStatus.value.includes("approved") || approvalDone("final"),
);
const readOnly = computed(() => isTerminated.value || isApproved.value);
const canRegenerateContentImages = computed(
  () => Boolean(project.value) && !isTerminated.value && currentStep.value === 9,
);
const currentStepMeta = computed(() => workflowSteps[currentStep.value - 1]);
const activeStepMeta = computed(() => workflowSteps[activeStep.value - 1]);
const workflowStateLabel = computed(() => {
  if (!project.value) return "上传 → 证据 → 审批";
  if (isTerminated.value) return "项目已终止";
  if (isApproved.value) return "终审通过，可交付";
  return (
    project.value.workflow?.state || project.value.workflow?.status || "处理中"
  );
});
const dimensions = computed(() => project.value?.dimensions || []);
const dimensionDisplayOrder = [
  "brand_product",
  "efficacy",
  "ingredients",
  "ingredient",
  "audience",
  "channels",
  "endorsement",
];
const orderedDimensions = computed(() =>
  [...dimensions.value].sort((a, b) => {
    const rank = (item: PharmaDimension) => {
      const index = dimensionDisplayOrder.indexOf(dimensionKey(item));
      return index === -1 ? dimensionDisplayOrder.length : index;
    };
    return rank(a) - rank(b);
  }),
);
const dimensionGeneration = computed(
  () => project.value?.dimension_generation || null,
);
const reviewItemTotal = computed(
  () =>
    dimensions.value.reduce(
      (sum, dimension) => sum + (dimension.items?.length || 0),
      0,
    ) + safetyConstraints.value.length,
);
const confirmedReviewCount = computed(
  () =>
    dimensions.value.reduce(
      (sum, dimension) =>
        sum + (dimension.items || []).filter((item) => item.confirmed).length,
      0,
    ) + safetyConstraints.value.filter((item) => item.confirmed).length,
);
const allReviewConfirmed = computed(
  () =>
    reviewItemTotal.value > 0 &&
    confirmedReviewCount.value === reviewItemTotal.value,
);
function toggleAllReviewConfirmed() {
  const target = !allReviewConfirmed.value;
  dimensions.value.forEach((dimension) => {
    (dimension.items || []).forEach((item) => {
      item.confirmed = target;
    });
  });
  safetyConstraints.value.forEach((item) => {
    item.confirmed = target;
  });
  if (target) {
    nextTick(() => {
      document
        .getElementById("dimension-step-actions")
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }
}
const safetyConstraints = computed(
  () => project.value?.safety_constraints || [],
);
const scenes = computed(() => project.value?.scenes || []);
const activeScenes = computed(() =>
  scenes.value.filter((scene) => !scene.deleted),
);
const channelCategories = ["医院", "药店", "诊所", "药品零售商", "药品批发商"];
function channelHit(
  dimension: {
    items: Array<{ text?: string; value?: string; status?: string }>;
  },
  category: string,
) {
  return dimension.items.some(
    (item) =>
      item.status !== "rejected" &&
      (item.text || item.value || "").trim() === category,
  );
}
function dimensionItemsOf(code: string) {
  const dimension = dimensions.value.find(
    (item) => dimensionKey(item) === code,
  );
  return (dimension?.items || [])
    .filter((item) => item.status !== "rejected")
    .map((item) => (item.text || item.value || "").trim())
    .filter(Boolean);
}
const dimensionDrugName = computed(
  () =>
    dimensionGeneration.value?.drug_name ||
    dimensionItemsOf("brand_product")[0] ||
    project.value?.product_name ||
    "",
);
// OCR 原文常因多证据拼接出现整段重复，按句子/行去重（忽略空白差异），保留首次出现
function dedupeSourceText(text: string) {
  const seen = new Set<string>();
  return (text || "")
    .split(/(?<=。)|\n/)
    .map((segment) => segment.trim())
    .filter((segment) => {
      const key = segment.replace(/\s+/g, "");
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .join("\n");
}
const dimensionSourceText = computed(() => {
  const dimension = dimensions.value.find(
    (item) => dimensionKey(item) === "efficacy",
  );
  const item = (dimension?.items || []).find((entry) => entry.source_text);
  const text = item?.source_text || dimensionItemsOf("efficacy").join("；");
  return dedupeSourceText(text);
});
const dimensionFlowHeadline = computed(
  () => dimensionItemsOf("efficacy")[0]?.slice(0, 12) || "说明书功能主治",
);
const dimensionFlowRows = computed(() =>
  ["efficacy", "audience", "channels", "brand_product"].map((code) => ({
    code,
    label: dimensionLabel({ dimension_code: code, items: [] }),
    text: dimensionItemsOf(code).slice(0, 3).join("、"),
  })),
);
const scenePriorityMatrix = computed(() => {
  const gaps = competitor.value?.analysis?.gap_map || [];
  const rows = activeScenes.value.map((scene) => {
    const signals =
      (scene.search_keywords?.length || 0) +
      (scene.user_voices?.length || 0) * 2;
    const market = signals >= 7 ? 3 : signals >= 4 ? 2 : 1;
    const coverage = scene.evidence_coverage || 0;
    const doability = coverage >= 0.8 ? 3 : coverage >= 0.5 ? 2 : 1;
    const gap = gaps.find((item) => item.our_scene_no === scene.scene_no);
    const score =
      market +
      doability +
      (scene.priority === "strong" ? 2 : scene.priority === "weak" ? -1 : 0);
    return {
      scene_id: scene.scene_id,
      scene_no: scene.scene_no || "",
      name: scene.name,
      market,
      doability,
      score,
      fixed: gap?.priority || "",
      priority: "" as "P0" | "P1" | "P2" | "",
    };
  });
  const ranked = [...rows].sort((a, b) => b.score - a.score);
  ranked.forEach((row, index) => {
    row.priority =
      (row.fixed as "P0" | "P1") ||
      (index < Math.max(1, Math.ceil(ranked.length / 3))
        ? "P0"
        : index < Math.ceil((ranked.length * 2) / 3)
        ? "P1"
        : "P2");
  });
  return ranked;
});
function starText(level: number) {
  return "★".repeat(level) + "☆".repeat(Math.max(0, 3 - level));
}
function levelText(level: number) {
  return ["", "低", "中", "高"][level] || "";
}
function priorityTierText(priority: string) {
  return (
    ({ P0: "首打", P1: "重点", P2: "差异化" } as Record<string, string>)[
      priority
    ] || ""
  );
}
const claims = computed(() => project.value?.claims || []);
const contents = computed(() => project.value?.contents || []);
const auditChain = computed<AuditChainRow[]>(
  () => project.value?.audit_chain || [],
);
const auditChainGaps = computed(() =>
  auditChain.value
    .filter((row) => row.step < 7 && row.status !== "confirmed")
    .map((row) => row.step_label),
);
const contentChannels = computed(
  () =>
    [
      ...new Set(contents.value.map((item) => item.channel).filter(Boolean)),
    ] as string[],
);
const finalRecord = computed(
  () =>
    (
      project.value?.approvals?.final as
        | { record?: Record<string, any> }
        | undefined
    )?.record || null,
);
const exportChecklist = computed(() => {
  const chain = auditChain.value;
  const done = (step: number) =>
    chain.find((row) => row.step === step)?.status === "confirmed";
  return [
    { text: "本报告（飞书文档，全文）", done: true },
    {
      text: "卖点-文献三联表（飞书多维表格，可挂确认状态字段）",
      done: done(2),
    },
    { text: "选题矩阵（飞书多维表格，含发布排期字段）", done: done(6) },
    { text: "存量违规内容处置清单（执行跟踪表）", done: done(5) },
  ];
});
watch(
  () => project.value?.project_id,
  (projectId) => {
    void loadSkuReuse(projectId);
  },
);
const filledFieldCount = computed(
  () => project.value?.fields.filter((field) => field.value.trim()).length || 0,
);
const selectedKeywordCount = computed(
  () =>
    project.value?.keywords.filter((keyword) => keyword.selected).length || 0,
);
const selectedSceneCount = computed(
  () => scenes.value.filter((scene) => scene.selected).length,
);
// 场景多选：确认提交上限 5 个，一键全选只取前 5 个未删除场景
const MAX_SELECTED_SCENES = 5;
const selectableScenes = computed(() =>
  scenes.value.filter((scene) => !scene.deleted),
);
const allScenesSelected = computed(() => {
  const candidates = selectableScenes.value.slice(0, MAX_SELECTED_SCENES);
  return candidates.length > 0 && candidates.every((scene) => scene.selected);
});
function scrollToSceneActions() {
  nextTick(() => {
    document
      .getElementById("scene-step-actions")
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  });
}
function toggleAllScenesSelected() {
  if (readOnly.value || currentStep.value !== 4) return;
  const target = !allScenesSelected.value;
  const candidates = selectableScenes.value.slice(0, MAX_SELECTED_SCENES);
  scenes.value.forEach((scene) => {
    scene.selected = target && candidates.includes(scene);
  });
  if (target) scrollToSceneActions();
}
function onSceneCheckboxChange(value: boolean | null) {
  if (!value || readOnly.value || currentStep.value !== 4) return;
  scrollToSceneActions();
}
const confirmedClaimCount = computed(
  () =>
    claims.value.filter(
      (claim) => claim.medical_confirmed && claim.evidence_level !== "none",
    ).length,
);
const criticalWithValueCount = computed(
  () =>
    project.value?.fields.filter(
      (field) => field.critical && field.value.trim(),
    ).length || 0,
);
const criticalConfirmedCount = computed(
  () =>
    project.value?.fields.filter(
      (field) => field.critical && field.value.trim() && field.confirmed,
    ).length || 0,
);
const confirmableFields = computed(
  () => project.value?.fields.filter((field) => field.value) || [],
);
const allFieldsConfirmed = computed({
  get: () =>
    confirmableFields.value.length > 0 &&
    confirmableFields.value.every((field) => field.confirmed),
  set: (value: boolean) => {
    confirmableFields.value.forEach((field) => {
      field.confirmed = value;
    });
  },
});
const someFieldsConfirmed = computed(() =>
  confirmableFields.value.some((field) => field.confirmed),
);
function onToggleAllFieldsConfirmed(value: boolean | null) {
  if (!value) return;
  nextTick(() => {
    document
      .getElementById("profile-step-actions")
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  });
}
const canConfirmEvidence = computed(() =>
  claims.value.some(
    (claim) => claim.evidence_level !== "none" && claim.medical_confirmed,
  ),
);
const literature = computed(
  () =>
    project.value?.literature || {
      documents: [],
      kb_ids: [],
      kb_names: [],
      matched_at: null,
    },
);
const literatureDocuments = computed(() => literature.value.documents || []);
const evidenceSortRank: Record<string, number> = {
  strong: 0,
  weak: 1,
  none: 2,
};
const literatureClaims = computed(() =>
  [...(project.value?.literature_claims || [])].sort(
    (a, b) =>
      (evidenceSortRank[a.evidence_level] ?? 2) -
        (evidenceSortRank[b.evidence_level] ?? 2) ||
      a.claim_no.localeCompare(b.claim_no),
  ),
);
const unusableClaims = computed(() => project.value?.unusable_claims || []);
const literatureClaimGroups = computed(() => {
  const order: Array<{ type: string; label: string; icon: string }> = [
    { type: "ingredients", label: "成分卖点", icon: "🧪" },
    { type: "efficacy", label: "功效卖点", icon: "🎯" },
    { type: "audience", label: "人群卖点", icon: "👥" },
    { type: "endorsement", label: "背书卖点", icon: "🏆" },
  ];
  return order
    .map((group) => ({
      ...group,
      items: literatureClaims.value.filter(
        (claim) => claim.claim_type === group.type,
      ),
    }))
    .filter((group) => group.items.length);
});
const literatureMatched = computed(() => Boolean(literature.value.matched_at));
// 进入文献来源步骤时自动执行一次文献匹配（每个项目版本仅一次）；
// 结果不满意时可随时点「重新执行文献匹配」手动再来一次。
const literatureAutoAttempts = new Set<string>();
watch([activeStep, currentStep, () => project.value?.workflow?.version], () => {
  if (
    !project.value ||
    activeStep.value !== 3 ||
    currentStep.value !== 3 ||
    readOnly.value ||
    literatureMatched.value ||
    literatureMatching.value ||
    !literatureClaims.value.length
  )
    return;
  const key = `${project.value.project_id}:${
    project.value.workflow?.version || 1
  }`;
  if (literatureAutoAttempts.has(key)) return;
  literatureAutoAttempts.add(key);
  runLiteratureMatch();
});
const literatureSignoff = computed(
  () => project.value?.literature_signoff || null,
);
function effectiveLevel(claim: PharmaLiteratureClaim) {
  return (
    literatureLevelDrafts.value[claim.claim_id]?.level || claim.evidence_level
  );
}
function levelDraft(claim: PharmaLiteratureClaim) {
  if (!literatureLevelDrafts.value[claim.claim_id]) {
    literatureLevelDrafts.value[claim.claim_id] = {
      level: claim.evidence_level,
      reason: "",
    };
  }
  return literatureLevelDrafts.value[claim.claim_id];
}
function setClaimLevel(
  claim: PharmaLiteratureClaim,
  level: PharmaLiteratureClaim["evidence_level"],
) {
  levelDraft(claim).level = level;
  if (level === "none") claim.accepted = false;
}
// 只有满足逐条勾选框启用条件（非无证据且有文献引用）的卖点才允许一键全选
const acceptableClaims = computed(() =>
  literatureClaims.value.filter(
    (claim) =>
      effectiveLevel(claim) !== "none" && (claim.citations || []).length > 0,
  ),
);
const allClaimsAccepted = computed(
  () =>
    acceptableClaims.value.length > 0 &&
    acceptableClaims.value.every((claim) => claim.accepted),
);
function toggleAllClaimsAccepted() {
  if (readOnly.value || currentStep.value !== 3) return;
  const target = !allClaimsAccepted.value;
  acceptableClaims.value.forEach((claim) => {
    claim.accepted = target;
  });
  if (target) {
    nextTick(() => {
      // 下滑到医学部签字节点，下方的「签字确认卖点验证，进入场景生成」按钮也一并进入视野
      document
        .getElementById("literature-signoff")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
}
const levelAdjustMissingReason = computed(() =>
  literatureClaims.value.some((claim) => {
    const draft = literatureLevelDrafts.value[claim.claim_id];
    return (
      draft && draft.level !== claim.evidence_level && !draft.reason.trim()
    );
  }),
);
const acceptedLiteratureCount = computed(
  () =>
    literatureClaims.value.filter(
      (claim) =>
        claim.accepted &&
        effectiveLevel(claim) !== "none" &&
        (claim.citations || []).length,
    ).length,
);
const canConfirmLiterature = computed(
  () =>
    literatureMatched.value &&
    acceptedLiteratureCount.value >= 1 &&
    !levelAdjustMissingReason.value &&
    Boolean(literatureSigner.value.name.trim()) &&
    literatureSignerQualified.value &&
    literatureChecklistDone.value,
);
const batchChannelOptions = [
  "小红书图文",
  "小红书视频",
  "抖音短视频",
  "视频号",
  "公众号",
  "朋友圈",
  "电商详情页",
  "评论区预埋",
  "私信承接",
  "问答平台",
];
const batchChannels = ref<string[]>([...batchChannelOptions]);
const batchTotal = ref(30);
const batchGenerating = ref(false);
const contentBatch = computed(() => project.value?.content_batch || null);
const batchFullContents = computed(() =>
  contents.value.filter(
    (item) =>
      item.batch_role === "full" || item.batch_role === "comment_replies",
  ),
);
const batchContentGroups = computed(() => {
  const batch = contentBatch.value;
  if (!batch) return [];
  const channels = [
    ...batch.channels,
    ...batchFullContents.value
      .map((item) => item.channel || "")
      .filter((name) => name && !batch.channels.includes(name)),
  ];
  return [...new Set(channels)].map((channel) => {
    const items = batchFullContents.value.filter(
      (item) => item.channel === channel,
    );
    return {
      channel,
      items,
      quota:
        batch.channel_stats?.find((row) => row.channel === channel)?.quota || 0,
      reworkCount: (batch.reworks || []).filter(
        (row) => row.channel === channel,
      ).length,
      blocked: items.some((item) =>
        (item.risks || []).some((risk) => risk.level === "block"),
      ),
    };
  });
});
const batchChecklistOptions = [
  { key: "topics", text: "① 选题勾选与排期已确认" },
  { key: "tone", text: "各平台内容调性贴合（无抖音写成小红书风等错位）" },
  { key: "labels", text: "② 3 条示范内容及全部内容合规标签已逐条过" },
  { key: "comment_replies", text: "③ 评论预埋话术已审定、未触碰红线" },
  { key: "claims", text: "每条内容正确引用 Step 2 已验证卖点" },
];
const batchSampleContents = computed(() =>
  contents.value
    .filter((item) => item.sample_no)
    .sort((a, b) => (a.sample_no || 0) - (b.sample_no || 0)),
);
const CHANNEL_ASPECTS: Record<string, string> = {
  小红书图文: "3:4",
  小红书视频: "3:4",
  抖音短视频: "3:4",
  视频号: "6:7",
  公众号: "2.35:1",
};
function channelAspect(channel?: string) {
  return CHANNEL_ASPECTS[channel || ""] || "1:1";
}
function aspectStyle(aspect?: string) {
  const [w, h] = (aspect || "3:4").split(":");
  return { aspectRatio: `${w} / ${h}` };
}
function sceneNameOf(sceneNo?: string) {
  return scenes.value.find((scene) => scene.scene_no === sceneNo)?.name || "";
}
type DemoBlock = { type: "p" | "ul"; lines: string[] };
function demoBlocks(body: string): DemoBlock[] {
  const blocks: DemoBlock[] = [];
  for (const raw of body.split("\n")) {
    const line = raw.trim();
    if (!line) {
      blocks.push({ type: "p", lines: [] });
      continue;
    }
    const item = line.match(/^(?:[-*•·]|\d+[.、])\s*(.+)$/);
    const type = item ? "ul" : "p";
    const last = blocks[blocks.length - 1];
    if (last && last.type === type && (type === "ul" || last.lines.length))
      last.lines.push(item ? item[1] : line);
    else blocks.push({ type, lines: [item ? item[1] : line] });
  }
  return blocks.filter((block) => block.lines.length);
}
function boldParts(line: string) {
  return line.split(/\*\*(.+?)\*\*/).map((text, index) => ({
    text,
    bold: index % 2 === 1,
  }));
}
const batchChecklist = ref<string[]>([]);
const reworkReasonOptions = [
  { key: "tone_mismatch", text: "平台调性错位" },
  { key: "label_missing", text: "合规标签遗漏" },
  { key: "comment_redline", text: "评论预埋触碰红线" },
  { key: "unverified_claim", text: "使用了未验证卖点" },
  { key: "other", text: "其他" },
];
const reworkDialog = ref(false);
const reworkChannel = ref("");
const reworkReason = ref("tone_mismatch");
const reworkComment = ref("");
const reworkLoading = ref("");
const reworkElapsed = ref(0);
let reworkTimer: ReturnType<typeof setInterval> | undefined;
const reworkElapsedText = computed(
  () =>
    `${Math.floor(reworkElapsed.value / 60)}:${String(
      reworkElapsed.value % 60,
    ).padStart(2, "0")}`,
);
const topicDrafts = ref<
  Record<number, { selected: boolean; publish_time: string }>
>({});
const topicsSaving = ref(false);
const topicsEditable = computed(
  () =>
    !readOnly.value &&
    currentStep.value === 9 &&
    !approvalDone("market") &&
    !batchGenerating.value,
);
const selectedTopicDraftCount = computed(
  () => Object.values(topicDrafts.value).filter((row) => row.selected).length,
);
watch(
  () => contentBatch.value?.topic_matrix,
  (matrix) => {
    const drafts: Record<number, { selected: boolean; publish_time: string }> =
      {};
    for (const group of matrix || [])
      for (const topic of group.topics)
        drafts[topic.no] = {
          selected: topic.selected !== false,
          publish_time: topic.publish_time || "",
        };
    topicDrafts.value = drafts;
  },
  { immediate: true },
);
const imageLoading = ref("");
const imageUrls = ref<Record<string, string>>({});
const imageFetching = new Set<string>();
watch(
  () => [
    project.value?.project_id || "",
    ...contents.value.flatMap((item) =>
      (item.images || []).map((image) => image.filename),
    ),
  ],
  ([projectId, ...filenames]) => {
    const wanted = new Set(filenames);
    for (const [name, url] of Object.entries(imageUrls.value)) {
      if (wanted.has(name)) continue;
      URL.revokeObjectURL(url);
      delete imageUrls.value[name];
    }
    if (!projectId) return;
    for (const filename of wanted) {
      if (imageUrls.value[filename] || imageFetching.has(filename)) continue;
      imageFetching.add(filename);
      pharmaTranslatorApi
        .contentImage(projectId, filename)
        .then((response) => {
          if (project.value?.project_id !== projectId) return;
          imageUrls.value[filename] = URL.createObjectURL(
            response.data as Blob,
          );
        })
        .catch(() => undefined)
        .finally(() => imageFetching.delete(filename));
    }
  },
  { immediate: true },
);
const allRisks = computed(() => [
  ...(project.value?.compliance?.risks || []),
  ...contents.value.flatMap((item) => item.risks || []),
]);
const hasBlockingRisk = computed(() =>
  allRisks.value.some((risk) => ["block", "违规/阻断"].includes(risk.level)),
);
const complianceReport = computed(() => project.value?.compliance || null);
const complianceTickets = computed(() =>
  (project.value?.compliance_tickets || []).filter(
    (ticket) => ticket.scope !== "compliance_filter",
  ),
);
const complianceRecord = computed(
  () => project.value?.approvals?.compliance?.record || null,
);
const projectLevelRisks = computed(() =>
  allRisks.value.filter((risk) => !risk.content_id),
);
const reviewableRisks = computed(() =>
  allRisks.value.filter((risk) => risk.risk_id && isReviewableRisk(risk)),
);
const pendingReviewCount = computed(
  () =>
    reviewableRisks.value.filter((risk) => {
      const draft = reviewDrafts.value[risk.risk_id as string];
      if (!draft?.decision) return true;
      return risk.level === "caution" && !draft.note.trim();
    }).length,
);
const canReviewCompliance = computed(
  () =>
    !readOnly.value &&
    currentStep.value === 9 &&
    approvalDone("market") &&
    !approvalDone("compliance"),
);
const approvalBlockers = computed(() => {
  const items: { text: string; channels?: string[]; fixable?: boolean }[] = [];
  if (approvalDone("final")) return items;
  if (!approvalDone("market")) {
    items.push({
      text: "市场确认未签字：请先完成 6.x 确认清单并点击「市场确认」",
    });
    return items;
  }
  const blocking = allRisks.value.filter((risk) =>
    ["block", "违规/阻断"].includes(risk.level),
  );
  if (blocking.length) {
    const channels = [
      ...new Set(
        blocking
          .map(
            (risk) =>
              contents.value.find((item) => item.content_id === risk.content_id)
                ?.channel || "",
          )
          .filter(Boolean),
      ),
    ];
    items.push({
      text: `存在 ${blocking.length} 条 ❌ 违规（红线）项，签字与终审被锁定，可「一键修复所有违规内容」或单独修复对应平台`,
      channels,
      fixable: true,
    });
  }
  if (!approvalDone("compliance")) {
    if (pendingReviewCount.value)
      items.push({
        text: `合规部还有 ${pendingReviewCount.value} 条谨慎/替换项未批注，可点击「一键批注全部」`,
      });
    if (!citationCovered.value)
      items.push({ text: "未勾选“已确认文献引证完整覆盖”" });
    return items;
  }
  if (auditChainGaps.value.length)
    items.push({
      text: `审计链缺环：${auditChainGaps.value.join(
        "、",
      )}，请先在对应步骤完成确认`,
    });
  return items;
});
const finalFormLocked = computed(
  () => readOnly.value || !approvalDone("compliance"),
);
const finalLockReason = computed(() => {
  if (readOnly.value) return "";
  if (!approvalDone("market"))
    return "待「市场确认」签字后，再完成合规签字方可终审";
  if (!approvalDone("compliance")) return "待合规部签字归档后开放终审填写";
  if (hasBlockingRisk.value)
    return "存在 ❌ 违规（红线）项，终审被锁定，请先返工对应平台";
  return "";
});
function finalChecklistItemLockReason(key: string) {
  if (key === "audit_chain" && auditChainGaps.value.length)
    return `审计链缺环：${auditChainGaps.value.join("、")}`;
  return "";
}
watch(auditChainGaps, (gaps) => {
  if (gaps.length && finalChecklist.value.includes("audit_chain"))
    finalChecklist.value = finalChecklist.value.filter(
      (key) => key !== "audit_chain",
    );
});
const finalMissing = computed(() => {
  const items: string[] = [];
  if (!finalTitleValid.value) items.push("职务须为品牌总监/业务负责人");
  if (!(Number(finalDuration.value) > 0)) items.push("填写确认时长");
  const unchecked = finalChecklistOptions.filter(
    (item) => !finalChecklist.value.includes(item.key),
  ).length;
  if (unchecked) items.push(`终审清单未勾选 ${unchecked} 项`);
  if (auditChainGaps.value.length)
    items.push(`审计链缺环：${auditChainGaps.value.join("、")}`);
  if (!finalAuthorized.value) items.push("开启「授权进入发布」");
  else if (finalStartDate.value && finalStartDate.value < todayStr)
    items.push("发布开始日期不能早于今天");
  return items;
});
function submitFinalApprove() {
  finalTouched.value = true;
  if (
    finalAuthorized.value &&
    finalStartDate.value &&
    finalStartDate.value < todayStr
  )
    return notify("发布开始日期不能早于今天", "warning");
  approve("final_approve");
}
const reworkOptions = computed(() =>
  visibleWorkflowSteps
    .filter((step) => step.step <= Math.max(1, currentStep.value))
    .map((step) => ({
      title: `${displayStepNo(step.step)}. ${step.title}`,
      value: step.step,
    })),
);
const complianceFilter = computed<ComplianceFilterState | null>(
  () => project.value?.compliance_filter || null,
);
const filterScanned = computed(() =>
  Boolean(
    complianceFilter.value?.scanned_at &&
      complianceFilter.value.status !== "not_scanned",
  ),
);
const canEditFilter = computed(
  () => !readOnly.value && currentStep.value === 6,
);
const filterInventoryDirty = computed(
  () =>
    filterInventoryFingerprint(filterInventoryDrafts.value) !==
    filterInventoryFingerprint(complianceFilter.value?.inventory || []),
);
const filterRiskGroups = computed(() => {
  const risks = complianceFilter.value?.risks || [];
  return [
    { level: "block", title: "🔴 一级 红线拦截" },
    { level: "caution", title: "🟡 二级 谨慎标记" },
    { level: "replace", title: "🟢 三级 建议替换" },
  ].map((group) => ({
    ...group,
    risks: risks.filter((risk) => risk.level === group.level),
  }));
});
const filterReviewableRisks = computed(() =>
  (complianceFilter.value?.risks || []).filter(
    (risk) =>
      risk.risk_id && (risk.level === "caution" || risk.level === "replace"),
  ),
);
const filterPendingReviewRisks = computed(() =>
  filterReviewableRisks.value.filter((risk) => {
    const draft = filterReviewDrafts.value[risk.risk_id as string];
    if (!draft?.decision) return true;
    return risk.level === "caution" && !draft.note.trim();
  }),
);
const filterPendingReviewCount = computed(
  () => filterPendingReviewRisks.value.length,
);
const filterDisposals = computed<FilterDisposal[]>(
  () => complianceFilter.value?.disposals || [],
);
const filterPendingDisposalCount = computed(
  () =>
    filterDisposals.value.filter((disposal) => {
      const draft = filterDisposalDrafts.value[disposal.disposal_id];
      if (!draft?.status) return true;
      return (
        draft.status === "scheduled" &&
        !/^\d{4}-\d{2}-\d{2}$/.test(draft.scheduled_date)
      );
    }).length,
);
const filterTicketRiskOptions = computed(() =>
  (complianceFilter.value?.risks || [])
    .filter((risk) => risk.risk_id)
    .map((risk) => ({
      title: `${riskLevelLabel(risk.level)} ${
        risk.platform ? `[${risk.platform}] ` : ""
      }${risk.message}`,
      value: risk.risk_id as string,
    })),
);
const filterTickets = computed<ComplianceExpertTicket[]>(() =>
  (project.value?.compliance_tickets || []).filter(
    (ticket) => ticket.scope === "compliance_filter",
  ),
);
const filterRecord = computed(() => complianceFilter.value?.record || null);

const fieldGroupMeta = [
  {
    key: "identity",
    title: "产品身份",
    subtitle: "药品名称与产品类型",
    icon: "mdi-card-account-details-outline",
    color: "primary",
    fieldCodes: ["drug_name", "product_type"],
  },
  {
    key: "ingredients_efficacy",
    title: "成分与主治功能",
    subtitle: "资料明确列示的成分与获批功能主治，不补写、不夸大",
    icon: "mdi-pill",
    color: "primary",
    fieldCodes: ["ingredients", "indications"],
  },
  {
    key: "spec_appearance",
    title: "规格与性状",
    subtitle: "包装规格与产品性状描述",
    icon: "mdi-package-variant",
    color: "primary",
    fieldCodes: ["specification", "appearance"],
  },
  {
    key: "audience",
    title: "对症人群",
    subtitle: "资料明确适用人群，不从禁忌推断",
    icon: "mdi-account-group-outline",
    color: "teal",
    fieldCodes: ["audience"],
  },
  {
    key: "endorsement",
    title: "批文",
    subtitle: "批准文号与批文类型",
    icon: "mdi-certificate-outline",
    color: "indigo",
    fieldCodes: ["approval_number", "approval_type"],
  },
  {
    key: "safety",
    title: "安全与使用约束",
    subtitle: "不作为营销关键词，必须独立核对",
    icon: "mdi-shield-alert-outline",
    color: "error",
    fieldCodes: ["dosage", "adverse_reactions"],
  },
];
const fieldGroups = computed(() => {
  const fields = project.value?.fields || [];
  const groups = fieldGroupMeta
    .map((meta) => ({
      ...meta,
      fields: meta.fieldCodes
        .map((code) => fields.find((field) => field.field_code === code))
        .filter((field): field is PharmaField => Boolean(field)),
    }))
    .filter((group) => group.fields.length);
  const knownCodes = new Set(fieldGroupMeta.flatMap((meta) => meta.fieldCodes));
  const extraFields = fields.filter(
    (field) => !knownCodes.has(field.field_code),
  );
  if (extraFields.length) {
    groups.push({
      key: "others",
      title: "其他字段",
      subtitle: "历史版本遗留字段",
      icon: "mdi-dots-horizontal-circle-outline",
      color: "grey",
      fieldCodes: [] as string[],
      fields: extraFields,
    });
  }
  return groups;
});
const filteredKeywords = computed(() => {
  const query = keywordSearch.value.trim().toLowerCase();
  if (!query) return project.value?.keywords || [];
  return (
    project.value?.keywords.filter(
      (item) =>
        item.keyword.toLowerCase().includes(query) ||
        item.source_label.toLowerCase().includes(query) ||
        item.source_text.toLowerCase().includes(query),
    ) || []
  );
});

watch(
  () => project.value?.project_id,
  () => {
    dimensionsError.value = "";
    literatureLevelDrafts.value = {};
    const signoff = project.value?.literature_signoff;
    literatureSigner.value = {
      name: signoff?.signer_name || "",
      title: signoff?.signer_title || "",
    };
    literatureChecklist.value = emptyLiteratureChecklist(
      Boolean(signoff?.checklist),
    );
  },
);
watch(selectedFile, (file) => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = file ? URL.createObjectURL(file) : "";
});
function previousReworkStep() {
  const steps = reworkOptions.value.map((option) => option.value);
  const earlier = steps.filter((step) => step < currentStep.value);
  return earlier.length ? earlier[earlier.length - 1] : steps[0] || 1;
}
watch(
  currentStep,
  (step) => {
    if (activeStep.value > step) activeStep.value = step;
    reworkTarget.value = previousReworkStep();
  },
  { immediate: true },
);
watch(workflowComment, (value, oldValue) => {
  if (value.trim() && !String(oldValue || "").trim()) {
    reworkTarget.value = previousReworkStep();
  }
});
watch(activeStep, (step) => {
  if ((step === 2 || step === 3) && !kbOptions.value.length) loadKbOptions();
  if (step === 5) loadCompetitorCaps();
  if (step === 6 || step === 9) {
    loadComplianceKb();
    if (!kbOptions.value.length) loadKbOptions();
  }
});
const LAST_PROJECT_KEY = "pharma-translator:last-project";
watch(
  () => project.value?.project_id || "",
  (id) => {
    if (id) localStorage.setItem(LAST_PROJECT_KEY, id);
  },
);
onMounted(async () => {
  window.addEventListener("scroll", updateBackToTop, {
    capture: true,
    passive: true,
  });
  await loadHistory();
  const lastId = localStorage.getItem(LAST_PROJECT_KEY);
  if (!lastId || project.value) return;
  if (history.value.some((item) => item.project_id === lastId)) {
    await openProject(lastId);
  } else {
    localStorage.removeItem(LAST_PROJECT_KEY);
  }
});
onBeforeUnmount(() => {
  window.removeEventListener("scroll", updateBackToTop, { capture: true });
  clearInterval(reworkTimer);
  clearInterval(reviewTimer);
  resetProjectContext();
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  Object.values(imageUrls.value).forEach((url) => URL.revokeObjectURL(url));
});

function normalizeProject(data: PharmaProject) {
  const normalized = {
    ...data,
    dimensions: data.dimensions || [],
    safety_constraints: data.safety_constraints || [],
    scenes: data.scenes || [],
    user_voices_pool: data.user_voices_pool || [],
    claims: data.claims || [],
    literature: data.literature || {
      documents: [],
      kb_ids: [],
      kb_names: [],
      matched_at: null,
    },
    literature_claims: data.literature_claims || [],
    unusable_claims: data.unusable_claims || [],
    contents: data.contents || [],
    compliance_tickets: data.compliance_tickets || [],
    approvals: data.approvals || {},
    version_history: data.version_history || [],
    user_notes: data.user_notes || [],
    workflow: data.workflow || {
      current_step: 1,
      status: data.status || "active",
      version: 1,
      step_status: {},
    },
  } as PharmaProject;
  selectedKbIds.value = [...(normalized.literature?.kb_ids || [])];
  dimensionKbIds.value = [
    ...(normalized.dimension_generation?.kb_ids ||
      normalized.literature?.kb_ids ||
      []),
  ];
  const aiKbIds = normalized.compliance?.ai_review?.kb_ids;
  complianceKbIds.value = [
    ...(aiKbIds?.length ? aiKbIds : selectedKbIds.value),
  ];
  const savedReviews = normalized.compliance?.reviews || {};
  const nextDrafts: Record<string, ReviewDraft> = {};
  for (const risk of normalized.compliance?.risks || []) {
    if (!risk.risk_id) continue;
    const saved = savedReviews[risk.risk_id];
    const previous =
      project.value?.project_id === normalized.project_id
        ? reviewDrafts.value[risk.risk_id]
        : undefined;
    nextDrafts[risk.risk_id] = saved
      ? { decision: saved.decision, note: saved.note || "" }
      : previous || { decision: null, note: "" };
  }
  reviewDrafts.value = nextDrafts;
  const defaultConfirm = <
    T extends { text?: string; value?: unknown; confirmed?: boolean },
  >(
    items: T[] = [],
  ): T[] =>
    items.map((item) =>
      (item.text || item.value) && item.confirmed === undefined
        ? { ...item, confirmed: true }
        : item,
    );
  normalized.dimensions = (normalized.dimensions || []).map((dimension) => ({
    ...dimension,
    items: defaultConfirm(dimension.items || []),
  }));
  normalized.safety_constraints = defaultConfirm(normalized.safety_constraints);
  userNotes.value = (normalized.user_notes || []).map((note) => ({
    note_id: String(note.note_id || nextNoteId()),
    title: String(note.title || ""),
    text: String(note.text || ""),
  }));
  syncComplianceFilterDrafts(normalized);
  return normalized;
}
function syncComplianceFilterDrafts(normalized: PharmaProject) {
  const sameProject = project.value?.project_id === normalized.project_id;
  const filter = normalized.compliance_filter || null;
  const serverInventory = filter?.inventory || [];
  const keepLocalInventory =
    sameProject &&
    !forceFilterInventorySync &&
    filterInventoryDirty.value &&
    filterInventoryFingerprint(filterInventoryDrafts.value) !==
      filterInventoryFingerprint(serverInventory);
  forceFilterInventorySync = false;
  if (!keepLocalInventory)
    filterInventoryDrafts.value = serverInventory.map((item) => ({
      ...emptyFilterInventory(),
      ...item,
      draft_key: item.inventory_id || nextFilterDraftKey(),
    }));
  const savedReviews = filter?.reviews || {};
  const nextReviews: Record<string, ReviewDraft> = {};
  for (const risk of filter?.risks || []) {
    if (!risk.risk_id) continue;
    const saved = savedReviews[risk.risk_id];
    const previous = sameProject
      ? filterReviewDrafts.value[risk.risk_id]
      : undefined;
    nextReviews[risk.risk_id] = saved
      ? { decision: saved.decision, note: saved.note || "" }
      : previous || { decision: null, note: "" };
  }
  filterReviewDrafts.value = nextReviews;
  const nextDisposals: Record<string, FilterDisposalDraft> = {};
  for (const disposal of filter?.disposals || []) {
    const previous = sameProject
      ? filterDisposalDrafts.value[disposal.disposal_id]
      : undefined;
    nextDisposals[disposal.disposal_id] =
      disposal.status === "done" || disposal.status === "scheduled"
        ? {
            status: disposal.status,
            scheduled_date: disposal.scheduled_date || "",
            note: disposal.note || "",
          }
        : previous || { status: null, scheduled_date: "", note: "" };
  }
  filterDisposalDrafts.value = nextDisposals;
  const filterAiKbIds = filter?.ai_review?.kb_ids;
  if (!sameProject || filterAiKbIds?.length)
    filterKbIds.value = [
      ...(filterAiKbIds?.length ? filterAiKbIds : selectedKbIds.value),
    ];
  const record = filter?.record;
  if (record) {
    filterSignerName.value = record.signer_name || "";
    filterSignerTitle.value = record.signer_title || "合规部";
    filterApplyDate.value = record.ad_review_schedule?.apply_date || "";
    filterAuthority.value =
      record.ad_review_schedule?.authority || "省级药品监督管理部门";
    filterAdNote.value = record.ad_review_schedule?.note || "";
    filterComment.value = record.comment || "";
  } else if (!sameProject) {
    filterSignerName.value = "";
    filterSignerTitle.value = "合规部";
    filterApplyDate.value = "";
    filterAuthority.value = "省级药品监督管理部门";
    filterAdNote.value = "";
    filterComment.value = "";
    filterConfirmChecks.value = [];
    aiAskQuestion.value = "";
    aiAskResult.value = null;
    filterTicketQuestion.value = "";
    filterTicketRiskIds.value = [];
  }
}
function notify(message: string, color = "success") {
  snackbar.value = { show: true, message, color };
}
function extractError(error: unknown) {
  if (typeof error === "string" && error.trim()) return error;
  type ValidationIssue = { loc?: Array<string | number>; msg?: string };
  type ErrorPayload = { message?: string; detail?: string | ValidationIssue[] };
  const axiosError = error as AxiosError<ErrorPayload>;
  const payload = axiosError.response?.data;
  if (payload?.message) return payload.message;
  const detail = payload?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length)
    return detail
      .map(
        (issue) =>
          `${
            issue.loc?.filter((part) => part !== "body").join(".") || "请求参数"
          }：${issue.msg || "格式不正确"}`,
      )
      .join("；");
  if (axiosError.response?.status)
    return `请求失败（HTTP ${axiosError.response.status}）`;
  if (axiosError.code === "ERR_NETWORK")
    return "与后端的连接中断（网络波动或服务重启），已自动重试仍失败；耗时操作后台可能仍在处理，请稍后刷新查看结果";
  if (axiosError.code === "ECONNABORTED")
    return "请求超时，后台可能仍在处理，请稍后刷新查看结果";
  return axiosError.message || "操作失败，请稍后重试";
}
function setFile(file?: File) {
  if (!file) return;
  const extension = file.name.split(".").pop()?.toLowerCase() || "";
  if (!["jpg", "jpeg", "png", "webp", "pdf"].includes(extension))
    return notify("仅支持 JPG、JPEG、PNG、WEBP 和 PDF", "error");
  const maxBytes = extension === "pdf" ? 100 * 1024 * 1024 : 20 * 1024 * 1024;
  if (file.size > maxBytes)
    return notify(
      extension === "pdf" ? "PDF 不得超过 100 MB" : "图片不得超过 20 MB",
      "error",
    );
  if (!file.size) return notify("上传文件为空", "error");
  selectedFile.value = file;
}
function handleDrop(event: DragEvent) {
  dragging.value = false;
  setFile(event.dataTransfer?.files?.[0]);
}
function handleFileInput(event: Event) {
  setFile((event.target as HTMLInputElement).files?.[0]);
}
function canVisitStep(step: number) {
  return Boolean(project.value) && step <= currentStep.value;
}
function selectStep(step: number) {
  if (canVisitStep(step)) activeStep.value = step;
}
const NON_RETRYABLE_STEPS = new Set([7, 8]);
const viewingDoneStep = computed(
  () => Boolean(project.value) && activeStep.value < currentStep.value,
);
const stepViewOnly = computed(() => viewingDoneStep.value);
const VIEW_ALLOWED_SELECTOR =
  ".v-expansion-panel-title, .v-tab, .v-btn-toggle, a[href], [data-view-allowed]";
const VIEW_BLOCKED_SELECTOR =
  'button, .v-btn, input, textarea, select, .v-selection-control, .v-field, .v-chip--link, [role="button"], [role="checkbox"], [role="switch"], [role="combobox"], [contenteditable="true"]';
function guardViewOnly(event: Event) {
  if (!viewingDoneStep.value) return;
  const target = event.target as HTMLElement | null;
  if (!target || target.closest(VIEW_ALLOWED_SELECTOR)) return;
  if (!target.closest(VIEW_BLOCKED_SELECTOR)) return;
  event.preventDefault();
  event.stopPropagation();
  if (event.type === "click") {
    notify("该步骤已完成，仅供查看；如需重新执行请点击「重试此步骤」", "info");
  }
}
const retryDialog = ref(false);
const retryComment = ref("");
function openRetryDialog() {
  if (NON_RETRYABLE_STEPS.has(activeStep.value)) {
    notify("该步骤不支持单独重试", "warning");
    return;
  }
  retryComment.value = "";
  retryDialog.value = true;
}
async function confirmRetryStep() {
  const comment = retryComment.value.trim();
  if (!comment) {
    notify("请填写重试原因", "warning");
    return;
  }
  const step = activeStep.value;
  retryDialog.value = false;
  await runAction(
    "rework",
    { target_step: step },
    `已返工到第 ${displayStepNo(step)} 步，可重新执行`,
    comment,
  );
}
function isStepDone(step: number) {
  const configured = project.value?.workflow?.step_status?.[String(step)];
  return configured
    ? ["passed", "completed", "approved", "confirmed"].includes(
        configured.toLowerCase(),
      )
    : Boolean(project.value && currentStep.value > step);
}

async function analyze() {
  if (!selectedFile.value || analyzing.value || openingProjectId.value) return;
  const context = resetProjectContext();
  analyzing.value = true;
  try {
    const response = await pharmaTranslatorApi.analyze({
      productName: productName.value.trim(),
      productType: productType.value,
      file: selectedFile.value,
    });
    if (context !== projectContext) return;
    project.value = normalizeProject(response.data.data);
    productName.value = project.value.product_name;
    productType.value = project.value.product_type;
    activeStep.value = currentStep.value;
    workflowComment.value = "";
    notify(`识别完成：${filledFieldCount.value} 个字段，等待人工确认`);
    await loadHistory();
  } catch (error) {
    notify(extractError(error), "error");
  } finally {
    analyzing.value = false;
  }
}
async function loadHistory() {
  loadingHistory.value = true;
  try {
    history.value = (await pharmaTranslatorApi.list()).data.data;
  } catch (error) {
    notify(extractError(error), "error");
  } finally {
    loadingHistory.value = false;
  }
}
function startNewProject() {
  resetProjectContext();
  openingProjectId.value = "";
  project.value = null;
  localStorage.removeItem(LAST_PROJECT_KEY);
  selectedFile.value = null;
  productName.value = "";
  productType.value = "自动识别";
  activeStep.value = 1;
  workflowComment.value = "";
  if (fileInput.value) fileInput.value.value = "";
  window.scrollTo({ top: 0, behavior: "smooth" });
  notify("请填写药品信息并上传说明书以建立新项目", "info");
}
function confirmDeleteProject(item: PharmaProjectSummary) {
  projectToDelete.value = item;
  deleteDialog.value = true;
}
async function deleteProject() {
  const item = projectToDelete.value;
  if (!item || deletingProjectId.value) return;
  deletingProjectId.value = item.project_id;
  try {
    await pharmaTranslatorApi.delete(item.project_id);
    if (project.value?.project_id === item.project_id) startNewProject();
    deleteDialog.value = false;
    projectToDelete.value = null;
    await loadHistory();
    notify("项目已删除");
  } catch (error) {
    notify(extractError(error), "error");
  } finally {
    deletingProjectId.value = "";
  }
}
async function openProject(projectId: string) {
  if (openingProjectId.value || deletingProjectId.value || analyzing.value)
    return;
  const context = resetProjectContext();
  openingProjectId.value = projectId;
  try {
    const [response, sourceResponse] = await Promise.all([
      pharmaTranslatorApi.get(projectId),
      pharmaTranslatorApi.source(projectId),
    ]);
    if (context !== projectContext) return;
    project.value = normalizeProject(response.data.data);
    selectedFile.value = new File(
      [sourceResponse.data as Blob],
      project.value.filename,
      { type: (sourceResponse.data as Blob).type },
    );
    productName.value = project.value.product_name;
    productType.value = project.value.product_type;
    activeStep.value = currentStep.value;
    window.scrollTo({ top: 640, behavior: "smooth" });
    notify("项目已打开，可以继续修改未冻结的内容");
    openingProjectId.value = "";
    await autoGenerateDimensions();
  } catch (error) {
    if (context === projectContext) notify(extractError(error), "error");
  } finally {
    if (context === projectContext) openingProjectId.value = "";
  }
}
// 页面状态与服务端步骤不一致（多标签页/他人操作/返工）时，拉取最新项目并跳到实际步骤。
async function syncProjectProgress(projectId: string, context: number) {
  try {
    const response = await pharmaTranslatorApi.get(projectId);
    if (context !== projectContext || project.value?.project_id !== projectId)
      return;
    project.value = normalizeProject(response.data.data);
    activeStep.value = currentStep.value;
  } catch {
    // 同步失败时保留原错误提示
  }
}
async function runAction(
  action: PharmaWorkflowAction,
  data: Record<string, unknown>,
  successMessage: string,
  comment = "",
) {
  if (
    !project.value ||
    actionLoading.value ||
    dimensionsLoading.value ||
    openingProjectId.value ||
    analyzing.value
  )
    return;
  const projectId = project.value.project_id;
  if (dimensionRequests.has(projectId) || actionRequests.has(projectId)) return;
  actionRequests.add(projectId);
  const context = projectContext;
  actionLoading.value = true;
  let confirmedProfile = false;
  try {
    const response = await pharmaTranslatorApi.workflowAction(
      projectId,
      action,
      data,
      comment,
    );
    if (context !== projectContext || project.value?.project_id !== projectId)
      return;
    project.value = normalizeProject(response.data.data);
    activeStep.value = currentStep.value;
    confirmedProfile = action === "confirm_profile" && currentStep.value === 2;
    notify(successMessage);
    if (!confirmedProfile) await loadHistory();
  } catch (error) {
    if (context === projectContext) {
      const message = extractError(error);
      notify(message, "error");
      if (message.includes("只能在第"))
        await syncProjectProgress(projectId, context);
    }
  } finally {
    actionRequests.delete(projectId);
    if (context === projectContext) actionLoading.value = false;
  }
  if (confirmedProfile && context === projectContext) {
    await autoGenerateDimensions(true);
    await loadHistory();
  }
}
const SKIPPABLE_FIELD_CODES = new Set(["approval_number", "approval_type"]);
function isSkippableField(field: PharmaField) {
  return field.critical && SKIPPABLE_FIELD_CODES.has(field.field_code);
}
function isManualSource(field: PharmaField) {
  return (
    field.source_type === "manual_input" ||
    field.source_type === "manual" ||
    field.source_type === "manual_review"
  );
}
function fieldPlaceholder(field: PharmaField) {
  if (isSkippableField(field)) return "未从原文识别到，可留空跳过或手动补充";
  return "未从原文识别到，保持为空";
}
function onFieldValueChange(field: PharmaField) {
  const value = field.value.trim();
  const machineValue = (field.machine_value || "").trim();
  if (!value) {
    if (!field.source_text) field.confirmed = false;
    return;
  }
  if (!field.source_text && value !== machineValue) {
    field.source_type = "manual_input";
    field.modified_by_human = true;
  }
}
function confirmProfile() {
  if (!project.value) return;
  const skippableCodes = new Set(["approval_number", "approval_type"]);
  const missing = project.value.fields.filter((field) => {
    if (!field.critical) return false;
    const value = field.value.trim();
    if (!value) return !skippableCodes.has(field.field_code);
    const hasSource = !!field.source_text.trim();
    const isManual =
      field.source_type === "manual_input" ||
      field.source_type === "manual" ||
      field.source_type === "manual_review";
    if (!hasSource && !isManual) return true;
    return !field.confirmed;
  });
  if (missing.length)
    return notify(
      `请先确认关键字段：${missing.map((field) => field.label).join("、")}`,
      "warning",
    );
  return runAction(
    "confirm_profile",
    {
      fields: project.value.fields,
      user_notes: userNotes.value.filter((note) => note.text.trim()),
    },
    "产品档案已冻结，已进入多维拆解",
  );
}
async function autoGenerateDimensions(afterProfile = false) {
  if (
    !project.value ||
    readOnly.value ||
    currentStep.value !== 2 ||
    actionLoading.value ||
    dimensionsLoading.value
  )
    return;
  const missing = ["ingredients", "audience"].some(
    (code) =>
      !dimensions.value
        .find((dimension) => dimensionKey(dimension) === code)
        ?.items.some((item) => (item.text || item.value || "").trim()),
  );
  if (!afterProfile && !missing) return;
  const key = `${project.value.project_id}:${
    project.value.workflow?.version || 1
  }`;
  if (
    dimensionAutoAttempts.has(key) ||
    dimensionRequests.has(project.value.project_id) ||
    actionRequests.has(project.value.project_id)
  )
    return;
  dimensionAutoAttempts.add(key);
  await generateDimensions();
}
async function generateDimensions() {
  if (
    !project.value ||
    dimensionsLoading.value ||
    actionLoading.value ||
    openingProjectId.value ||
    analyzing.value ||
    readOnly.value ||
    currentStep.value !== 2
  )
    return;
  const projectId = project.value.project_id;
  if (dimensionRequests.has(projectId) || actionRequests.has(projectId)) return;
  dimensionRequests.add(projectId);
  const context = projectContext;
  const version = project.value.workflow?.version || 1;
  dimensionAutoAttempts.add(`${projectId}:${version}`);
  dimensionsLoading.value = true;
  dimensionsError.value = "";
  try {
    const response = await pharmaTranslatorApi.generateDimensions(projectId, {
      kbIds: dimensionKbIds.value,
      searchMode: dimensionSearchMode.value,
    });
    if (
      context !== projectContext ||
      project.value?.project_id !== projectId ||
      (project.value.workflow?.version || 1) !== version
    )
      return;
    const updated = normalizeProject(response.data.data);
    dimensionAutoAttempts.add(`${projectId}:${updated.workflow?.version || 1}`);
    project.value.dimensions = updated.dimensions;
    project.value.dimension_generation = updated.dimension_generation;
    project.value.workflow = updated.workflow;
    project.value.version_history = updated.version_history;
    project.value.audit_events = updated.audit_events;
    project.value.updated_at = updated.updated_at;
    notify("模型候选已生成，请逐条对照来源人工确认");
    await loadHistory();
  } catch (error) {
    if (context !== projectContext || project.value?.project_id !== projectId)
      return;
    if ((error as AxiosError).response?.status === 409) {
      // 生成期间项目已被其他请求更新（如另一窗口的生成），同步最新数据而不是报错
      try {
        const latest = normalizeProject(
          (await pharmaTranslatorApi.get(projectId)).data.data,
        );
        if (
          context !== projectContext ||
          project.value?.project_id !== projectId
        )
          return;
        project.value = latest;
        activeStep.value = currentStep.value;
        dimensionAutoAttempts.add(
          `${projectId}:${latest.workflow?.version || 1}`,
        );
        notify("项目已在生成期间更新，已同步最新维度，可按需重新生成");
        await loadHistory();
        return;
      } catch (refreshError) {
        dimensionsError.value = extractError(refreshError);
        return;
      }
    }
    dimensionsError.value = extractError(error);
  } finally {
    dimensionRequests.delete(projectId);
    if (context === projectContext) dimensionsLoading.value = false;
  }
}
async function confirmDimensions() {
  const cleanedDimensions = dimensions.value.map((dimension) => ({
    ...dimension,
    items: (dimension.items || [])
      .filter((item) => (item.source_text || "").trim())
      .map((item) => ({ ...item, confirmed: true })),
  }));
  const cleanedConstraints = safetyConstraints.value
    .filter((item) => (item.source_text || "").trim())
    .map((item) => ({ ...item, confirmed: true }));
  await runAction(
    "confirm_dimensions",
    {
      dimensions: cleanedDimensions,
      safety_constraints: cleanedConstraints,
    },
    "多维拆解已确认，已进入文献来源",
  );
  if (activeStep.value === 3) {
    nextTick(() => scrollToAnchor("literature-step"));
  }
}
async function loadKbOptions() {
  if (kbLoading.value) return;
  kbLoading.value = true;
  try {
    const response = await knowledgeApi.list({ page: 1, page_size: 100 });
    const items =
      (
        response as {
          data?: {
            data?: { items?: Array<{ kb_id?: string; kb_name?: string }> };
          };
        }
      ).data?.data?.items || [];
    kbOptions.value = items
      .filter((item) => item.kb_id)
      .map((item) => ({
        title: String(item.kb_name || item.kb_id),
        value: String(item.kb_id),
      }));
  } catch {
    kbOptions.value = [];
  } finally {
    kbLoading.value = false;
  }
}
async function uploadLiterature() {
  if (
    !project.value ||
    literatureUploading.value ||
    !literatureFiles.value.length
  )
    return;
  literatureUploading.value = true;
  try {
    const response = await pharmaTranslatorApi.uploadLiterature(
      project.value.project_id,
      { docKind: literatureDocKind.value, files: literatureFiles.value },
    );
    project.value = normalizeProject(response.data.data);
    literatureFiles.value = [];
    notify("文献已上传并切片，请重新执行文献匹配");
  } catch (error) {
    notify(extractError(error), "error");
  } finally {
    literatureUploading.value = false;
  }
}
async function removeLiterature(docId: string) {
  if (!project.value || literatureUploading.value) return;
  literatureUploading.value = true;
  try {
    const response = await pharmaTranslatorApi.deleteLiterature(
      project.value.project_id,
      docId,
    );
    project.value = normalizeProject(response.data.data);
    notify("文献已移除，请重新执行文献匹配");
  } catch (error) {
    notify(extractError(error), "error");
  } finally {
    literatureUploading.value = false;
  }
}
async function pollLiteratureMatch(
  projectId: string,
  previousMatchedAt: string | null,
) {
  const deadline = Date.now() + 240000;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 5000));
    try {
      const response = await pharmaTranslatorApi.get(projectId);
      const latest = normalizeProject(response.data.data);
      const matchedAt = latest.literature?.matched_at || null;
      if (matchedAt && matchedAt !== previousMatchedAt) return latest;
    } catch {
      // 后端重启或网络抖动时继续轮询，直到超时
    }
  }
  return null;
}
async function runLiteratureMatch() {
  if (!project.value || literatureMatching.value) return;
  literatureMatching.value = true;
  const projectId = project.value.project_id;
  const previousMatchedAt = project.value.literature?.matched_at || null;
  try {
    const response = await pharmaTranslatorApi.matchLiterature(projectId, {
      kbIds: selectedKbIds.value,
      tier: literatureTier.value,
    });
    project.value = normalizeProject(response.data.data);
    literatureLevelDrafts.value = {};
    notify("文献匹配完成，请逐条核对三色标签与三联卡");
  } catch (error) {
    // 匹配含知识库检索 + 生成模型分析，耗时可能超过 2 分钟；长连接被代理/网络重置
    // 或前端超时时后端通常仍在继续执行，改为轮询项目状态取回结果。
    const axiosError = error as AxiosError;
    if (axiosError.response) {
      notify(extractError(error), "error");
    } else {
      const recovered = await pollLiteratureMatch(projectId, previousMatchedAt);
      if (recovered) {
        if (project.value?.project_id === projectId) project.value = recovered;
        literatureLevelDrafts.value = {};
        notify("文献匹配完成，请逐条核对三色标签与三联卡");
      } else {
        notify("文献匹配连接中断且未取回结果，请稍后刷新项目或重试", "error");
      }
    }
  } finally {
    literatureMatching.value = false;
  }
}
async function confirmLiterature() {
  if (!canConfirmLiterature.value) {
    if (levelAdjustMissingReason.value)
      return notify("调整证据等级必须填写理由", "warning");
    if (
      !literatureSigner.value.name.trim() ||
      !literatureSigner.value.title.trim()
    )
      return notify("请填写确认签字人姓名与职务", "warning");
    if (!literatureSignerQualified.value)
      return notify("确认人必须为企业医学部/学术部人员，不可代签", "warning");
    if (!literatureChecklistDone.value)
      return notify("请逐项完成医学部确认清单", "warning");
    return notify("请先执行文献匹配，并至少确认一条有证据的卖点", "warning");
  }
  const claims = literatureClaims.value.map((claim) => {
    const draft = literatureLevelDrafts.value[claim.claim_id];
    return {
      ...claim,
      evidence_level: effectiveLevel(claim),
      adjust_reason: draft?.reason?.trim() || claim.adjust_reason || "",
    };
  });
  await runAction(
    "confirm_literature",
    {
      claims,
      signoff: {
        signer_name: literatureSigner.value.name.trim(),
        signer_title: literatureSigner.value.title.trim(),
        checklist: { ...literatureChecklist.value },
      },
    },
    "文献来源已签字确认，场景候选已生成",
  );
  if (literatureSignoff.value) literatureLevelDrafts.value = {};
  if (activeStep.value === 4) {
    nextTick(() => scrollToAnchor("scene-step"));
  }
}
async function exportLiteratureTripleTable() {
  if (!project.value) return;
  await download(
    pharmaTranslatorApi.exportLiteratureTripleTable(project.value.project_id),
    `${project.value.product_name}_卖点文献话术三联表.csv`,
    "三联表已导出",
  );
}
async function loadLiteratureRedlines() {
  literatureRedlineDialog.value = true;
  literatureRedlineLoading.value = true;
  try {
    const response = await pharmaTranslatorApi.literatureRedlines(
      project.value?.project_id,
    );
    literatureRedlines.value = response.data.data?.items || [];
  } catch (error) {
    notify(extractError(error), "error");
  } finally {
    literatureRedlineLoading.value = false;
  }
}
const anchorSlug = (s?: string) =>
  encodeURIComponent(s || "default").replace(/%/g, "");
const batchGroupAnchor = (ch?: string) => `batch-group-${anchorSlug(ch)}`;
const contentAnchor = (id: string) => `content-card-${id}`;
function scrollToAnchor(id: string) {
  document
    .getElementById(id)
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
}
// 等待数据渲染完成后再滚动到锚点
async function scrollAfterRender(id: string) {
  await nextTick();
  requestAnimationFrame(() =>
    document
      .getElementById(id)
      ?.scrollIntoView({ behavior: "smooth", block: "center" }),
  );
}
const showBackToTop = ref(false);
function updateBackToTop() {
  const el = document.getElementById("result-section-top");
  showBackToTop.value = !!el && el.getBoundingClientRect().top < -200;
}
function backToBatch(content: PharmaContent) {
  const el =
    document.getElementById(
      batchGroupAnchor(content.channel || content.platform),
    ) || document.getElementById("batch-report-top");
  el?.scrollIntoView({ behavior: "smooth", block: "start" });
}
function jumpToContent(channel: string) {
  const c = contents.value.find((x) => (x.channel || x.platform) === channel);
  if (c) scrollToAnchor(contentAnchor(c.content_id));
  else notify("该平台暂无内容卡片", "warning");
}
async function copyContent(content: PharmaContent) {
  const text = content.body_with_footnotes || content.body || "";
  const ok = await copyToClipboard(text).catch(() => false);
  if (ok) notify(content.footnotes?.length ? "已复制（含文献脚注）" : "已复制");
  else notify("复制失败，请手动选择文本复制", "error");
}
function citationIcon(channel?: string) {
  return (
    (
      {
        leaflet: "mdi-file-document-outline",
        uploaded: "mdi-file-upload-outline",
        knowledge_base: "mdi-database-outline",
        pubmed: "mdi-earth",
      } as Record<string, string>
    )[channel || ""] || "mdi-book-open-page-variant-outline"
  );
}
function toggleSceneDeleted(scene: PharmaScene) {
  scene.deleted = !scene.deleted;
  if (scene.deleted) scene.selected = false;
}
async function confirmScenes() {
  if (selectedSceneCount.value < 1 || selectedSceneCount.value > 5)
    return notify("请选择 1—5 个重点场景", "warning");
  await runAction(
    "confirm_scenes",
    { scenes: scenes.value },
    "场景已锁定，已进入竞品内容扫描",
  );
  if (activeStep.value === 5) {
    nextTick(() => scrollToAnchor("competitor-step"));
  }
}
const competitor = computed(() => project.value?.competitor || null);
const competitorAnalysis = computed(() => competitor.value?.analysis || null);
const sampleAssessment = computed(
  () => competitorAnalysis.value?.sample_assessment || null,
);
const samplePlatformSummary = computed(() =>
  Object.entries(sampleAssessment.value?.platform_counts || {})
    .map(([platform, count]) => `${competitorPlatformLabel(platform)} ${count}`)
    .join(" / "),
);
function applySampleSuggestions(scanNow: boolean) {
  const assessment = sampleAssessment.value;
  if (!assessment) return;
  // 合并建议关键词，保留用户已填写的
  const keywords = [
    ...splitLines(competitorKeywords.value),
    ...(assessment.suggested_keywords || []),
  ];
  competitorKeywords.value = [...new Set(keywords)].join("\n");
  // 旧分析无结构化建议时，至少补上电商平台以获取价格数据
  const platforms = assessment.suggested_platforms?.length
    ? assessment.suggested_platforms
    : (["ecommerce"] as CompetitorPlatform[]);
  competitorPlatforms.value = [
    ...new Set([...competitorPlatforms.value, ...platforms]),
  ];
  competitorPerKeyword.value = Math.min(
    50,
    Math.max(Number(competitorPerKeyword.value) || 20, 30),
  );
  if (competitorMode.value === "light") {
    competitorMode.value = competitorCaps.value?.tikhub_configured
      ? "deep"
      : "standard";
  }
  if (scanNow) void scanCompetitors();
  else notify("已填入补采参数，可调整后点击「补采」", "success");
}
const competitorItemMap = computed(
  () =>
    new Map(
      (competitor.value?.items || []).map((item) => [item.item_id, item]),
    ),
);
const competitorGaps = computed<CompetitorGap[]>(
  () => competitorAnalysis.value?.gap_map || [],
);
const selectedGapCount = computed(
  () => competitorGaps.value.filter((gap) => gap.selected).length,
);
const selectedP0Count = computed(
  () =>
    competitorGaps.value.filter((gap) => gap.selected && gap.priority === "P0")
      .length,
);
function toggleGap(gap: CompetitorGap, selected: boolean) {
  gap.selected = selected;
  if (selected && !gap.priority) gap.priority = gap.suggested_priority || "P1";
}
function selectGaps(mode: "all" | "P0" | "invert" | "none") {
  for (const gap of competitorGaps.value) {
    const next =
      mode === "all"
        ? true
        : mode === "P0"
        ? gap.suggested_priority === "P0"
        : mode === "invert"
        ? !gap.selected
        : false;
    toggleGap(gap, next);
  }
}
function selectGapsAndScroll(mode: "all") {
  selectGaps(mode);
  nextTick(() => scrollToAnchor("competitor-user-platform-group"));
}
function setSelectedGapPriority(priority: "P0" | "P1") {
  for (const gap of competitorGaps.value)
    if (gap.selected) gap.priority = priority;
}
// 分析结果或项目切换时，用已保存的确认数据/模型建议预填确认区
watch(
  () => [
    project.value?.project_id,
    competitor.value?.analyzed_at,
    competitor.value?.confirmed_at,
  ],
  () => {
    const state = competitor.value;
    competitorOurPrice.value = state?.our_price || "";
    competitorRadarBrands.value = [
      ...new Set([
        ...(state?.radar_brands || []),
        ...(state?.analysis?.radar_brands || []),
      ]),
    ];
    const saved = new Map(
      (state?.signal_responses || []).map((row) => [
        row.signal_id,
        row.response,
      ]),
    );
    competitorSignalResponses.value = Object.fromEntries(
      (state?.analysis?.competitor_signals || []).map((sig) => [
        sig.signal_id,
        saved.get(sig.signal_id) ?? sig.suggested_response ?? "",
      ]),
    );
  },
  { immediate: true },
);
function competitorItemTitle(id: string) {
  const item = competitorItemMap.value.get(id);
  return item?.title || item?.text?.slice(0, 30) || id;
}
function heatEngagementText(ids: string[], commercialIds: string[] = []) {
  const values = ids
    .map((id) => {
      const item = competitorItemMap.value.get(id);
      return item?.likes ?? item?.heat;
    })
    .filter((value) => value != null);
  if (!values.length) return "-";
  return `${values.join("/")}赞${commercialIds.length ? "（商单）" : ""}`;
}
const competitorCollectionSummary = computed(() =>
  (competitor.value?.scans || [])
    .map((scan) => {
      const counts = (scan.keyword_counts || [])
        .map(
          (row) =>
            `${competitorPlatformLabel(row.platform)}「${row.keyword}」${
              row.count
            }条`,
        )
        .join(" + ");
      return `${scan.mode_label}${
        counts ? ` ${counts}` : `（${scan.added} 条）`
      }`;
    })
    .join("；"),
);
function heatSignalLabel(signal: string) {
  return (
    (
      {
        hot: "🔥 热",
        new: "🆕 新切口",
        warning: "⚠️ 预警",
        stable: "稳定",
      } as Record<string, string>
    )[signal] || signal
  );
}
function anchorStanceLabel(stance: string) {
  return (
    (
      {
        follow: "跟",
        avoid: "不跟",
        lead: "主打",
        leverage: "借势",
        reverse: "反向操作",
      } as Record<string, string>
    )[stance] || stance
  );
}
const canConfirmCompetitor = computed(
  () =>
    selectedGapCount.value > 0 &&
    !competitor.value?.analysis_stale &&
    competitorGaps.value.every(
      (gap) => !gap.selected || gap.priority === "P0" || gap.priority === "P1",
    ),
);
const competitorPlatformOptions = [
  { value: "douyin", title: "抖音" },
  { value: "xiaohongshu", title: "小红书" },
  { value: "zhihu", title: "知乎" },
  { value: "ecommerce", title: "电商" },
];
// 知乎 API 链接（api.zhihu.com）需要登录，转换为可直接打开的网页链接
const ZHIHU_WEB_PATHS: Record<string, string> = {
  answers: "https://www.zhihu.com/answer/",
  articles: "https://zhuanlan.zhihu.com/p/",
  questions: "https://www.zhihu.com/question/",
  zvideos: "https://www.zhihu.com/zvideo/",
  pins: "https://www.zhihu.com/pin/",
};
function webUrl(url?: string) {
  const match = url?.match(
    /^https?:\/\/api\.zhihu\.com\/(answers|articles|questions|zvideos|pins)\/(\d+)/,
  );
  return match ? ZHIHU_WEB_PATHS[match[1]] + match[2] : url;
}
function competitorPlatformLabel(platform?: string) {
  return (
    competitorPlatformOptions.find((item) => item.value === platform)?.title ||
    platform ||
    "未知平台"
  );
}
function splitLines(value: string) {
  return value
    .split(/[\r\n,，、]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}
async function loadCompetitorCaps() {
  if (competitorCaps.value) return;
  try {
    const response = await pharmaTranslatorApi.competitorCapabilities();
    competitorCaps.value = response.data.data;
    if (competitorCaps.value.tikhub_configured) competitorMode.value = "deep";
    else if (competitorCaps.value.opencli_available)
      competitorMode.value = "standard";
  } catch {
    competitorCaps.value = null;
  }
}
async function scanCompetitors() {
  if (!project.value || competitorScanning.value || competitorAnalyzing.value)
    return;
  // 「开始实时采集 / 补采」统一走 TikHub 深度档
  await loadCompetitorCaps();
  if (competitorCaps.value && !competitorCaps.value.tikhub_configured)
    return notify("TikHub 未配置（缺少 API Key），无法实时采集", "error");
  competitorMode.value = "deep";
  if (!competitorPlatforms.value.length)
    competitorPlatforms.value = ["douyin", "xiaohongshu"];
  const urls = splitLines(competitorUrls.value);
  const projectId = project.value.project_id;
  const context = projectContext;
  competitorScanning.value = true;
  try {
    const response = await pharmaTranslatorApi.scanCompetitors(projectId, {
      mode: "deep",
      platforms: competitorPlatforms.value,
      keywords: splitLines(competitorKeywords.value),
      brands: splitLines(competitorBrands.value),
      urls,
      per_keyword: Math.min(
        50,
        Math.max(1, Number(competitorPerKeyword.value) || 20),
      ),
    });
    if (context !== projectContext || project.value?.project_id !== projectId)
      return;
    project.value = normalizeProject(response.data.data);
    const latest = project.value.competitor?.scans?.slice(-1)[0];
    notify(
      latest
        ? `采集完成：获取 ${latest.fetched} 条，新增 ${latest.added} 条，请执行竞品分析`
        : "采集完成，请执行竞品分析",
      latest && !latest.added ? "warning" : "success",
    );
  } catch (error) {
    if (context === projectContext) notify(extractError(error), "error");
  } finally {
    if (context === projectContext) competitorScanning.value = false;
  }
}
async function analyzeCompetitors() {
  if (!project.value || competitorScanning.value || competitorAnalyzing.value)
    return;
  const projectId = project.value.project_id;
  const context = projectContext;
  competitorAnalyzing.value = true;
  try {
    const response = await pharmaTranslatorApi.analyzeCompetitors(projectId, {
      our_price: competitorOurPrice.value.trim() || undefined,
    });
    if (context !== projectContext || project.value?.project_id !== projectId)
      return;
    project.value = normalizeProject(response.data.data);
    competitorVoiceImports.value = [];
    notify("竞品分析完成，请核对内容缺口地图并选定 P0/P1 蓝海切口");
    await nextTick();
    scrollToAnchor("competitor-market-group");
  } catch (error) {
    if (context === projectContext) notify(extractError(error), "error");
  } finally {
    if (context === projectContext) competitorAnalyzing.value = false;
  }
}
function confirmCompetitor() {
  if (!canConfirmCompetitor.value)
    return notify("请至少选定一个蓝海切口并设置 P0/P1 优先级", "warning");
  return runAction(
    "confirm_competitor",
    {
      gaps: competitorGaps.value.map((gap) => ({
        gap_id: gap.gap_id,
        selected: gap.selected,
        priority: gap.priority,
      })),
      import_voices: competitorVoiceImports.value,
      radar_brands: competitorRadarBrands.value,
      signal_responses: Object.entries(competitorSignalResponses.value)
        .filter(([, response]) => response.trim())
        .map(([signal_id, response]) => ({
          signal_id,
          response: response.trim(),
        })),
    },
    "竞品地图与蓝海切口已确认，已进入合规过滤",
  );
}
function confirmKeywords() {
  if (!selectedKeywordCount.value)
    return notify("请至少选择一个关键词", "warning");
  return runAction(
    "confirm_keywords",
    { keywords: project.value?.keywords || [] },
    "关键词与优先级已确认",
  );
}
function confirmEvidence() {
  if (!canConfirmEvidence.value)
    return notify("每个卖点都必须有证据并经医学确认", "warning");
  return runAction(
    "confirm_evidence",
    { claims: claims.value },
    "医学证据已确认，内容工厂已解锁",
  );
}
async function generateContentBatch() {
  if (!project.value || batchGenerating.value || !batchChannels.value.length)
    return;
  const projectId = project.value.project_id;
  const context = projectContext;
  batchGenerating.value = true;
  const previousGeneratedAt = project.value.content_batch?.generated_at || "";
  try {
    const response = await pharmaTranslatorApi.generateContentBatch(projectId, {
      channels: batchChannels.value,
      total: Math.min(50, Math.max(10, Number(batchTotal.value) || 30)),
    });
    if (context !== projectContext || project.value?.project_id !== projectId)
      return;
    project.value = normalizeProject(response.data.data);
    notify("批量内容规划已生成并完成逐条合规自检，请市场部+合规部双确认");
    await scrollAfterRender("batch-topic-actions");
  } catch (error) {
    if (context !== projectContext) return;
    if ((error as AxiosError).response) {
      notify(extractError(error), "error");
      return;
    }
    // 连接中断（Network Error/超时）：后端仍在后台生成，轮询项目取回结果
    notify("连接中断，后台仍在生成，正在等待结果…", "info");
    const deadline = Date.now() + 15 * 60 * 1000;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 10000));
      if (context !== projectContext || project.value?.project_id !== projectId)
        return;
      try {
        const latest = await pharmaTranslatorApi.get(projectId);
        const generatedAt = latest.data.data.content_batch?.generated_at || "";
        if (generatedAt && generatedAt !== previousGeneratedAt) {
          project.value = normalizeProject(latest.data.data);
          notify("批量内容规划已生成并完成逐条合规自检，请市场部+合规部双确认");
          await scrollAfterRender("batch-topic-actions");
          return;
        }
      } catch {
        // 后端重启或网络抖动时继续等待
      }
    }
    notify("批量生成未返回结果，请检查模型服务后重试", "error");
  } finally {
    if (context === projectContext) batchGenerating.value = false;
  }
}
async function saveContentTopics() {
  if (!project.value || topicsSaving.value || !topicsEditable.value) return;
  const projectId = project.value.project_id;
  const context = projectContext;
  topicsSaving.value = true;
  try {
    const topics = Object.entries(topicDrafts.value).map(([no, row]) => ({
      no: Number(no),
      selected: row.selected,
      publish_time: row.publish_time.trim(),
    }));
    const response = await pharmaTranslatorApi.updateContentTopics(
      projectId,
      topics,
    );
    if (context !== projectContext || project.value?.project_id !== projectId)
      return;
    project.value = normalizeProject(response.data.data);
    notify(`选题勾选与排期已保存（已选 ${selectedTopicDraftCount.value} 条）`);
    await scrollAfterRender("batch-checklist-section");
  } catch (error) {
    if (context === projectContext) notify(extractError(error), "error");
  } finally {
    if (context === projectContext) topicsSaving.value = false;
  }
}
async function generateContentImages(
  content: PharmaContent,
  indexes?: number[],
) {
  if (!project.value || imageLoading.value || !canRegenerateContentImages.value)
    return;
  if (
    isApproved.value &&
    !window.confirm(
      "重新生成配图将撤销当前市场、合规与终审签字，生成成功后需重新审核。是否继续？",
    )
  )
    return;
  const projectId = project.value.project_id;
  const context = projectContext;
  const wasApproved = isApproved.value;
  imageLoading.value =
    indexes?.length === 1
      ? `${content.content_id}#${indexes[0]}`
      : content.content_id;
  try {
    const response = await pharmaTranslatorApi.generateContentImages(
      projectId,
      {
        content_id: content.content_id,
        ...(indexes?.length ? { indexes } : {}),
      },
    );
    if (context !== projectContext || project.value?.project_id !== projectId)
      return;
    project.value = normalizeProject(response.data.data);
    const updated = project.value.contents?.find(
      (item) => item.content_id === content.content_id,
    );
    notify(
      updated?.image_errors?.length
        ? `配图部分完成：${updated.image_errors.length} 张失败，可单张重试`
        : wasApproved
          ? indexes?.length === 1
            ? `图${indexes[0]} 已重新生成，原审批已撤销，请重新完成市场、合规与终审确认`
            : "配图已重新生成，原审批已撤销，请重新完成市场、合规与终审确认"
          : indexes?.length === 1
            ? `图${indexes[0]} 已生成，请核对图文对应关系`
            : "配图已按素材清单生成，请核对图文对应关系",
      updated?.image_errors?.length ? "warning" : "success",
    );
  } catch (error) {
    if (context === projectContext) notify(extractError(error), "error");
  } finally {
    if (context === projectContext) imageLoading.value = "";
  }
}
function channelBlockingRisks(channel: string) {
  return allRisks.value.filter(
    (risk) =>
      ["block", "违规/阻断"].includes(risk.level) &&
      contents.value.find((item) => item.content_id === risk.content_id)
        ?.channel === channel,
  );
}
function blockingReworkComment(channel: string) {
  const lines = channelBlockingRisks(channel)
    .slice(0, 8)
    .map((risk, index) =>
      [
        `${index + 1}. ${risk.message || "违规表述"}`,
        risk.matched_text ? `原文「${risk.matched_text}」` : "",
        risk.suggestion ? `建议：${risk.suggestion}` : "",
      ]
        .filter(Boolean)
        .join("；"),
    );
  return `修复以下 ❌ 违规（红线）项，删除或改写违规表述后重新生成：\n${lines.join("\n")}`.slice(
    0,
    500,
  );
}
function blockingReworkReason(channel: string) {
  return channel === "评论区预埋" ? "comment_redline" : "other";
}
function openRework(channel: string) {
  if (reworkLoading.value)
    return notify(
      `「${reworkLoading.value}」正在返工，请等待完成后再返工其他平台`,
      "warning",
    );
  reworkChannel.value = channel;
  const blocked = channelBlockingRisks(channel).length > 0;
  reworkReason.value = blocked
    ? blockingReworkReason(channel)
    : "tone_mismatch";
  reworkComment.value = blocked ? blockingReworkComment(channel) : "";
  reworkDialog.value = true;
}
function fixChannelViolations(channel: string) {
  if (reworkLoading.value)
    return notify(
      `「${reworkLoading.value}」正在处理，请等待完成后再修复其他平台`,
      "warning",
    );
  if (!channelBlockingRisks(channel).length) return openRework(channel);
  reworkChannel.value = channel;
  reworkReason.value = blockingReworkReason(channel);
  reworkComment.value = blockingReworkComment(channel);
  submitRework();
}
async function requestRework(
  projectId: string,
  channel: string,
  reason: string,
  comment: string,
) {
  const response = await pharmaTranslatorApi.reworkContentChannel(projectId, {
    channel,
    reason,
    comment,
  });
  if (project.value?.project_id === projectId)
    project.value = normalizeProject(response.data.data);
}
async function submitRework() {
  const comment = reworkComment.value.trim();
  if (!project.value || reworkLoading.value || !comment) return;
  const projectId = project.value.project_id;
  const context = projectContext;
  const channel = reworkChannel.value;
  reworkLoading.value = channel;
  // 返工需模型重写整组内容（通常 2-5 分钟），不阻塞弹窗，改为页面内进度提示
  reworkDialog.value = false;
  reworkElapsed.value = 0;
  clearInterval(reworkTimer);
  reworkTimer = setInterval(() => reworkElapsed.value++, 1000);
  notify(`已开始返工「${channel}」，约需 2-5 分钟，可继续浏览页面`, "info");
  try {
    await requestRework(projectId, channel, reworkReason.value, comment);
    if (context !== projectContext || project.value?.project_id !== projectId)
      return;
    batchChecklist.value = [];
    notify(`「${channel}」已返工重写并重新合规自检，请重新双确认`);
  } catch (error) {
    if (context === projectContext) notify(extractError(error), "error");
  } finally {
    clearInterval(reworkTimer);
    if (context === projectContext) reworkLoading.value = "";
  }
}
const FIX_ALL_LABEL = "一键修复所有违规内容";
async function fixAllViolations() {
  if (!project.value || reworkLoading.value) return;
  const projectId = project.value.project_id;
  const context = projectContext;
  reworkLoading.value = FIX_ALL_LABEL;
  reworkElapsed.value = 0;
  clearInterval(reworkTimer);
  reworkTimer = setInterval(() => reworkElapsed.value++, 1000);
  notify(
    "已开始一键修复所有违规内容：先 AI 改写违规片段，仍未清零的平台自动返工重写（后台运行），可继续浏览页面",
    "info",
  );
  const failed: string[] = [];
  try {
    try {
      const response = await pharmaTranslatorApi.autoFixContent(projectId);
      if (context !== projectContext || project.value?.project_id !== projectId)
        return;
      project.value = normalizeProject(response.data.data);
    } catch (error) {
      if (context !== projectContext) return;
      failed.push(`片段改写：${extractError(error)}`);
    }
    const channels = [
      ...new Set(
        allRisks.value
          .filter((risk) => ["block", "违规/阻断"].includes(risk.level))
          .map(
            (risk) =>
              contents.value.find((item) => item.content_id === risk.content_id)
                ?.channel || "",
          )
          .filter(Boolean),
      ),
    ];
    for (const channel of channels) {
      if (context !== projectContext || project.value?.project_id !== projectId)
        return;
      try {
        await requestRework(
          projectId,
          channel,
          blockingReworkReason(channel),
          blockingReworkComment(channel),
        );
      } catch (error) {
        failed.push(`「${channel}」：${extractError(error)}`);
      }
    }
    if (context !== projectContext) return;
    batchChecklist.value = [];
    if (!hasBlockingRisk.value)
      notify(
        "所有 ❌ 违规项已清零；请重新市场确认，再一键批注并点击合规确认",
        failed.length ? "warning" : "success",
      );
    else
      notify(
        `仍有 ❌ 违规项未清零${
          failed.length ? `（${failed.slice(0, 3).join("；")}）` : ""
        }，可再次点击「一键修复所有违规内容」或单独返工对应平台`,
        "warning",
      );
  } finally {
    clearInterval(reworkTimer);
    if (context === projectContext) reworkLoading.value = "";
  }
}
const AUTO_FIX_LABEL = "一键修复";
async function autoFixAll() {
  if (!project.value || reworkLoading.value) return;
  const projectId = project.value.project_id;
  const context = projectContext;
  reworkLoading.value = AUTO_FIX_LABEL;
  reworkElapsed.value = 0;
  clearInterval(reworkTimer);
  reworkTimer = setInterval(() => reworkElapsed.value++, 1000);
  notify(
    "已开始一键修复：调用已配置的 AI 模型改写违规片段（后台运行，3 分钟内完成），可继续浏览页面",
    "info",
  );
  try {
    const response = await pharmaTranslatorApi.autoFixContent(projectId);
    if (context !== projectContext || project.value?.project_id !== projectId)
      return;
    project.value = normalizeProject(response.data.data);
    batchChecklist.value = [];
    notify(
      hasBlockingRisk.value
        ? "一键修复完成，仍有 ❌ 项无法自动改写（如处方药公域投放），请返工对应平台"
        : "一键修复完成，❌ 违规项已清零；请重新市场确认，再一键批注并点击合规确认",
      hasBlockingRisk.value ? "warning" : "success",
    );
  } catch (error) {
    if (context === projectContext) notify(extractError(error), "error");
  } finally {
    clearInterval(reworkTimer);
    if (context === projectContext) reworkLoading.value = "";
  }
}
function approve(
  action: "market_confirm" | "compliance_confirm" | "final_approve",
) {
  const messages = {
    market_confirm: "市场确认已记录",
    compliance_confirm: "合规审查记录已签字归档",
    final_approve: "品牌终审已通过，可以导出交付包",
  };
  if (action === "market_confirm" && contentBatch.value) {
    const missing = batchChecklistOptions.filter(
      (item) => !batchChecklist.value.includes(item.key),
    );
    if (missing.length)
      return notify(
        `请完成确认清单：${missing
          .map((item) => item.text)
          .join("；")}；不符合项请分平台返工`,
        "warning",
      );
    return runAction(
      action,
      { checklist: batchChecklist.value },
      messages[action],
    );
  }
  if (action === "final_approve") {
    const signer = finalSigner.value.trim();
    const title = (finalSignerTitle.value || "").trim();
    if (!/品牌|总监|负责人/.test(title))
      return notify("终审确认人须为品牌总监或业务负责人，不可代签", "warning");
    const missing = finalChecklistOptions.filter(
      (item) => !finalChecklist.value.includes(item.key),
    );
    if (missing.length)
      return notify(
        `请逐项完成终审清单：${missing.map((item) => item.text).join("；")}`,
        "warning",
      );
    if (auditChainGaps.value.length)
      return notify(
        `审计链缺环：${auditChainGaps.value.join("、")}，请返工整体复盘`,
        "warning",
      );
    if (!finalAuthorized.value)
      return notify("终审通过须同时授权发布", "warning");
    return runAction(
      action,
      {
        signer_name: signer,
        signer_title: title,
        checklist: finalChecklist.value,
        duration_minutes: Number(finalDuration.value) || 0,
        business_goal_note: finalGoalNote.value.trim(),
        publish_authorization: {
          authorized: true,
          channels: finalChannels.value,
          start_date: finalStartDate.value,
        },
      },
      messages[action],
    );
  }
  if (action !== "compliance_confirm")
    return runAction(action, {}, messages[action]);
  if (pendingReviewCount.value)
    return notify(
      `仍有 ${pendingReviewCount.value} 条谨慎/替换项未逐条处理`,
      "warning",
    );
  if (!citationCovered.value)
    return notify("请先确认文献引证已覆盖全部合规风险点", "warning");
  const reviews: Record<string, ComplianceReviewDecision> = {};
  for (const risk of reviewableRisks.value) {
    const draft = reviewDrafts.value[risk.risk_id as string];
    if (draft?.decision)
      reviews[risk.risk_id as string] = {
        decision: draft.decision,
        note: draft.note.trim(),
      };
  }
  return runAction(
    "compliance_confirm",
    {
      signer_title: "合规部",
      citation_covered: true,
      duration_minutes: complianceDuration.value || null,
      reviews,
    },
    messages[action],
  );
}
async function loadComplianceKb() {
  if (complianceKb.value) return;
  try {
    const response = await pharmaTranslatorApi.complianceKnowledgeBase();
    complianceKb.value = response.data.data;
  } catch (error) {
    notify(extractError(error), "error");
  }
}
async function selectAllBatchChecklist() {
  batchChecklist.value = batchChecklistOptions.map((item) => item.key);
  await nextTick();
  scrollToAnchor("kb-review-section");
}
async function pollReviewProgress(projectId: string) {
  try {
    const response = await pharmaTranslatorApi.complianceReviewProgress(projectId);
    if (project.value?.project_id !== projectId || !complianceReviewing.value) return;
    reviewProgress.value = response.data.data;
    await nextTick();
    document
      .querySelectorAll<HTMLElement>(".review-progress .auto-bottom")
      .forEach((el) => (el.scrollTop = el.scrollHeight));
  } catch {
    // 进度轮询失败不影响复核本身
  }
}
async function runComplianceReview() {
  if (!project.value || complianceReviewing.value) return;
  const projectId = project.value.project_id;
  complianceReviewing.value = true;
  reviewProgress.value = null;
  reviewElapsed.value = 0;
  const startedAt = Date.now();
  clearInterval(reviewTimer);
  reviewTimer = window.setInterval(() => {
    reviewElapsed.value = Math.floor((Date.now() - startedAt) / 1000);
    void pollReviewProgress(projectId);
  }, 1500);
  try {
    const kbNames = complianceKbIds.value.map(
      (id) => kbOptions.value.find((item) => item.value === id)?.title || id,
    );
    const response = await pharmaTranslatorApi.runComplianceReview(projectId, {
      kbIds: complianceKbIds.value,
      kbNames,
    });
    if (project.value?.project_id !== projectId) return;
    project.value = normalizeProject(response.data.data);
    notify("知识库检索与模型复核完成，请逐条批注新增风险");
  } catch (error) {
    notify(extractError(error), "error");
  } finally {
    clearInterval(reviewTimer);
    complianceReviewing.value = false;
  }
}
async function answerComplianceTicket(ticketId: string) {
  if (!project.value || ticketSubmitting.value) return;
  const draft = ticketAnswerDraft(ticketId);
  if (!draft.answer.trim() || !draft.expertName.trim())
    return notify("请填写专家答复和答复专家", "warning");
  ticketSubmitting.value = true;
  try {
    const response = await pharmaTranslatorApi.answerComplianceTicket(
      project.value.project_id,
      ticketId,
      { answer: draft.answer.trim(), expertName: draft.expertName.trim() },
    );
    project.value = normalizeProject(response.data.data);
    delete ticketAnswerDrafts.value[ticketId];
    notify("专家答复已登记");
  } catch (error) {
    notify(extractError(error), "error");
  } finally {
    ticketSubmitting.value = false;
  }
}
function reviewDraft(riskId: string) {
  if (!reviewDrafts.value[riskId])
    reviewDrafts.value[riskId] = { decision: null, note: "" };
  return reviewDrafts.value[riskId];
}
function sampleSourceLabel(source?: string) {
  if (source === "inventory") return "品牌存量";
  if (source === "competitor") return "竞品样本";
  return source || "—";
}
function riskSourceLabel(source?: string) {
  if (source === "rule") return "规则引擎";
  if (source === "ai") return "模型复核";
  if (source === "ai_search") return "AI 搜索";
  return source || "规则引擎";
}
function filterSampleTitle(contentId?: string) {
  if (!contentId) return "";
  const sample = complianceFilter.value?.samples?.find(
    (item) => item.content_id === contentId,
  );
  if (!sample) return "";
  return `${sampleSourceLabel(sample.source)} · ${sample.platform || "—"} · ${
    sample.title || "无标题"
  }`;
}
function filterReviewDraft(riskId: string) {
  if (!filterReviewDrafts.value[riskId])
    filterReviewDrafts.value[riskId] = { decision: null, note: "" };
  return filterReviewDrafts.value[riskId];
}
function adoptAllFilterReviews() {
  for (const risk of filterPendingReviewRisks.value) {
    const draft = filterReviewDraft(risk.risk_id as string);
    if (!draft.decision) draft.decision = "adopt";
    if (risk.level === "caution" && !draft.note.trim())
      draft.note = "已复核，采纳合规建议";
  }
}
function adoptAllComplianceReviews() {
  for (const risk of reviewableRisks.value) {
    const draft = reviewDraft(risk.risk_id as string);
    if (!draft.decision) draft.decision = "adopt";
    if (risk.level === "caution" && !draft.note.trim())
      draft.note = "已复核，采纳合规建议";
  }
  notify("已批量批注全部谨慎/替换项，请核对后填写签字信息并确认");
}
const oneClickApproving = ref(false);
function blockingChannels() {
  return approvalBlockers.value.flatMap((item) => item.channels || []);
}
async function oneClickApprove() {
  if (readOnly.value || oneClickApproving.value || approvalDone("final"))
    return;
  oneClickApproving.value = true;
  try {
    if (!approvalDone("market")) {
      batchChecklist.value = batchChecklistOptions.map((item) => item.key);
      await approve("market_confirm");
      if (!approvalDone("market")) return;
    }
    if (hasBlockingRisk.value) {
      const channels = blockingChannels();
      return notify(
        `存在 ❌ 违规（红线）项，不能一键跳过，请先返工${
          channels.length ? `「${channels.join("」「")}」` : "对应平台"
        }，自检通过后再点一键审批`,
        "warning",
      );
    }
    if (!approvalDone("compliance")) {
      for (const risk of reviewableRisks.value) {
        const draft = reviewDraft(risk.risk_id as string);
        if (!draft.decision) draft.decision = "adopt";
        if (risk.level === "caution" && !draft.note.trim())
          draft.note = "已复核，采纳合规建议";
      }
      citationCovered.value = true;
      if (!complianceDuration.value) complianceDuration.value = 15;
      await approve("compliance_confirm");
      if (!approvalDone("compliance")) return;
    }
    if (auditChainGaps.value.length)
      return notify(
        `审计链缺环：${auditChainGaps.value.join(
          "、",
        )}，请先在对应步骤完成确认`,
        "warning",
      );
    finalChecklist.value = finalChecklistOptions.map((item) => item.key);
    finalAuthorized.value = true;
    if (!finalTitleValid.value) finalSignerTitle.value = "品牌总监";
    if (!(Number(finalDuration.value) > 0)) finalDuration.value = 45;
    if (!finalStartDate.value || finalStartDate.value < todayStr)
      finalStartDate.value = todayStr;
    await approve("final_approve");
  } finally {
    oneClickApproving.value = false;
  }
}
function filterDisposalDraft(disposalId: string) {
  if (!filterDisposalDrafts.value[disposalId])
    filterDisposalDrafts.value[disposalId] = {
      status: null,
      scheduled_date: "",
      note: "",
    };
  return filterDisposalDrafts.value[disposalId];
}
async function runComplianceFilter() {
  if (!project.value || filterRunning.value || !canEditFilter.value) return;
  const projectId = project.value.project_id;
  filterRunning.value = true;
  try {
    const kbNames = filterKbIds.value.map(
      (id) => kbOptions.value.find((item) => item.value === id)?.title || id,
    );
    const response = await pharmaTranslatorApi.runComplianceFilter(projectId, {
      kb_ids: filterKbIds.value,
      kb_names: kbNames,
      ai_search: filterAiSearch.value,
      inventory: filterInventoryPayload(),
    });
    if (project.value?.project_id !== projectId) return;
    forceFilterInventorySync = true;
    project.value = normalizeProject(response.data.data);
    notify("合规过滤完成，请逐条复核谨慎/替换项并确认存量处置清单");
    nextTick(() => scrollToAnchor("filter-adopt-all"));
  } catch (error) {
    notify(extractError(error), "error");
  } finally {
    filterRunning.value = false;
  }
}
async function createFilterTicket() {
  if (
    !project.value ||
    ticketSubmitting.value ||
    !filterTicketQuestion.value.trim()
  )
    return;
  ticketSubmitting.value = true;
  try {
    const response = await pharmaTranslatorApi.createComplianceTicket(
      project.value.project_id,
      {
        question: filterTicketQuestion.value.trim(),
        riskIds: filterTicketRiskIds.value,
      },
    );
    project.value = normalizeProject(response.data.data);
    filterTicketQuestion.value = "";
    filterTicketRiskIds.value = [];
    notify("已提交中睿合规专家答疑，24 小时内响应");
  } catch (error) {
    notify(extractError(error), "error");
  } finally {
    ticketSubmitting.value = false;
  }
}
async function askComplianceAi() {
  const question = aiAskQuestion.value.trim();
  if (!project.value || aiAskLoading.value || !question) return;
  aiAskLoading.value = true;
  try {
    const response = await pharmaTranslatorApi.askComplianceAi(
      project.value.project_id,
      question,
    );
    aiAskResult.value = response.data.data;
  } catch (error) {
    notify(extractError(error), "error");
  } finally {
    aiAskLoading.value = false;
  }
}
function escalateAiQuestion() {
  filterTicketQuestion.value = aiAskQuestion.value.trim();
  consultDialog.value = false;
  return createFilterTicket();
}
async function confirmComplianceFilter() {
  if (!filterScanned.value) return notify("请先运行合规过滤", "warning");
  if (filterInventoryDirty.value)
    return notify("存量内容已修改，请重新运行合规过滤后再确认", "warning");
  const signer = filterSignerName.value.trim();
  const title = filterSignerTitle.value.trim();
  if (!title.includes("合规"))
    return notify("签字人部门/职务须为合规部，不可代签", "warning");
  if (filterPendingReviewCount.value)
    return notify(
      `仍有 ${filterPendingReviewCount.value} 条谨慎/替换项未逐条复核（谨慎项须填写批注）`,
      "warning",
    );
  const datePattern = /^\d{4}-\d{2}-\d{2}$/;
  const reviews: Record<string, ComplianceReviewDecision> = {};
  for (const risk of filterReviewableRisks.value) {
    const draft = filterReviewDraft(risk.risk_id as string);
    if (draft.decision)
      reviews[risk.risk_id as string] = {
        decision: draft.decision,
        note: draft.note.trim(),
      };
  }
  const disposals: Record<
    string,
    { status: string; scheduled_date: string; note: string }
  > = {};
  for (const disposal of filterDisposals.value) {
    const draft = filterDisposalDraft(disposal.disposal_id);
    if (!draft.status) continue;
    disposals[disposal.disposal_id] = {
      status: draft.status,
      scheduled_date: draft.status === "scheduled" ? draft.scheduled_date : "",
      note: draft.note.trim(),
    };
  }
  const applyDate = filterApplyDate.value.trim();
  if (!datePattern.test(applyDate))
    return notify("请填写广审文号申请排期日期（YYYY-MM-DD）", "warning");
  if (!filterConfirmChecksComplete.value)
    return notify("请逐项勾选人工确认节点的 4 项确认内容", "warning");
  await runAction(
    "confirm_compliance_filter",
    {
      signer_name: signer,
      signer_title: title,
      reviews,
      disposals,
      confirm_checks: filterConfirmChecks.value,
      ad_review_schedule: {
        apply_date: applyDate,
        authority: filterAuthority.value.trim() || "省级药品监督管理部门",
        note: filterAdNote.value.trim(),
      },
    },
    "合规过滤已确认，已进入搜索词排序",
    filterComment.value.trim(),
  );
  if (activeStep.value !== 9) return;
  await nextTick();
  scrollToAnchor(
    document.getElementById("batch-report-top")
      ? "batch-report-top"
      : "approval-step",
  );
}
function ticketAnswerDraft(ticketId: string) {
  if (!ticketAnswerDrafts.value[ticketId])
    ticketAnswerDrafts.value[ticketId] = { answer: "", expertName: "" };
  return ticketAnswerDrafts.value[ticketId];
}
function isReviewableRisk(risk: ComplianceRisk) {
  return ["caution", "replace", "谨慎"].includes(risk.level);
}
function riskLevelLabel(level: ComplianceRisk["level"]) {
  return ["block", "违规/阻断"].includes(level)
    ? "❌ 违规"
    : ["caution", "谨慎"].includes(level)
    ? "⚠️ 谨慎"
    : level === "replace"
    ? "🟢 建议替换"
    : "✅ 合规";
}
function complianceLabelColor(label?: ComplianceLabel) {
  return label === "blocked"
    ? "error"
    : label === "caution"
    ? "warning"
    : "success";
}
function formatDateTime(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
function reworkProject() {
  if (!workflowComment.value.trim())
    return notify("返工必须填写批注", "warning");
  return runAction(
    "rework",
    { target_step: reworkTarget.value, reason: finalReworkReason.value },
    `已返工到第 ${reworkTarget.value} 步`,
    workflowComment.value.trim(),
  ).then(() => {
    workflowComment.value = "";
    finalReworkReason.value = "";
  });
}
function terminateProject() {
  if (!workflowComment.value.trim())
    return notify("终止必须填写原因", "warning");
  return runAction(
    "terminate",
    {},
    "项目已终止并归档",
    workflowComment.value.trim(),
  ).then(() => {
    workflowComment.value = "";
  });
}
async function exportKeywords() {
  if (project.value)
    await download(
      pharmaTranslatorApi.exportKeywords(project.value.project_id),
      `${project.value.product_name}_关键词表.csv`,
      "关键词表已导出",
    );
}
async function exportDelivery() {
  if (project.value && isApproved.value)
    await download(
      pharmaTranslatorApi.exportDelivery(project.value.project_id),
      `${project.value.product_name}_交付包.json`,
      "交付包已导出",
    );
}
async function exportApproval(kind: PharmaApprovalExportKind) {
  if (!project.value) return;
  const names: Record<PharmaApprovalExportKind, [string, string]> = {
    "approval-report.md": [
      "全流程报告.md",
      "飞书文档（全流程报告）已导出，可直接导入飞书",
    ],
    "approval.xlsx": ["审批包.xlsx", "市场部审批 Excel 已导出"],
    "feishu-bitable.xlsx": [
      "多维表格.xlsx",
      "多维表格已导出（含发布状态字段），可导入飞书多维表格",
    ],
    "full-report.json": [
      "全流程报告.json",
      "全流程 JSON 已导出，可对接企业内容管理系统",
    ],
  };
  const [suffix, message] = names[kind];
  await download(
    pharmaTranslatorApi.exportApproval(project.value.project_id, kind),
    `${project.value.product_name}_${suffix}`,
    message,
  );
}
const REPORT_STYLE = `body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;max-width:960px;margin:24px auto;padding:0 24px;color:#222;line-height:1.7;font-size:14px}
h1{font-size:24px;border-bottom:2px solid #5e35b1;padding-bottom:8px}h2{font-size:20px;margin-top:28px;border-bottom:1px solid #ddd;padding-bottom:4px}h3{font-size:16px;margin-top:20px}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}th,td{border:1px solid #ccc;padding:6px 8px;text-align:left;vertical-align:top}th{background:#f3effa}
blockquote{margin:12px 0;padding:8px 14px;border-left:4px solid #b39ddb;background:#faf8fd;color:#555}code{background:#f4f4f4;padding:1px 4px;border-radius:3px}
img{max-width:100%;max-height:480px;border:1px solid #eee;border-radius:6px;margin:8px 0}a{color:#5e35b1;word-break:break-all}
@media print{body{margin:0;max-width:none}h2{page-break-after:avoid}tr,img{page-break-inside:avoid}}`;
function reportFileBase() {
  return `${project.value?.product_name || "项目"}_全流程报告`;
}
function buildReportHtml() {
  return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>${reportFileBase()}</title><style>${REPORT_STYLE}</style></head><body>${
    reportPreview.value.html
  }</body></html>`;
}
function blobToDataUrl(blob: Blob) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}
// 报告中的配图以 content-images/{filename} 相对路径引用，预览/下载/打印前内嵌为 data URL；外链新窗口打开
async function resolveReportAssets(projectId: string, html: string) {
  const doc = new DOMParser().parseFromString(
    `<div>${html}</div>`,
    "text/html",
  );
  const root = doc.body.firstElementChild as HTMLElement;
  root.querySelectorAll("a[href^='http']").forEach((a) => {
    a.setAttribute("target", "_blank");
    a.setAttribute("rel", "noopener noreferrer");
  });
  await Promise.all(
    Array.from(
      root.querySelectorAll<HTMLImageElement>("img[src^='content-images/']"),
    ).map(async (img) => {
      const filename = decodeURIComponent(
        img.getAttribute("src")!.slice("content-images/".length),
      );
      try {
        const res = await pharmaTranslatorApi.contentImage(projectId, filename);
        img.setAttribute("src", await blobToDataUrl(res.data as Blob));
      } catch {
        img.replaceWith(doc.createTextNode(`[配图缺失：${filename}]`));
      }
    }),
  );
  return root.innerHTML;
}
async function openReportPreview() {
  if (!project.value) return;
  const projectId = project.value.project_id;
  reportPreview.value = { show: true, loading: true, markdown: "", html: "" };
  try {
    const res = await pharmaTranslatorApi.exportApproval(
      projectId,
      "approval-report.md",
    );
    const markdown = await (res.data as Blob).text();
    reportPreview.value.markdown = markdown;
    reportPreview.value.html = await resolveReportAssets(
      projectId,
      DOMPurify.sanitize(reportMarkdown.render(markdown)),
    );
  } catch (error) {
    reportPreview.value.show = false;
    notify(extractError(error), "error");
  } finally {
    reportPreview.value.loading = false;
  }
}
function downloadReport(kind: "md" | "html") {
  if (!reportPreview.value.markdown) return;
  const blob =
    kind === "md"
      ? new Blob([reportPreview.value.markdown], {
          type: "text/markdown;charset=utf-8",
        })
      : new Blob([buildReportHtml()], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${reportFileBase()}.${kind}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  notify(
    kind === "md"
      ? "报告已下载（Markdown）"
      : "报告已下载（HTML，可直接用浏览器打开）",
  );
}
function printReport() {
  if (!reportPreview.value.html) return;
  const frame = document.createElement("iframe");
  frame.style.cssText =
    "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
  document.body.appendChild(frame);
  const doc = frame.contentWindow?.document;
  if (!doc || !frame.contentWindow) {
    frame.remove();
    return;
  }
  doc.open();
  doc.write(buildReportHtml());
  doc.close();
  setTimeout(() => {
    frame.contentWindow?.focus();
    frame.contentWindow?.print();
    setTimeout(() => frame.remove(), 1000);
  }, 300);
}
async function loadSkuReuse(projectId?: string) {
  skuReuse.value = null;
  if (!projectId) return;
  try {
    const response = await pharmaTranslatorApi.skuReuse(projectId);
    if (project.value?.project_id === projectId)
      skuReuse.value = response.data.data;
  } catch {
    skuReuse.value = null;
  }
}
async function download(
  request: ReturnType<typeof pharmaTranslatorApi.exportKeywords>,
  filename: string,
  message: string,
) {
  exporting.value = true;
  try {
    const response = await request;
    const url = URL.createObjectURL(response.data as Blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
    notify(message);
  } catch (error) {
    notify(extractError(error), "error");
  } finally {
    exporting.value = false;
  }
}

function selectRecommended() {
  project.value?.keywords.forEach((keyword) => {
    keyword.selected = keyword.confidence >= 0.7;
  });
}
function clearKeywordSelection() {
  project.value?.keywords.forEach((keyword) => {
    keyword.selected = false;
  });
}
function dimensionKey(item: PharmaDimension) {
  return item.dimension_id || item.dimension_code || item.code || "unknown";
}
function dimensionLabel(item: PharmaDimension) {
  const code = dimensionKey(item);
  if (code === "endorsement") return "批号";
  return (
    item.label ||
    item.name ||
    (
      {
        ingredients: "成分",
        ingredient: "成分",
        efficacy: "主治功能",
        audience: "对症人群",
        endorsement: "批号",
        channels: "现有渠道",
        brand_product: "品牌名和产品名",
      } as Record<string, string>
    )[code] ||
    code
  );
}
function dimensionIcon(code: string) {
  return (
    (
      {
        ingredients: "mdi-flask-outline",
        ingredient: "mdi-flask-outline",
        efficacy: "mdi-heart-pulse",
        audience: "mdi-account-group-outline",
        endorsement: "mdi-certificate-outline",
        channels: "mdi-storefront-outline",
        brand_product: "mdi-tag-outline",
      } as Record<string, string>
    )[code] || "mdi-card-text-outline"
  );
}
function audienceText(value: string[] | string) {
  return Array.isArray(value) ? value.join("、") : value;
}
function claimText(claim: PharmaClaim) {
  return claim.text || claim.claim_text || "未命名卖点";
}
function approvalDone(type: "market" | "medical" | "compliance" | "final") {
  return Boolean(project.value?.approvals?.[type]);
}
function contentRisks(contentId: string) {
  return allRisks.value.filter((risk) => risk.content_id === contentId);
}
function evidenceLabel(level: PharmaClaim["evidence_level"]) {
  return (
    { strong: "🟢 强证据", weak: "🟡 弱证据", none: "🔴 无证据" } as const
  )[level];
}
function claimTypeIcon(type?: string) {
  return (
    (
      {
        ingredients: "🧪",
        efficacy: "🎯",
        audience: "👥",
        endorsement: "🏆",
      } as Record<string, string>
    )[type || ""] || ""
  );
}
function evidenceColor(level: PharmaClaim["evidence_level"]) {
  return level === "strong"
    ? "success"
    : level === "weak"
    ? "warning"
    : "error";
}
function riskClass(level: ComplianceRisk["level"]) {
  return ["block", "违规/阻断"].includes(level)
    ? "risk-block"
    : ["caution", "谨慎"].includes(level)
    ? "risk-caution"
    : level === "replace"
    ? "risk-replace"
    : "risk-pass";
}
function keywordSourceLabel(source: string) {
  return (
    (
      {
        platform_observed: "平台真实观测",
        enterprise_history: "企业历史数据",
        model_suggested: "模型建议（无真实搜索量）",
        document_extracted: "说明书抽取",
        manual_input: "人工输入",
        manual_review: "人工校对",
        manual: "人工添加",
      } as Record<string, string>
    )[source] || source
  );
}
function confidenceColor(value: number) {
  return value >= 0.9 ? "success" : value >= 0.7 ? "warning" : "error";
}
function confidenceClass(value: number) {
  return value >= 0.9 ? "high" : value >= 0.7 ? "medium" : "low";
}
function confidenceText(value: number, source: string) {
  return source ? `${Math.round(value * 100)}%` : "无证据";
}
function providerLabel(provider: string) {
  return (
    (
      {
        manual_review_text: "人工校对文本",
        pdf_text_layer: "PDF 文本层",
        remote_provider: "外部 OCR Provider",
        rapidocr_local: "本地 RapidOCR",
        tesseract: "Tesseract OCR",
      } as Record<string, string>
    )[provider] || provider
  );
}
function auditAction(action: string) {
  return (
    (
      {
        analyze: "上传并执行识别抽取",
        confirm: "人工确认字段与关键词",
        confirm_profile: "确认产品档案",
        confirm_dimensions: "确认多维拆解",
        confirm_scenes: "确认场景",
        scan_competitors: "竞品采集",
        analyze_competitors: "竞品分析（AI 模型）",
        confirm_competitor: "确认竞品地图与蓝海切口",
        confirm_keywords: "确认搜索词",
        confirm_evidence: "医学确认卖点证据",
        generate_contents: "生成内容并扫描合规",
        generate_content_batch: "批量内容生产（AI 模型）",
        rework_content_channel: "分平台返工",
        market_confirm: "市场确认",
        compliance_confirm: "合规确认",
        final_approve: "品牌终审",
        rework: "返工",
        terminate: "终止项目",
        update_publish_status: "发布状态更新",
        record_performance: "数据回传",
      } as Record<string, string>
    )[action] || action
  );
}
function historyStatusLabel(item: PharmaProjectSummary) {
  const status = (item.workflow_status || item.status).toLowerCase();
  return status.includes("terminat")
    ? "已终止"
    : status.includes("approved")
    ? "已终审"
    : "进行中";
}
function historyStatusColor(item: PharmaProjectSummary) {
  const label = historyStatusLabel(item);
  return label === "已终止"
    ? "error"
    : label === "已终审"
    ? "success"
    : "warning";
}
function formatBytes(bytes: number) {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
function formatDate(value: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
</script>

<style scoped>
.approval-blockers {
  margin: 4px 0 0;
  padding-left: 20px;
}
.approval-blockers li {
  margin: 2px 0;
}
.report-preview-body {
  font-size: 14px;
  line-height: 1.7;
  color: #222;
  overflow-x: auto;
}
.report-preview-body :deep(h1) {
  font-size: 22px;
  border-bottom: 2px solid #5e35b1;
  padding-bottom: 6px;
  margin: 8px 0 12px;
}
.report-preview-body :deep(h2) {
  font-size: 18px;
  border-bottom: 1px solid #ddd;
  padding-bottom: 4px;
  margin: 24px 0 10px;
}
.report-preview-body :deep(h3) {
  font-size: 15px;
  margin: 18px 0 8px;
}
.report-preview-body :deep(p),
.report-preview-body :deep(ul),
.report-preview-body :deep(ol) {
  margin: 6px 0;
}
.report-preview-body :deep(ul),
.report-preview-body :deep(ol) {
  padding-left: 22px;
}
.report-preview-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 10px 0;
  font-size: 13px;
}
.report-preview-body :deep(th),
.report-preview-body :deep(td) {
  border: 1px solid #ccc;
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
}
.report-preview-body :deep(th) {
  background: #f3effa;
}
.report-preview-body :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 14px;
  border-left: 4px solid #b39ddb;
  background: #faf8fd;
  color: #555;
}
.pharma-page {
  --pharma-primary: #2a52be;
  --pharma-primary-deep: #13285f;
  --pharma-teal: #0f9b8e;
  --pharma-ink: #142038;
  --pharma-muted: #66718b;
  --pharma-border: #e2e7f0;
  --pharma-soft: #f5f7fb;
  --shadow-1: none;
  --shadow-2: none;
  --shadow-3: none;
  --shadow-4: none;
  position: relative;
  max-width: 1500px;
  margin: 0 auto;
  padding: 24px 24px 64px;
  color: var(--pharma-ink);
  isolation: isolate;
}
/* L0 背景层：柔光 + 细网格 */
.pharma-page::before {
  content: "";
  position: absolute;
  inset: 0 -40px;
  z-index: -1;
  pointer-events: none;
  background: radial-gradient(
      900px 420px at 15% 0%,
      rgba(42, 82, 190, 0.08),
      transparent 70%
    ),
    radial-gradient(
      700px 380px at 95% 30%,
      rgba(15, 155, 142, 0.06),
      transparent 70%
    ),
    linear-gradient(rgba(42, 82, 190, 0.035) 1px, transparent 1px) 0 0 / 32px
      32px,
    linear-gradient(90deg, rgba(42, 82, 190, 0.035) 1px, transparent 1px) 0 0 /
      32px 32px;
  mask-image: linear-gradient(to bottom, #000 0, #000 900px, transparent 1400px);
}

/* ===== L4 主视觉 Hero ===== */
.hero-panel {
  position: relative;
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 32px;
  padding: 40px 44px 60px;
  overflow: hidden;
  border-radius: 16px 16px 0 0;
  color: white;
  background: radial-gradient(
      120% 140% at 100% 0%,
      rgba(64, 196, 220, 0.32),
      transparent 45%
    ),
    radial-gradient(80% 120% at 0% 100%, rgba(15, 155, 142, 0.28), transparent 50%),
    linear-gradient(135deg, #0e1f4d 0%, #1a3a8f 48%, #2a52be 100%);
  box-shadow: none;
  animation: pharma-rise 0.6s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}
.hero-panel::after {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px) 0
      0 / 28px 28px,
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px) 0 0 /
      28px 28px;
  mask-image: radial-gradient(70% 90% at 70% 30%, #000, transparent 75%);
}
.hero-decor {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(2px);
}
.hero-orb--a {
  top: -120px;
  right: 220px;
  width: 300px;
  height: 300px;
  background: radial-gradient(
    circle at 35% 35%,
    rgba(255, 255, 255, 0.18),
    rgba(255, 255, 255, 0) 65%
  );
}
.hero-orb--b {
  bottom: -160px;
  left: 30%;
  width: 360px;
  height: 360px;
  background: radial-gradient(
    circle,
    rgba(64, 196, 220, 0.22),
    rgba(64, 196, 220, 0) 65%
  );
}
.hero-molecule {
  position: absolute;
  top: 50%;
  right: 300px;
  width: 260px;
  height: 260px;
  color: rgba(255, 255, 255, 0.13);
  transform: translateY(-50%) rotate(-8deg);
  animation: pharma-float 14s ease-in-out infinite;
}
.hero-main,
.hero-state {
  position: relative;
  z-index: 1;
}
.hero-main {
  min-width: 0;
  max-width: 820px;
}
.hero-eyebrow {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  padding: 0 0 7px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.28);
  background: transparent;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  backdrop-filter: blur(6px);
}
.hero-panel h1 {
  margin: 18px 0 12px;
  font-size: clamp(28px, 3.2vw, 44px);
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: -0.03em;
  text-shadow: 0 2px 18px rgba(4, 14, 44, 0.35);
}
.hero-panel h1 em {
  margin: 0 6px;
  color: #6fe3d4;
  font-style: normal;
}
.hero-panel p {
  max-width: 760px;
  margin: 0;
  color: rgba(255, 255, 255, 0.78);
  font-size: 14.5px;
  line-height: 1.85;
}
.hero-pillars {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 24px 0 0;
  padding: 0;
  list-style: none;
}
.hero-pillars li {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  padding: 6px 14px 6px 0;
  color: rgba(255, 255, 255, 0.92);
  background: transparent;
  font-size: 12.5px;
  font-weight: 600;
}
.hero-pillars li :deep(.v-icon) {
  color: #6fe3d4;
}
.hero-state {
  display: flex;
  min-width: 280px;
  max-width: 320px;
  flex-direction: column;
  padding: 8px 0 8px 28px;
  border-left: 1px solid rgba(255, 255, 255, 0.24);
  background: transparent;
  box-shadow: none;
  animation: pharma-rise 0.7s 0.12s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}
.hero-state-label {
  align-self: flex-start;
  padding: 0 0 5px;
  border-bottom: 1px solid rgba(111, 227, 212, 0.5);
  color: #bff3ec;
  background: transparent;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
}
.hero-state strong {
  display: block;
  margin: 14px 0 4px;
  font-size: 17px;
  font-weight: 700;
}
.hero-state-step {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: auto;
  padding-top: 10px;
}
.hero-state-step b {
  font-size: 54px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.04em;
  font-variant-numeric: tabular-nums;
  background: linear-gradient(180deg, #ffffff, #9fd8ff);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.hero-state-step span {
  color: rgba(255, 255, 255, 0.55);
  font-size: 16px;
  font-weight: 700;
}
.hero-progress {
  height: 6px;
  margin: 14px 0 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
}
.hero-progress i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #6fe3d4, #9fd8ff);
  box-shadow: 0 0 12px rgba(111, 227, 212, 0.7);
  transition: width 0.5s ease;
}
.hero-state small {
  display: block;
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
}

/* ===== 步骤导航：作为报告目录接续 Hero ===== */
.workflow-strip {
  position: relative;
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 0;
  margin: 0 0 34px;
  padding: 14px 0 16px;
  border-bottom: 1px solid var(--pharma-border);
  background: transparent;
  animation: pharma-rise 0.6s 0.18s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}
.step-view-only
  :deep(
    :is(.v-btn, .v-field, .v-selection-control, textarea, input):not(
        .v-expansion-panel-title,
        .v-expansion-panel-title *,
        .v-tab,
        [data-view-allowed]
      )
  ) {
  cursor: not-allowed;
  opacity: 0.6;
}
.workflow-step {
  position: relative;
  display: flex;
  min-width: 0;
  gap: 10px;
  align-items: center;
  padding: 11px 12px;
  border: 0;
  border-right: 1px solid var(--pharma-border);
  border-radius: 0;
  color: var(--pharma-muted);
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: color 0.2s ease, background 0.2s ease;
}
.workflow-step:last-child {
  border-right: 0;
}
.workflow-step:not(:disabled):not(.active):hover {
  background: rgba(42, 82, 190, 0.035);
}
.workflow-step:disabled {
  cursor: not-allowed;
}
.workflow-step > span {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex: none;
  border: 1px solid var(--pharma-border);
  border-radius: 10px;
  background: rgb(var(--v-theme-surface));
  font-size: 12px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.workflow-step strong,
.workflow-step small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workflow-step strong {
  color: var(--pharma-ink);
  font-size: 12.5px;
}
.workflow-step small {
  margin-top: 2px;
  font-size: 10.5px;
}
.workflow-step.done > span {
  border-color: transparent;
  color: var(--pharma-teal);
  background: rgba(15, 155, 142, 0.12);
}
.workflow-step.active {
  color: var(--pharma-primary);
  background: rgba(42, 82, 190, 0.055);
  box-shadow: inset 0 -2px 0 var(--pharma-primary);
}
.workflow-step.active > span {
  border-color: var(--pharma-primary);
  color: var(--pharma-primary);
  background: transparent;
  box-shadow: none;
}
.workflow-step.locked {
  opacity: 0.5;
}

/* ===== 工作区：连续报告双栏 ===== */
.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.65fr);
  gap: 0;
  border-bottom: 1px solid var(--pharma-border);
  animation: pharma-rise 0.6s 0.26s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}
.surface-card {
  position: relative;
  padding: 10px 30px 38px;
  border: 0;
  border-radius: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}
.surface-card + .surface-card {
  border-left: 1px solid var(--pharma-border);
}
.back-to-top-btn {
  position: fixed;
  right: 32px;
  bottom: 40px;
  z-index: 20;
}

.section-heading,
.step-intro,
.result-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.section-heading {
  margin-bottom: 22px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--pharma-border);
}
.section-heading--compact {
  align-items: center;
  margin-bottom: 16px;
}
.section-kicker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  color: var(--pharma-primary);
  font-size: 10.5px;
  font-weight: 900;
  letter-spacing: 0.16em;
}
.section-kicker::before {
  content: "";
  width: 14px;
  height: 2px;
  border-radius: 2px;
  background: currentColor;
}
.section-heading h2,
.result-toolbar h2,
.step-intro h3 {
  margin: 0;
  color: var(--pharma-ink);
  font-weight: 800;
  letter-spacing: -0.02em;
}
.section-heading h2,
.result-toolbar h2 {
  font-size: 22px;
}
.step-intro h3 {
  font-size: 18px;
}
.section-heading p,
.result-toolbar p,
.step-intro p {
  margin: 6px 0 0;
  color: var(--pharma-muted);
  font-size: 13px;
  line-height: 1.7;
}
.form-grid {
  display: grid;
  grid-template-columns: 1.3fr 0.7fr;
  gap: 14px;
}
/* L1 内嵌凹槽 */
.drop-zone {
  display: flex;
  min-height: 168px;
  margin-top: 18px;
  padding: 26px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1.5px dashed #c3cce0;
  border-radius: 18px;
  background: radial-gradient(
      120% 100% at 50% 0%,
      rgba(42, 82, 190, 0.05),
      transparent 60%
    ),
    var(--pharma-soft);
  box-shadow: inset 0 2px 6px rgba(20, 32, 56, 0.04);
  cursor: pointer;
  transition: 0.25s ease;
}
.drop-zone:hover,
.drop-zone--active {
  border-color: var(--pharma-primary);
  background: #f0f4ff;
  box-shadow: inset 0 0 0 4px rgba(42, 82, 190, 0.06);
}
.drop-zone--filled {
  border-style: solid;
  border-color: rgba(15, 155, 142, 0.45);
  background: #f2fbf9;
}
.drop-icon {
  display: grid;
  place-items: center;
  width: 60px;
  height: 60px;
  margin-bottom: 8px;
  border-radius: 18px;
  color: white;
  background: linear-gradient(135deg, #2a52be, #1a3a8f);
  box-shadow: 0 12px 24px -10px rgba(42, 82, 190, 0.7),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
  transition: transform 0.25s ease;
}
.drop-zone:hover .drop-icon {
  transform: translateY(-3px);
}
.drop-zone span {
  color: var(--pharma-muted);
  font-size: 12px;
}
.upload-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-top: 22px;
  padding-top: 18px;
  border-top: 1px dashed var(--pharma-border);
}
.privacy-note {
  display: flex;
  gap: 7px;
  align-items: center;
  color: var(--pharma-muted);
  font-size: 12px;
}
.preview-card {
  display: flex;
  min-height: 520px;
  flex-direction: column;
}
.preview-stage {
  display: grid;
  min-height: 395px;
  flex: 1;
  place-items: center;
  overflow: hidden;
  border: 1px solid var(--pharma-border);
  border-radius: 16px;
  background: linear-gradient(rgba(42, 82, 190, 0.04) 1px, transparent 1px) 0 0 /
      20px 20px,
    linear-gradient(90deg, rgba(42, 82, 190, 0.04) 1px, transparent 1px) 0 0 /
      20px 20px,
    #f3f5f9;
  box-shadow: inset 0 2px 10px rgba(20, 32, 56, 0.06);
}
.preview-stage iframe,
.preview-stage img {
  width: 100%;
  height: 100%;
  min-height: 395px;
  border: 0;
  object-fit: contain;
}
.preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #8d96aa;
  text-align: center;
}
.preview-empty span {
  max-width: 260px;
  font-size: 12px;
}
.quality-warnings,
.quality-ok {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 12px;
  font-size: 12px;
}
.quality-warnings {
  border-left: 3px solid #e0a526;
  color: #8a6412;
  background: #fff8e8;
}
.quality-warnings div,
.quality-ok {
  display: flex;
  align-items: center;
  gap: 7px;
}
.quality-ok {
  border-left: 3px solid var(--pharma-teal);
  color: #12715f;
  background: #ecf8f5;
}

/* ===== 结果 / 历史：同一报告流中的章节 ===== */
.result-section,
.history-section {
  position: relative;
  margin-top: 0;
  padding: 42px 30px;
  border: 0;
  border-bottom: 1px solid var(--pharma-border);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.result-section {
  animation: pharma-rise 0.6s 0.34s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}
.result-toolbar {
  align-items: center;
  margin: 0;
  padding: 0 0 24px;
  border-bottom: 1px solid var(--pharma-border);
  border-radius: 0;
  background: transparent;
}
.result-toolbar-step {
  display: flex;
  width: 64px;
  min-height: 64px;
  flex: none;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-right: 1px solid var(--pharma-border);
  color: var(--pharma-primary);
  background: transparent;
  box-shadow: none;
}
.result-toolbar-step small {
  font-size: 9.5px;
  font-weight: 800;
  letter-spacing: 0.2em;
  opacity: 0.7;
}
.result-toolbar-step b {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.05;
  font-variant-numeric: tabular-nums;
}
.result-toolbar-main {
  min-width: 0;
  flex: 1;
}
.result-stats {
  display: flex;
  gap: 0;
}
.result-stats div {
  min-width: 112px;
  padding: 8px 16px;
  border-left: 1px solid var(--pharma-border);
  background: transparent;
  box-shadow: none;
  text-align: center;
}
.result-stats strong,
.result-stats span {
  display: block;
}
.result-stats strong {
  color: var(--pharma-primary);
  font-size: 22px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.result-stats span {
  color: var(--pharma-muted);
  font-size: 11px;
}
.status-alert {
  margin-top: 20px;
}
.step-panel {
  padding-top: 28px;
  animation: pharma-fade 0.35s ease both;
}
.step-intro {
  align-items: center;
  margin-bottom: 28px;
  padding: 0 0 18px 18px;
  border: 0;
  border-left: 3px solid var(--pharma-primary);
  border-bottom: 1px solid var(--pharma-border);
  border-radius: 0;
  background: transparent;
}
@keyframes pharma-rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
@keyframes pharma-fade {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
@keyframes pharma-float {
  0%,
  100% {
    transform: translateY(-50%) rotate(-8deg);
  }
  50% {
    transform: translateY(-54%) rotate(-3deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .hero-panel,
  .hero-state,
  .hero-molecule,
  .workflow-strip,
  .workspace-grid,
  .result-section,
  .step-panel {
    animation: none;
  }
}
.field-group + .field-group {
  margin-top: 28px;
}
.field-group--single .field-card-grid {
  grid-template-columns: minmax(0, 1fr);
}
.user-notes-panel {
  margin-top: 24px;
  padding: 16px;
  border: 1px dashed rgba(99, 102, 241, 0.4);
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.04);
}
.user-notes-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 12px 0;
}
.user-note-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid rgba(99, 102, 241, 0.2);
}
.field-group-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.field-group-title strong,
.field-group-title small {
  display: block;
}
.field-group-title small {
  margin-top: 2px;
  color: var(--pharma-muted);
  font-size: 11px;
}
.dimension-source-bar {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}
.dimension-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 10px 14px;
  border: 1px solid var(--pharma-border);
  border-radius: 12px;
  background: #fbfcfe;
}
.dimension-progress {
  color: var(--pharma-muted);
  font-size: 12px;
}
.field-card-grid,
.dimension-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-items: start;
}
.dimension-card {
  --dim-accent: var(--pharma-primary);
  border-top: 3px solid var(--dim-accent);
}
.dimension-card[data-dimension="brand_product"] {
  --dim-accent: #6366f1;
}
.dimension-card[data-dimension="efficacy"] {
  --dim-accent: #0d9488;
}
.dimension-card[data-dimension="ingredients"],
.dimension-card[data-dimension="ingredient"] {
  --dim-accent: #3c96ca;
}
.dimension-card[data-dimension="endorsement"] {
  --dim-accent: #d97706;
}
.dimension-card[data-dimension="audience"] {
  --dim-accent: #0891b2;
}
.dimension-card[data-dimension="channels"] {
  --dim-accent: #7c3aed;
}
.field-card,
.dimension-card,
.scene-card,
.claim-card,
.content-card {
  padding: 16px;
  border: 1px solid var(--pharma-border);
  border-radius: 14px;
  background: #fbfcfe;
}
.field-card-head,
.dimension-card header,
.scene-card header,
.claim-card header,
.content-card header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.field-card-head > div {
  display: flex;
  align-items: center;
  gap: 7px;
}
.evidence-line {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  margin-top: 9px;
  color: var(--pharma-muted);
  font-size: 11px;
}
.evidence-line span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.evidence-line span:first-child {
  color: #485675;
}
.step-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  margin-top: 22px;
  padding-top: 18px;
  border-top: 1px solid var(--pharma-border);
}
.step-actions.split {
  justify-content: space-between;
}
.dimension-card header {
  justify-content: flex-start;
  color: var(--dim-accent, var(--pharma-primary));
  margin: -16px -16px 0;
  padding: 11px 16px;
  border-radius: 13px 13px 0 0;
  background: color-mix(in srgb, var(--dim-accent, #3c96ca) 9%, #ffffff);
}
.dimension-card header strong {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.dimension-items {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}
.dimension-items div {
  min-width: 0;
  padding: 11px;
  border-radius: 10px;
  background: #f3f6fb;
}
.dimension-items p,
.dimension-items small {
  margin: 0;
}
.dimension-items p {
  color: #1f2a44;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.6;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.dimension-items small {
  display: block;
  margin-top: 5px;
  color: var(--pharma-muted);
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.ui-hidden {
  display: none !important;
}
.safety-panel {
  margin-top: 22px;
  padding: 18px;
  border: 1px solid #f1d8dc;
  border-top: 3px solid #f44336;
  border-radius: 15px;
  background: #fffafb;
}
.safety-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-items: start;
}
.safety-grid article {
  padding: 13px;
  border-radius: 10px;
  background: white;
}
.safety-grid p,
.safety-grid small {
  margin: 5px 0 0;
}
.safety-grid small {
  color: var(--pharma-muted);
}
.channel-category-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 6px 0;
}
.scene-flow {
  margin-bottom: 16px;
  padding: 18px;
  border: 1px solid var(--pharma-border, rgba(0, 0, 0, 0.08));
  border-radius: 14px;
  background: linear-gradient(180deg, #fbfcff 0%, #f6f8fd 100%);
  box-shadow: 0 8px 24px rgba(32, 47, 86, 0.06);
}
.scene-flow h4 {
  margin: 0 0 14px;
  padding-left: 10px;
  border-left: 4px solid var(--pharma-primary, #4f6bd8);
  font-size: 18px;
}
.scene-flow-body {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 72px 3fr;
  gap: 14px;
  align-items: stretch;
}
.scene-flow-input {
  padding: 14px;
  border: 1px solid rgba(49, 89, 200, 0.16);
  border-radius: 12px;
  background: linear-gradient(
    160deg,
    rgba(49, 89, 200, 0.1),
    rgba(49, 89, 200, 0.03)
  );
}
.scene-flow-input > strong {
  display: inline-block;
  margin-bottom: 6px;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--pharma-primary, #3159c8);
  color: #fff;
  font-size: 11px;
  letter-spacing: 1px;
}
.scene-flow-input p {
  max-height: 180px;
  margin: 6px 0 12px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-line;
}
/* 维度小卡：仿统计图指标卡，左色条 + 标签 + 数值 */
.scene-flow-input dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 6px 0 0;
  font-size: 13px;
}
.flow-dim-card {
  position: relative;
  min-width: 0;
  padding: 9px 10px 9px 14px;
  border: 1px solid rgba(49, 89, 200, 0.14);
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(32, 47, 86, 0.05);
}
.flow-dim-card::before {
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 0;
  width: 4px;
  border-radius: 4px;
  background: linear-gradient(180deg, #4f6bd8, #8fa5ec);
  content: "";
}
.flow-dim-card dt {
  margin-bottom: 3px;
  color: var(--pharma-muted);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1px;
}
.flow-dim-card dd {
  margin: 0;
  color: #1f2a44;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.scene-flow-arrow {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #8a6d1f;
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 2px;
}
.scene-flow-arrow .v-icon {
  padding: 12px;
  border-radius: 50%;
  background: linear-gradient(150deg, #f0b429, #d98e04);
  color: #fff;
  box-shadow: 0 6px 16px rgba(217, 142, 4, 0.35);
}
.scene-persona-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  counter-reset: persona;
}
.scene-persona {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 12px 12px;
  border: 1px solid rgba(184, 134, 11, 0.18);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 2px 10px rgba(32, 47, 86, 0.05);
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease;
  counter-increment: persona;
}
.scene-persona::before {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  height: 4px;
  border-radius: 12px 12px 0 0;
  background: linear-gradient(90deg, #f0b429, #f6d365);
  content: "";
}
.scene-persona::after {
  position: absolute;
  top: 10px;
  right: 10px;
  color: rgba(138, 109, 31, 0.4);
  font-size: 11px;
  font-weight: 700;
  content: "TA " counter(persona, decimal-leading-zero);
}
.scene-persona:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(32, 47, 86, 0.12);
}
.scene-persona strong {
  padding-right: 40px;
  color: #8a6d1f;
}
.scene-persona p {
  margin: 0;
  font-size: 13px;
}
.scene-persona small {
  color: var(--pharma-muted);
}
.scene-persona em {
  font-style: normal;
  color: #b8860b;
  font-size: 13px;
  font-weight: 600;
}
.scene-matrix {
  margin-top: 14px;
}
.scene-matrix-head strong,
.scene-matrix-head small {
  display: block;
}
.scene-matrix-head small,
.muted-text {
  color: var(--pharma-muted);
}
.scene-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.scene-card.selected {
  border-color: rgba(49, 89, 200, 0.5);
  box-shadow: 0 8px 24px rgba(49, 89, 200, 0.08);
}
.scene-card header {
  justify-content: flex-start;
}
.scene-card header strong,
.scene-card header small {
  display: block;
}
.scene-card header small {
  color: var(--pharma-muted);
}
.scene-card dl {
  display: grid;
  grid-template-columns: 70px 1fr;
  margin: 14px 0;
  gap: 6px;
  font-size: 12px;
}
.scene-card dt {
  color: var(--pharma-muted);
}
.scene-card dd {
  margin: 0;
}
.scene-card.deleted {
  opacity: 0.45;
}
.scene-card.deleted header strong {
  text-decoration: line-through;
}
.scope-note {
  display: block;
  color: var(--pharma-muted);
  margin-top: 2px;
}
.monologue {
  margin: 0;
  padding: 6px 10px;
  border-left: 3px solid rgba(49, 89, 200, 0.5);
  background: rgba(49, 89, 200, 0.06);
  border-radius: 4px;
  font-style: italic;
}
.keywords-notice {
  display: block;
  color: var(--pharma-muted);
  margin: 4px 0;
}
.linked-claims,
.voice-anchor {
  margin: 8px 0;
  font-size: 12px;
}
.linked-label {
  color: var(--pharma-muted);
  display: block;
  margin-bottom: 4px;
}
.voice-anchor ul {
  margin: 0;
  padding-left: 16px;
}
.voice-anchor li {
  margin-bottom: 2px;
}
.voice-anchor li small {
  color: var(--pharma-muted);
}
.scene-review {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: center;
  margin-top: 10px;
}
.competitor-form {
  display: grid;
  gap: 12px;
  margin-bottom: 14px;
}
.competitor-report-head h4 {
  font-size: 1.15rem;
  margin-bottom: 6px;
}
/* 竞品报告层级：L1 报告头 > L2 分组 > L3 板块卡片 > L4 条目 */
.competitor-step-panel {
  --report-ink: #17213b;
  --report-muted: #64708a;
  --report-line: #dce3f0;
  padding: 0 0 4px;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.competitor-step-panel > .step-intro {
  margin: 0 0 28px;
  padding: 0 0 18px 18px;
  border: 0;
  border-left: 3px solid var(--pharma-primary);
  border-bottom: 1px solid var(--report-line);
  border-radius: 0;
  background: transparent;
  color: var(--report-ink);
}
.competitor-step-panel > .step-intro h3 {
  color: var(--report-ink);
  font-size: 22px;
}
.competitor-step-panel > .step-intro p {
  max-width: 820px;
  color: var(--report-muted);
  line-height: 1.75;
}
.competitor-step-panel > .step-intro .v-chip {
  color: var(--pharma-primary) !important;
  background: rgba(42, 82, 190, 0.07) !important;
  border: 0;
}
.competitor-report-head {
  position: relative;
  overflow: hidden;
  margin: 12px 0 22px;
  padding: 24px 26px;
  border-radius: 18px;
  background: linear-gradient(135deg, #17213b, #263d74 70%, #3159c8);
  border: 1px solid rgba(49, 89, 200, 0.24);
  box-shadow: 0 14px 34px rgba(31, 49, 92, 0.18);
  color: #fff;
}
.competitor-report-head::after {
  position: absolute;
  right: -45px;
  top: -70px;
  width: 210px;
  height: 210px;
  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 50%;
  content: "";
}
.competitor-report-kicker {
  position: relative;
  z-index: 1;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.16em;
  color: #8fb0ff;
  margin-bottom: 5px;
}
.competitor-report-head h3 {
  position: relative;
  z-index: 1;
  font-size: 1.55rem;
  font-weight: 800;
  line-height: 1.4;
  margin: 0 0 10px;
  color: #fff;
}
.competitor-report-date {
  margin-left: 10px;
  font-size: 0.8rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.66);
}
.competitor-report-head .competitor-report-source {
  position: relative;
  z-index: 1;
  border: none;
  padding: 0;
  margin: 0 0 3px;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.78);
}
.competitor-report-meta {
  position: relative;
  z-index: 1;
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
}
.competitor-group {
  position: relative;
  display: flex;
  align-items: center;
  gap: 11px;
  margin: 34px 0 16px;
  padding: 0 0 11px 4px;
  border-bottom: 1px solid #dce3f0;
}
.competitor-group::after {
  position: absolute;
  bottom: -1px;
  left: 4px;
  width: 92px;
  height: 3px;
  border-radius: 3px;
  background: #3159c8;
  content: "";
}
.competitor-group-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: #17213b;
  box-shadow: 0 5px 12px rgba(23, 33, 59, 0.18);
  color: #fff;
  font-weight: 800;
  font-size: 13px;
}
.competitor-group-title {
  color: var(--report-ink);
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: 0.01em;
}
.competitor-group-desc {
  padding-left: 2px;
  font-size: 12px;
  color: var(--report-muted);
}
.competitor-report-source {
  border-left: 3px solid rgba(var(--v-border-color), 0.3);
  padding: 4px 12px;
  margin: 0 0 10px;
  color: rgba(var(--v-theme-on-surface), 0.65);
}
.competitor-gap-selected {
  background: rgba(var(--v-theme-success), 0.06);
}
.competitor-anchor-lead td {
  font-weight: 700;
}
.competitor-section {
  --sec: 49, 89, 200;
  position: relative;
  margin: 0 0 18px 14px;
  padding: 18px 22px 20px;
  border: 1px solid rgba(var(--sec), 0.17);
  border-left: 4px solid rgb(var(--sec));
  border-radius: 14px;
  background: linear-gradient(110deg, rgba(var(--sec), 0.035), #fff 34%);
  box-shadow: 0 7px 22px rgba(31, 49, 92, 0.065);
  line-height: 1.75;
  font-size: 14px;
}
.competitor-section.sec-raw {
  --sec: 120, 130, 145;
  box-shadow: none;
  background: rgba(var(--v-theme-on-surface), 0.02);
}
.competitor-section.sec-heat {
  --sec: 229, 115, 25;
}
.competitor-section.sec-price {
  --sec: 0, 137, 123;
}
.competitor-section.sec-gap {
  --sec: 46, 160, 67;
}
.competitor-section.sec-trust {
  --sec: 63, 81, 181;
}
.competitor-section.sec-formula {
  --sec: 191, 120, 0;
}
.competitor-section.sec-signal {
  --sec: 211, 47, 47;
}
.competitor-section.sec-voice {
  --sec: 142, 36, 170;
}
.competitor-section.sec-platform {
  --sec: 2, 136, 209;
}
.competitor-section h4 {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 9px;
  margin: 0 0 16px;
  padding-bottom: 11px;
  border-bottom: 1px solid rgba(var(--sec), 0.18);
  font-size: 1.06rem;
  font-weight: 800;
  color: #17213b;
}
.competitor-section .sec-no {
  display: inline-block;
  padding: 0 9px;
  border-radius: 7px;
  background: rgba(var(--sec), 0.12);
  color: rgb(var(--sec));
  font-size: 12px;
  line-height: 23px;
  font-weight: 800;
}
.competitor-section .sec-sub {
  font-size: 12px;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.5);
}
.competitor-section .sec-sub-key {
  padding: 0 8px;
  border-radius: 10px;
  background: rgba(var(--sec), 0.12);
  color: rgb(var(--sec));
  font-weight: 600;
}
.competitor-section p {
  margin: 6px 0;
}
.competitor-list {
  padding-left: 20px;
}
.competitor-list li {
  margin-bottom: 8px;
}
.competitor-list li strong {
  color: rgb(var(--sec));
}
.platform-name {
  font-size: 15px;
  font-weight: 700;
  color: rgb(var(--sec));
  margin-bottom: 2px;
}
.platform-tone {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.55);
  margin-bottom: 6px;
}
.platform-strategy {
  line-height: 1.75;
}
.formula-platform {
  display: inline-block;
  margin-bottom: 10px;
  padding: 0 10px;
  border-radius: 10px;
  background: rgba(var(--sec), 0.12);
  color: rgb(var(--sec));
  font-size: 12px;
  font-weight: 700;
  line-height: 22px;
}
.formula-step {
  --step: 46, 160, 67;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: start;
  padding: 6px 0 6px 10px;
  border-left: 3px solid rgb(var(--step));
  margin-bottom: 8px;
  line-height: 1.7;
}
.formula-step:last-child {
  margin-bottom: 0;
}
.formula-open {
  --step: 46, 160, 67;
}
.formula-middle {
  --step: 229, 115, 25;
}
.formula-end {
  --step: 142, 36, 170;
}
.formula-label {
  font-size: 12px;
  font-weight: 700;
  color: rgb(var(--step));
  white-space: nowrap;
  line-height: 1.9;
}
.signal-list {
  display: grid;
  gap: 10px;
}
.signal-item {
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(var(--sec), 0.05);
  border-left: 3px solid rgba(var(--sec), 0.6);
}
.signal-brand {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  color: rgb(var(--sec));
}
.signal-text {
  margin-top: 2px;
  line-height: 1.75;
}
.signal-refs {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
}
.voice-meta {
  color: rgba(var(--v-theme-on-surface), 0.55);
}
.voice-pain {
  color: rgb(211, 47, 47);
}
.competitor-table th {
  color: rgb(var(--sec)) !important;
  font-weight: 700 !important;
}
.competitor-table td {
  line-height: 1.7;
  padding-top: 6px !important;
  padding-bottom: 6px !important;
}
.competitor-table .competitor-text {
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.competitor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.competitor-card {
  border: 1px solid rgba(var(--sec), 0.2);
  border-radius: 10px;
  padding: 14px 16px;
  background: rgba(var(--sec), 0.03);
}
.competitor-our-row td {
  font-weight: 600;
  background: rgba(49, 89, 200, 0.06);
}
.competitor-confirm {
  border-top: 1px dashed rgba(49, 89, 200, 0.3);
  padding-top: 12px;
}
.competitor-card.selected {
  border-color: rgba(49, 89, 200, 0.7);
  background: rgba(49, 89, 200, 0.04);
}
.competitor-card-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.competitor-refs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: var(--pharma-muted);
}
.competitor-voice {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.competitor-meta {
  color: var(--pharma-muted);
  font-size: 12px;
  margin-right: auto;
}
.competitor-bulk-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.competitor-bulk-bar .competitor-meta {
  margin-right: 0;
}
.scene-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 14px 0 10px;
}
.scene-toolbar small {
  color: var(--pharma-muted);
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.keyword-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.keyword-actions .v-text-field {
  width: 250px;
}
.keyword-table-wrap {
  overflow: auto;
  border: 1px solid var(--pharma-border);
  border-radius: 14px;
}
.keyword-table {
  width: 100%;
  min-width: 1100px;
  border-collapse: collapse;
  font-size: 13px;
}
.keyword-table th {
  padding: 12px 14px;
  color: #5f6a82;
  background: #f6f7fa;
  font-size: 11px;
  text-align: left;
  white-space: nowrap;
}
.keyword-table td {
  padding: 9px 14px;
  border-top: 1px solid #edf0f5;
  vertical-align: middle;
}
.keyword-table tr.selected td {
  background: rgba(49, 89, 200, 0.035);
}
.check-col {
  width: 62px;
  text-align: center !important;
}
.source-cell {
  max-width: 320px;
  overflow: hidden;
  color: var(--pharma-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.table-subtext {
  display: block;
  color: var(--pharma-muted);
}
.score-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 6px;
  border-radius: 50%;
}
.score-dot.high {
  background: #20a66a;
}
.score-dot.medium {
  background: #e5a12c;
}
.score-dot.low {
  background: #dc4b55;
}
.empty-row {
  padding: 42px !important;
  color: var(--pharma-muted);
  text-align: center;
}
.claim-list {
  margin: 16px 0;
  padding: 16px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
}
.batch-generator-panel {
  grid-template-columns: minmax(0, 1fr) 120px auto;
  align-items: stretch;
  margin: 26px 0 34px;
  padding: 18px 0;
  border: 0;
  border-top: 1px solid rgba(36, 86, 126, 0.18);
  border-bottom: 1px solid rgba(36, 86, 126, 0.18);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.batch-generator-panel > .v-btn {
  min-height: 56px;
  padding-inline: 22px;
  letter-spacing: 0.02em;
}
.batch-report {
  margin: 30px 0 0;
  padding: 0 0 32px;
  overflow: visible;
  border: 0;
  border-top: 1px solid rgba(29, 69, 97, 0.18);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.batch-report-hero {
  position: relative;
  margin: 0 0 34px;
  padding: 28px 30px;
  overflow: hidden;
  color: #f8fbfc;
  background: linear-gradient(125deg, #122b3c 0%, #1d4b5a 62%, #2b6b69 100%);
}
.batch-report-hero::after {
  position: absolute;
  right: -52px;
  bottom: -80px;
  width: 210px;
  height: 210px;
  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 50%;
  content: "";
}
.batch-report-kicker {
  margin-bottom: 8px;
  color: #8fd5c5;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.18em;
}
.batch-report-hero h3 {
  margin: 0 0 12px;
  font-family: "Noto Serif SC", "Source Han Serif SC", serif;
  font-size: clamp(24px, 3vw, 34px);
  font-weight: 700;
  letter-spacing: 0.04em;
}
.batch-report-hero .competitor-report-source {
  max-width: 980px;
  margin: 0;
  padding: 0;
  border: 0;
  color: rgba(248, 251, 252, 0.9);
  background: transparent;
  font-size: 14px;
  line-height: 1.85;
}
.batch-report-hero .competitor-meta {
  margin: 14px 0 0;
  color: rgba(219, 237, 238, 0.72);
  line-height: 1.7;
}
.batch-section-title {
  display: flex;
  align-items: center;
  gap: 11px;
  margin: 30px 0 14px;
  color: #183a4a;
  font-size: 18px;
  font-weight: 750;
  letter-spacing: 0.01em;
}
.batch-section-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 46px;
  height: 28px;
  padding: 0 10px;
  border-radius: 8px;
  color: #fff;
  background: #1d5963;
  box-shadow: 0 6px 14px rgba(29, 89, 99, 0.2);
  font-size: 12px;
  letter-spacing: 0.05em;
}
.batch-group {
  margin: 0;
  border: 0;
  border-bottom: 1px solid rgba(35, 75, 99, 0.14);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.batch-topic-group {
  padding: 16px 18px 12px;
  border-left: 4px solid #3b8e86;
}
.batch-topic-group > h5 {
  margin: 0 0 8px;
  color: #1e5960;
  font-size: 14px;
  font-weight: 750;
}
.batch-topic-group ol {
  margin: 0;
  padding-left: 28px;
}
.batch-topic-group li {
  padding: 9px 8px 9px 3px;
  border-bottom: 1px dashed rgba(40, 85, 104, 0.12);
  color: #294451;
  line-height: 1.75;
}
.batch-topic-group li:last-child {
  border-bottom: 0;
}
.batch-topic-actions {
  justify-content: space-between;
  margin: 18px 0 34px;
  padding: 14px 0;
  border: 0;
  border-top: 1px solid rgba(47, 112, 107, 0.18);
  border-bottom: 1px solid rgba(47, 112, 107, 0.18);
  border-radius: 0;
  background: rgba(238, 247, 244, 0.58);
}
.batch-topic-actions .competitor-meta {
  color: #285c5b;
  font-weight: 650;
}
.batch-section-heading {
  justify-content: space-between;
  margin-top: 4px;
}
.batch-section-heading .batch-section-title {
  margin-right: auto;
}
.batch-platform-group {
  overflow: hidden;
}
.batch-platform-head {
  margin: 0 !important;
  padding: 18px 0 12px;
  border-bottom: 1px solid rgba(31, 73, 94, 0.11);
  background: transparent;
}
.batch-platform-head > span:first-child {
  margin-right: auto;
  color: #193f4d;
  font-size: 15px;
  font-weight: 750;
}
.batch-report h5 {
  margin: 0 0 8px;
}
.batch-report ol,
.batch-report ul {
  line-height: 1.8;
}
.batch-sample {
  margin: 0;
  padding: 20px 16px;
  border: 0;
  border-bottom: 1px solid rgba(35, 77, 99, 0.11);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.batch-sample > h5 {
  color: #173c4d;
  font-size: 14px;
  line-height: 1.65;
}
.batch-demo {
  margin: 18px 0;
  padding: 22px 0;
  border-top: 1px solid rgba(62, 129, 118, 0.21);
  border-bottom: 1px solid rgba(62, 129, 118, 0.21);
  background: transparent;
  box-shadow: none;
}
.batch-demo-body {
  max-width: 980px;
  margin: 16px 0 4px;
  padding: 8px 0 8px 18px;
  border-left: 3px solid #57a497;
  border-radius: 0;
  color: #334c57;
  background: transparent;
}
.batch-demo-body pre {
  margin: 4px 0;
  white-space: pre-wrap;
  font-family: inherit;
}
.batch-demo-body p {
  margin: 9px 0;
  line-height: 1.85;
}
.batch-demo-body ul {
  margin: 8px 0 8px 20px;
  line-height: 1.85;
}
.topic-check {
  width: 15px;
  height: 15px;
  margin-right: 8px;
  vertical-align: middle;
  accent-color: #28766f;
}
.topic-off {
  color: var(--pharma-muted);
  text-decoration: line-through;
}
.topic-time {
  width: 190px;
  min-height: 30px;
  padding: 3px 9px;
  border: 1px solid rgba(44, 87, 105, 0.2);
  border-radius: 7px;
  color: #294854;
  background: #f9fbfb;
  font-size: 12px;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease;
}
.topic-time:focus {
  border-color: #3a8d84;
  outline: none;
  box-shadow: 0 0 0 3px rgba(58, 141, 132, 0.12);
}
.topic-time:disabled {
  color: #72858c;
  background: #f1f5f5;
  opacity: 1;
}
.current-content-image-action {
  min-width: 190px;
  font-weight: 700;
}
/* 最多 3 列，容器变窄时自动降为 2 列 / 1 列 */
.content-image-grid {
  display: grid;
  grid-template-columns: repeat(
    auto-fill,
    minmax(max(200px, calc((100% - 40px) / 3)), 1fr)
  );
  gap: 20px;
  margin-top: 14px;
  align-items: stretch;
}
.content-image-grid--current {
  padding: 16px;
  border: 1px solid rgba(49, 123, 113, 0.16);
  border-radius: 14px;
  background: linear-gradient(145deg, #f5faf8 0%, #eef6f5 100%);
}
.content-image {
  display: flex;
  flex-direction: column;
  min-width: 0;
  margin: 0;
  border: 1px solid rgba(35, 77, 99, 0.1);
  border-radius: 16px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 10px 24px rgba(32, 65, 82, 0.08);
  transition: box-shadow 0.2s, transform 0.2s;
}
.content-image:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 30px rgba(32, 65, 82, 0.13);
}
.content-image-clickable {
  cursor: zoom-in;
  transition: opacity 0.15s;
}
.content-image-clickable:hover {
  opacity: 0.88;
}
.content-image img,
.content-image-loading {
  display: block;
  width: 100%;
  aspect-ratio: 3 / 4;
  object-fit: cover;
}
.content-image-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--pharma-muted);
  font-size: 12px;
}
.content-image figcaption {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px 8px;
  color: #36535e;
  font-size: 13px;
  line-height: 1.6;
}
.content-image-caption {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  word-break: break-all;
}
.content-image-caption small {
  color: var(--pharma-muted);
  font-size: 11px;
}
.content-image-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-top: auto;
  margin-left: -6px;
  color: #4b6670;
}
.batch-channel-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.batch-checklist {
  margin-top: 8px;
  padding: 8px 12px;
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.2);
  border-radius: 8px;
}
.content-list {
  display: grid;
  gap: 12px;
}
.claim-card header > div strong,
.claim-card header > div small {
  display: block;
}
.claim-card header small {
  margin-top: 3px;
  color: var(--pharma-muted);
}
.claim-evidence {
  display: flex;
  gap: 10px;
  margin: 14px 0 8px;
  padding: 12px;
  border-radius: 10px;
  background: #f4f6fa;
}
.claim-evidence p,
.claim-evidence small {
  margin: 0;
}
.claim-evidence small {
  display: block;
  margin-top: 4px;
  color: var(--pharma-muted);
}
.literature-sources {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 14px;
}
.literature-sources h4 {
  margin: 0 0 10px;
  font-size: 15px;
}
.literature-upload,
.literature-kb {
  padding: 14px;
  border: 1px solid #e3e8f0;
  border-radius: 12px;
  background: #fafbfe;
}
.upload-row {
  display: grid;
  grid-template-columns: 180px 1fr auto;
  gap: 10px;
  align-items: center;
}
.literature-doc-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}
.literature-doc {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #ffffff;
  border: 1px solid #eceff5;
}
.literature-doc > div {
  flex: 1;
  min-width: 0;
}
.literature-doc strong,
.literature-doc small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.literature-doc small {
  color: var(--pharma-muted);
}
.literature-hint {
  margin: 10px 0 0;
  color: var(--pharma-muted);
  font-size: 13px;
}
.citation-list {
  display: grid;
  gap: 8px;
}
.citation-list .claim-evidence {
  margin: 8px 0 0;
}
.ai-analysis {
  display: flex;
  gap: 10px;
  margin: 10px 0 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: #eef4ff;
  border: 1px solid #d8e5fb;
}
.ai-analysis.adjusted {
  background: #fdf6ec;
  border-color: #f0dcb8;
}
.ai-analysis p,
.ai-analysis small {
  margin: 0;
}
.ai-analysis small {
  display: block;
  margin-top: 4px;
  color: var(--pharma-muted);
}
.verdict-note {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin: 10px 0 0;
  padding: 8px 12px;
  border-radius: 10px;
  background: #f6f8fa;
  border: 1px solid #e3e8ee;
}
.verdict-note p {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
}
.verdict-note small {
  display: block;
  margin-top: 2px;
  color: var(--pharma-muted);
}
.ai-note-line {
  margin-top: 2px;
}
.disposal-text {
  color: #b3261e;
}
.triple-card-panels {
  margin: 10px 0;
}
.claim-groups {
  margin: 16px 0;
}
.claim-groups h4,
.literature-summary h4,
.claim-list-title {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 700;
}
.claim-group {
  margin-bottom: 10px;
}
.claim-group h5 {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 600;
}
.claim-group ul {
  margin: 0;
  padding-left: 18px;
}
.claim-group li {
  font-size: 13px;
  line-height: 1.9;
}
.claim-group li b {
  margin-right: 4px;
}
.claim-group li .v-chip {
  margin-left: 6px;
}
.literature-summary {
  margin: 16px 0;
  overflow-x: auto;
}
.literature-summary-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  background: #fff;
}
.literature-summary-table th,
.literature-summary-table td {
  border: 1px solid #e2e8f0;
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
  line-height: 1.6;
}
.literature-summary-table th {
  background: #f8fafc;
  font-weight: 600;
  white-space: nowrap;
}
.literature-summary-table td.nowrap {
  white-space: nowrap;
}
.claim-list-title {
  margin-top: 18px;
}
.claim-list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 18px 0 10px;
}
.claim-list-head .claim-list-title {
  margin: 0;
}
.triple-card-grid {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 8px 14px;
  margin: 0;
}
.triple-card-grid dt {
  font-weight: 600;
  color: var(--pharma-muted);
}
.triple-card-grid dd {
  margin: 0;
}
.violation-copy {
  color: #b3261e;
}
.tier-select {
  max-width: 420px;
}
.claim-chips {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}
.literature-signoff {
  margin-top: 16px;
  padding: 14px;
  border: 1px solid #c8d6f0;
  border-radius: 12px;
  background: #f5f8fd;
}
.literature-checklist {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  margin-bottom: 8px;
}
.error-text {
  color: rgb(var(--v-theme-error));
}
.literature-signoff h4 {
  margin: 0 0 6px;
}
.literature-signoff-done {
  margin-top: 16px;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.content-footnotes {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 12px;
  color: #5f6368;
}
.unusable-box {
  margin-top: 16px;
  padding: 14px;
  border: 1px dashed #d98b8b;
  border-radius: 12px;
  background: #fdf5f5;
}
.unusable-box h4 {
  margin: 0 0 10px;
  font-size: 15px;
  color: #b3261e;
}
.unusable-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}
.unusable-item span {
  flex: 1;
}
.unusable-item small {
  color: var(--pharma-muted);
}
@media (max-width: 1100px) {
  .literature-sources {
    grid-template-columns: 1fr;
  }
  .upload-row {
    grid-template-columns: 1fr;
  }
}
.platform-picker {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  margin-bottom: 18px;
}
.review-progress {
  margin-bottom: 18px;
  padding: 12px 14px;
  border: 1px solid rgba(var(--v-theme-primary), 0.25);
  border-radius: 10px;
  background: rgba(var(--v-theme-primary), 0.04);
}
.review-progress__head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  margin-bottom: 8px;
}
.review-progress__logs {
  max-height: 150px;
  overflow-y: auto;
  margin: 0 0 8px;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.7;
}
.review-progress__stream {
  margin-top: 8px;
}
.review-progress__label {
  font-size: 12px;
  opacity: 0.7;
  margin-bottom: 4px;
}
.review-progress__stream pre {
  max-height: 160px;
  overflow-y: auto;
  margin: 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.04);
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
.content-card header > div {
  display: flex;
  align-items: center;
  gap: 10px;
}
.content-card pre {
  margin: 14px 0;
  padding: 14px;
  border-radius: 10px;
  background: #f4f6fa;
  white-space: pre-wrap;
  font: 13px/1.7 inherit;
}
.risk-list {
  display: grid;
  gap: 7px;
  margin-top: 10px;
}
.risk-item {
  display: grid;
  gap: 5px;
  padding: 9px 11px;
  border-radius: 9px;
  font-size: 12px;
}
.risk-item-head {
  display: grid;
  grid-template-columns: 90px 1fr auto;
  gap: 8px;
  align-items: baseline;
}
.risk-item-head small {
  opacity: 0.75;
}
.risk-item-line {
  padding-left: 98px;
  line-height: 1.5;
}
.risk-item-line mark {
  padding: 0 3px;
  color: #b3261e;
  background: #ffe1e1;
  border-radius: 3px;
}
.risk-review {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px;
  align-items: center;
  padding-left: 98px;
}
.risk-block {
  color: #972d38;
  background: #fff0f2;
}
.risk-caution {
  color: #8a6412;
  background: #fff8e8;
}
.risk-replace {
  color: #1d5f8a;
  background: #eef6fc;
}
.risk-pass {
  color: #16714a;
  background: #edf9f4;
}
.compliance-kb-panel {
  margin-bottom: 14px;
}
.compliance-kb p,
.compliance-kb h4 {
  margin: 8px 0;
  font-size: 13px;
}
.compliance-kb ul {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.6;
}
.compliance-kb-layers {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
}
.compliance-kb-layers article {
  padding: 10px 12px;
  border: 1px solid var(--pharma-border);
  border-radius: 10px;
}
.compliance-step-panel {
  --compliance-ink: #17213b;
  --compliance-muted: #64708a;
  --compliance-line: #dce3f0;
  padding: 0 0 4px;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.compliance-step-panel > .step-intro {
  position: relative;
  overflow: hidden;
  margin: 0 0 28px;
  padding: 0 0 18px 18px;
  border: 0;
  border-left: 3px solid var(--pharma-primary);
  border-bottom: 1px solid var(--compliance-line);
  border-radius: 0;
  background: transparent;
  color: var(--compliance-ink);
}
.compliance-step-panel > .step-intro::after {
  content: none;
}
.compliance-step-panel > .step-intro > * {
  position: relative;
  z-index: 1;
}
.compliance-step-panel > .step-intro h3 {
  margin-bottom: 8px;
  color: var(--compliance-ink);
  font-size: 22px;
  letter-spacing: 0.02em;
}
.compliance-step-panel > .step-intro p {
  max-width: 960px;
  margin: 0;
  color: var(--compliance-muted);
  line-height: 1.8;
}
.compliance-step-panel > .step-intro .v-chip {
  color: var(--pharma-primary) !important;
  background: rgba(42, 82, 190, 0.07) !important;
  border: 0;
}
.compliance-step-panel > .compliance-kb-panel {
  overflow: hidden;
  border: 1px solid #dce5f2;
  border-radius: 14px;
  box-shadow: 0 6px 18px rgba(31, 49, 92, 0.05);
}
.compliance-step-panel > .compliance-kb-panel :deep(.v-expansion-panel-title) {
  min-height: 56px;
  color: #29456f;
  background: #f7faff;
  font-weight: 700;
}
.compliance-section {
  display: grid;
  gap: 14px;
  margin-top: 18px;
  padding: 20px 22px;
  border: 1px solid var(--pharma-border);
  border-radius: 15px;
  background: #fff;
}
.compliance-section > header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 13px;
  border-bottom: 1px solid #e5eaf3;
}
.compliance-section h4 {
  margin: 0;
  color: var(--compliance-ink, #17213b);
  font-size: 15px;
  line-height: 1.55;
}
.compliance-section small {
  color: var(--compliance-muted, var(--pharma-muted));
}
.compliance-run-section {
  border-color: #cddbf2;
  border-left: 4px solid #3159c8;
  background: linear-gradient(115deg, rgba(49, 89, 200, 0.055), #fff 38%);
  box-shadow: 0 8px 24px rgba(49, 89, 200, 0.07);
}
.compliance-results-section {
  border-color: #c9e5dc;
  border-left: 4px solid #16826a;
  background: linear-gradient(115deg, rgba(22, 130, 106, 0.05), #fff 38%);
  box-shadow: 0 8px 24px rgba(22, 130, 106, 0.07);
}
.compliance-signoff-section {
  border-color: #dacff1;
  border-left: 4px solid #6546a8;
  background: linear-gradient(115deg, rgba(101, 70, 168, 0.055), #fff 38%);
  box-shadow: 0 10px 28px rgba(63, 42, 108, 0.09);
}
.compliance-signoff-section > header h4 {
  color: #3f2a6c;
  font-size: 16px;
}
.compliance-step-panel .keyword-table-wrap {
  overflow: hidden;
  border: 1px solid #e0e6f0;
  border-radius: 12px;
}
.compliance-step-panel .keyword-table th {
  color: #50607c;
  background: #f4f7fb;
  font-size: 12px;
  font-weight: 750;
}
.compliance-step-panel .keyword-table td {
  line-height: 1.55;
}
.compliance-step-panel .filter-risk-group {
  padding-top: 4px;
}
.compliance-step-panel .filter-risk-group h5 {
  margin: 12px 0 9px;
  color: #293752;
  font-size: 14px;
}
.compliance-step-panel .risk-list {
  gap: 10px;
}
.compliance-step-panel .risk-item {
  padding: 13px 14px;
  border: 1px solid transparent;
  border-left-width: 3px;
  line-height: 1.6;
}
.compliance-step-panel .risk-block {
  border-color: #f1cbd0;
}
.compliance-step-panel .risk-caution {
  border-color: #ead9a8;
}
.compliance-step-panel .risk-replace {
  border-color: #c8dfef;
}
.compliance-step-panel .risk-pass {
  border-color: #c7e6d7;
}
.compliance-ticket {
  display: grid;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f7f8fb;
  font-size: 12px;
}
.compliance-ticket header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.compliance-ticket p {
  margin: 0;
}
.ticket-answer {
  padding: 6px 9px;
  border-radius: 7px;
  background: #edf9f4;
}
.compliance-record {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  overflow: hidden;
  border: 1px solid #dfe5f0;
  border-radius: 12px;
  background: #dfe5f0;
  font-size: 12px;
}
.compliance-record > div {
  min-width: 0;
  padding: 11px 13px;
  background: rgba(255, 255, 255, 0.96);
  line-height: 1.6;
}
.compliance-record b {
  display: inline-block;
  min-width: 84px;
  color: #596780;
  font-weight: 700;
}
.compliance-sign-form {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  align-items: center;
  padding: 16px;
  border: 1px solid #e1d9f0;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.78);
}
.compliance-signoff-section .zr-confirm-checks {
  padding: 15px 16px;
  border: 1px solid #e5def1;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
}
.compliance-signoff-section .zr-confirm-checks > b {
  display: block;
  margin-bottom: 9px;
  color: #3f2a6c;
  line-height: 1.6;
}
.compliance-signoff-section .zr-confirm-checks-grid {
  gap: 3px 18px;
}
.compliance-signoff-section .risk-item {
  margin-top: 10px;
}
.zr-panels {
  margin-top: 10px;
}
.zr-layer-grid,
.zr-rule-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}
.zr-layer,
.zr-rule {
  border: 1px solid var(--pharma-border, rgba(0, 0, 0, 0.12));
  border-radius: 8px;
  padding: 10px 12px;
}
.zr-layer h5,
.zr-rule h5,
.zr-subtitle {
  margin: 0 0 6px;
  font-size: 14px;
}
.zr-subtitle {
  margin-top: 14px;
}
.zr-layer ul,
.zr-rule ul {
  margin: 0;
  padding-left: 18px;
  line-height: 1.8;
}
.zr-rule--red {
  border-left: 4px solid rgb(var(--v-theme-error));
}
.zr-rule--amber {
  border-left: 4px solid rgb(var(--v-theme-warning));
}
.zr-rule--green {
  border-left: 4px solid rgb(var(--v-theme-success));
}
.zr-confirm-checks {
  margin: 10px 0;
}
.zr-confirm-checks-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
}
.zr-confirm-hint {
  color: rgb(var(--v-theme-warning));
}
.zr-consult-intro {
  margin-bottom: 12px;
  color: var(--pharma-muted);
}
.zr-consult-grid {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 20px;
}
.zr-consult-qr {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  text-align: center;
}
.zr-consult-qr img {
  width: 240px;
  height: 240px;
  object-fit: contain;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
}
.zr-consult-qr-missing {
  width: 240px;
  height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  font-size: 12px;
  padding: 12px;
}
.zr-consult-ai {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.zr-consult-actions {
  display: flex;
  gap: 8px;
}
.zr-consult-answer pre {
  white-space: pre-wrap;
  font-family: inherit;
  margin: 0 0 6px;
  line-height: 1.7;
}
@media (max-width: 760px) {
  .zr-consult-grid,
  .zr-confirm-checks-grid {
    grid-template-columns: 1fr;
  }
}
.compliance-sign-form .v-checkbox {
  grid-column: 1 / -1;
}
.approval-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 20px;
}
.approval-grid article {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  padding: 15px;
  border: 1px solid var(--pharma-border);
  border-radius: 13px;
}
.approval-grid article span {
  grid-column: 2;
  color: var(--pharma-muted);
  font-size: 11px;
}
.approval-grid article .v-btn {
  grid-column: 3;
  grid-row: 1/3;
}
.approval-grid article.done {
  border-color: #bce4d0;
  background: #f2fbf6;
}
.final-sign-form {
  display: grid;
  gap: 10px;
}
.final-sign-fields {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  align-items: start;
}
.final-checklist-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}
.final-submit-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
  padding-top: 8px;
  border-top: 1px dashed rgba(0, 0, 0, 0.12);
}
.final-missing {
  color: rgb(var(--v-theme-warning));
  font-size: 13px;
}
.final-ready {
  color: rgb(var(--v-theme-success));
  font-size: 13px;
}
.final-checklist {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
}
.audit-chain-table {
  overflow-x: auto;
  margin-top: 8px;
}
.audit-chain-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.audit-chain-table th,
.audit-chain-table td {
  border: 1px solid #e3e6ec;
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
}
.audit-chain-table th {
  background: #f5f6f8;
  font-weight: 600;
  white-space: nowrap;
}
.audit-chain-table tr.gap td:first-child {
  border-left: 3px solid #f0a020;
}
.export-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 12px;
  font-size: 13px;
}
.export-meta h5 {
  margin: 0 0 6px;
  font-size: 13px;
}
.export-meta ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
.export-meta li {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.export-meta p {
  margin: 0 0 6px;
}
.reuse-hint {
  color: #2f7a52;
}
.export-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.final-reviews {
  flex-basis: 100%;
  font-size: 12px;
}
.final-reviews p {
  margin: 4px 0 0;
  color: var(--pharma-muted);
}
.compliance-boundary {
  color: var(--pharma-muted);
  font-size: 11px;
}
.empty-state {
  padding: 40px 36px;
  border: 1.5px dashed #cfd6e4;
  border-radius: 16px;
  color: var(--pharma-muted);
  background: radial-gradient(
      100% 120% at 50% 0%,
      rgba(42, 82, 190, 0.05),
      transparent 60%
    ),
    var(--pharma-soft);
  box-shadow: inset 0 2px 6px rgba(20, 32, 56, 0.035);
  text-align: center;
}
.empty-state.compact {
  padding: 18px;
}
.filter-inventory-item {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--pharma-border);
  border-radius: 12px;
  background: #fff;
}
.filter-inventory-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.filter-inventory-flags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
}
.filter-risk-group h5 {
  margin: 12px 0 8px;
  font-size: 13px;
  font-weight: 700;
}
@media (max-width: 900px) {
  .filter-inventory-grid {
    grid-template-columns: 1fr;
  }
}
.source-audit-panels {
  margin-top: 24px;
  border: 1px solid var(--pharma-border);
  border-radius: 14px;
  overflow: hidden;
}
.ocr-pages {
  display: grid;
  gap: 14px;
}
.ocr-pages article {
  border: 1px solid var(--pharma-border);
  border-radius: 14px;
  overflow: hidden;
}
.ocr-pages header {
  display: flex;
  justify-content: space-between;
  padding: 11px 15px;
  background: #f6f7fa;
}
.ocr-pages pre {
  max-height: 420px;
  margin: 0;
  padding: 18px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font:
    13px/1.8 ui-monospace,
    SFMono-Regular,
    Consolas,
    monospace;
}
.audit-list {
  padding: 8px 4px;
}
.audit-item {
  display: flex;
  gap: 12px;
  padding: 0 0 18px;
}
.audit-item > span {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 50%;
  color: white;
  background: var(--pharma-primary);
}
.audit-item p,
.audit-item small {
  margin: 4px 0 0;
  color: var(--pharma-muted);
  font-size: 12px;
}
.workflow-controls {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-top: 24px;
  padding: 18px 20px;
  border: 1px solid var(--pharma-border);
  border-radius: 16px;
  background: linear-gradient(180deg, var(--pharma-soft), rgb(var(--v-theme-surface)));
  box-shadow: var(--shadow-1);
}
.workflow-controls > div {
  display: flex;
  flex: 1;
  gap: 10px;
}
.workflow-controls > div:last-child {
  flex: none;
  align-items: center;
}
.history-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.history-heading-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.history-card {
  position: relative;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--pharma-border);
  border-radius: 16px;
  background: rgb(var(--v-theme-surface));
  box-shadow: var(--shadow-1);
  overflow: hidden;
  transition: transform 0.22s ease, box-shadow 0.22s ease,
    border-color 0.22s ease;
}
.history-card::before {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: linear-gradient(90deg, var(--pharma-primary), var(--pharma-teal));
  opacity: 0;
  transition: opacity 0.22s ease;
}
.history-card:hover {
  border-color: rgba(42, 82, 190, 0.3);
  box-shadow: var(--shadow-3);
  transform: translateY(-3px);
}
.history-card:hover::before {
  opacity: 1;
}
.history-card-main {
  display: flex;
  width: 100%;
  padding: 18px 18px 14px;
  flex-direction: column;
  gap: 6px;
  border: 0;
  color: inherit;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.history-card-main > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--pharma-primary);
}
.history-card-main span,
.history-card-main small {
  overflow: hidden;
  max-width: 100%;
  color: var(--pharma-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-card-actions {
  display: flex;
  gap: 8px;
  padding: 12px 18px 16px;
  border-top: 1px solid var(--pharma-border);
  background: var(--pharma-soft);
  flex-wrap: wrap;
}
.history-empty {
  padding: 36px;
  border: 1.5px dashed #cfd6e4;
  border-radius: 16px;
  color: var(--pharma-muted);
  background: var(--pharma-soft);
  text-align: center;
}
@media (max-width: 1250px) {
  .workflow-strip {
    grid-template-columns: repeat(4, 1fr);
  }
  .hero-molecule {
    display: none;
  }
  .scene-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .approval-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 900px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }
  .history-grid,
  .field-card-grid,
  .dimension-grid,
  .safety-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .result-toolbar,
  .step-intro {
    align-items: flex-start;
    flex-direction: column;
  }
  .workflow-strip {
    margin: 0 0 28px;
  }
  .surface-card + .surface-card {
    border-left: 0;
    border-top: 1px solid var(--pharma-border);
  }
  .workflow-controls {
    flex-direction: column;
  }
}
@media (max-width: 650px) {
  .pharma-page {
    padding: 14px 12px 36px;
  }
  .hero-panel {
    padding: 24px 22px 30px;
    flex-direction: column;
    border-radius: 12px 12px 0 0;
  }
  .hero-state {
    min-width: 0;
    max-width: none;
    padding: 18px 0 0;
    border-top: 1px solid rgba(255, 255, 255, 0.24);
    border-left: 0;
  }
  .hero-state-step b {
    font-size: 40px;
  }
  .result-toolbar {
    margin: 0;
    padding: 0 0 18px;
  }
  .result-toolbar-step {
    width: auto;
    min-height: 0;
    padding-bottom: 8px;
    border-right: 0;
    border-bottom: 1px solid var(--pharma-border);
    align-items: flex-start;
  }
  .result-toolbar-step b {
    font-size: 22px;
  }
  .result-stats {
    flex-wrap: wrap;
  }
  .workflow-strip,
  .form-grid,
  .field-card-grid,
  .dimension-grid,
  .safety-grid,
  .scene-grid,
  .history-grid {
    grid-template-columns: 1fr;
  }
  .workflow-step:not(.active):not(.done) {
    display: none;
  }
  .surface-card,
  .result-section,
  .history-section {
    padding: 28px 6px;
  }
  .upload-actions,
  .keyword-actions,
  .step-actions,
  .platform-picker,
  .workflow-controls > div {
    align-items: stretch;
    flex-direction: column;
  }
  .platform-picker {
    display: flex;
  }
  .batch-generator-panel {
    gap: 10px;
    padding: 16px 0;
    border-radius: 0;
  }
  .batch-generator-panel :deep(.v-text-field) {
    max-width: none !important;
  }
  .batch-report {
    padding: 0 0 20px;
    border-radius: 0;
  }
  .batch-report-hero {
    margin: 0 0 24px;
    padding: 24px 18px 21px;
  }
  .batch-report-hero h3 {
    font-size: 24px;
  }
  .batch-section-title {
    align-items: flex-start;
    margin-top: 24px;
    font-size: 16px;
    line-height: 1.55;
  }
  .batch-topic-group {
    padding: 14px 12px 10px;
  }
  .batch-topic-group li {
    padding-block: 10px;
  }
  .topic-time {
    display: block;
    width: 100%;
    margin: 7px 0 0 !important;
  }
  .batch-topic-actions,
  .batch-section-heading,
  .batch-platform-head {
    align-items: stretch;
    flex-direction: column;
  }
  .batch-topic-actions .v-btn,
  .batch-section-heading .v-btn,
  .batch-platform-head .v-btn {
    width: 100%;
  }
  .batch-platform-head > span:first-child {
    margin-right: 0;
  }
  .batch-sample,
  .batch-demo {
    margin: 0;
    padding: 18px 0;
  }
  .batch-demo-body {
    padding: 8px 0 8px 13px;
  }
  .content-image-grid,
  .content-image-grid--current {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    padding: 10px;
  }
  .current-content-image-action {
    width: 100%;
  }
  .keyword-actions .v-text-field {
    width: 100%;
  }
  .result-stats {
    width: 100%;
    overflow: auto;
  }
  .step-actions.split {
    align-items: stretch;
  }
  .risk-item-head,
  .risk-review,
  .compliance-sign-form,
  .compliance-record,
  .final-sign-fields {
    grid-template-columns: 1fr;
  }
  .risk-item-line,
  .risk-review {
    padding-left: 0;
  }
  .competitor-step-panel,
  .compliance-step-panel {
    padding: 0 0 4px;
    border-radius: 0;
  }
  .competitor-step-panel > .step-intro,
  .compliance-step-panel > .step-intro {
    margin: 0 0 22px;
    padding: 0 0 16px 14px;
    border-radius: 0;
  }
  .compliance-section {
    padding: 16px 14px;
  }
  .compliance-sign-form {
    padding: 12px;
  }
}
/* 修复选择/文件框文字重影：VSelect 把选中值同时渲染在 .v-select__selection 和内部 input 的 value 里 */
.upload-row :deep(.v-select .v-field__input > input[type="text"]),
.literature-kb :deep(.v-select .v-field__input > input[type="text"]),
.step-actions :deep(.v-select .v-field__input > input[type="text"]),
.dimension-source-bar :deep(.v-select .v-field__input > input[type="text"]),
.workflow-controls :deep(.v-select .v-field__input > input[type="text"]) {
  opacity: 0;
  position: absolute;
  width: 100%;
  pointer-events: none;
  caret-color: transparent;
}
.upload-row :deep(.v-file-input input[type="file"]) {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
  z-index: 1;
}
.literature-kb .v-select {
  margin-top: 4px;
}
</style>
