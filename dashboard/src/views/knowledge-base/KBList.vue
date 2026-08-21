<template>
  <div class="kb-list-page">
    <div class="kb-list-toolbar">
      <div class="kb-list-summary">
        <v-icon icon="mdi-bookshelf" size="20" />
        <span class="kb-list-summary__value">{{ total || kbList.length }}</span>
        <span>{{ t('list.title') }}</span>
      </div>

      <div class="kb-list-toolbar__actions">
        <v-btn
          prepend-icon="mdi-refresh"
          color="primary"
          variant="tonal"
          class="kb-toolbar-btn"
          :loading="loading"
          @click="loadKnowledgeBases(true)"
        >
          {{ t('list.refresh') }}
        </v-btn>
        <v-btn
          prepend-icon="mdi-plus"
          color="primary"
          variant="flat"
          class="kb-toolbar-btn kb-toolbar-btn--primary"
          @click="showCreateDialog = true"
        >
          {{ t('list.create') }}
        </v-btn>
      </div>
    </div>

    <div v-if="loading && kbList.length === 0" class="loading-container">
      <v-progress-circular indeterminate color="primary" size="42" width="3" />
      <p>{{ t('list.loading') }}</p>
    </div>

    <div v-else-if="kbList.length > 0" class="kb-list">
      <OutlinedActionListItem
        v-for="kb in kbList"
        :key="kb.kb_id"
        :title="kb.kb_name"
        :clickable="!kb.init_error"
        @click="navigateToDetail(kb.kb_id)"
      >
        <template #title-prepend>
          <span class="kb-list-emoji">{{ kb.emoji || '📚' }}</span>
        </template>

        <template #title-extra>
          <v-chip
            v-if="kb.init_error"
            color="error"
            size="x-small"
            variant="tonal"
          >
            {{ t('list.initError') }}
          </v-chip>
        </template>

        <div v-if="!kb.init_error" class="kb-description text-body-2 text-medium-emphasis">
          {{ kb.description || '暂无描述' }}
        </div>

        <div v-if="kb.init_error" class="kb-error-panel">
            <div class="kb-error-title">
              <v-icon size="16" color="error">mdi-close-circle</v-icon>
              <span>{{ t('list.initError') }}</span>
            </div>
            <div class="kb-error-detail" :title="kb.init_error">{{ kb.init_error }}</div>
        </div>

        <div class="kb-stats" v-if="!kb.init_error">
            <div class="stat-item">
              <v-icon size="small">mdi-file-document</v-icon>
              <span>{{ kb.doc_count || 0 }} {{ t('list.documents') }}</span>
            </div>
            <div class="stat-item">
              <v-icon size="small">mdi-text-box</v-icon>
              <span>{{ kb.chunk_count || 0 }} {{ t('list.chunks') }}</span>
            </div>
        </div>

        <template #actions>
          <v-tooltip v-if="!kb.init_error" :text="t('card.edit')" location="top">
            <template #activator="{ props }">
              <v-btn
                v-bind="props"
                icon="mdi-pencil-outline"
                variant="text"
                size="small"
                class="list-action-icon-btn list-action-icon-btn--edit"
                @click.stop="editKB(kb)"
              />
            </template>
          </v-tooltip>

          <v-tooltip :text="t('card.delete')" location="top">
            <template #activator="{ props }">
              <v-btn
                v-bind="props"
                icon="mdi-delete-outline"
                variant="text"
                size="small"
                class="list-action-icon-btn list-action-icon-btn--delete"
                @click.stop="confirmDelete(kb)"
              />
            </template>
          </v-tooltip>
        </template>
      </OutlinedActionListItem>

      <v-pagination
        v-if="total > pageSize"
        v-model="page"
        :length="Math.ceil(total / pageSize)"
        :total-visible="7"
        class="mt-4"
        @update:model-value="loadKnowledgeBases()"
      />
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <div class="empty-state__icon">
        <v-icon size="34">mdi-book-open-variant</v-icon>
      </div>
      <h2>{{ t('list.empty') }}</h2>
      <p>创建一个知识库后，可以集中管理文档、分块和检索配置。</p>
      <v-btn prepend-icon="mdi-plus" color="primary" variant="tonal" size="large"
        @click="showCreateDialog = true">
        {{ t('list.create') }}
      </v-btn>
    </div>

    <!-- 创建/编辑对话框 -->
    <v-dialog v-model="showCreateDialog" max-width="640px" persistent>
      <v-card class="kb-form-card">
        <div class="kb-form-header">
          <div class="kb-form-header__main">
            <div>
              <h3>{{ editingKB ? t('edit.title') : t('create.title') }}</h3>
              <p>设置名称与描述。</p>
            </div>
          </div>
          <v-btn icon="mdi-close" variant="tonal" class="kb-form-close" @click="closeCreateDialog" />
        </div>

        <v-card-text class="kb-form-body">
          <button type="button" class="kb-icon-selector" @click="showEmojiPicker = true">
            <span class="kb-icon-selector__preview">{{ formData.emoji }}</span>
            <span class="kb-icon-selector__text">
              <strong>{{ t('create.emojiLabel') }}</strong>
              <small>用于列表展示</small>
            </span>
            <v-icon icon="mdi-chevron-right" size="18" />
          </button>

          <v-form ref="formRef" class="kb-form-fields" @submit.prevent="submitForm">
            <v-text-field v-model="formData.kb_name" :label="t('create.nameLabel')"
              :placeholder="t('create.namePlaceholder')" variant="outlined"
              :rules="[v => !!v || t('create.nameRequired')]" required class="kb-form-input" hint="后续如修改知识库名称，需重新在配置文件更新。" persistent-hint />

            <v-textarea v-model="formData.description" :label="t('create.descriptionLabel')"
              :placeholder="t('create.descriptionPlaceholder')" variant="outlined" rows="3" class="kb-form-input" />
          </v-form>
        </v-card-text>

        <v-card-actions class="kb-form-actions">
          <v-spacer />
          <v-btn variant="tonal" class="kb-form-cancel" @click="closeCreateDialog">
            {{ t('create.cancel') }}
          </v-btn>
          <v-btn color="primary" variant="flat" class="kb-form-submit" @click="submitForm" :loading="saving">
            {{ editingKB ? t('edit.submit') : t('create.submit') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Emoji 选择器对话框 -->
    <v-dialog v-model="showEmojiPicker" max-width="500px">
      <v-card>
        <v-card-title class="text-h3 pa-4 pb-0 pl-6">{{ t('emoji.title') }}</v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <div v-for="category in emojiCategories" :key="category.key" class="mb-4">
            <p class="text-subtitle-2 mb-2">{{ t(`emoji.categories.${category.key}`) }}</p>
            <div class="emoji-grid">
              <div v-for="emoji in category.emojis" :key="emoji" class="emoji-item" @click="selectEmoji(emoji)">
                {{ emoji }}
              </div>
            </div>
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="showEmojiPicker = false">
            {{ t('emoji.close') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 删除确认对话框 -->
    <v-dialog v-model="showDeleteDialog" max-width="450px" persistent>
      <v-card>
        <v-card-title class="text-h3 pa-4 pb-0 pl-6">{{ t('delete.title') }}</v-card-title>
        <v-divider />
        <v-card-text class="pa-6">
          <p>{{ t('delete.confirmText', { name: deleteTarget?.kb_name || '' }) }}</p>
          <v-alert type="error" variant="tonal" density="compact" class="mt-4">
            {{ t('delete.warning') }}
          </v-alert>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="cancelDelete">
            {{ t('delete.cancel') }}
          </v-btn>
          <v-btn color="error" variant="tonal" @click="deleteKB" :loading="deleting">
            {{ t('delete.confirm') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 消息提示 -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color">
      {{ snackbar.text }}
    </v-snackbar>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { knowledgeApi } from '@/api/v1'
import { useModuleI18n } from '@/i18n/composables'
import OutlinedActionListItem from '@/components/shared/OutlinedActionListItem.vue'

const { tm: t } = useModuleI18n('features/knowledge-base/index')
const router = useRouter()

// 状态
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const kbList = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 对话框
const showCreateDialog = ref(false)
const showEmojiPicker = ref(false)
const showDeleteDialog = ref(false)

// Snackbar 通知
const snackbar = ref({
  show: false,
  text: '',
  color: 'success'
})

// 表单
const formRef = ref()
const editingKB = ref<any>(null)
const deleteTarget = ref<any>(null)
const formData = ref({
  kb_name: '',
  description: '',
  emoji: '📚',
  embedding_provider_id: null,
  rerank_provider_id: null
})

// Emoji 分类
const emojiCategories = [
  {
    key: 'books',
    emojis: ['📚', '📖', '📕', '📗', '📘', '📙', '📓', '📔', '📒', '📑', '🗂️', '📂', '📁', '🗃️', '🗄️']
  },
  {
    key: 'emotions',
    emojis: ['😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '🙃', '😉', '😊', '😇', '🥰', '😍']
  },
  {
    key: 'objects',
    emojis: ['💡', '🔬', '🔭', '🗿', '🏆', '🎯', '🎓', '🔑', '🔒', '🔓', '🔔', '🔕', '🔨', '🛠️', '⚙️']
  },
  {
    key: 'symbols',
    emojis: ['❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '🤍', '🤎', '⭐', '🌟', '✨', '💫', '⚡', '🔥']
  }
]

// 加载知识库列表
const loadKnowledgeBases = async (refreshStats = false) => {
  loading.value = true
  try {
    if (refreshStats) {
      page.value = 1
    }
    const response = await knowledgeApi.list({
      page: page.value,
      page_size: pageSize.value,
      refresh_stats: refreshStats
    })
    if (response.data.status === 'ok') {
      const data = response.data.data
      kbList.value = data.items || []
      total.value = data.total || 0
    } else {
      showSnackbar(response.data.message || t('messages.loadError'), 'error')
    }
  } catch (error) {
    console.error('Failed to load knowledge bases:', error)
    showSnackbar(t('messages.loadError'), 'error')
  } finally {
    loading.value = false
  }
}

// 导航到详情页
const navigateToDetail = (kbId: string) => {
  router.push({ name: 'NativeKBDetail', params: { kbId } })
}

// 编辑知识库
const editKB = (kb: any) => {
  editingKB.value = kb
  formData.value = {
    kb_name: kb.kb_name,
    description: kb.description || '',
    emoji: kb.emoji || '📚',
    embedding_provider_id: kb.embedding_provider_id,
    rerank_provider_id: kb.rerank_provider_id
  }
  showCreateDialog.value = true
}

// 确认删除
const confirmDelete = (kb: any) => {
  deleteTarget.value = kb
  showDeleteDialog.value = true
}

// 取消删除
const cancelDelete = () => {
  showDeleteDialog.value = false
  deleteTarget.value = null
}

// 删除知识库
const deleteKB = async () => {
  if (!deleteTarget.value) return

  deleting.value = true
  try {
    const response = await knowledgeApi.delete(deleteTarget.value.kb_id)

    console.log('Delete response:', response.data) // 调试日志

    if (response.data.status === 'ok') {
      showSnackbar(t('messages.deleteSuccess'))
      if (kbList.value.length === 1 && page.value > 1) {
        page.value -= 1
      }
      await loadKnowledgeBases()
      showDeleteDialog.value = false
      deleteTarget.value = null
    } else {
      showSnackbar(response.data.message || t('messages.deleteFailed'), 'error')
    }
  } catch (error) {
    console.error('Failed to delete knowledge base:', error)
    showSnackbar(t('messages.deleteFailed'), 'error')
  } finally {
    deleting.value = false
  }
}

// 提交表单
const submitForm = async () => {
  const { valid } = await formRef.value.validate()
  if (!valid) return

  saving.value = true
  try {
    const payload = {
      kb_name: formData.value.kb_name,
      description: formData.value.description,
      emoji: formData.value.emoji,
      embedding_provider_id: formData.value.embedding_provider_id,
      rerank_provider_id: formData.value.rerank_provider_id
    }

    let response
    if (editingKB.value) {
      response = await knowledgeApi.update(editingKB.value.kb_id, payload)
    } else {
      response = await knowledgeApi.create(payload)
    }

    if (response.data.status === 'ok') {
      showSnackbar(editingKB.value ? t('messages.updateSuccess') : t('messages.createSuccess'))
      closeCreateDialog()
      await loadKnowledgeBases()
    } else {
      showSnackbar(response.data.message || (editingKB.value ? t('messages.updateFailed') : t('messages.createFailed')), 'error')
    }
  } catch (error) {
    console.error('Failed to save knowledge base:', error)
    showSnackbar(editingKB.value ? t('messages.updateFailed') : t('messages.createFailed'), 'error')
  } finally {
    saving.value = false
  }
}

// 关闭创建对话框
const closeCreateDialog = () => {
  showCreateDialog.value = false
  editingKB.value = null
  formData.value = {
    kb_name: '',
    description: '',
    emoji: '📚',
    embedding_provider_id: null,
    rerank_provider_id: null
  }
  formRef.value?.reset()
}

// 选择 emoji
const selectEmoji = (emoji: string) => {
  formData.value.emoji = emoji
  showEmojiPicker.value = false
}

// 显示通知
const showSnackbar = (text: string, color: string = 'success') => {
  snackbar.value.text = text
  snackbar.value.color = color
  snackbar.value.show = true
}

onMounted(() => {
  loadKnowledgeBases(true)  // 首次加载时刷新统计信息
})
</script>

<style scoped>
.kb-list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  width: 100%;
}

.kb-list-toolbar {
  align-items: center;
  background: linear-gradient(180deg, #f8fcff 0%, #ffffff 100%);
  border: 1px solid #d9ebf7;
  border-radius: 14px;
  display: flex;
  gap: 14px;
  justify-content: space-between;
  padding: 12px 14px;
}

.kb-list-summary {
  align-items: center;
  color: #416071;
  display: inline-flex;
  font-size: 0.9rem;
  gap: 8px;
  min-width: 0;
}

.kb-list-summary :deep(.v-icon) {
  color: #2f96cf;
}

.kb-list-summary__value {
  color: #15384c;
  font-size: 1.05rem;
  font-weight: 800;
}

.kb-list-toolbar__actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.kb-toolbar-btn {
  border-radius: 10px;
  font-weight: 700;
  letter-spacing: 0;
}

.kb-toolbar-btn--primary {
  box-shadow: 0 8px 18px rgba(47, 150, 207, 0.18);
}

.kb-list {
  background: #ffffff;
  border: 1px solid #dceaf3;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow: hidden;
}

.kb-list :deep(.outlined-action-list-item) {
  background: #ffffff;
  border: 0;
  border-bottom: 1px solid #e4eef5;
  border-radius: 0 !important;
  box-shadow: none;
  transition: background-color 0.18s ease, box-shadow 0.18s ease;
}

.kb-list :deep(.outlined-action-list-item:last-of-type) {
  border-bottom: 0;
}

.kb-list :deep(.outlined-action-list-item:hover),
.kb-list :deep(.outlined-action-list-item:focus-within) {
  background: #f6fbff;
  box-shadow: inset 3px 0 0 #49a3d6;
}

.kb-list :deep(.outlined-action-list-item__main) {
  min-height: 112px;
  padding: 18px 20px;
}

.kb-list :deep(.outlined-action-list-item__content) {
  flex: 1 1 auto;
}

.kb-list :deep(.outlined-action-list-item__header) {
  gap: 10px;
  margin-bottom: 8px;
}

.kb-list :deep(.outlined-action-list-item__title) {
  color: #162331;
  font-size: 1.05rem;
}

.kb-list :deep(.outlined-action-list-item__actions) {
  border-left: 1px solid #e2edf4;
  padding-left: 14px;
}

.kb-list-emoji {
  align-items: center;
  background: #eaf6fd;
  border: 1px solid #cce8f8;
  border-radius: 10px;
  color: #2f96cf;
  display: inline-flex;
  font-size: 1.25rem;
  height: 38px;
  justify-content: center;
  line-height: 1;
  width: 38px;
}

.kb-description {
  color: #5b6b78;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
  font-size: 0.875rem;
  line-height: 1.5;
  overflow: hidden;
}

.kb-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.kb-error-panel {
  width: 100%;
  text-align: left;
  background: rgba(var(--v-theme-error), 0.08);
  border: 1px solid rgba(var(--v-theme-error), 0.18);
  border-radius: 10px;
  padding: 10px 12px;
}

.kb-error-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8rem;
  font-weight: 600;
  color: rgb(var(--v-theme-error));
  margin-bottom: 4px;
}

.kb-error-detail {
  font-size: 0.78rem;
  line-height: 1.35;
  color: rgba(var(--v-theme-on-surface), 0.82);
  word-break: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.stat-item {
  background: #f7fafc;
  border: 1px solid #dfeaf1;
  border-radius: 999px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.82rem;
  color: #526776;
  padding: 4px 9px;
}

.list-action-icon-btn {
  border-radius: 10px;
  color: #2879aa;
  height: 34px;
  width: 34px;
}

.list-action-icon-btn--edit {
  background: #eaf6fd;
}

.list-action-icon-btn--edit:hover {
  background: #d9effc;
  color: #1676ad;
}

.list-action-icon-btn--delete {
  background: #fff0f0;
  color: #e54848;
}

.list-action-icon-btn--delete:hover {
  background: #ffe1e1;
  color: #d72f2f;
}

/* 空状态 */
.empty-state,
.loading-container {
  align-items: center;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 320px;
  text-align: center;
  background: linear-gradient(180deg, #fbfdff 0%, #ffffff 100%);
  border: 1px solid #dceaf3;
  border-radius: 16px;
  color: #62717d;
  gap: 12px;
}

.empty-state__icon {
  align-items: center;
  background: #eaf6fd;
  border: 1px solid #cce8f8;
  border-radius: 16px;
  color: #2f96cf;
  display: flex;
  height: 68px;
  justify-content: center;
  width: 68px;
}

.empty-state h2 {
  color: #162331;
  font-size: 1.1rem;
  line-height: 1.3;
  margin: 0;
}

.empty-state p,
.loading-container p {
  color: #647482;
  font-size: 0.9rem;
  margin: 0;
}

.kb-form-card {
  border: 1px solid #d9e9f5;
  border-radius: 18px !important;
  box-shadow: 0 22px 58px rgba(28, 54, 74, 0.2) !important;
  overflow: hidden;
}

.kb-form-header {
  align-items: center;
  background: #f7fbfe;
  border-bottom: 1px solid #dfeaf3;
  display: flex;
  justify-content: space-between;
  padding: 18px 22px;
}

.kb-form-header__main {
  align-items: center;
  display: flex;
  gap: 14px;
  min-width: 0;
}

.kb-form-header h3 {
  color: #162331;
  font-size: 1.15rem;
  font-weight: 800;
  line-height: 1.25;
  margin: 0;
}

.kb-form-header p {
  color: #607381;
  font-size: 0.86rem;
  margin: 5px 0 0;
}

.kb-form-close {
  background: #edf5fa;
  border-radius: 12px;
  color: #335163;
  height: 38px;
  width: 38px;
}

.kb-form-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 22px 22px !important;
}

.kb-icon-selector {
  align-items: center;
  background: #fbfdff;
  border: 1px solid #dbeaf4;
  border-radius: 14px;
  color: #162331;
  cursor: pointer;
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  text-align: left;
  transition: border-color 0.18s ease, background-color 0.18s ease;
  width: 100%;
}

.kb-icon-selector:hover {
  background: #f4faff;
  border-color: #acd8f2;
}

.kb-icon-selector__preview {
  align-items: center;
  background: #eaf6fd;
  border: 1px solid #cbe8f8;
  border-radius: 13px;
  display: flex;
  flex: 0 0 auto;
  font-size: 1.65rem;
  height: 52px;
  justify-content: center;
  line-height: 1;
  width: 52px;
}

.kb-icon-selector__text {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.kb-icon-selector__text strong {
  font-size: 0.95rem;
  font-weight: 800;
}

.kb-icon-selector__text small {
  color: #6b7c88;
  font-size: 0.8rem;
}

.kb-form-fields {
  background: #ffffff;
  border: 1px solid #e1edf5;
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
}

.kb-form-input {
  margin: 0;
}

.kb-form-input :deep(.v-field) {
  background: #ffffff;
  border-radius: 12px;
}

.kb-form-input :deep(.v-field__outline) {
  --v-field-border-opacity: 0.22;
}

.kb-form-input :deep(.v-field--focused .v-field__outline) {
  --v-field-border-opacity: 0.55;
}

.kb-form-input :deep(.v-messages__message) {
  color: #738393;
  font-size: 0.76rem;
  line-height: 1.35;
}

.kb-form-actions {
  background: #fbfdff;
  border-top: 1px solid #e2edf5;
  gap: 10px;
  padding: 14px 18px !important;
}

.kb-form-actions :deep(.v-btn) {
  border-radius: 10px;
  font-weight: 700;
  letter-spacing: 0;
  min-width: 82px;
}

.kb-form-cancel {
  color: #455d6d;
}

.kb-form-submit {
  box-shadow: 0 8px 18px rgba(47, 150, 207, 0.18);
}

/* 加载状态 */
/* .loading-container shared with empty state */
/* Emoji 显示和选择器 */
.emoji-display {
  font-size: 72px;
  cursor: pointer;
  transition: transform 0.2s ease;
  display: inline-block;
  padding: 0px 16px;
  border-radius: 12px;
  background: rgba(var(--v-theme-primary), 0.05);
}

.emoji-display:hover {
  transform: scale(1.1);
  background: rgba(var(--v-theme-primary), 0.1);
}

.emoji-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 8px;
}

.emoji-item {
  font-size: 32px;
  padding: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.emoji-item:hover {
  background: rgba(var(--v-theme-primary), 0.1);
  transform: scale(1.2);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .kb-list-toolbar,
  .kb-list-toolbar__actions {
    align-items: stretch;
    flex-direction: column;
  }

  .kb-list :deep(.outlined-action-list-item__actions) {
    border-left: 0;
    padding-left: 0;
  }

  .emoji-grid {
    grid-template-columns: repeat(6, 1fr);
  }
}
</style>
