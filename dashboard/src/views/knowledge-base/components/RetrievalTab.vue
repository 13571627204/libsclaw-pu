<template>
  <div class="retrieval-tab">
    <v-card class="retrieval-panel" variant="flat">
      <div class="retrieval-panel__header">
        <div>
          <h2>{{ t('retrieval.title') }}</h2>
          <p>{{ t('retrieval.subtitle') }}</p>
        </div>
      </div>

      <v-progress-linear v-if="loading" indeterminate color="primary" height="2" />

      <v-card-text class="retrieval-panel__body">
        <!-- 查询输入区域 -->
        <div class="retrieval-query-card">
          <div class="retrieval-query-card__main">
            <v-textarea
              v-model="query"
              :label="t('retrieval.query')"
              :placeholder="t('retrieval.queryPlaceholder')"
              variant="outlined"
              rows="3"
              auto-grow
              clearable
              class="retrieval-query-input"
              hide-details="auto"
            />
          </div>

          <div class="retrieval-query-card__side">
            <div class="retrieval-setting-title">{{ t('retrieval.settings') }}</div>
            <v-text-field
              v-model.number="topK"
              :label="t('retrieval.topK')"
              :hint="t('retrieval.topKHint')"
              type="number"
              variant="outlined"
              density="compact"
              persistent-hint
              class="retrieval-top-k"
            />
            <v-btn
              prepend-icon="mdi-magnify"
              color="primary"
              variant="tonal"
              class="retrieval-search-btn"
              @click="performRetrieval"
            :loading="loading" :disabled="!query || query.trim() === ''">
              {{ loading ? t('retrieval.searching') : t('retrieval.search') }}
            </v-btn>
          </div>
        </div>

        <!-- 检索结果 -->
        <div v-if="hasSearched" class="results-section">
          <div class="results-section__header">
            <h3>{{ t('retrieval.results') }}</h3>
            <v-chip color="primary" variant="tonal" size="small">
              {{ results.length }} {{ t('retrieval.results') }}
            </v-chip>
          </div>

          <!-- 结果列表 -->
          <div v-if="results.length > 0" class="results-list">
            <v-card v-for="(result, index) in results" :key="result.chunk_id" class="result-item" variant="flat">
              <div class="result-item__header">
                <v-chip size="x-small" color="primary" variant="tonal">
                  #{{ index + 1 }}
                </v-chip>
                <span class="result-item__title">
                  {{ t('retrieval.chunk', { index: result.chunk_index }) }}
                </span>
                <div class="result-item__meta">
                  <v-chip size="x-small" variant="tonal">
                    <v-icon start size="small">mdi-file-document</v-icon>
                    {{ result.doc_name }}
                  </v-chip>
                  <v-chip size="x-small" variant="tonal">
                    <v-icon start size="small">mdi-text</v-icon>
                    {{ t('retrieval.charCount', { count: result.char_count }) }}
                  </v-chip>
                </div>
                <v-chip size="x-small" :color="getScoreColor(result.score)">
                  {{ t('retrieval.score') }}: {{ result.score.toFixed(4) }}
                </v-chip>
              </div>

              <v-card-text class="result-item__body">
                <div class="content-box">
                  {{ result.content }}
                </div>
              </v-card-text>
            </v-card>
          </div>

          <!-- 空结果 -->
          <div v-else class="text-center py-12">
            <v-icon size="80" color="grey-lighten-2">mdi-text-box-search-outline</v-icon>
            <p class="text-h6 mt-4 text-medium-emphasis">{{ t('retrieval.noResults') }}</p>
            <p class="text-body-2 text-medium-emphasis">{{ t('retrieval.tryDifferentQuery') }}</p>
          </div>
        </div>
      </v-card-text>
    </v-card>

    <!-- 消息提示 -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color">
      {{ snackbar.text }}
    </v-snackbar>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { knowledgeApi } from '@/api/v1'
import { useModuleI18n } from '@/i18n/composables'

const { tm: t } = useModuleI18n('features/knowledge-base/detail')

const props = defineProps<{
  kbId: string,
}>()

// 状态
const loading = ref(false)
const query = ref('')
const topK = ref(5)
const results = ref<any[]>([])
const hasSearched = ref(false)

const snackbar = ref({
  show: false,
  text: '',
  color: 'success'
})

const showSnackbar = (text: string, color: string = 'success') => {
  snackbar.value.text = text
  snackbar.value.color = color
  snackbar.value.show = true
}

// 执行检索
const performRetrieval = async () => {
  if (!query.value || query.value.trim() === '') {
    showSnackbar(t('retrieval.queryRequired'), 'warning')
    return
  }

  loading.value = true
  hasSearched.value = false

  try {
    const response = await knowledgeApi.retrieve(props.kbId, {
      query: query.value,
      kb_ids: [props.kbId],
      top_k: topK.value
    })

    if (response.data.status === 'ok') {
      results.value = response.data.data.results || []
      hasSearched.value = true

      showSnackbar(t('retrieval.searchSuccess', { count: results.value.length }))
    } else {
      showSnackbar(response.data.message || t('retrieval.searchFailed'), 'error')
    }
  } catch (error) {
    console.error('Retrieval failed:', error)
    showSnackbar(t('retrieval.searchFailed'), 'error')
  } finally {
    loading.value = false
  }
}

// 根据分数获取颜色
const getScoreColor = (score: number) => {
  if (score >= 0.8) return 'success'
  if (score >= 0.6) return 'info'
  if (score >= 0.4) return 'warning'
  return 'error'
}
</script>

<style scoped>
.retrieval-tab {
  animation: fadeIn 0.3s ease;
}

.retrieval-panel {
  overflow: hidden;
  border: 1px solid #dceaf4;
  border-radius: 16px;
  background: #fff;
}

.retrieval-panel__header {
  padding: 22px 26px 18px;
  border-bottom: 1px solid #e2edf5;
  background: #fff;
}

.retrieval-panel__header h2 {
  margin: 0;
  color: #162334;
  font-size: 21px;
  font-weight: 800;
  line-height: 1.25;
}

.retrieval-panel__header p {
  margin: 8px 0 0;
  color: #6e7e8c;
  font-size: 14px;
}

.retrieval-panel__body {
  padding: 18px 26px 24px !important;
}

.retrieval-query-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  gap: 16px;
  align-items: end;
  padding: 16px 18px;
  border: 1px solid #dfeaf3;
  border-radius: 12px;
  background: #fff;
}

.retrieval-query-card__main,
.retrieval-query-card__side {
  min-width: 0;
}

.retrieval-query-card__side {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0;
  border: 0;
  background: transparent;
}

.retrieval-setting-title {
  color: #182536;
  font-size: 14px;
  font-weight: 800;
}

.retrieval-query-input :deep(.v-field),
.retrieval-top-k :deep(.v-field) {
  border-radius: 12px;
  background: #fff;
}

.retrieval-query-input :deep(.v-field__outline),
.retrieval-top-k :deep(.v-field__outline) {
  color: #cfe0eb;
}

.retrieval-query-input :deep(textarea),
.retrieval-top-k :deep(input) {
  color: #152235;
  font-weight: 550;
}

.retrieval-search-btn {
  min-height: 40px;
  border: 1px solid #b9dff4;
  border-radius: 10px;
  font-weight: 700;
}

.results-section {
  margin-top: 20px;
  animation: slideUp 0.4s ease;
}

.results-section__header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.results-section__header h3 {
  margin: 0;
  color: #162334;
  font-size: 17px;
  font-weight: 800;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-item {
  overflow: hidden;
  border: 1px solid #dfeaf3;
  border-radius: 10px;
  background: #fff;
}

.result-item__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid #edf3f7;
  background: #fff;
}

.result-item__title {
  color: #172333;
  font-size: 14px;
  font-weight: 800;
}

.result-item__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  margin-left: 6px;
}

.result-item__body {
  padding: 14px !important;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.content-box {
  background: #fbfcfd;
  border: 1px solid #eef3f6;
  border-radius: 8px;
  padding: 14px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.9rem;
  line-height: 1.6;
  height: 108px;
  overflow-y: auto;
  font-size: 13px;
}

@media (max-width: 960px) {
  .retrieval-query-card {
    grid-template-columns: 1fr;
  }

  .result-item__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .result-item__meta {
    flex-wrap: wrap;
    margin-left: 0;
  }
}
</style>
