<template>
  <div class="kb-detail-page">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <v-progress-circular indeterminate color="primary" size="64" />
    </div>

    <!-- 主内容 -->
    <div v-else class="kb-content">
      <div class="kb-nav-row">
        <!-- 标签页 -->
        <v-tabs v-model="activeTab" class="kb-tabs" color="primary">
          <v-tab value="overview">
            <v-icon start>mdi-information-outline</v-icon>
            {{ t('tabs.overview') }}
          </v-tab>
          <v-tab value="documents">
            <v-icon start>mdi-file-document-multiple</v-icon>
            {{ t('tabs.documents') }}
            <v-chip class="ml-2" size="small" variant="tonal">{{ kb.doc_count || 0 }}</v-chip>
          </v-tab>
          <v-tab value="graph">
            <v-icon start>mdi-graph-outline</v-icon>
            知识图谱
          </v-tab>
        </v-tabs>

        <v-btn
          color="primary"
          variant="tonal"
          prepend-icon="mdi-download"
          class="kb-export-btn"
          :loading="exporting"
          @click="exportWiki"
        >
          导出知识库
        </v-btn>
      </div>

      <!-- 标签页内容 -->
      <v-window v-model="activeTab" class="kb-tab-window">
        <!-- 概览 -->
        <v-window-item value="overview">
          <div class="overview-layout">
            <section class="overview-card overview-card--identity">
              <div class="overview-card__header">
                <div>
                  <h2>{{ t('overview.title') }}</h2>
                  <p>知识库的基础属性与更新时间</p>
                </div>
                <div class="overview-emoji">{{ kb.emoji || '📚' }}</div>
              </div>

              <div class="identity-list">
                <div class="identity-row">
                  <span class="identity-marker"></span>
                  <div>
                    <div class="identity-label">{{ t('overview.name') }}</div>
                    <div class="identity-value">{{ kb.kb_name }}</div>
                  </div>
                </div>

                <div v-if="kb.description" class="identity-row identity-row--wide">
                  <span class="identity-marker"></span>
                  <div>
                    <div class="identity-label">{{ t('overview.description') }}</div>
                    <div class="identity-value identity-value--muted">{{ kb.description }}</div>
                  </div>
                </div>

                <div class="identity-row">
                  <span class="identity-marker"></span>
                  <div>
                    <div class="identity-label">{{ t('overview.createdAt') }}</div>
                    <div class="identity-value">{{ formatDate(kb.created_at) }}</div>
                  </div>
                </div>

                <div class="identity-row">
                  <span class="identity-marker"></span>
                  <div>
                    <div class="identity-label">{{ t('overview.updatedAt') }}</div>
                    <div class="identity-value">{{ formatDate(kb.updated_at) }}</div>
                  </div>
                </div>
              </div>
            </section>

            <div class="overview-side">
              <section class="overview-card">
                <div class="overview-card__header">
                  <div>
                    <h2>{{ t('overview.stats') }}</h2>
                    <p>当前知识库索引规模</p>
                  </div>
                </div>

                <div class="stat-grid">
                  <div class="stat-box stat-box--docs">
                    <span class="stat-icon">
                      <v-icon size="24">mdi-file-document-outline</v-icon>
                    </span>
                    <div class="stat-value">{{ kb.doc_count || 0 }}</div>
                    <div class="stat-label">{{ t('overview.docCount') }}</div>
                  </div>

                  <div class="stat-box stat-box--chunks">
                    <span class="stat-icon">
                      <v-icon size="24">mdi-text-box-outline</v-icon>
                    </span>
                    <div class="stat-value">{{ kb.chunk_count || 0 }}</div>
                    <div class="stat-label">{{ t('overview.chunkCount') }}</div>
                  </div>
                </div>
              </section>

            </div>
          </div>
        </v-window-item>

        <!-- 文档管理 -->
        <v-window-item value="documents">
          <DocumentsTab :kb-id="kbId" :kb="kb" @refresh="loadKB" />
        </v-window-item>

        <v-window-item value="wiki">
          <WikiTab :kb-id="kbId" :requested-page="requestedWikiPage" @refresh="loadKB" />
        </v-window-item>

        <v-window-item value="graph">
          <KnowledgeGraphTab :kb-id="kbId" @open-page="openWikiPage" />
        </v-window-item>

        <!-- 知识库检索 -->
        <v-window-item value="retrieval">
          <RetrievalTab :kb-id="kbId" />
        </v-window-item>

        <!-- 设置 -->
        <v-window-item value="settings">
          <SettingsTab :kb="kb" @updated="loadKB" />
        </v-window-item>
      </v-window>
    </div>

    <!-- 消息提示 -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color">
      {{ snackbar.text }}
    </v-snackbar>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import { knowledgeApi } from '@/api/v1'
import { useModuleI18n } from '@/i18n/composables'
import DocumentsTab from './components/DocumentsTab.vue'
import KnowledgeGraphTab from './components/KnowledgeGraphTab.vue'
import RetrievalTab from './components/RetrievalTab.vue'
import SettingsTab from './components/SettingsTab.vue'
import WikiTab from './components/WikiTab.vue'

const { tm: t } = useModuleI18n('features/knowledge-base/detail')
const route = useRoute()

const emit = defineEmits<{
  (event: 'title-change', title: string): void
}>()

const kbId = ref(route.params.kbId as string)
const loading = ref(true)
const activeTab = ref('overview')
const kb = ref<any>({})
const exporting = shallowRef(false)

const snackbar = ref({
  show: false,
  text: '',
  color: 'success',
})

const showSnackbar = (text: string, color: string = 'success') => {
  snackbar.value.text = text
  snackbar.value.color = color
  snackbar.value.show = true
}

const requestedWikiPage = ref<{ path: string; requestId: number } | null>(null)
let wikiRequestId = 0

const openWikiPage = (path: string) => {
  wikiRequestId += 1
  requestedWikiPage.value = { path, requestId: wikiRequestId }
  activeTab.value = 'wiki'
}

const exportWiki = async () => {
  if (exporting.value) return
  exporting.value = true
  try {
    const response = await knowledgeApi.exportWiki(kbId.value)
    const disposition = String(response.headers['content-disposition'] || '')
    const fallbackName = `${String(kb.value.kb_name || 'knowledge-base')
      .replace(/[\x00-\x1f/\\:*?"<>|]+/g, '_')
      .replace(/^[ ._]+|[ ._]+$/g, '') || 'knowledge-base'}.zip`
    let filename = fallbackName
    const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
    const quotedMatch = disposition.match(/filename="([^"]+)"/i)
    if (utf8Match?.[1]) {
      try {
        filename = decodeURIComponent(utf8Match[1])
      } catch {
        filename = utf8Match[1]
      }
    } else if (quotedMatch?.[1]) {
      filename = quotedMatch[1]
    }

    const downloadUrl = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = filename
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(downloadUrl)
    showSnackbar('知识库导出成功')
  } catch (error) {
    console.error('Failed to export knowledge base:', error)
    showSnackbar('导出知识库失败', 'error')
  } finally {
    exporting.value = false
  }
}

// 加载知识库详情
const loadKB = async () => {
  try {
    const response = await knowledgeApi.get(kbId.value)
    if (response.data.status === 'ok') {
      kb.value = response.data.data
      emit('title-change', kb.value.kb_name || '')
    } else {
      showSnackbar(response.data.message || '加载失败', 'error')
    }
  } catch (error) {
    console.error('Failed to load knowledge base:', error)
    showSnackbar('加载知识库详情失败', 'error')
  } finally {
    loading.value = false
  }
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(() => {
  loadKB()
})

watch(
  () => kb.value?.kb_name,
  (name) => {
    emit('title-change', name || '')
  },
)
</script>

<style scoped>
.kb-detail-page {
  width: 100%;
}

.kb-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.kb-detail-page :deep(.v-card--variant-outlined) {
  background: rgb(var(--v-theme-surface));
}

.kb-nav-row {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.kb-export-btn {
  flex: 0 0 auto;
  border-radius: 10px;
  font-weight: 700;
  letter-spacing: 0;
}

.kb-tabs {
  background: #ffffff;
  border: 1px solid #dceaf3;
  border-radius: 14px;
  flex: 1 1 auto;
  min-width: 0;
  padding: 1px;
}

.kb-tabs :deep(.v-slide-group__content) {
  gap: 2px;
}

.kb-tabs :deep(.v-tab) {
  border-radius: 10px;
  color: #314756;
  font-weight: 700;
  letter-spacing: 0;
  min-height: 42px;
  padding: 0 14px;
}

.kb-tabs :deep(.v-tab--selected) {
  background: #eaf6fd;
  color: #2385bd;
}

.kb-tabs :deep(.v-tab__slider) {
  display: none;
}

.kb-tabs :deep(.v-chip) {
  background: #eef3f6;
  color: #3f5564;
  font-weight: 700;
}

.kb-tab-window {
  padding: 0;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}

.overview-layout {
  display: grid;
  gap: 20px;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 0.9fr);
}

.overview-side {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.overview-card {
  background: linear-gradient(180deg, #fbfdff 0%, #ffffff 100%);
  border: 1px solid #dceaf3;
  border-radius: 16px;
  padding: 18px 20px;
}

.overview-card--identity {
  min-height: 270px;
}

.overview-card__header {
  align-items: flex-start;
  border-bottom: 1px solid #e5eef5;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 14px;
}

.overview-card__header h2 {
  color: #162331;
  font-size: 1.08rem;
  font-weight: 800;
  line-height: 1.3;
  margin: 0 0 4px;
}

.overview-card__header p {
  color: #687a88;
  font-size: 0.86rem;
  line-height: 1.45;
  margin: 0;
}

.overview-emoji {
  align-items: center;
  background: #eaf6fd;
  border: 1px solid #cce8f8;
  border-radius: 14px;
  display: flex;
  font-size: 1.55rem;
  height: 54px;
  justify-content: center;
  width: 54px;
}

.identity-list {
  display: grid;
  gap: 10px 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.identity-row {
  align-items: flex-start;
  background: #ffffff;
  border: 1px solid #e4eef5;
  border-radius: 12px;
  display: flex;
  gap: 10px;
  min-width: 0;
  padding: 12px 14px;
  transition: background-color 0.18s ease, border-color 0.18s ease;
}

.identity-row:hover {
  background: #f8fcff;
  border-color: #cfe5f2;
}

.identity-row--wide {
  grid-column: 1 / -1;
}

.identity-marker {
  background: #49a3d6;
  border-radius: 999px;
  flex: 0 0 auto;
  height: 7px;
  margin-top: 7px;
  width: 7px;
}

.identity-label {
  color: #72818b;
  font-size: 0.82rem;
  line-height: 1.4;
  margin-bottom: 3px;
}

.identity-value {
  color: #172331;
  font-size: 0.96rem;
  font-weight: 700;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.identity-value--muted {
  color: #4d5e6b;
  font-weight: 600;
}

.stat-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.stat-box {
  background: #ffffff;
  border: 1px solid #dceaf3;
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: 154px;
  padding: 18px;
  text-align: center;
  transition: background-color 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}

.stat-box:hover {
  background: #f7fbfe;
  border-color: #bee2f7;
  transform: translateY(-1px);
}

.stat-icon {
  align-items: center;
  border-radius: 12px;
  display: flex;
  height: 48px;
  justify-content: center;
  margin-bottom: 12px;
  width: 48px;
}

.stat-box--docs .stat-icon {
  background: #eaf6fd;
  color: #2f96cf;
}

.stat-box--chunks .stat-icon {
  background: #eef8f4;
  color: #2b9d70;
}

.stat-value {
  color: #142636;
  font-size: 2rem;
  font-weight: 800;
  line-height: 1.1;
}

.stat-label {
  color: #5e7080;
  font-size: 0.875rem;
  margin-top: 4px;
}

/* 响应式设计 */
@media (max-width: 1080px) {
  .overview-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .kb-title {
    font-size: 1.25rem;
  }

  .kb-nav-row {
    align-items: stretch;
    flex-direction: column;
  }

  .kb-export-btn {
    width: 100%;
  }

  .identity-list,
  .stat-grid {
    grid-template-columns: 1fr;
  }

  .overview-card {
    padding: 16px;
  }
}
</style>
