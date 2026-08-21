<template>
  <div class="settings-tab">
    <v-card class="settings-panel" variant="flat">
      <div class="settings-panel__header">
        <div>
          <div class="settings-panel__eyebrow">Retrieval Settings</div>
          <h2>{{ t('settings.title') }}</h2>
          <p>控制知识库分块、检索召回和模型提供商配置。</p>
        </div>
        <div class="settings-panel__actions">
          <span>提示：修改检索设置后，将影响后续的知识库查询效果。</span>
          <v-btn
            color="success"
            variant="tonal"
            prepend-icon="mdi-content-save"
            class="settings-save-btn"
            @click="saveSettings"
            :loading="saving"
          >
            {{ t('settings.save') }}
          </v-btn>
        </div>
      </div>

      <v-card-text class="settings-panel__body">
        <v-form ref="formRef" class="settings-form">
          <section class="settings-section">
            <div class="settings-section__header">
              <span class="settings-section__index">01</span>
              <div>
                <h3>{{ t('settings.basic') }}</h3>
                <p>设置文档切分后的片段长度与重叠范围。</p>
              </div>
            </div>

            <div class="settings-grid">
              <v-text-field
                v-model.number="formData.chunk_size"
                :label="t('settings.chunkSize')"
                type="number"
                variant="outlined"
                density="comfortable"
                class="settings-field"
                hide-details="auto"
              />
              <v-text-field
                v-model.number="formData.chunk_overlap"
                :label="t('settings.chunkOverlap')"
                type="number"
                variant="outlined"
                density="comfortable"
                class="settings-field"
                hide-details="auto"
              />
            </div>
          </section>

          <section class="settings-section">
            <div class="settings-section__header">
              <span class="settings-section__index">02</span>
              <div>
                <h3>{{ t('settings.retrieval') }}</h3>
                <p>调整粗召回与精确检索的候选数量。</p>
              </div>
            </div>

            <div class="settings-grid">
              <v-text-field
                v-model.number="formData.top_k_dense"
                :label="t('settings.topKDense')"
                type="number"
                variant="outlined"
                density="comfortable"
                class="settings-field"
                hide-details="auto"
              />
              <v-text-field
                v-model.number="formData.top_k_sparse"
                :label="t('settings.topKSparse')"
                type="number"
                variant="outlined"
                density="comfortable"
                class="settings-field"
                hide-details="auto"
              />
            </div>
          </section>

          <section class="settings-section">
            <div class="settings-section__header">
              <span class="settings-section__index">03</span>
              <div>
                <h3>{{ t('settings.embeddingProvider') }}</h3>
                <p>选择嵌入模型与重排序模型，影响知识库检索效果。</p>
              </div>
            </div>

            <div class="settings-grid">
              <v-select
                v-model="formData.embedding_provider_id"
                :items="embeddingProviders"
                :item-title="item => item.embedding_model || item.id"
                :item-value="'id'"
                :label="t('settings.embeddingProvider')"
                variant="outlined"
                density="comfortable"
                class="settings-field"
                hide-details="auto"
                @update:model-value="handleEmbeddingProviderChange"
                clearable
              />
              <v-select
                v-model="formData.rerank_provider_id"
                :items="rerankProviders"
                :item-title="item => item.rerank_model || item.id"
                :item-value="'id'"
                :label="t('settings.rerankProvider')"
                variant="outlined"
                density="comfortable"
                class="settings-field"
                hide-details="auto"
                clearable
              />
            </div>
          </section>

          <div class="settings-alerts">
            <v-alert type="warning" variant="tonal" class="settings-note settings-note--warning" v-if="showEmbeddingWarning">
              <strong>注意:</strong> 保存后系统会从 Markdown 真源重建全部派生索引，完成前请勿重复修改设置。
            </v-alert>
          </div>
        </v-form>
      </v-card-text>

    </v-card>

    <!-- 消息提示 -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color">
      {{ snackbar.text }}
    </v-snackbar>

    <!-- Embedding Provider修改确认对话框 -->
    <v-dialog v-model="embeddingChangeDialog" max-width="500px" persistent>
      <v-card>
        <v-card-title class="text-h3 pa-4 pb-0 pl-6">
          <v-icon class="mr-2">mdi-alert</v-icon>
          确认修改嵌入模型
        </v-card-title>
        <v-card-text class="pa-6">
          <v-alert type="warning" variant="tonal" class="mb-4">
            <strong>提示:</strong> 修改嵌入模型将触发以下操作:
          </v-alert>
          <ul class="text-body-2">
            <li>系统会从 Markdown 真源重新分块并生成索引</li>
            <li>页面和原始资料不会被删除</li>
            <li>页面较多时保存可能需要一些时间</li>
            <li>清空模型后将切换为纯关键词检索</li>
          </ul>
          <div class="mt-4 text-body-2">
            您确定要将嵌入模型从 <strong>{{ originalEmbeddingProvider || '未配置' }}</strong> 修改为 <strong>{{ pendingEmbeddingProvider || '未配置' }}</strong> 吗?
          </div>
        </v-card-text>
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="cancelEmbeddingChange">
            取消
          </v-btn>
          <v-btn color="warning" variant="tonal" @click="confirmEmbeddingChange">
            确认修改
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { knowledgeApi, providerApi } from '@/api/v1'
import { useModuleI18n } from '@/i18n/composables'

const { tm: t } = useModuleI18n('features/knowledge-base/detail')

const props = defineProps<{
  kb: any
}>()

const emit = defineEmits(['updated'])

// 状态
const saving = ref(false)
const formRef = ref()
const embeddingProviders = ref<any[]>([])
const rerankProviders = ref<any[]>([])
const originalEmbeddingProvider = ref('')
const showEmbeddingWarning = ref(false)
const embeddingChangeDialog = ref(false)
const pendingEmbeddingProvider = ref('')

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

// 表单数据
const formData = ref({
  chunk_size: 800,
  chunk_overlap: 80,
  top_k_dense: 50,
  top_k_sparse: 50,
  embedding_provider_id: '',
  rerank_provider_id: ''
})

// 监听 kb 变化,更新表单
watch(() => props.kb, (kb) => {
  if (kb) {
    formData.value = {
      chunk_size: kb.chunk_size ?? 800,
      chunk_overlap: kb.chunk_overlap ?? 80,
      top_k_dense: kb.top_k_dense || 50,
      top_k_sparse: kb.top_k_sparse || 50,
      // top_m_final: kb.top_m_final || 5,
      embedding_provider_id: kb.embedding_provider_id || '',
      rerank_provider_id: kb.rerank_provider_id || ''
    }
    // 保存原始的embedding provider
    originalEmbeddingProvider.value = kb.embedding_provider_id || ''
  }
}, { immediate: true })

// 加载提供商列表
const loadProviders = async () => {
  try {
    const response = await providerApi.listByProviderType('embedding,rerank')
    if (response.data.status === 'ok') {
      embeddingProviders.value = response.data.data.filter(
        (p: any) => p.provider_type === 'embedding'
      )
      rerankProviders.value = response.data.data.filter(
        (p: any) => p.provider_type === 'rerank'
      )
    }
  } catch (error) {
    console.error('Failed to load providers:', error)
  }
}

// 处理embedding provider变更
const handleEmbeddingProviderChange = (newValue: string | null) => {
  const normalizedValue = newValue || ''
  if (normalizedValue !== originalEmbeddingProvider.value) {
    // 显示警告并需要确认
    showEmbeddingWarning.value = true
    pendingEmbeddingProvider.value = normalizedValue
    embeddingChangeDialog.value = true
  } else {
    showEmbeddingWarning.value = false
  }
}

// 确认修改embedding provider
const confirmEmbeddingChange = () => {
  formData.value.embedding_provider_id = pendingEmbeddingProvider.value
  embeddingChangeDialog.value = false
  showEmbeddingWarning.value = true
}

// 取消修改embedding provider
const cancelEmbeddingChange = () => {
  formData.value.embedding_provider_id = originalEmbeddingProvider.value
  embeddingChangeDialog.value = false
  showEmbeddingWarning.value = false
  pendingEmbeddingProvider.value = ''
}

// 保存设置
const saveSettings = async () => {
  const { valid } = await formRef.value.validate()
  if (!valid) return

  saving.value = true
  try {
    const response = await knowledgeApi.update(props.kb.kb_id, {
      chunk_size: formData.value.chunk_size,
      chunk_overlap: formData.value.chunk_overlap,
      top_k_dense: formData.value.top_k_dense,
      top_k_sparse: formData.value.top_k_sparse,
      // top_m_final: formData.value.top_m_final,
      embedding_provider_id: formData.value.embedding_provider_id || null,
      rerank_provider_id: formData.value.rerank_provider_id
    })

    if (response.data.status === 'ok') {
      showSnackbar(t('settings.saveSuccess'))
      emit('updated')
    } else {
      showSnackbar(response.data.message || t('settings.saveFailed'), 'error')
    }
  } catch (error) {
    console.error('Failed to save settings:', error)
    showSnackbar(t('settings.saveFailed'), 'error')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadProviders()
})
</script>

<style scoped>
.settings-tab {
  animation: fadeIn 0.3s ease;
}

.settings-panel {
  overflow: hidden;
  border: 1px solid #d7e8f3;
  border-radius: 16px;
  background: #fff;
}

.settings-panel__header {
  padding: 22px 28px 18px;
  border-bottom: 1px solid #dbeaf4;
  background: #fff;
}

.settings-panel__eyebrow {
  margin-bottom: 6px;
  color: #5a9dca;
  font-size: 12px;
  font-weight: 650;
}

.settings-panel__header h2 {
  margin: 0;
  color: #172333;
  font-size: 21px;
  font-weight: 800;
  line-height: 1.25;
}

.settings-panel__header p {
  margin: 8px 0 0;
  color: #6a7a89;
  font-size: 14px;
}

.settings-panel__body {
  padding: 18px 28px 4px !important;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.settings-section {
  position: relative;
  padding: 16px 18px;
  border: 1px solid #e0ebf3;
  border-radius: 12px;
  background: #fcfdff;
}

.settings-section__header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.settings-section__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 28px;
  width: 28px;
  height: 28px;
  border: 1px solid #cce5f5;
  border-radius: 8px;
  background: #eef8ff;
  color: #238cca;
  font-size: 12px;
  font-weight: 800;
}

.settings-section__header h3 {
  margin: 0;
  color: #101a27;
  font-size: 16px;
  font-weight: 800;
}

.settings-section__header p {
  margin: 4px 0 0;
  color: #718292;
  font-size: 13px;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 18px;
}

.settings-field :deep(.v-field) {
  border-radius: 10px;
  background: #fff;
}

.settings-field :deep(.v-field__outline) {
  color: #cfe0ec;
}

.settings-field :deep(.v-field--focused .v-field__outline) {
  color: #8fc7ea;
}

.settings-field :deep(.v-label) {
  color: #6f7f8d;
  font-size: 13px;
}

.settings-field :deep(input) {
  color: #142235;
  font-weight: 600;
}

.settings-alerts {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 2px;
}

.settings-note {
  min-height: 44px;
  border: 1px solid #d7edf3;
  border-radius: 10px;
  background: #f7fcfd !important;
  color: #357888;
}

.settings-note--warning {
  border-color: #ffe0a8;
  background: #fff9ed !important;
  color: #9a650d;
}

.settings-panel__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 14px;
  padding: 10px 12px 10px 14px;
  border: 1px solid #cfeadc;
  border-radius: 10px;
  background: #f5fcf8;
}

.settings-panel__actions span {
  color: #28724a;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}

.settings-save-btn {
  min-width: 108px;
  border: 1px solid #addbc0;
  border-radius: 10px;
  font-weight: 700;
}

@media (max-width: 960px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }

  .settings-panel__actions {
    align-items: center;
    justify-content: space-between;
  }

  .settings-save-btn {
    width: 100%;
  }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
