<script setup lang="ts">
import { computed, onMounted, onUnmounted, shallowRef, watch } from 'vue'
import { knowledgeApi } from '@/api/v1'
import type { WikiGraphEdge, WikiGraphNode } from '@/api/v1'
import KnowledgeGraphCanvas from './KnowledgeGraphCanvas.vue'

interface Props {
  kbId: string
}

interface SelectedRelation {
  edge: WikiGraphEdge
  direction: 'incoming' | 'outgoing'
  node?: WikiGraphNode
}

const props = defineProps<Props>()

const emit = defineEmits<{
  openPage: [path: string]
}>()

const typeStyles: Record<string, { label: string; color: string }> = {
  entity: { label: '实体', color: '#4f8cff' },
  concept: { label: '概念', color: '#8b5cf6' },
  source: { label: '来源', color: '#f59e0b' },
  synthesis: { label: '综合', color: '#ef4444' },
  overview: { label: '概述', color: '#eab308' },
  comparison: { label: '比较', color: '#14b8a6' },
  other: { label: '其他', color: '#94a3b8' },
}

const nodeColors = Object.fromEntries(
  Object.entries(typeStyles).map(([type, style]) => [type, style.color]),
)

const normalizeNodeType = (nodeType?: string) =>
  nodeType && typeStyles[nodeType] ? nodeType : 'other'

const loading = shallowRef(false)
const detailLoading = shallowRef(false)
const errorMessage = shallowRef('')
const nodes = shallowRef<WikiGraphNode[]>([])
const edges = shallowRef<WikiGraphEdge[]>([])
const selectedNodeId = shallowRef('')
const selectedExcerpt = shallowRef('')
const searchInput = shallowRef('')
const search = shallowRef('')
const activeTypes = shallowRef(new Set(Object.keys(typeStyles)))
const graphExpanded = shallowRef(false)
let graphLoadRequestId = 0
let detailLoadRequestId = 0
let searchTimer: number | null = null
let previousBodyOverflow = ''

const nodeMap = computed(() => new Map(nodes.value.map((node) => [node.id, node])))

const selectedNode = computed(() => nodeMap.value.get(selectedNodeId.value) || null)

const legendItems = computed(() =>
  Object.entries(typeStyles).map(([type, style]) => ({
    type,
    ...style,
    active: activeTypes.value.has(type),
    count: nodes.value.filter((node) => normalizeNodeType(node.node_type) === type).length,
  })),
)

const filteredNodes = computed(() => {
  const query = search.value.trim().toLocaleLowerCase()
  return nodes.value.filter((node) => {
    const nodeType = normalizeNodeType(node.node_type)
    if (!activeTypes.value.has(nodeType)) return false
    if (!query) return true
    return `${node.label} ${node.id} ${node.category}`.toLocaleLowerCase().includes(query)
  })
})

const filteredNodeIds = computed(() => new Set(filteredNodes.value.map((node) => node.id)))

const filteredEdges = computed(() =>
  edges.value.filter(
    (edge) => filteredNodeIds.value.has(edge.source) && filteredNodeIds.value.has(edge.target),
  ),
)

const selectedRelations = computed<SelectedRelation[]>(() => {
  if (!selectedNodeId.value) return []
  return edges.value.flatMap<SelectedRelation>((edge) => {
    if (edge.source === selectedNodeId.value) {
      return [
        {
          edge,
          direction: 'outgoing',
          node: nodeMap.value.get(edge.target),
        },
      ]
    }
    if (edge.target === selectedNodeId.value) {
      return [
        {
          edge,
          direction: 'incoming',
          node: nodeMap.value.get(edge.source),
        },
      ]
    }
    return []
  })
})

const stripMarkdown = (content: string) =>
  content
    .replace(/^---\s*\n[\s\S]*?\n---\s*\n?/, '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(
      /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g,
      (_match, target: string, alias?: string) => alias || target,
    )
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^>\s?/gm, '')
    .replace(/[*_~`]/g, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
    .slice(0, 1200)

const loadGraph = async () => {
  const requestId = ++graphLoadRequestId
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await knowledgeApi.wikiGraph(props.kbId)
    if (response.data.status !== 'ok') throw new Error(response.data.message || '加载失败')
    if (requestId !== graphLoadRequestId) return
    nodes.value = response.data.data?.nodes || []
    edges.value = response.data.data?.edges || []
    activeTypes.value = new Set(Object.keys(typeStyles))
    if (selectedNodeId.value && !nodeMap.value.has(selectedNodeId.value)) {
      selectedNodeId.value = ''
      selectedExcerpt.value = ''
    }
  } catch (error) {
    if (requestId !== graphLoadRequestId) return
    console.error('Failed to load knowledge graph:', error)
    errorMessage.value = '加载知识图谱失败'
  } finally {
    if (requestId === graphLoadRequestId) loading.value = false
  }
}

const loadNodeExcerpt = async (node: WikiGraphNode) => {
  const requestId = ++detailLoadRequestId
  selectedExcerpt.value = node.evidence || ''
  if (!node.page_path) return
  detailLoading.value = true
  try {
    const response = await knowledgeApi.wikiPage(props.kbId, node.page_path)
    if (requestId !== detailLoadRequestId) return
    if (response.data.status === 'ok') {
      selectedExcerpt.value =
        stripMarkdown(response.data.data?.content || '') || node.evidence || '暂无摘要'
    }
  } catch (error) {
    if (requestId !== detailLoadRequestId) return
    console.error('Failed to load graph node excerpt:', error)
  } finally {
    if (requestId === detailLoadRequestId) detailLoading.value = false
  }
}

const selectNode = (nodeId: string) => {
  selectedNodeId.value = nodeId
  const node = nodeMap.value.get(nodeId)
  if (node) void loadNodeExcerpt(node)
}

const closeDetails = () => {
  detailLoadRequestId += 1
  detailLoading.value = false
  selectedNodeId.value = ''
  selectedExcerpt.value = ''
}

const toggleType = (type: string) => {
  const next = new Set(activeTypes.value)
  if (next.has(type)) next.delete(type)
  else next.add(type)
  activeTypes.value = next
}

const showAllTypes = () => {
  activeTypes.value = new Set(Object.keys(typeStyles))
}

watch(filteredNodeIds, (visibleIds) => {
  if (selectedNodeId.value && !visibleIds.has(selectedNodeId.value)) {
    closeDetails()
  }
})

watch(searchInput, (value) => {
  if (searchTimer !== null) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    search.value = value
    searchTimer = null
  }, 140)
})

watch(graphExpanded, (expanded) => {
  if (expanded) {
    previousBodyOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return
  }
  document.body.style.overflow = previousBodyOverflow
})

onMounted(loadGraph)

onUnmounted(() => {
  if (searchTimer !== null) window.clearTimeout(searchTimer)
  if (graphExpanded.value) document.body.style.overflow = previousBodyOverflow
})
</script>

<template>
  <v-card variant="flat" class="graph-card">
    <v-card-title class="graph-toolbar">
      <div class="graph-title-block">
        <div class="graph-title-line">
          <span class="graph-title">知识图谱</span>
          <span class="graph-count-pill">
            {{ filteredNodes.length }} / {{ nodes.length }} 个节点
          </span>
          <span class="graph-count-pill graph-count-pill--muted">
            {{ filteredEdges.length }} 条关系
          </span>
        </div>
        <div class="graph-subtitle">查看知识节点之间的引用、概念与来源关系。</div>
      </div>
      <v-spacer />
      <div class="graph-toolbar-actions">
        <v-text-field
          v-model="searchInput"
          prepend-inner-icon="mdi-magnify"
          density="compact"
          hide-details
          clearable
          placeholder="搜索节点"
          variant="outlined"
          class="graph-search"
        />
        <v-btn
          prepend-icon="mdi-refresh"
          variant="tonal"
          class="graph-refresh-btn"
          :loading="loading"
          @click="loadGraph"
        >
          刷新
        </v-btn>
      </div>
    </v-card-title>

    <v-card-text class="graph-content">
      <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-3">
        {{ errorMessage }}
      </v-alert>

      <div v-if="loading && nodes.length === 0" class="graph-empty">
        <v-progress-circular indeterminate color="primary" />
      </div>
      <div v-else-if="filteredNodes.length === 0" class="graph-empty text-medium-emphasis">
        <v-icon size="72" color="grey-lighten-1"> mdi-graph-outline </v-icon>
        <div class="mt-3">当前筛选条件下没有节点</div>
        <v-btn class="mt-3" variant="tonal" @click="showAllTypes"> 显示全部类型 </v-btn>
      </div>
      <Teleport v-else to="body" :disabled="!graphExpanded">
        <div class="graph-shell" :class="{ 'graph-shell--expanded': graphExpanded }">
          <KnowledgeGraphCanvas
            :nodes="filteredNodes"
            :edges="filteredEdges"
            :selected-node-id="selectedNodeId"
            :node-colors="nodeColors"
            :expanded="graphExpanded"
            @select-node="selectNode"
            @toggle-expanded="graphExpanded = !graphExpanded"
          />

          <div class="graph-legend">
            <div class="legend-heading">
              <div>
                <span class="legend-title">节点类型</span>
                <span class="legend-subtitle">点击切换显示</span>
              </div>
              <v-btn size="x-small" variant="tonal" class="legend-reset-btn" @click="showAllTypes">
                全部
              </v-btn>
            </div>
            <button
              v-for="item in legendItems"
              :key="item.type"
              type="button"
              class="legend-row"
              :class="{ 'legend-row--inactive': !item.active }"
              @click="toggleType(item.type)"
            >
              <span class="legend-dot" :style="{ backgroundColor: item.color }" />
              <span>{{ item.label }}</span>
              <v-spacer />
              <span class="text-medium-emphasis">{{ item.count }}</span>
              <v-icon size="16">
                {{ item.active ? 'mdi-eye-outline' : 'mdi-eye-off-outline' }}
              </v-icon>
            </button>
          </div>

          <v-card v-if="selectedNode" class="graph-detail" variant="elevated">
            <v-card-title class="graph-detail-title">
              <div class="min-width-0">
                <div class="text-subtitle-1 font-weight-bold text-truncate">
                  {{ selectedNode.label }}
                </div>
                <div class="text-caption text-medium-emphasis text-truncate">
                  {{ selectedNode.id }}
                </div>
              </div>
              <v-spacer />
              <v-btn icon="mdi-close" size="small" variant="text" @click="closeDetails" />
            </v-card-title>
            <v-divider />
            <v-card-text class="graph-detail-body">
              <div class="d-flex align-center flex-wrap ga-2 mb-4">
                <v-chip
                  size="small"
                  :color="
                    typeStyles[normalizeNodeType(selectedNode.node_type)].color ||
                    typeStyles.other.color
                  "
                  variant="tonal"
                >
                  {{ typeStyles[normalizeNodeType(selectedNode.node_type)].label }}
                </v-chip>
                <v-chip size="small" variant="outlined">
                  {{ selectedNode.category }}
                </v-chip>
                <v-chip size="small" variant="outlined">
                  {{ selectedRelations.length }} 条关系
                </v-chip>
              </div>

              <div v-if="selectedNode.source" class="detail-section">
                <div class="detail-label">来源</div>
                <div class="text-body-2">{{ selectedNode.source }}</div>
              </div>

              <div class="detail-section">
                <div class="detail-label">笔记摘要</div>
                <v-progress-linear
                  v-if="detailLoading"
                  indeterminate
                  color="primary"
                  class="mb-3"
                />
                <div class="detail-excerpt">
                  {{ selectedExcerpt || selectedNode.evidence || '暂无摘要' }}
                </div>
              </div>

              <div v-if="selectedRelations.length" class="detail-section">
                <div class="detail-label">关联节点</div>
                <div class="relation-list">
                  <button
                    v-for="relation in selectedRelations"
                    :key="relation.edge.id"
                    type="button"
                    class="relation-row"
                    @click="relation.node && selectNode(relation.node.id)"
                  >
                    <v-icon size="16">
                      {{
                        relation.direction === 'outgoing' ? 'mdi-arrow-right' : 'mdi-arrow-left'
                      }}
                    </v-icon>
                    <span class="relation-label">
                      {{ relation.node?.label || '未知节点' }}
                    </span>
                    <span class="relation-type">{{ relation.edge.relation }}</span>
                  </button>
                </div>
              </div>
            </v-card-text>
            <v-divider />
            <v-card-actions class="px-4 py-3">
              <v-spacer />
              <v-btn
                v-if="selectedNode.page_path"
                prepend-icon="mdi-file-edit-outline"
                color="primary"
                variant="tonal"
                @click="emit('openPage', selectedNode.page_path)"
              >
                打开笔记
              </v-btn>
            </v-card-actions>
          </v-card>
        </div>
      </Teleport>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.graph-card {
  min-height: 760px;
  overflow: hidden;
  border: 1px solid #d8e8f3;
  border-radius: 16px;
  background: #ffffff;
}

.graph-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 86px;
  flex-wrap: wrap;
  border-bottom: 1px solid #e1edf6;
  background: linear-gradient(180deg, #f7fbfe 0%, #ffffff 100%);
  padding: 16px 18px;
}

.graph-title-block {
  min-width: 0;
}

.graph-title-line,
.graph-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.graph-title {
  color: #102033;
  font-size: 1rem;
  font-weight: 750;
}

.graph-subtitle {
  color: #6b7d8f;
  font-size: 0.78rem;
  margin-top: 5px;
}

.graph-count-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  border: 1px solid #c8e3f6;
  border-radius: 999px;
  background: #eaf6fd;
  color: #2584bd;
  font-size: 0.74rem;
  font-weight: 700;
  padding: 0 9px;
}

.graph-count-pill--muted {
  border-color: #dfe8ef;
  background: #f4f8fb;
  color: #5f7285;
}

.graph-search {
  width: 300px;
}

.graph-search :deep(.v-field) {
  border-radius: 12px;
  background: #ffffff;
}

.graph-refresh-btn {
  border-radius: 10px;
  color: #2a8cc7;
  font-weight: 700;
  letter-spacing: 0;
}

.graph-content {
  padding: 16px;
  background: #fbfdff;
}

.graph-shell {
  position: relative;
  min-height: 660px;
  overflow: hidden;
  border: 1px solid #dceaf4;
  border-radius: 16px;
  background: #ffffff;
  transition: min-height 0.22s ease;
}

.graph-shell--expanded {
  position: fixed;
  z-index: 10050;
  inset: 0;
  width: 100vw;
  height: 100vh;
  min-height: 100vh;
  border: 0;
  border-radius: 0;
  background: #fbfdff;
  box-shadow: none;
}

.graph-shell--expanded .graph-detail {
  max-height: calc(100vh - 36px);
}

.graph-empty {
  display: flex;
  min-height: 660px;
  align-items: center;
  flex-direction: column;
  justify-content: center;
  text-align: center;
}

.graph-legend,
.graph-detail {
  position: absolute;
  z-index: 3;
  border: 1px solid #d9e8f3;
}

.graph-legend {
  right: 18px;
  bottom: 18px;
  width: 210px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 12px 34px rgba(42, 79, 110, 0.12);
  padding: 12px;
}

.legend-heading,
.legend-row {
  display: flex;
  align-items: center;
}

.legend-heading {
  justify-content: space-between;
  margin-bottom: 8px;
}

.legend-title,
.legend-subtitle {
  display: block;
}

.legend-title {
  color: #14263a;
  font-size: 0.82rem;
  font-weight: 750;
}

.legend-subtitle {
  color: #8090a2;
  font-size: 0.68rem;
  margin-top: 2px;
}

.legend-reset-btn {
  border-radius: 8px;
  color: #2a8cc7;
  font-weight: 700;
}

.legend-row {
  width: 100%;
  gap: 9px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: #203247;
  cursor: pointer;
  font-size: 0.78rem;
  padding: 7px 6px;
  text-align: left;
}

.legend-row:hover {
  background: #f1f8fd;
}

.legend-row--inactive {
  opacity: 0.42;
}

.legend-dot {
  width: 9px;
  height: 9px;
  flex: 0 0 auto;
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgba(47, 150, 211, 0.08);
}

.graph-detail {
  top: 18px;
  right: 18px;
  display: flex;
  width: min(390px, calc(100% - 32px));
  max-height: 610px;
  flex-direction: column;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 18px 46px rgba(42, 79, 110, 0.16);
}

.graph-detail-title {
  display: flex;
  min-width: 0;
  align-items: center;
  padding: 14px 16px;
}

.min-width-0 {
  min-width: 0;
}

.graph-detail-body {
  overflow-y: auto;
  padding: 16px;
}

.detail-section + .detail-section {
  margin-top: 18px;
}

.detail-label {
  color: rgb(var(--v-theme-on-surface-variant));
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin-bottom: 7px;
  text-transform: uppercase;
}

.detail-excerpt {
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.86rem;
  line-height: 1.72;
  white-space: pre-wrap;
}

.relation-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.relation-row {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
  border: 0;
  border-radius: 8px;
  background: rgba(var(--v-theme-surface-variant), 0.45);
  color: inherit;
  cursor: pointer;
  padding: 8px 9px;
  text-align: left;
}

.relation-row:hover {
  background: rgba(var(--v-theme-primary), 0.1);
}

.relation-label {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.relation-type {
  color: rgb(var(--v-theme-on-surface-variant));
  font-size: 0.68rem;
}

@media (max-width: 960px) {
  .graph-card {
    min-height: 700px;
  }

  .graph-search {
    width: 100%;
    max-width: none;
  }

  .graph-detail {
    top: 12px;
    right: 12px;
    width: calc(100% - 24px);
    max-height: 520px;
  }

  .graph-legend {
    right: 12px;
    bottom: 12px;
  }
}
</style>
