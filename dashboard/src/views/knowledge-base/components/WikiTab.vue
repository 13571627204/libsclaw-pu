<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from 'vue'
import { knowledgeApi } from '@/api/v1'
import type { WikiTreeNode } from '@/api/v1'
import WikiFileBrowser from './WikiFileBrowser.vue'
import WikiImportDialog from './WikiImportDialog.vue'

interface Props {
  kbId: string
  requestedPage?: { path: string; requestId: number } | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  refresh: []
}>()

const treeLoading = shallowRef(false)
const pageLoading = shallowRef(false)
const saving = shallowRef(false)
const rebuilding = shallowRef(false)
const deleting = shallowRef(false)
const moving = shallowRef(false)
const importing = shallowRef(false)
const importDialog = shallowRef(false)
const deleteDialog = shallowRef(false)
const moveDialog = shallowRef(false)
const discardDialog = shallowRef(false)
const tree = shallowRef<WikiTreeNode | null>(null)
const selectedPath = shallowRef('')
const editorPath = shallowRef('')
const editorContent = shallowRef('')
const originalContent = shallowRef('')
const pendingPagePath = shallowRef('')
const pendingAction = shallowRef<(() => void) | null>(null)
const pathActionTarget = shallowRef<WikiTreeNode | null>(null)
const moveTargetDirectory = shallowRef('')
const errorMessage = shallowRef('')
const successMessage = shallowRef('')
let treeLoadRequestId = 0
let pageLoadRequestId = 0

const hasChanges = computed(() => editorContent.value !== originalContent.value)
const writeInProgress = computed(
  () => saving.value || deleting.value || moving.value || rebuilding.value || importing.value,
)
const operationBusy = computed(() => pageLoading.value || writeInProgress.value)

const directoryOptions = computed(() => {
  const options = [{ title: 'knowledge/（根目录）', value: '' }]
  const target = pathActionTarget.value
  const visit = (node: WikiTreeNode) => {
    if (node.type !== 'directory') return
    const isCurrentOrDescendant =
      target?.type === 'directory' &&
      (node.path === target.path || node.path.startsWith(`${target.path}/`))
    if (node.path && !isCurrentOrDescendant) {
      options.push({ title: node.path, value: node.path })
    }
    node.children?.forEach(visit)
  }
  if (tree.value) visit(tree.value)
  return options
})

const notify = (message: string, type: 'success' | 'error') => {
  successMessage.value = type === 'success' ? message : ''
  errorMessage.value = type === 'error' ? message : ''
}

const loadTree = async () => {
  const requestId = ++treeLoadRequestId
  treeLoading.value = true
  try {
    const response = await knowledgeApi.wikiTree(props.kbId)
    if (response.data.status !== 'ok') throw new Error(response.data.message || '加载失败')
    if (requestId !== treeLoadRequestId) return
    tree.value = response.data.data?.tree || null
  } catch (error) {
    if (requestId !== treeLoadRequestId) return
    console.error('Failed to load Wiki tree:', error)
    notify('加载知识页面失败', 'error')
  } finally {
    if (requestId === treeLoadRequestId) treeLoading.value = false
  }
}

const confirmDiscard = (action: () => void) => {
  if (!hasChanges.value) {
    action()
    return
  }
  pendingAction.value = action
  discardDialog.value = true
}

const cancelDiscard = () => {
  pendingAction.value = null
  discardDialog.value = false
}

const discardChanges = () => {
  const action = pendingAction.value
  pendingAction.value = null
  discardDialog.value = false
  action?.()
}

const loadPage = async (path: string) => {
  const requestId = ++pageLoadRequestId
  const selectedPathAtStart = selectedPath.value
  const editorPathAtStart = editorPath.value
  const editorContentAtStart = editorContent.value
  pendingPagePath.value = path
  pageLoading.value = true
  try {
    const response = await knowledgeApi.wikiPage(props.kbId, path)
    if (response.data.status !== 'ok') throw new Error(response.data.message || '加载失败')
    if (requestId !== pageLoadRequestId) return
    if (
      selectedPath.value !== selectedPathAtStart ||
      editorPath.value !== editorPathAtStart ||
      editorContent.value !== editorContentAtStart
    ) {
      notify('编辑内容已变化，已取消页面切换', 'error')
      return
    }
    selectedPath.value = path
    editorPath.value = path
    editorContent.value = response.data.data?.content || ''
    originalContent.value = editorContent.value
    notify('', 'success')
  } catch (error) {
    if (requestId !== pageLoadRequestId) return
    console.error('Failed to load Wiki page:', error)
    notify('读取知识页面失败', 'error')
  } finally {
    if (requestId === pageLoadRequestId) {
      pendingPagePath.value = ''
      pageLoading.value = false
    }
  }
}

const openPage = (path: string) => {
  if (writeInProgress.value) {
    notify('当前操作完成后才能切换页面', 'error')
    return
  }
  if (pageLoading.value) {
    if (path === selectedPath.value) {
      pageLoadRequestId += 1
      pendingPagePath.value = ''
      pageLoading.value = false
      notify('已取消页面切换', 'success')
    } else if (path !== pendingPagePath.value) {
      notify('正在读取页面，请先点击当前页面取消切换', 'error')
    }
    return
  }
  if (path === selectedPath.value) return
  confirmDiscard(() => void loadPage(path))
}

const newPage = () => {
  if (operationBusy.value) {
    notify('当前操作完成后才能新建页面', 'error')
    return
  }
  confirmDiscard(() => {
    pageLoadRequestId += 1
    pendingPagePath.value = ''
    pageLoading.value = false
    selectedPath.value = ''
    editorPath.value = 'notes/new-page.md'
    editorContent.value = '# New Page\n\n> Source: Manual\n\n'
    originalContent.value = ''
    notify('', 'success')
  })
}

const openImportDialog = () => {
  if (operationBusy.value) {
    notify('当前操作完成后才能导入 Wiki', 'error')
    return
  }
  if (hasChanges.value) {
    notify('请先保存或放弃未保存修改，再导入 Wiki', 'error')
    return
  }
  importDialog.value = true
}

const handleWikiImported = async () => {
  await loadTree()
  emit('refresh')
  notify('Wiki 导入完成', 'success')
}

const savePage = async () => {
  if (operationBusy.value) {
    notify('当前操作完成后才能保存页面', 'error')
    return
  }
  if (!editorPath.value.trim() || !editorContent.value.trim()) {
    notify('页面路径和内容不能为空', 'error')
    return
  }
  const path = editorPath.value.trim()
  const content = editorContent.value
  const originalPath = selectedPath.value
  saving.value = true
  try {
    const response = await knowledgeApi.saveWikiPage(
      props.kbId,
      path,
      content,
      originalPath || undefined,
    )
    if (response.data.status !== 'ok') throw new Error(response.data.message || '保存失败')
    const savedPath = response.data.data?.path || path
    if (selectedPath.value === originalPath && editorPath.value.trim() === path) {
      selectedPath.value = savedPath
      editorPath.value = savedPath
      originalContent.value = content
    }
    await loadTree()
    emit('refresh')
    notify('知识页面已保存', 'success')
  } catch (error) {
    console.error('Failed to save Wiki page:', error)
    notify('保存知识页面失败', 'error')
  } finally {
    saving.value = false
  }
}

const requestMove = (entry: WikiTreeNode) => {
  if (operationBusy.value) {
    notify('当前操作完成后才能移动文件', 'error')
    return
  }
  if (hasChanges.value) {
    notify('请先保存或放弃未保存修改，再移动文件', 'error')
    return
  }
  pathActionTarget.value = entry
  moveTargetDirectory.value = entry.path.split('/').slice(0, -1).join('/')
  moveDialog.value = true
}

const movePath = async () => {
  const target = pathActionTarget.value
  if (!target || operationBusy.value) return
  const name = target.path.split('/').pop()
  if (!name) return
  const targetPath = moveTargetDirectory.value ? `${moveTargetDirectory.value}/${name}` : name
  if (targetPath === target.path) {
    notify('请选择不同的目标文件夹', 'error')
    return
  }
  moving.value = true
  try {
    const response = await knowledgeApi.moveWikiPath(props.kbId, target.path, targetPath)
    if (response.data.status !== 'ok') throw new Error(response.data.message || '移动失败')
    if (selectedPath.value === target.path || selectedPath.value.startsWith(`${target.path}/`)) {
      const suffix = selectedPath.value.slice(target.path.length)
      selectedPath.value = `${targetPath}${suffix}`
      editorPath.value = selectedPath.value
    }
    moveDialog.value = false
    pathActionTarget.value = null
    await loadTree()
    emit('refresh')
    notify('知识文件已移动', 'success')
  } catch (error) {
    console.error('Failed to move Wiki path:', error)
    notify('移动知识文件失败', 'error')
  } finally {
    moving.value = false
  }
}

const requestDelete = (entry: WikiTreeNode) => {
  if (operationBusy.value) {
    notify('当前操作完成后才能删除文件', 'error')
    return
  }
  if (hasChanges.value) {
    notify('请先保存或放弃未保存修改，再删除文件', 'error')
    return
  }
  pathActionTarget.value = entry
  deleteDialog.value = true
}

const requestSelectedPageDelete = () => {
  if (!selectedPath.value) return
  requestDelete({
    name: selectedPath.value.split('/').pop() || selectedPath.value,
    path: selectedPath.value,
    type: 'page',
    title: selectedPath.value.split('/').pop(),
  })
}

const deletePath = async () => {
  const target = pathActionTarget.value
  if (operationBusy.value || !target) return
  const path = target.path
  deleteDialog.value = false
  deleting.value = true
  try {
    const response = await knowledgeApi.deleteWikiPath(
      props.kbId,
      path,
      target.type === 'directory',
    )
    if (response.data.status !== 'ok') throw new Error(response.data.message || '删除失败')
    if (
      selectedPath.value === path ||
      (target.type === 'directory' && selectedPath.value.startsWith(`${path}/`))
    ) {
      pageLoadRequestId += 1
      selectedPath.value = ''
      editorPath.value = ''
      editorContent.value = ''
      originalContent.value = ''
    }
    await loadTree()
    emit('refresh')
    pathActionTarget.value = null
    notify(target.type === 'directory' ? '知识文件夹已删除' : '知识页面已删除', 'success')
  } catch (error) {
    console.error('Failed to delete Wiki path:', error)
    notify('删除知识文件失败', 'error')
  } finally {
    deleting.value = false
  }
}

const rebuildIndex = async () => {
  if (operationBusy.value) {
    notify('当前操作完成后才能重建索引', 'error')
    return
  }
  if (hasChanges.value) {
    notify('请先保存或放弃未保存修改，再重建索引', 'error')
    return
  }
  rebuilding.value = true
  try {
    const response = await knowledgeApi.rebuildWiki(props.kbId)
    if (response.data.status !== 'ok') throw new Error(response.data.message || '重建失败')
    await loadTree()
    emit('refresh')
    notify(
      `索引已重建：${response.data.data?.pages || 0} 个页面，${
        response.data.data?.chunks || 0
      } 个片段`,
      'success',
    )
  } catch (error) {
    console.error('Failed to rebuild Wiki index:', error)
    notify('重建知识库索引失败', 'error')
  } finally {
    rebuilding.value = false
  }
}

onMounted(loadTree)

watch(
  () => props.requestedPage,
  (request) => {
    if (request?.path) {
      openPage(request.path)
    }
  },
  { immediate: true },
)
</script>

<template>
  <div>
    <div class="wiki-actions mb-4">
      <div class="wiki-actions__copy">
        <div class="wiki-actions__title">知识文件</div>
        <div class="wiki-actions__desc">
          文件夹是真实目录，移动后会自动维护内部链接和索引。
        </div>
      </div>
      <v-spacer />
      <v-btn
        prepend-icon="mdi-file-plus-outline"
        color="primary"
        variant="tonal"
        class="wiki-action-btn wiki-action-btn--primary"
        :disabled="operationBusy"
        @click="newPage"
      >
        新建页面
      </v-btn>
      <v-btn
        prepend-icon="mdi-folder-upload-outline"
        variant="outlined"
        class="wiki-action-btn"
        :disabled="operationBusy"
        :loading="importing"
        @click="openImportDialog"
      >
        导入
      </v-btn>
      <v-btn
        prepend-icon="mdi-database-refresh"
        variant="text"
        class="wiki-action-btn wiki-action-btn--ghost"
        :disabled="operationBusy"
        :loading="rebuilding"
        @click="rebuildIndex"
      >
        重建索引
      </v-btn>
    </div>

    <div class="wiki-layout">
      <WikiFileBrowser
        :tree="tree"
        :selected-path="selectedPath"
        :loading="treeLoading"
        :busy="operationBusy"
        @open-page="openPage"
        @request-move="requestMove"
        @request-delete="requestDelete"
      />

      <v-card class="wiki-editor" variant="flat">
        <v-card-title class="wiki-toolbar">
          <div class="wiki-toolbar__label">
            <v-icon size="18">mdi-file-document-edit-outline</v-icon>
            编辑页面
          </div>
          <v-text-field
            v-model="editorPath"
            density="compact"
            hide-details
            placeholder="category/page-name.md"
            prepend-inner-icon="mdi-file-tree"
            :readonly="!!selectedPath"
            :disabled="operationBusy"
            variant="outlined"
            class="wiki-path-field"
          />
          <v-spacer />
          <v-btn
            v-if="selectedPath"
            color="error"
            prepend-icon="mdi-delete-outline"
            variant="text"
            :disabled="operationBusy"
            :loading="deleting"
            @click="requestSelectedPageDelete"
          >
            删除
          </v-btn>
          <v-btn
            color="primary"
            prepend-icon="mdi-content-save-outline"
            variant="tonal"
            class="wiki-save-btn"
            :disabled="operationBusy || (!hasChanges && !!selectedPath)"
            :loading="saving"
            @click="savePage"
          >
            保存
          </v-btn>
        </v-card-title>
        <v-card-text class="wiki-editor-content">
          <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-3">
            {{ errorMessage }}
          </v-alert>
          <v-alert v-if="successMessage" type="success" variant="tonal" class="mb-3">
            {{ successMessage }}
          </v-alert>
          <v-textarea
            v-model="editorContent"
            class="wiki-textarea"
            hide-details
            placeholder="选择左侧页面，或新建 Markdown 知识页面。"
            variant="outlined"
            spellcheck="false"
            :disabled="operationBusy"
          />
        </v-card-text>
      </v-card>
    </div>

    <v-dialog v-model="deleteDialog" max-width="460">
      <v-card>
        <v-card-title class="text-h3 pa-4 pb-0 pl-6">删除知识文件</v-card-title>
        <v-card-text class="pt-4">
          确定删除
          <strong>{{ pathActionTarget?.path }}</strong>
          吗？
          <template v-if="pathActionTarget?.type === 'directory'">
            文件夹内全部页面都会递归删除。
          </template>
          Markdown 真源及其派生索引会一并删除，此操作无法撤销。
        </v-card-text>
        <v-card-actions class="px-6 pb-4">
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">取消</v-btn>
          <v-btn color="error" variant="tonal" :loading="deleting" @click="deletePath">
            删除
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="moveDialog" max-width="520">
      <v-card>
        <v-card-title class="text-h3 pa-4 pb-0 pl-6">移动知识文件</v-card-title>
        <v-card-text class="pt-4">
          <div class="text-body-2 mb-4">
            将 <strong>{{ pathActionTarget?.path }}</strong> 移动到：
          </div>
          <v-select
            v-model="moveTargetDirectory"
            :items="directoryOptions"
            item-title="title"
            item-value="value"
            label="目标文件夹"
            variant="outlined"
            density="comfortable"
          />
          <v-alert type="info" variant="tonal" density="compact">
            文件名保持不变，相关 Markdown 链接与知识图谱索引会自动更新。
          </v-alert>
        </v-card-text>
        <v-card-actions class="px-6 pb-4">
          <v-spacer />
          <v-btn variant="text" @click="moveDialog = false">取消</v-btn>
          <v-btn color="primary" variant="tonal" :loading="moving" @click="movePath"> 移动 </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="discardDialog" max-width="460" persistent>
      <v-card>
        <v-card-title class="text-h3 pa-4 pb-0 pl-6">放弃未保存修改</v-card-title>
        <v-card-text class="pt-4"> 当前页面还有未保存的内容。继续后这些修改会丢失。 </v-card-text>
        <v-card-actions class="px-6 pb-4">
          <v-spacer />
          <v-btn variant="text" @click="cancelDiscard">继续编辑</v-btn>
          <v-btn color="warning" variant="tonal" @click="discardChanges">放弃并继续</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <WikiImportDialog
      v-model="importDialog"
      :kb-id="kbId"
      @busy="importing = $event"
      @imported="handleWikiImported"
    />
  </div>
</template>

<style scoped>
.wiki-layout {
  display: grid;
  grid-template-columns: minmax(340px, 34%) minmax(0, 1fr);
  gap: 18px;
  min-height: 620px;
}

.wiki-editor {
  display: flex;
  min-height: 620px;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #d8e8f3;
  border-radius: 16px;
  background: linear-gradient(180deg, #fbfdff 0%, #ffffff 34%);
}

.wiki-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  border-bottom: 1px solid #dcebf5;
  padding-bottom: 12px;
}

.wiki-actions__title {
  color: #102033;
  font-size: 1rem;
  font-weight: 700;
}

.wiki-actions__desc {
  color: #667789;
  font-size: 0.8rem;
  margin-top: 3px;
}

.wiki-action-btn {
  border-radius: 10px;
  font-weight: 600;
  letter-spacing: 0;
}

.wiki-action-btn--primary {
  background: #e7f4fd;
}

.wiki-action-btn--ghost {
  color: #2f8fc8;
}

.wiki-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 68px;
  border-bottom: 1px solid #e1edf6;
  background: #f7fbfe;
  padding: 12px 16px;
}

.wiki-toolbar__label {
  display: inline-flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 6px;
  color: #365268;
  font-size: 0.86rem;
  font-weight: 700;
}

.wiki-editor-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  padding: 16px;
  background: #ffffff;
}

.wiki-path-field {
  max-width: 560px;
}

.wiki-path-field :deep(.v-field) {
  border-radius: 12px;
  background: #ffffff;
  box-shadow: none;
}

.wiki-save-btn {
  min-width: 88px;
  border-radius: 10px;
  font-weight: 700;
}

.wiki-textarea {
  flex: 1;
}

.wiki-textarea :deep(.v-field) {
  min-height: 100%;
  border-radius: 14px;
  background:
    linear-gradient(#ffffff, #ffffff) padding-box,
    linear-gradient(180deg, #dcebf6, #edf4f9) border-box;
}

.wiki-textarea :deep(.v-field__input) {
  padding: 18px 20px;
}

.wiki-textarea :deep(textarea) {
  min-height: 470px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  line-height: 1.6;
}

@media (max-width: 960px) {
  .wiki-layout {
    grid-template-columns: 1fr;
  }

  .wiki-editor {
    min-height: auto;
  }
}
</style>
