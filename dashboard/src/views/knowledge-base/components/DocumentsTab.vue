<template>
  <div class="documents-tab">
    <!-- 操作栏 -->
    <div class="action-bar">
      <div class="document-actions">
        <v-btn
          prepend-icon="mdi-upload"
          color="primary"
          variant="flat"
          class="document-action-btn document-action-btn--primary"
          @click="showUploadDialog = true"
        >
          {{ t('documents.upload') }}
        </v-btn>
        <v-btn
          prepend-icon="mdi-folder-upload-outline"
          color="primary"
          variant="tonal"
          class="document-action-btn"
          :loading="wikiImporting"
          @click="showWikiImportDialog = true"
        >
          导入 Wiki
        </v-btn>
        <div v-if="selectedDocumentIds.length > 0" class="bulk-delete-actions">
          <span class="bulk-selected-count">已选 {{ selectedDocumentIds.length }} 个</span>
          <v-btn
            prepend-icon="mdi-delete-outline"
            color="error"
            variant="tonal"
            class="document-action-btn bulk-delete-btn"
            :loading="batchDeleting"
            @click="showBatchDeleteDialog = true"
          >
            批量删除
          </v-btn>
        </div>
      </div>
      <v-text-field
        v-model="searchQuery"
        prepend-inner-icon="mdi-magnify"
        :placeholder="'搜索文档...'"
        variant="outlined"
        density="compact"
        hide-details
        clearable
        class="document-search"
      />
    </div>

    <!-- 文档列表 -->
    <v-card variant="outlined" class="documents-table-card">
      <v-data-table-server
        :headers="headers"
        :items="documents"
        :loading="loading"
        :items-per-page="pageSize"
        :items-per-page-options="itemsPerPageOptions"
        :page="page"
        :items-length="total"
        v-model="selectedDocumentIds"
        item-value="doc_id"
        show-select
        class="documents-table"
        density="compact"
        @update:page="onPageChange"
        @update:items-per-page="onItemsPerPageChange"
      >
        <template #item.doc_name="{ item }">
          <div class="document-name-cell">
            <span class="document-file-icon">
              <v-icon :color="getFileColor(item.file_type)" size="18">
              {{ getFileIcon(item.file_type) }}
            </v-icon>
            </span>
            <div class="document-name-content">
              <span class="document-name">{{ item.doc_name }}</span>
              <!-- 上传进度 -->
              <div v-if="item.uploading" class="mt-1">
                <div class="text-caption text-medium-emphasis mb-1">
                  {{ getStageText(item.uploadProgress?.stage || 'waiting') }}
                  <span v-if="item.uploadProgress?.current"> ({{ item.uploadProgress.current }} / {{ item.uploadProgress.total }}) </span>
                </div>
                <v-progress-linear :model-value="getUploadPercentage(item)" color="primary" height="4" rounded striped />
              </div>
            </div>
          </div>
        </template>

        <template #item.file_type="{ item }">
          <span class="file-type-pill">{{ item.file_type || '-' }}</span>
        </template>

        <template #item.file_size="{ item }">
          <span class="table-muted-text">{{ formatFileSize(item.file_size) }}</span>
        </template>

        <template #item.created_at="{ item }">
          <span class="table-muted-text">{{ formatDate(item.created_at) }}</span>
        </template>

        <template #item.actions="{ item }">
          <div class="document-row-actions">
            <v-btn
              icon="mdi-eye"
              variant="text"
              size="small"
              class="document-icon-btn document-icon-btn--view"
              @click="viewDocument(item)"
            />
            <v-btn
              icon="mdi-delete-outline"
              variant="text"
              size="small"
              class="document-icon-btn document-icon-btn--delete"
              @click="confirmDelete(item)"
            />
          </div>
        </template>

        <template #no-data>
          <div class="document-empty">
            <span class="document-empty__icon">
              <v-icon size="32">mdi-file-document-outline</v-icon>
            </span>
            <p>{{ t('documents.empty') }}</p>
          </div>
        </template>
      </v-data-table-server>
    </v-card>

    <!-- 上传对话框 -->
    <v-dialog v-model="showUploadDialog" max-width="680px" persistent @after-enter="initUploadSettings">
      <v-card class="upload-dialog-card">
        <v-card-title class="upload-dialog-title">
          <div>
            <span>{{ t('upload.title') }}</span>
            <p>选择本地文档后，系统会在后台完成解析、分块和索引。</p>
          </div>
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" class="upload-dialog-close" @click="closeUploadDialog" />
        </v-card-title>

        <v-card-text class="upload-dialog-body">
          <div class="upload-dropzone" :class="{ dragover: isDragging }" @drop.prevent="handleDrop" @dragover.prevent="isDragging = true" @dragleave="isDragging = false" @click="fileInput?.click()">
            <p class="upload-dropzone__title">{{ t('upload.dropzone') }}</p>
            <p class="upload-dropzone__meta">
              {{ t('upload.supportedFormats') }}
            </p>
            <p class="upload-dropzone__meta">
              {{ t('upload.maxSize') }}
            </p>
            <input ref="fileInput" type="file" multiple hidden accept=".txt,.md,.markdown,.rst,.adoc,.pdf,.docx,.epub,.xls,.xlsx" @change="handleFileSelect" />
          </div>

          <div v-if="selectedFiles.length > 0" class="selected-files-panel">
            <div class="selected-files-header">
              <span>已选择 {{ selectedFiles.length }} 个文件</span>
              <v-btn variant="text" size="small" class="selected-files-clear" @click="selectedFiles = []">清空</v-btn>
            </div>
            <div class="files-list">
              <div v-for="(file, index) in selectedFiles" :key="index" class="file-item">
                <div class="file-item__info">
                  <span class="file-item__icon">
                    <v-icon size="18">{{ getFileIcon(file.name) }}</v-icon>
                  </span>
                  <div>
                    <div class="file-item__name">{{ file.name }}</div>
                    <div class="file-item__size">
                      {{ formatFileSize(file.size) }}
                    </div>
                  </div>
                </div>
                <v-btn icon="mdi-close" variant="text" size="small" class="file-item__remove" @click="removeFile(index)" />
              </div>
            </div>
          </div>

          <div class="batch-settings-panel">
            <h3>{{ t('upload.batchSettings') }}</h3>
            <v-row>
              <v-col cols="12" sm="4">
                <v-text-field v-model.number="uploadSettings.batch_size" :label="t('upload.batchSize')" hint="每批处理的文本数量" persistent-hint type="number" variant="outlined" density="compact" />
              </v-col>
              <v-col cols="12" sm="4">
                <v-text-field v-model.number="uploadSettings.tasks_limit" :label="t('upload.tasksLimit')" hint="并发任务数量限制" persistent-hint type="number" variant="outlined" density="compact" />
              </v-col>
              <v-col cols="12" sm="4">
                <v-text-field v-model.number="uploadSettings.max_retries" :label="t('upload.maxRetries')" hint="失败时的最大重试次数" persistent-hint type="number" variant="outlined" density="compact" />
              </v-col>
            </v-row>
          </div>
        </v-card-text>

        <v-card-actions class="upload-dialog-actions">
          <v-spacer />
          <v-btn variant="text" class="upload-cancel-btn" @click="closeUploadDialog" :disabled="uploading">
            {{ t('upload.cancel') }}
          </v-btn>
          <v-btn color="primary" variant="flat" class="upload-submit-btn" @click="startUpload" :loading="uploading" :disabled="isUploadDisabled">
            {{ t('upload.submit') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 删除确认对话框 -->
    <v-dialog v-model="showDeleteDialog" max-width="450px">
      <v-card>
        <v-card-title class="text-h3 pa-4 pb-0 pl-6">{{ t('documents.delete') }}</v-card-title>
        <v-card-text class="pa-6">
          <p>
            {{
              t('documents.deleteConfirm', {
                name: deleteTarget?.doc_name || '',
              })
            }}
          </p>
          <v-alert type="error" variant="tonal" density="compact" class="mt-4">
            {{ t('documents.deleteWarning') }}
          </v-alert>
        </v-card-text>
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="showDeleteDialog = false">取消</v-btn>
          <v-btn color="error" variant="tonal" @click="deleteDocument" :loading="deleting"> 删除 </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 批量删除确认对话框 -->
    <v-dialog v-model="showBatchDeleteDialog" max-width="520px">
      <v-card class="delete-dialog-card delete-dialog-card--batch">
        <v-card-title class="delete-dialog-title">
          <span class="delete-dialog-icon">
            <v-icon size="22">mdi-delete-outline</v-icon>
          </span>
          <div>
            <h3>批量删除文档</h3>
            <p>将删除选中的 {{ selectedDocumentIds.length }} 个文档及其所有分块。</p>
          </div>
        </v-card-title>
        <v-card-text class="delete-dialog-body">
          <div class="delete-target-list">
            <div v-for="doc in selectedDocumentsPreview" :key="doc.doc_id" class="delete-target-item">
              {{ doc.doc_name }}
            </div>
            <div v-if="selectedDocumentIds.length > selectedDocumentsPreview.length" class="delete-target-more">
              还有 {{ selectedDocumentIds.length - selectedDocumentsPreview.length }} 个文档
            </div>
          </div>
          <p class="delete-dialog-warning">此操作不可恢复，请确认后再删除。</p>
        </v-card-text>
        <v-card-actions class="delete-dialog-actions">
          <v-spacer />
          <v-btn variant="text" class="delete-cancel-btn" @click="showBatchDeleteDialog = false">取消</v-btn>
          <v-btn color="error" variant="tonal" class="delete-confirm-btn" :loading="batchDeleting" @click="batchDeleteDocuments">
            确认删除
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 消息提示 -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color">
      {{ snackbar.text }}
    </v-snackbar>

    <!-- Tavily Key 配置对话框 -->
    <TavilyKeyDialog v-model="showTavilyDialog" @success="onTavilyKeySet" />
    <WikiImportDialog v-model="showWikiImportDialog" :kb-id="kbId" @busy="wikiImporting = $event" @imported="onWikiImported" />
  </div>
</template>

<script setup lang="ts">
import TavilyKeyDialog from './TavilyKeyDialog.vue'
import WikiImportDialog from './WikiImportDialog.vue'
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { configProfileApi, knowledgeApi, providerApi } from '@/api/v1'
import { useModuleI18n } from '@/i18n/composables'

const { tm: t } = useModuleI18n('features/knowledge-base/detail')
const router = useRouter()

const props = defineProps<{
  kbId: string
  kb: any
}>()

const emit = defineEmits(['refresh'])

// 状态
const loading = ref(false)
const uploading = ref(false)
const deleting = ref(false)
const batchDeleting = ref(false)
const documents = ref<any[]>([])
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const searchQuery = ref('')
const showUploadDialog = ref(false)
const showWikiImportDialog = ref(false)
const wikiImporting = ref(false)
const showDeleteDialog = ref(false)
const showBatchDeleteDialog = ref(false)
const selectedFiles = ref<File[]>([])
const selectedDocumentIds = ref<string[]>([])
const deleteTarget = ref<any>(null)
const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const uploadMode = ref('file') // 'file' or 'url'
const uploadUrl = ref('')
const llmProviders = ref<any[]>([])
const uploadingTasks = ref<Map<string, any>>(new Map())
const progressPollingInterval = ref<number | null>(null)
const tavilyConfigStatus = ref('loading') // 'loading', 'configured', 'not_configured', 'error'
const showTavilyDialog = ref(false)

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

// 上传设置
const uploadSettings = ref({
  batch_size: 32,
  tasks_limit: 3,
  max_retries: 3,
  enable_cleaning: false,
  cleaning_provider_id: null as string | null,
})

// 初始化上传设置
const initUploadSettings = () => {
  uploadSettings.value = {
    batch_size: 32,
    tasks_limit: 3,
    max_retries: 3,
    enable_cleaning: false,
    cleaning_provider_id: null,
  }
}

const isUploadDisabled = computed(() => {
  if (uploading.value) {
    return true
  }
  if (uploadMode.value === 'file') {
    return selectedFiles.value.length === 0
  }
  if (uploadMode.value === 'url') {
    if (!uploadUrl.value) {
      return true
    }
    if (uploadSettings.value.enable_cleaning && !uploadSettings.value.cleaning_provider_id) {
      return true
    }
    return false
  }
  return true
})

const selectedDocumentsPreview = computed(() => {
  const selectedSet = new Set(selectedDocumentIds.value)
  return documents.value.filter((doc) => selectedSet.has(doc.doc_id)).slice(0, 4)
})

// 表格列
const headers = [
  { title: t('documents.name'), key: 'doc_name', sortable: true },
  { title: t('documents.type'), key: 'file_type', sortable: true },
  { title: t('documents.size'), key: 'file_size', sortable: true },
  { title: t('documents.chunks'), key: 'chunk_count', sortable: true },
  { title: t('documents.createdAt'), key: 'created_at', sortable: true },
  {
    title: t('documents.actions'),
    key: 'actions',
    sortable: false,
    align: 'end' as const,
  },
]

const itemsPerPageOptions = [
  { title: '10', value: 10 },
  { title: '25', value: 25 },
  { title: '50', value: 50 },
  { title: '100', value: 100 },
  { title: '全部', value: -1 },
]

// 加载文档列表
const loadDocuments = async () => {
  loading.value = true
  try {
    const response = await knowledgeApi.documents(props.kbId, {
      page: page.value,
      page_size: pageSize.value,
      search: searchQuery.value.trim() || undefined,
    })
    if (response.data.status === 'ok') {
      const data = response.data.data
      documents.value = data.items || []
      total.value = data.total || 0
      selectedDocumentIds.value = selectedDocumentIds.value.filter((docId) => documents.value.some((doc) => doc.doc_id === docId))
    }
  } catch (error) {
    console.error('Failed to load documents:', error)
    showSnackbar('加载文档列表失败', 'error')
  } finally {
    loading.value = false
  }
}

// Handle pagination
const onPageChange = (newPage: number) => {
  page.value = newPage
  loadDocuments()
}

const onItemsPerPageChange = (newSize: number) => {
  pageSize.value = newSize
  page.value = 1
  loadDocuments()
}

// 文件选择
const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    const newFiles = Array.from(target.files)
    addFiles(newFiles)
  }
  target.value = ''
}

// 添加文件
const addFiles = (files: File[]) => {
  selectedFiles.value.push(...files)
}

// 移除文件
const removeFile = (index: number) => {
  selectedFiles.value.splice(index, 1)
}

// 拖放上传
const handleDrop = (event: DragEvent) => {
  isDragging.value = false
  if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
    const newFiles = Array.from(event.dataTransfer.files)
    addFiles(newFiles)
  }
}

// 上传调度器
const startUpload = async () => {
  if (uploadMode.value === 'file') {
    await uploadFiles()
  } else if (uploadMode.value === 'url') {
    await uploadFromUrl()
  }
}

// 上传文件
const uploadFiles = async () => {
  if (selectedFiles.value.length === 0) {
    showSnackbar(t('upload.fileRequired'), 'warning')
    return
  }

  uploading.value = true

  try {
    const formData = new FormData()

    // 添加所有文件
    selectedFiles.value.forEach((file) => {
      formData.append('files', file)
    })

    formData.append('kb_id', props.kbId)
    formData.append('batch_size', uploadSettings.value.batch_size.toString())
    formData.append('tasks_limit', uploadSettings.value.tasks_limit.toString())
    formData.append('max_retries', uploadSettings.value.max_retries.toString())

    const response = await knowledgeApi.uploadDocument(props.kbId, formData)

    if (response.data.status === 'ok') {
      const result = response.data.data
      const taskId = result.task_id

      showSnackbar(`正在后台上传 ${result.file_count} 个文件...`, 'info')

      // 为每个文件添加占位条目到文档列表
      const uploadingDocs = selectedFiles.value.map((file, index) => ({
        doc_id: `uploading_${taskId}_${index}`,
        doc_name: file.name,
        file_type: file.name.split('.').pop() || '',
        file_size: file.size,
        chunk_count: 0,
        created_at: new Date().toISOString(),
        uploading: true,
        taskId: taskId,
        uploadProgress: {
          stage: 'waiting',
          current: 0,
          total: 100,
        },
      }))

      // 添加到文档列表顶部
      documents.value = [...uploadingDocs, ...documents.value]

      // 关闭对话框
      closeUploadDialog()

      // 开始轮询进度
      if (taskId) {
        startProgressPolling(taskId)
      }
    } else {
      showSnackbar(response.data.message || t('documents.uploadFailed'), 'error')
    }
  } catch (error) {
    console.error('Failed to upload document:', error)
    showSnackbar(t('documents.uploadFailed'), 'error')
  } finally {
    uploading.value = false
  }
}

// 从 URL 上传
const uploadFromUrl = async () => {
  if (!uploadUrl.value) {
    showSnackbar(t('upload.urlRequired'), 'warning')
    return
  }

  uploading.value = true

  try {
    const payload: any = {
      kb_id: props.kbId,
      url: uploadUrl.value,
      batch_size: uploadSettings.value.batch_size,
      tasks_limit: uploadSettings.value.tasks_limit,
      max_retries: uploadSettings.value.max_retries,
    }
    if (uploadSettings.value.enable_cleaning) {
      payload.enable_cleaning = true
      if (uploadSettings.value.cleaning_provider_id) {
        payload.cleaning_provider_id = uploadSettings.value.cleaning_provider_id
      }
    }

    const response = await knowledgeApi.importDocumentFromUrl(props.kbId, payload)

    if (response.data.status === 'ok') {
      const result = response.data.data
      const taskId = result.task_id

      showSnackbar(`正在从 URL 后台提取内容...`, 'info')

      // 添加占位条目
      const uploadingDoc = {
        doc_id: `uploading_${taskId}_0`,
        doc_name: result.url,
        file_type: 'url',
        file_size: 0, // URL has no size
        chunk_count: 0,
        created_at: new Date().toISOString(),
        uploading: true,
        taskId: taskId,
        uploadProgress: {
          stage: 'waiting',
          current: 0,
          total: 100,
        },
      }

      documents.value = [uploadingDoc, ...documents.value]
      closeUploadDialog()

      if (taskId) {
        startProgressPolling(taskId)
      }
    } else {
      showSnackbar(response.data.message || t('documents.uploadFailed'), 'error')
    }
  } catch (error: any) {
    console.error('Failed to upload from URL:', error)
    const message = error.response?.data?.message || t('documents.uploadFailed')
    showSnackbar(message, 'error')
  } finally {
    uploading.value = false
  }
}

// 开始轮询进度
const startProgressPolling = (taskId: string) => {
  // 如果已经在轮询，先停止
  if (progressPollingInterval.value) {
    stopProgressPolling()
  }

  progressPollingInterval.value = window.setInterval(async () => {
    try {
      const response = await knowledgeApi.task(taskId)

      if (response.data.status === 'ok') {
        const data = response.data.data
        const status = data.status

        if (status === 'processing' && data.progress) {
          // 更新进度
          const progress = data.progress
          const fileIndex = progress.file_index || 0

          // 更新对应文件的进度
          documents.value = documents.value.map((doc) => {
            if (doc.taskId === taskId) {
              const docIndex = parseInt(doc.doc_id.split('_').pop() || '0')
              if (docIndex === fileIndex) {
                return {
                  ...doc,
                  uploadProgress: {
                    stage: progress.stage || 'waiting',
                    current: progress.current || 0,
                    total: progress.total || 100,
                  },
                }
              }
            }
            return doc
          })
        } else if (status === 'completed') {
          // 任务完成
          stopProgressPolling()

          const result = data.result
          const successCount = result?.success_count || 0
          const failedCount = result?.failed_count || 0

          // 移除上传中的占位文档
          documents.value = documents.value.filter((doc) => doc.taskId !== taskId)

          // Reload current page
          await loadDocuments()
          emit('refresh')

          if (failedCount === 0) {
            showSnackbar(`成功上传 ${successCount} 个文档`)
          } else {
            showSnackbar(`上传完成: ${successCount} 个成功, ${failedCount} 个失败`, 'warning')
          }
        } else if (status === 'failed') {
          // 任务失败
          stopProgressPolling()

          // 移除上传中的占位文档
          documents.value = documents.value.filter((doc) => doc.taskId !== taskId)

          showSnackbar(`上传失败: ${data.error || '未知错误'}`, 'error')
        }
      } else {
        // 任务不存在，停止轮询
        stopProgressPolling()
        documents.value = documents.value.filter((doc) => doc.taskId !== taskId)
      }
    } catch (error) {
      console.error('Failed to fetch progress:', error)
      // 不立即停止，允许重试
    }
  }, 500) // 每500ms轮询一次
}

// 停止轮询进度
const stopProgressPolling = () => {
  if (progressPollingInterval.value) {
    clearInterval(progressPollingInterval.value)
    progressPollingInterval.value = null
  }
}

// 获取上传百分比
const getUploadPercentage = (item: any) => {
  if (!item.uploadProgress) return 0
  const { current, total } = item.uploadProgress
  if (!total || total === 0) return 0
  return (current / total) * 100
}

// 获取阶段文本
const getStageText = (stage: string) => {
  const stageMap: Record<string, string> = {
    waiting: '等待中...',
    extracting: '提取内容...',
    cleaning: '清洗内容...',
    parsing: '解析文档...',
    chunking: '文本分块...',
    embedding: '生成向量...',
  }
  return stageMap[stage] || stage
}

// 关闭上传对话框
const closeUploadDialog = () => {
  showUploadDialog.value = false
  selectedFiles.value = []
  uploadUrl.value = ''
  uploadMode.value = 'file'
  initUploadSettings()
}

// 查看文档
const viewDocument = (doc: any) => {
  router.push({
    name: 'NativeDocumentDetail',
    params: { kbId: props.kbId, docId: doc.doc_id },
  })
}

// 确认删除
const confirmDelete = (doc: any) => {
  deleteTarget.value = doc
  showDeleteDialog.value = true
}

// 删除文档
const deleteDocument = async () => {
  if (!deleteTarget.value) return

  deleting.value = true
  try {
    const response = await knowledgeApi.deleteDocument(props.kbId, deleteTarget.value.doc_id)

    if (response.data.status === 'ok') {
      showSnackbar(t('documents.deleteSuccess'))
      showDeleteDialog.value = false
      // If current page becomes empty after delete and is not the first page, go back one page
      if (documents.value.length === 1 && page.value > 1) {
        page.value -= 1
      }
      await loadDocuments()
      emit('refresh')
    } else {
      showSnackbar(response.data.message || t('documents.deleteFailed'), 'error')
    }
  } catch (error) {
    console.error('Failed to delete document:', error)
    showSnackbar(t('documents.deleteFailed'), 'error')
  } finally {
    deleting.value = false
  }
}

// 批量删除文档
const batchDeleteDocuments = async () => {
  const ids = [...selectedDocumentIds.value]
  if (ids.length === 0) return

  batchDeleting.value = true
  try {
    const results = await Promise.allSettled(ids.map((docId) => knowledgeApi.deleteDocument(props.kbId, docId)))
    const successCount = results.filter((result) => result.status === 'fulfilled' && result.value.data.status === 'ok').length
    const failedCount = ids.length - successCount

    if (successCount > 0) {
      selectedDocumentIds.value = []
      showBatchDeleteDialog.value = false
      if (documents.value.length <= successCount && page.value > 1) {
        page.value -= 1
      }
      await loadDocuments()
      emit('refresh')
    }

    if (failedCount === 0) {
      showSnackbar(`已删除 ${successCount} 个文档`)
    } else if (successCount > 0) {
      showSnackbar(`批量删除完成：成功 ${successCount} 个，失败 ${failedCount} 个`, 'warning')
    } else {
      showSnackbar('批量删除失败', 'error')
    }
  } catch (error) {
    console.error('Failed to batch delete documents:', error)
    showSnackbar('批量删除失败', 'error')
  } finally {
    batchDeleting.value = false
  }
}

// 工具函数
const getFileIcon = (fileType: string) => {
  const type = fileType?.toLowerCase() || ''
  if (type.includes('pdf')) return 'mdi-file-pdf-box'
  if (type.includes('epub')) return 'mdi-book-open-page-variant'
  if (type.includes('rst') || type.includes('adoc')) return 'mdi-file-document-outline'
  if (type.includes('md') || type.includes('markdown')) return 'mdi-language-markdown'
  if (type.includes('txt')) return 'mdi-file-document-outline'
  if (type.includes('url')) return 'mdi-link-variant'
  return 'mdi-file'
}

const getFileColor = (fileType: string) => {
  const type = fileType?.toLowerCase() || ''
  if (type.includes('pdf')) return 'error'
  if (type.includes('epub')) return 'warning'
  if (type.includes('rst') || type.includes('adoc')) return 'success'
  if (type.includes('md')) return 'info'
  if (type.includes('txt')) return 'success'
  if (type.includes('url')) return 'primary'
  return 'grey'
}

const formatFileSize = (bytes: number) => {
  if (!bytes) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(2)} ${units[unitIndex]}`
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// 加载LLM providers
const loadLlmProviders = async () => {
  try {
    const response = await providerApi.listByProviderType('chat_completion')
    if (response.data.status === 'ok') {
      llmProviders.value = response.data.data
    }
  } catch (error) {
    console.error('Failed to load LLM providers:', error)
  }
}

// 检查Tavily Key配置
const checkTavilyConfig = async () => {
  tavilyConfigStatus.value = 'loading'
  try {
    const response = await configProfileApi.get('default')
    if (response.data.status === 'ok') {
      const config = ((response.data.data as any).config || {}) as any
      const tavilyKeys = config?.provider_settings?.websearch_tavily_key
      if (Array.isArray(tavilyKeys) && tavilyKeys.length > 0 && tavilyKeys.some((key) => key.trim() !== '')) {
        tavilyConfigStatus.value = 'configured'
      } else {
        tavilyConfigStatus.value = 'not_configured'
      }
    } else {
      tavilyConfigStatus.value = 'error'
    }
  } catch (error) {
    console.warn('Failed to check Tavily key config:', error)
    tavilyConfigStatus.value = 'error'
  }
}

const onTavilyKeySet = () => {
  showSnackbar('Tavily API Key 配置成功', 'success')
  checkTavilyConfig()
}

const onWikiImported = async () => {
  await loadDocuments()
  showSnackbar('Wiki 导入完成', 'success')
  emit('refresh')
}

// Reset to page 1 and reload when search text changes
watch(searchQuery, () => {
  page.value = 1
  loadDocuments()
})

onMounted(() => {
  loadDocuments()
  loadLlmProviders()
  checkTavilyConfig()
})

onUnmounted(() => {
  stopProgressPolling()
})
</script>

<style scoped>
.documents-tab {
  animation: fadeIn 0.3s ease;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

.action-bar {
  align-items: center;
  background: linear-gradient(180deg, #f8fcff 0%, #ffffff 100%);
  border: 1px solid #dceaf3;
  border-radius: 14px;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  padding: 10px;
  flex-wrap: wrap;
}

.document-actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.document-action-btn {
  border-radius: 10px;
  font-weight: 700;
  letter-spacing: 0;
}

.document-action-btn--primary {
  box-shadow: 0 8px 18px rgba(47, 150, 207, 0.16);
}

.bulk-delete-actions {
  align-items: center;
  background: #fff7f7;
  border: 1px solid #ffd4d4;
  border-radius: 12px;
  display: flex;
  gap: 8px;
  padding: 4px;
}

.bulk-selected-count {
  color: #b42323;
  font-size: 0.82rem;
  font-weight: 800;
  padding: 0 8px;
  white-space: nowrap;
}

.bulk-delete-btn {
  background: #ffe8e8;
}

.document-search {
  flex: 0 1 330px;
  min-width: 240px;
}

.document-search :deep(.v-field) {
  background: #ffffff;
  border-radius: 12px;
}

.documents-table-card {
  background: #ffffff;
  border-color: #dceaf3;
  border-radius: 14px;
  overflow: hidden;
}

.documents-table {
  background: transparent;
}

.documents-table :deep(thead th) {
  background: #f7fbfe !important;
  border-bottom: 1px solid #dceaf3 !important;
  color: #263d4f !important;
  font-size: 0.82rem;
  font-weight: 800 !important;
  height: 44px !important;
}

.documents-table :deep(.v-data-table__td--select-row),
.documents-table :deep(.v-data-table__th--select) {
  width: 44px;
}

.documents-table :deep(.v-selection-control) {
  min-height: 30px;
}

.documents-table :deep(.v-selection-control__wrapper) {
  height: 28px;
  width: 28px;
}

.documents-table :deep(tbody tr) {
  transition: background-color 0.16s ease, box-shadow 0.16s ease;
}

.documents-table :deep(tbody tr:hover) {
  background: #f8fcff !important;
  box-shadow: inset 3px 0 0 #49a3d6;
}

.documents-table :deep(tbody td) {
  border-bottom: 1px solid #e5eef5 !important;
  color: #152638;
  font-size: 0.88rem;
  height: 48px !important;
  padding-bottom: 6px !important;
  padding-top: 6px !important;
}

.document-name-cell {
  align-items: center;
  display: flex;
  gap: 8px;
  min-width: 0;
}

.document-file-icon {
  align-items: center;
  background: #eaf6fd;
  border: 1px solid #cce8f8;
  border-radius: 7px;
  display: flex;
  flex: 0 0 auto;
  height: 24px;
  justify-content: center;
  width: 24px;
}

.document-name-content {
  min-width: 0;
  padding: 2px 0;
}

.document-name {
  color: #152638;
  display: block;
  font-size: 0.9rem;
  font-weight: 700;
  max-width: 560px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-type-pill {
  background: #eef8f4;
  border: 1px solid #d2efe3;
  border-radius: 999px;
  color: #23805e;
  display: inline-flex;
  font-size: 0.74rem;
  font-weight: 800;
  line-height: 1;
  padding: 4px 8px;
}

.table-muted-text {
  color: #526776;
  font-weight: 600;
}

.document-row-actions {
  align-items: center;
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.document-icon-btn {
  border-radius: 9px;
  height: 30px;
  width: 30px;
}

.document-icon-btn--view {
  background: #eaf6fd;
  color: #2385bd;
}

.document-icon-btn--view:hover {
  background: #d9effc;
}

.document-icon-btn--delete {
  background: #fff0f0;
  color: #e54848;
}

.document-icon-btn--delete:hover {
  background: #ffe1e1;
}

.document-empty {
  align-items: center;
  color: #647482;
  display: flex;
  flex-direction: column;
  gap: 10px;
  justify-content: center;
  min-height: 220px;
  padding: 28px;
}

.document-empty__icon {
  align-items: center;
  background: #eaf6fd;
  border: 1px solid #cce8f8;
  border-radius: 14px;
  color: #2f96cf;
  display: flex;
  height: 62px;
  justify-content: center;
  width: 62px;
}

.document-empty p {
  margin: 0;
}

.delete-dialog-card {
  background: linear-gradient(180deg, #fffafa 0%, #ffffff 48%);
  border: 1px solid #ffcaca;
  border-radius: 16px !important;
  overflow: hidden;
}

.delete-dialog-title {
  align-items: center;
  display: flex;
  gap: 14px;
  padding: 24px 28px 12px !important;
}

.delete-dialog-icon {
  align-items: center;
  background: #fff0f0;
  border: 1px solid #ffbcbc;
  border-radius: 11px;
  color: #ef4444;
  display: flex;
  flex: 0 0 auto;
  height: 42px;
  justify-content: center;
  width: 42px;
}

.delete-dialog-title h3 {
  color: #162331;
  font-size: 1.18rem;
  font-weight: 850;
  line-height: 1.35;
  margin: 0;
}

.delete-dialog-title p {
  color: #6d4d4d;
  font-size: 0.86rem;
  line-height: 1.45;
  margin: 4px 0 0;
}

.delete-dialog-body {
  padding: 14px 28px 8px !important;
}

.delete-target-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.delete-target-item,
.delete-target-more {
  background: #fff5f5;
  border: 1px solid #ffd8d8;
  border-radius: 10px;
  color: #d73333;
  font-size: 0.84rem;
  font-weight: 800;
  line-height: 1.4;
  overflow: hidden;
  padding: 9px 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.delete-target-more {
  color: #8d4a4a;
  font-weight: 700;
}

.delete-dialog-warning {
  color: #805454;
  font-size: 0.84rem;
  line-height: 1.45;
  margin: 12px 0 0;
}

.delete-dialog-actions {
  padding: 12px 28px 24px !important;
}

.delete-cancel-btn,
.delete-confirm-btn {
  border-radius: 10px;
  font-weight: 800;
  letter-spacing: 0;
  min-width: 86px;
}

.upload-dialog-card {
  border: 1px solid #dceaf3;
  border-radius: 16px !important;
  overflow: hidden;
}

.upload-dialog-title {
  align-items: flex-start;
  background: linear-gradient(180deg, #f8fcff 0%, #ffffff 100%);
  border-bottom: 1px solid #e4eef5;
  display: flex;
  padding: 20px 24px 16px;
}

.upload-dialog-title span {
  color: #162331;
  display: block;
  font-size: 1.2rem;
  font-weight: 800;
  line-height: 1.35;
}

.upload-dialog-title p {
  color: #657785;
  font-size: 0.86rem;
  font-weight: 400;
  line-height: 1.45;
  margin: 4px 0 0;
}

.upload-dialog-close {
  background: #f3f7fa;
  border-radius: 10px;
  color: #425766;
}

.upload-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 24px 18px !important;
}

.upload-dropzone {
  align-items: center;
  background: #f8fcff;
  border: 1px dashed #8ec7e8;
  border-radius: 14px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  min-height: 160px;
  justify-content: center;
  padding: 24px;
  text-align: center;
  transition: background-color 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}

.upload-dropzone:hover,
.upload-dropzone.dragover {
  background: #eef9ff;
  border-color: #3c9bd2;
  transform: translateY(-1px);
}

.upload-dropzone__title {
  color: #172331;
  font-size: 1.02rem;
  font-weight: 800;
  line-height: 1.4;
  margin: 0 0 10px;
}

.upload-dropzone__meta {
  color: #657785;
  font-size: 0.82rem;
  line-height: 1.5;
  margin: 0;
}

.selected-files-panel,
.batch-settings-panel {
  background: #ffffff;
  border: 1px solid #dceaf3;
  border-radius: 14px;
  padding: 14px;
}

.selected-files-header {
  align-items: center;
  color: #263d4f;
  display: flex;
  font-size: 0.9rem;
  font-weight: 800;
  justify-content: space-between;
  margin-bottom: 10px;
}

.selected-files-clear {
  border-radius: 9px;
  color: #2f89be;
  font-weight: 700;
}

.files-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 220px;
  overflow-y: auto;
}

.file-item {
  align-items: center;
  background: #f8fcff;
  border: 1px solid #e2edf5;
  border-radius: 12px;
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  transition: background-color 0.18s ease, border-color 0.18s ease;
}

.file-item:hover {
  background: #f1f9fe;
  border-color: #cce8f8;
}

.file-item__info {
  align-items: center;
  display: flex;
  gap: 10px;
  min-width: 0;
}

.file-item__icon {
  align-items: center;
  background: #eaf6fd;
  border: 1px solid #cce8f8;
  border-radius: 9px;
  color: #2f96cf;
  display: flex;
  flex: 0 0 auto;
  height: 32px;
  justify-content: center;
  width: 32px;
}

.file-item__name {
  color: #172331;
  font-size: 0.9rem;
  font-weight: 700;
  line-height: 1.4;
  max-width: 500px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-item__size {
  color: #6d7c88;
  font-size: 0.78rem;
  line-height: 1.4;
}

.file-item__remove {
  border-radius: 9px;
  color: #6d7c88;
}

.batch-settings-panel h3 {
  color: #263d4f;
  font-size: 0.95rem;
  font-weight: 800;
  line-height: 1.4;
  margin: 0 0 12px;
}

.upload-dialog-actions {
  background: #fbfdff;
  border-top: 1px solid #e4eef5;
  padding: 14px 24px !important;
}

.upload-cancel-btn,
.upload-submit-btn {
  border-radius: 10px;
  font-weight: 700;
  letter-spacing: 0;
}

.upload-submit-btn {
  min-width: 86px;
}

@media (max-width: 768px) {
  .action-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .action-bar > *,
  .document-search {
    width: 100%;
    max-width: none;
  }

  .document-name {
    max-width: 260px;
  }

  .file-item__name {
    max-width: 220px;
  }
}
</style>
