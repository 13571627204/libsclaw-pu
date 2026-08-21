<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue'
import type { WikiTreeNode } from '@/api/v1'

interface Props {
  tree: WikiTreeNode | null
  selectedPath: string
  loading?: boolean
  busy?: boolean
}

interface BrowserEntry extends WikiTreeNode {
  descendantCount: number
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  busy: false,
})

const emit = defineEmits<{
  openPage: [path: string]
  requestMove: [entry: WikiTreeNode]
  requestDelete: [entry: WikiTreeNode]
}>()

const currentPath = shallowRef('')
const search = shallowRef('')

const allEntries = computed(() => {
  const entries: WikiTreeNode[] = []
  const visit = (node: WikiTreeNode) => {
    if (node.path) entries.push(node)
    node.children?.forEach(visit)
  }
  if (props.tree) visit(props.tree)
  return entries
})

const directoryMap = computed(() => {
  const directories = new Map<string, WikiTreeNode>()
  if (props.tree) directories.set('', props.tree)
  allEntries.value.forEach((entry) => {
    if (entry.type === 'directory') directories.set(entry.path, entry)
  })
  return directories
})

const descendantPageCount = (node: WikiTreeNode): number =>
  node.type === 'page'
    ? 1
    : (node.children || []).reduce((total, child) => total + descendantPageCount(child), 0)

const currentDirectory = computed(() => directoryMap.value.get(currentPath.value) || props.tree)

const visibleEntries = computed<BrowserEntry[]>(() => {
  const query = search.value.trim().toLocaleLowerCase()
  const source = query
    ? allEntries.value.filter((entry) =>
        `${entry.title || entry.name} ${entry.path}`.toLocaleLowerCase().includes(query),
      )
    : currentDirectory.value?.children || []
  return source
    .map((entry) => ({
      ...entry,
      descendantCount: descendantPageCount(entry),
    }))
    .sort((left, right) => {
      if (left.type !== right.type) return left.type === 'directory' ? -1 : 1
      return (left.title || left.name).localeCompare(right.title || right.name, 'zh-CN')
    })
})

const breadcrumbs = computed(() => {
  const crumbs = [{ title: 'knowledge', path: '' }]
  let path = ''
  currentPath.value.split('/').forEach((part) => {
    if (!part) return
    path = path ? `${path}/${part}` : part
    crumbs.push({ title: part, path })
  })
  return crumbs
})

const parentPath = computed(() => {
  const parts = currentPath.value.split('/').filter(Boolean)
  parts.pop()
  return parts.join('/')
})

const formatFileSize = (bytes?: number) => {
  if (!bytes) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`
}

const openEntry = (entry: WikiTreeNode) => {
  if (props.busy) return
  if (entry.type === 'directory') {
    currentPath.value = entry.path
    search.value = ''
    return
  }
  emit('openPage', entry.path)
}

watch(
  () => props.tree,
  () => {
    if (!directoryMap.value.has(currentPath.value)) currentPath.value = ''
  },
)

watch(
  () => props.selectedPath,
  (path) => {
    if (!path) return
    const parent = path.split('/').slice(0, -1).join('/')
    if (directoryMap.value.has(parent)) currentPath.value = parent
  },
)
</script>

<template>
  <v-card class="file-browser" variant="flat">
    <v-card-title class="file-browser-title">
      <div>
        <div class="file-browser-heading">文件管理</div>
        <div class="file-browser-desc">按目录浏览 Markdown 真源</div>
      </div>
      <v-spacer />
      <v-chip class="file-browser-count" size="small" variant="tonal">
        {{ tree ? descendantPageCount(tree) : 0 }} 个页面
      </v-chip>
    </v-card-title>

    <v-card-text class="file-browser-body">
      <v-text-field
        v-model="search"
        prepend-inner-icon="mdi-magnify"
        density="compact"
        hide-details
        clearable
        placeholder="搜索文件名或路径"
        variant="outlined"
        class="file-search mb-3"
      />

      <div v-if="!search" class="breadcrumb-bar mb-3">
        <v-btn
          icon="mdi-arrow-up"
          size="x-small"
          variant="text"
          :disabled="!currentPath || busy"
          @click="currentPath = parentPath"
        />
        <div class="breadcrumb-list">
          <template v-for="(crumb, index) in breadcrumbs" :key="crumb.path">
            <v-icon v-if="index" size="15">mdi-chevron-right</v-icon>
            <button
              class="breadcrumb-button"
              :class="{
                'breadcrumb-button--active': index === breadcrumbs.length - 1,
              }"
              type="button"
              :disabled="busy"
              @click="currentPath = crumb.path"
            >
              {{ crumb.title }}
            </button>
          </template>
        </div>
      </div>

      <div v-if="loading && visibleEntries.length === 0" class="browser-empty">
        <v-progress-circular indeterminate color="primary" />
      </div>

      <div v-else-if="visibleEntries.length" class="file-grid">
        <div
          v-for="entry in visibleEntries"
          :key="entry.path"
          role="button"
          :tabindex="busy ? -1 : 0"
          :aria-disabled="busy"
          class="file-card"
          :class="{
            'file-card--folder': entry.type === 'directory',
            'file-card--selected': entry.path === selectedPath,
            'file-card--disabled': busy,
          }"
          @click="openEntry(entry)"
          @keydown.enter.prevent="openEntry(entry)"
          @keydown.space.prevent="openEntry(entry)"
        >
          <div class="file-card-icon">
            <v-icon :color="entry.type === 'directory' ? 'warning' : 'info'" size="34">
              {{ entry.type === 'directory' ? 'mdi-folder' : 'mdi-language-markdown-outline' }}
            </v-icon>
          </div>
          <div class="file-card-content">
            <div class="file-card-name" :title="entry.title || entry.name">
              {{ entry.title || entry.name }}
            </div>
            <div class="file-card-meta">
              <span v-if="entry.type === 'directory'"> {{ entry.descendantCount }} 个页面 </span>
              <span v-else>
                {{ entry.node_type || 'other' }}
                <template v-if="formatFileSize(entry.size)">
                  · {{ formatFileSize(entry.size) }}
                </template>
              </span>
            </div>
            <div v-if="search" class="file-card-path">{{ entry.path }}</div>
          </div>

          <v-menu location="bottom end">
            <template #activator="{ props: menuProps }">
              <v-btn
                v-bind="menuProps"
                class="file-card-menu"
                icon="mdi-dots-vertical"
                size="x-small"
                variant="text"
                :disabled="busy"
                @click.stop
              />
            </template>
            <v-list density="compact">
              <v-list-item
                v-if="entry.type === 'page'"
                prepend-icon="mdi-file-edit-outline"
                title="打开"
                @click="emit('openPage', entry.path)"
              />
              <v-list-item
                prepend-icon="mdi-folder-move-outline"
                title="移动"
                @click="emit('requestMove', entry)"
              />
              <v-list-item
                prepend-icon="mdi-delete-outline"
                title="删除"
                base-color="error"
                @click="emit('requestDelete', entry)"
              />
            </v-list>
          </v-menu>
        </div>
      </div>

      <div v-else class="browser-empty text-medium-emphasis">
        <v-icon size="56" color="grey-lighten-1">
          {{ search ? 'mdi-file-search-outline' : 'mdi-folder-open-outline' }}
        </v-icon>
        <div class="mt-3">
          {{ search ? '没有匹配的文件' : '当前文件夹为空' }}
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.file-browser {
  min-height: 620px;
  overflow: hidden;
  border: 1px solid #d8e8f3;
  border-radius: 16px;
  background: #ffffff;
}

.file-browser-title {
  display: flex;
  align-items: center;
  min-height: 76px;
  border-bottom: 1px solid #e1edf6;
  background: #f7fbfe;
  padding: 16px 18px;
}

.file-browser-heading {
  color: #102033;
  font-size: 0.98rem;
  font-weight: 750;
}

.file-browser-desc {
  color: #6b7d8f;
  font-size: 0.76rem;
  margin-top: 4px;
}

.file-browser-count {
  background: #e6f3fb;
  color: #2b83b9;
  font-weight: 700;
}

.file-browser-body {
  height: 544px;
  overflow: auto;
  padding: 16px;
}

.file-search :deep(.v-field) {
  border-radius: 12px;
  background: #fbfdff;
}

.breadcrumb-bar,
.breadcrumb-list {
  display: flex;
  align-items: center;
}

.breadcrumb-bar {
  min-height: 36px;
  border: 1px solid #dceaf4;
  border-radius: 12px;
  background: #f8fbfd;
  padding: 2px 6px;
}

.breadcrumb-list {
  min-width: 0;
  overflow-x: auto;
}

.breadcrumb-button {
  border: 0;
  background: transparent;
  color: #607184;
  cursor: pointer;
  font-size: 0.78rem;
  padding: 4px 7px;
  white-space: nowrap;
}

.breadcrumb-button--active {
  color: #172437;
  font-weight: 600;
}

.file-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-card {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: 66px;
  align-items: center;
  gap: 12px;
  border: 1px solid #e3edf5;
  border-radius: 12px;
  background: #ffffff;
  color: inherit;
  cursor: pointer;
  padding: 10px 40px 10px 12px;
  text-align: left;
  transition:
    background-color 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease;
}

.file-card:hover {
  border-color: #b9dcf3;
  background: #f6fbff;
  box-shadow: inset 3px 0 0 #46a1d8;
}

.file-card--disabled {
  cursor: wait;
  opacity: 0.62;
}

.file-card--folder {
  background: #fffdf8;
}

.file-card--selected {
  border-color: #95cdf0;
  background: #eef8ff;
  box-shadow: inset 3px 0 0 #2f96d3;
}

.file-card-icon {
  display: inline-flex;
  width: 38px;
  height: 38px;
  align-items: center;
  flex: 0 0 auto;
  justify-content: center;
  border-radius: 11px;
  background: #eef8ff;
}

.file-card-content {
  min-width: 0;
  flex: 1;
}

.file-card-name,
.file-card-path {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-card-name {
  color: #172437;
  font-size: 0.86rem;
  font-weight: 700;
}

.file-card-meta,
.file-card-path {
  color: #718296;
  font-size: 0.72rem;
  margin-top: 4px;
}

.file-card-menu {
  position: absolute;
  right: 4px;
  top: 4px;
}

.browser-empty {
  display: flex;
  min-height: 300px;
  align-items: center;
  flex-direction: column;
  justify-content: center;
  text-align: center;
}

@media (max-width: 960px) {
  .file-browser,
  .file-browser-body {
    min-height: auto;
    height: auto;
  }

  .file-browser-body {
    max-height: 460px;
  }
}
</style>
