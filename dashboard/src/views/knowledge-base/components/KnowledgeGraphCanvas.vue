<script setup lang="ts">
import * as d3 from 'd3'
import { nextTick, onMounted, onUnmounted, shallowRef, watch } from 'vue'
import type { WikiGraphEdge, WikiGraphNode } from '@/api/v1'

interface Props {
  nodes: WikiGraphNode[]
  edges: WikiGraphEdge[]
  selectedNodeId?: string
  nodeColors: Record<string, string>
  expanded?: boolean
}

interface SimulationNode extends WikiGraphNode, d3.SimulationNodeDatum {
  degree: number
}

interface SimulationEdge extends d3.SimulationLinkDatum<SimulationNode> {
  id: string
  relation: string
  evidence?: string | null
}

interface ConnectedEdgeElement {
  element: SVGLineElement
  edge: SimulationEdge
}

const props = withDefaults(defineProps<Props>(), {
  selectedNodeId: '',
  expanded: false,
})

const emit = defineEmits<{
  selectNode: [nodeId: string]
  toggleExpanded: []
}>()

const containerRef = shallowRef<HTMLDivElement | null>(null)
const svgRef = shallowRef<SVGSVGElement | null>(null)
let simulation: d3.Simulation<SimulationNode, SimulationEdge> | null = null
let zoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null
let graphGroup: d3.Selection<SVGGElement, unknown, null, undefined> | null = null
let nodeSelection: d3.Selection<SVGGElement, SimulationNode, SVGGElement, unknown> | null = null
let edgeSelection: d3.Selection<SVGLineElement, SimulationEdge, SVGGElement, unknown> | null = null
let labelSelection: d3.Selection<SVGTextElement, SimulationNode, SVGGElement, unknown> | null = null
let resizeObserver: ResizeObserver | null = null
let resizeFrame: number | null = null
let zoomFrame: number | null = null
let pendingZoomTransform: d3.ZoomTransform | null = null
let adjacency = new Map<string, Set<string>>()
let edgeElementsByNode = new Map<string, ConnectedEdgeElement[]>()
let hoveredNodeId = ''
let currentScale = 1
let labelsHiddenByScale = false
let labelVisibilityThreshold = 0.58
let lastWidth = 0
let lastHeight = 0

const nodeId = (value: string | number | SimulationNode) =>
  typeof value === 'object' ? value.id : String(value)

const nodeRadius = (node: SimulationNode) =>
  Math.min(28, 9 + Math.sqrt(Math.max(node.degree, 1)) * 4.2)

const nodeColor = (node: WikiGraphNode) =>
  props.nodeColors[node.node_type || 'other'] || props.nodeColors.other

const connectedNodeIds = (activeId: string) => {
  return adjacency.get(activeId) || new Set<string>([activeId])
}

const applyLabelVisibility = () => {
  const activeId = hoveredNodeId || props.selectedNodeId
  const connectedIds = activeId ? connectedNodeIds(activeId) : null
  labelSelection?.attr('opacity', (node) => {
    if (props.expanded) return !connectedIds || connectedIds.has(node.id) ? 1 : 0.2
    if (labelsHiddenByScale && node.id !== activeId) return 0
    return !connectedIds || connectedIds.has(node.id) ? 1 : 0.08
  })
}

const applyHighlight = () => {
  const activeId = hoveredNodeId || props.selectedNodeId
  const connectedIds = activeId ? connectedNodeIds(activeId) : null
  edgeSelection
    ?.attr('stroke-opacity', (edge) => {
      if (!activeId) return 0.24
      return nodeId(edge.source) === activeId || nodeId(edge.target) === activeId ? 0.86 : 0.045
    })
    .attr('stroke-width', (edge) => {
      if (!activeId) return 1.1
      return nodeId(edge.source) === activeId || nodeId(edge.target) === activeId ? 2.2 : 0.8
    })
  nodeSelection
    ?.attr('opacity', (node) => (!connectedIds || connectedIds.has(node.id) ? 1 : 0.16))
    .select('circle')
    .attr('stroke', (node) =>
      node.id === props.selectedNodeId
        ? 'rgb(var(--v-theme-primary))'
        : 'rgb(var(--v-theme-surface))',
    )
    .attr('stroke-width', (node) => (node.id === props.selectedNodeId ? 4 : 2))
  applyLabelVisibility()
}

const fitGraph = (animate = true) => {
  if (!svgRef.value || !containerRef.value || !graphGroup || !zoomBehavior) return
  const groupNode = graphGroup.node()
  if (!groupNode) return
  const bounds = groupNode.getBBox()
  if (!bounds.width || !bounds.height) return
  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight
  const padding = props.expanded ? 72 : 34
  const scaleBoost = props.expanded ? 1 : 1.28
  const scale = Math.min(
    2.4,
    Math.max(
      0.12,
      Math.min((width - padding * 2) / bounds.width, (height - padding * 2) / bounds.height) *
        scaleBoost,
    ),
  )
  const translateX = width / 2 - (bounds.x + bounds.width / 2) * scale
  const translateY = height / 2 - (bounds.y + bounds.height / 2) * scale
  const transform = d3.zoomIdentity.translate(translateX, translateY).scale(scale)
  const svg = d3.select(svgRef.value)
  if (animate) {
    svg.interrupt().transition().duration(420).call(zoomBehavior.transform, transform)
  } else {
    svg.call(zoomBehavior.transform, transform)
  }
}

const zoomBy = (factor: number) => {
  if (!svgRef.value || !zoomBehavior) return
  d3.select(svgRef.value).interrupt().transition().duration(180).call(zoomBehavior.scaleBy, factor)
}

const renderGraph = async () => {
  await nextTick()
  if (!svgRef.value || !containerRef.value) return
  simulation?.stop()
  if (zoomFrame !== null) window.cancelAnimationFrame(zoomFrame)
  zoomFrame = null
  pendingZoomTransform = null

  const width = Math.max(containerRef.value.clientWidth, 320)
  const height = Math.max(containerRef.value.clientHeight, 520)
  const svg = d3.select(svgRef.value)
  svg.interrupt().on('.zoom', null)
  svg.selectAll('*').remove()
  svg.attr('viewBox', `0 0 ${width} ${height}`)
  lastWidth = width
  lastHeight = height
  currentScale = 1

  const degreeMap = new Map<string, number>()
  adjacency = new Map(props.nodes.map((node) => [node.id, new Set<string>([node.id])]))
  props.edges.forEach((edge) => {
    degreeMap.set(edge.source, (degreeMap.get(edge.source) || 0) + 1)
    degreeMap.set(edge.target, (degreeMap.get(edge.target) || 0) + 1)
    adjacency.get(edge.source)?.add(edge.target)
    adjacency.get(edge.target)?.add(edge.source)
  })
  const nodes: SimulationNode[] = props.nodes.map((node) => ({
    ...node,
    degree: degreeMap.get(node.id) || 0,
  }))
  const nodeIds = new Set(nodes.map((node) => node.id))
  const edges: SimulationEdge[] = props.edges
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .map((edge) => ({ ...edge }))
  const isLargeGraph = nodes.length > 300 || edges.length > 700
  labelVisibilityThreshold = isLargeGraph ? 1 : 0.8
  labelsHiddenByScale = false

  const definitions = svg.append('defs')
  definitions
    .append('marker')
    .attr('id', 'knowledge-graph-arrow')
    .attr('viewBox', '0 -5 10 10')
    .attr('refX', 18)
    .attr('refY', 0)
    .attr('markerWidth', 5)
    .attr('markerHeight', 5)
    .attr('orient', 'auto')
    .append('path')
    .attr('d', 'M0,-4L9,0L0,4')
    .attr('fill', '#94a3b8')
    .attr('opacity', 0.7)

  graphGroup = svg.append('g').attr('class', 'graph-stage')
  zoomBehavior = d3
    .zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.12, 5])
    .on('start', () => {
      hoveredNodeId = ''
      nodeSelection?.style('pointer-events', 'none')
      labelSelection?.attr('visibility', 'hidden')
      edgeSelection?.attr('marker-end', null)
    })
    .on('zoom', (event) => {
      pendingZoomTransform = event.transform
      if (zoomFrame !== null) return
      zoomFrame = window.requestAnimationFrame(() => {
        zoomFrame = null
        if (!pendingZoomTransform) return
        const transform = pendingZoomTransform
        pendingZoomTransform = null
        currentScale = transform.k
        graphGroup?.attr('transform', transform.toString())
        labelsHiddenByScale = !props.expanded && currentScale < labelVisibilityThreshold
      })
    })
    .on('end', () => {
      if (zoomFrame !== null) window.cancelAnimationFrame(zoomFrame)
      zoomFrame = null
      if (pendingZoomTransform) {
        currentScale = pendingZoomTransform.k
        graphGroup?.attr('transform', pendingZoomTransform.toString())
        pendingZoomTransform = null
      }
      labelsHiddenByScale = !props.expanded && currentScale < labelVisibilityThreshold
      edgeSelection?.attr('marker-end', 'url(#knowledge-graph-arrow)')
      labelSelection?.attr('visibility', null)
      nodeSelection?.style('pointer-events', null)
      applyHighlight()
    })
  svg.call(zoomBehavior).on('dblclick.zoom', null)

  edgeSelection = graphGroup
    .append('g')
    .attr('class', 'graph-links')
    .selectAll<SVGLineElement, SimulationEdge>('line')
    .data(edges, (edge) => edge.id)
    .join('line')
    .attr('stroke', '#94a3b8')
    .attr('stroke-opacity', 0.24)
    .attr('stroke-width', 1.1)
    .attr('marker-end', 'url(#knowledge-graph-arrow)')
    .style('pointer-events', 'none')

  edgeElementsByNode = new Map(nodes.map((node) => [node.id, []]))
  edgeSelection.each(function (edge) {
    const connectedEdge = { element: this, edge }
    edgeElementsByNode.get(nodeId(edge.source))?.push(connectedEdge)
    edgeElementsByNode.get(nodeId(edge.target))?.push(connectedEdge)
  })

  nodeSelection = graphGroup
    .append('g')
    .attr('class', 'graph-nodes')
    .selectAll<SVGGElement, SimulationNode>('g')
    .data(nodes, (node) => node.id)
    .join('g')
    .attr('class', 'graph-node')
    .attr('tabindex', 0)
    .attr('role', 'button')
    .attr('aria-label', (node) => node.label)
    .style('cursor', 'grab')

  nodeSelection
    .append('circle')
    .attr('r', nodeRadius)
    .attr('fill', nodeColor)
    .attr('stroke', 'rgb(var(--v-theme-surface))')
    .attr('stroke-width', 2)

  labelSelection = nodeSelection
    .append('text')
    .text((node) => (node.label.length > 22 ? `${node.label.slice(0, 21)}…` : node.label))
    .attr('x', (node) => nodeRadius(node) + 9)
    .attr('y', 4)
    .attr('font-size', 11)
    .attr('font-weight', 600)
    .attr('fill', '#334155')
    .attr('paint-order', 'stroke')
    .attr('stroke', 'rgba(255, 255, 255, 0.94)')
    .attr('stroke-width', 3)
    .attr('stroke-linejoin', 'round')
    .style('pointer-events', 'none')

  nodeSelection.append('title').text((node) => `${node.label}\n${node.id}`)

  simulation = d3
    .forceSimulation<SimulationNode>(nodes)
    .force(
      'link',
      d3
        .forceLink<SimulationNode, SimulationEdge>(edges)
        .id((node) => node.id)
        .distance((edge) => (edge.relation === 'links_to' ? 118 : 100))
        .strength(0.42),
    )
    .force(
      'charge',
      d3
        .forceManyBody<SimulationNode>()
        .strength(isLargeGraph ? -150 : -230)
        .distanceMax(isLargeGraph ? 360 : 680)
        .theta(0.9),
    )
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('x', d3.forceX<SimulationNode>(width / 2).strength(0.04))
    .force('y', d3.forceY<SimulationNode>(height / 2).strength(0.04))
    .force(
      'collision',
      d3
        .forceCollide<SimulationNode>()
        .radius((node) => nodeRadius(node) + 28)
        .strength(0.86),
    )
    .alphaMin(isLargeGraph ? 0.012 : 0.008)
    .alphaDecay(isLargeGraph ? 0.075 : 0.055)
    .velocityDecay(0.42)
    .on('tick', () => {
      edgeSelection
        ?.attr('x1', (edge) => (edge.source as SimulationNode).x || 0)
        .attr('y1', (edge) => (edge.source as SimulationNode).y || 0)
        .attr('x2', (edge) => (edge.target as SimulationNode).x || 0)
        .attr('y2', (edge) => (edge.target as SimulationNode).y || 0)
      nodeSelection?.attr('transform', (node) => `translate(${node.x || 0},${node.y || 0})`)
    })
    .on('end', () => fitGraph())

  simulation.stop()
  simulation.tick(
    Math.ceil(Math.log(simulation.alphaMin()) / Math.log(1 - simulation.alphaDecay())),
  )
  edgeSelection
    .attr('x1', (edge) => (edge.source as SimulationNode).x || 0)
    .attr('y1', (edge) => (edge.source as SimulationNode).y || 0)
    .attr('x2', (edge) => (edge.target as SimulationNode).x || 0)
    .attr('y2', (edge) => (edge.target as SimulationNode).y || 0)
  nodeSelection.attr('transform', (node) => `translate(${node.x || 0},${node.y || 0})`)
  fitGraph(false)

  const dragBehavior = d3
    .drag<SVGGElement, SimulationNode>()
    .on('start', function (event, node) {
      event.sourceEvent.stopPropagation()
      simulation?.stop()
      if (svgRef.value) d3.select(svgRef.value).interrupt()
      node.fx = node.x
      node.fy = node.y
      d3.select(this).style('cursor', 'grabbing')
    })
    .on('drag', function (event, node) {
      node.x = event.x
      node.y = event.y
      node.fx = event.x
      node.fy = event.y

      this.setAttribute('transform', `translate(${event.x},${event.y})`)
      edgeElementsByNode.get(node.id)?.forEach(({ element, edge }) => {
        const source = edge.source as SimulationNode
        const target = edge.target as SimulationNode
        element.setAttribute('x1', String(source.x ?? 0))
        element.setAttribute('y1', String(source.y ?? 0))
        element.setAttribute('x2', String(target.x ?? 0))
        element.setAttribute('y2', String(target.y ?? 0))
      })
    })
    .on('end', function (event, node) {
      node.x = event.x
      node.y = event.y
      node.fx = event.x
      node.fy = event.y
      d3.select(this).style('cursor', 'grab')
    })

  nodeSelection
    .call(dragBehavior)
    .on('mouseenter', (_event, node) => {
      hoveredNodeId = node.id
      applyHighlight()
    })
    .on('mouseleave', () => {
      hoveredNodeId = ''
      applyHighlight()
    })
    .on('click', (event, node) => {
      if (event.defaultPrevented) return
      emit('selectNode', node.id)
    })
    .on('keydown', (event, node) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        emit('selectNode', node.id)
      }
    })
    .on('dblclick', (event, node) => {
      event.stopPropagation()
      node.fx = null
      node.fy = null
      simulation?.alpha(0.45).restart()
    })

  applyHighlight()
}

const resizeGraph = () => {
  if (resizeFrame !== null) return
  resizeFrame = window.requestAnimationFrame(() => {
    resizeFrame = null
    if (!containerRef.value || !svgRef.value || !simulation) return
    const width = Math.max(containerRef.value.clientWidth, 320)
    const height = Math.max(containerRef.value.clientHeight, 520)
    if (Math.abs(width - lastWidth) < 2 && Math.abs(height - lastHeight) < 2) return
    lastWidth = width
    lastHeight = height
    d3.select(svgRef.value).attr('viewBox', `0 0 ${width} ${height}`)
    simulation
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('x', d3.forceX<SimulationNode>(width / 2).strength(0.04))
      .force('y', d3.forceY<SimulationNode>(height / 2).strength(0.04))
      .alpha(Math.max(simulation.alpha(), 0.12))
      .restart()
  })
}

watch([() => props.nodes, () => props.edges], () => void renderGraph())

watch(
  () => props.selectedNodeId,
  () => applyHighlight(),
)

watch(
  () => props.expanded,
  async () => {
    await nextTick()
    resizeGraph()
    labelsHiddenByScale = false
    window.setTimeout(() => {
      fitGraph()
      applyHighlight()
    }, 240)
  },
)

onMounted(() => {
  void renderGraph()
  if (containerRef.value) {
    resizeObserver = new ResizeObserver(resizeGraph)
    resizeObserver.observe(containerRef.value)
  }
})

onUnmounted(() => {
  simulation?.stop()
  resizeObserver?.disconnect()
  if (resizeFrame !== null) window.cancelAnimationFrame(resizeFrame)
  if (zoomFrame !== null) window.cancelAnimationFrame(zoomFrame)
})
</script>

<template>
  <div ref="containerRef" class="graph-canvas-shell" :class="{ 'graph-canvas-shell--expanded': expanded }">
    <svg ref="svgRef" class="graph-canvas" aria-label="知识图谱" />
    <div class="graph-controls">
      <v-btn
        icon="mdi-plus"
        size="small"
        variant="flat"
        aria-label="放大"
        @click="zoomBy(1.3)"
      />
      <v-btn
        icon="mdi-minus"
        size="small"
        variant="flat"
        aria-label="缩小"
        @click="zoomBy(0.77)"
      />
      <v-btn
        :icon="expanded ? 'mdi-fullscreen-exit' : 'mdi-fit-to-screen-outline'"
        size="small"
        variant="flat"
        :aria-label="expanded ? '收起图谱' : '放大图谱'"
        :class="{ 'graph-control-btn--active': expanded }"
        @click="emit('toggleExpanded')"
      />
    </div>
    <div class="graph-help text-caption text-medium-emphasis">
      拖动节点可固定位置 · 双击节点释放 · 滚轮缩放
    </div>
  </div>
</template>

<style scoped>
.graph-canvas-shell {
  position: relative;
  contain: layout paint;
  isolation: isolate;
  width: 100%;
  height: 660px;
  overflow: hidden;
  background:
    radial-gradient(circle at 50% 42%, rgba(47, 150, 211, 0.08), transparent 34%),
    linear-gradient(rgba(148, 163, 184, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.06) 1px, transparent 1px),
    #fbfdff;
  background-size: auto, 32px 32px, 32px 32px, auto;
  transition: height 0.22s ease;
}

.graph-canvas-shell--expanded {
  height: 100vh;
}

.graph-canvas {
  display: block;
  width: 100%;
  height: 100%;
  touch-action: none;
}

.graph-controls {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  border: 1px solid #d8e8f3;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 10px 28px rgba(42, 79, 110, 0.1);
  padding: 6px;
}

.graph-controls :deep(.v-btn) {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: #eef8ff;
  color: #2a8cc7;
}

.graph-controls :deep(.v-btn:hover) {
  background: #dff1fb;
}

.graph-controls :deep(.graph-control-btn--active) {
  background: #2f96d3;
  color: #ffffff;
}

.graph-controls :deep(.graph-control-btn--active:hover) {
  background: #2388c5;
}

.graph-help {
  position: absolute;
  left: 16px;
  bottom: 16px;
  border: 1px solid #d8e8f3;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  color: #6c7d8f;
  padding: 6px 12px;
  pointer-events: none;
}

@media (max-width: 960px) {
  .graph-canvas-shell {
    height: 620px;
  }

  .graph-canvas-shell--expanded {
    height: 100vh;
  }

  .graph-help {
    display: none;
  }
}
</style>
