<script setup lang="ts">
/**
 * 组件管理页面 - 主入口
 * 
 * 模块化结构：
 * - types.ts: 类型定义
 * - composables/useComponentData.ts: 数据获取和状态管理
 * - composables/useCommandFilters.ts: 过滤逻辑
 * - composables/useCommandActions.ts: 操作方法
 * - components/CommandFilters.vue: 过滤器组件
 * - components/CommandTable.vue: 表格组件
 * - components/RenameDialog.vue: 重命名对话框
 * - components/DetailsDialog.vue: 详情对话框
 */
import { onMounted, ref, watch } from 'vue';
import { useModuleI18n } from '@/i18n/composables';

// Composables
import { useComponentData } from './composables/useComponentData';
import { useCommandFilters } from './composables/useCommandFilters';
import { useCommandActions } from './composables/useCommandActions';
import { useToolActions } from './composables/useToolActions';

// Components
import CommandFilters from './components/CommandFilters.vue';
import CommandTable from './components/CommandTable.vue';
import ToolTable from './components/ToolTable.vue';
import RenameDialog from './components/RenameDialog.vue';
import DetailsDialog from './components/DetailsDialog.vue';

// Types
import type { CommandItem, ToolItem } from './types';

defineOptions({ name: 'ComponentPanel' });
const props = withDefaults(defineProps<{ active?: boolean }>(), {
  active: true
});

const { tm } = useModuleI18n('features/command');
const { tm: tmTool } = useModuleI18n('features/tooluse');

const viewMode = ref<'commands' | 'tools'>('commands');

// 数据管理
const { 
  loading, 
  commands, 
  tools,
  toolsLoading,
  summary, 
  snackbar, 
  toast, 
  fetchCommands,
  fetchTools 
} = useComponentData();

// 过滤逻辑
const {
  searchQuery,
  pluginFilter,
  permissionFilter,
  statusFilter,
  typeFilter,
  showSystemPlugins,
  expandedGroups,
  hasSystemPluginConflict,
  effectiveShowSystemPlugins,
  availablePlugins,
  filteredCommands,
  toggleGroupExpand
} = useCommandFilters(commands);

// 操作方法
const {
  renameDialog,
  detailsDialog,
  toggleCommand,
  updatePermission,
  openRenameDialog,
  confirmRename,
  openDetailsDialog
} = useCommandActions(toast, () => fetchCommands(tm('messages.loadFailed')));

// 工具操作方法
const {
  toolSearch,
  showBuiltinTools,
  filteredTools,
  toolSummary,
  toggleTool,
  updateToolPermission,
} = useToolActions(tools, toast);

// 处理切换指令状态
const handleToggleCommand = async (cmd: CommandItem) => {
  await toggleCommand(cmd, tm('messages.toggleSuccess'), tm('messages.toggleFailed'));
};

const handleUpdatePermission = async (cmd: CommandItem, permission: 'admin' | 'member') => {
  await updatePermission(cmd, permission, tm('messages.updateSuccess'), tm('messages.updateFailed'));
};

const handleToggleTool = async (tool: ToolItem) => {
  await toggleTool(tool, tmTool('messages.toggleToolReadonly'), tmTool('messages.toggleToolSuccess'), tmTool('messages.toggleToolError', { error: '' }));
};

const handleUpdateToolPermission = async (tool: ToolItem, permission: 'admin' | 'member') => {
  await updateToolPermission(tool, permission, tmTool('messages.updateToolPermissionSuccess', { name: tool.name }), tmTool('messages.updateToolPermissionBuiltin'), tmTool('messages.updateToolPermissionFailed'));
};

// 处理确认重命名
const handleConfirmRename = async () => {
  await confirmRename(tm('messages.renameSuccess'), tm('messages.renameFailed'));
};

// 生命周期
onMounted(async () => {
  await Promise.all([
    fetchCommands(tm('messages.loadFailed')),
    fetchTools(tmTool('messages.getToolsError', { error: '' }))
  ]);
});

watch(() => props.active, async (isActive) => {
  if (!isActive) return;
  if (viewMode.value === 'commands') {
    await fetchCommands(tm('messages.loadFailed'));
  } else {
    await fetchTools(tmTool('messages.getToolsError', { error: '' }));
  }
});

watch(viewMode, async (mode) => {
  if (mode === 'commands') {
    await fetchCommands(tm('messages.loadFailed'));
  } else {
    await fetchTools(tmTool('messages.getToolsError', { error: '' }));
  }
});
</script>

<template>
  <v-row class="component-panel">
    <v-col cols="12">
      <v-card class="component-panel-card" variant="flat">
        <v-card-text class="component-panel-body">
          <div class="component-mode-bar">
            <v-btn-toggle
              v-model="viewMode"
              color="primary"
              variant="outlined"
              density="comfortable"
              mandatory
              class="component-mode-toggle"
            >
              <v-btn value="commands">
                <v-icon size="18" class="mr-1">mdi-console-line</v-icon>
                {{ tm('type.command') }}
              </v-btn>
              <v-btn value="tools">
                <v-icon size="18" class="mr-1">mdi-function-variant</v-icon>
                {{ tmTool('functionTools.title') }}
              </v-btn>
            </v-btn-toggle>
            <v-progress-linear
              v-if="viewMode === 'commands' && loading"
              indeterminate
              color="primary"
              class="component-loading"
            />
            <v-progress-linear
              v-else-if="viewMode === 'tools' && toolsLoading"
              indeterminate
              color="primary"
              class="component-loading"
            />
          </div>

          <div v-if="viewMode === 'commands'" class="component-section">
            <CommandFilters
              :plugin-filter="pluginFilter"
              @update:plugin-filter="pluginFilter = $event"
              :type-filter="typeFilter"
              @update:type-filter="typeFilter = $event"
              :permission-filter="permissionFilter"
              @update:permission-filter="permissionFilter = $event"
              :status-filter="statusFilter"
              @update:status-filter="statusFilter = $event"
              :show-system-plugins="showSystemPlugins"
              @update:show-system-plugins="showSystemPlugins = $event"
              :search-query="searchQuery"
              @update:search-query="searchQuery = $event"
              :available-plugins="availablePlugins"
              :has-system-plugin-conflict="hasSystemPluginConflict"
              :effective-show-system-plugins="effectiveShowSystemPlugins"
            >
              <template #stats>
                <div class="d-flex align-center">
                  <v-icon size="18" color="primary" class="mr-1">mdi-console-line</v-icon>
                  <span class="text-body-2 text-medium-emphasis mr-1">{{ tm('summary.total') }}:</span>
                  <span class="text-body-1 font-weight-bold text-primary">{{ filteredCommands.length }}</span>
                </div>
                <v-divider vertical class="mx-1" style="height: 20px;" />
                <div class="d-flex align-center">
                  <v-icon size="18" color="error" class="mr-1">mdi-close-circle-outline</v-icon>
                  <span class="text-body-2 text-medium-emphasis mr-1">{{ tm('summary.disabled') }}:</span>
                  <span class="text-body-1 font-weight-bold text-error">{{ summary.disabled }}</span>
                </div>
              </template>
            </CommandFilters>
            
            <v-alert
              v-if="summary.conflicts > 0"
              type="error"
              variant="tonal"
              class="mb-4"
              prominent
              border="start"
            >
              <template v-slot:prepend>
                <v-icon size="28">mdi-alert-circle</v-icon>
              </template>
              <v-alert-title class="text-subtitle-1 font-weight-bold">
                {{ tm('conflictAlert.title') }}
              </v-alert-title>
              <div class="text-body-2 mt-1">
                {{ tm('conflictAlert.description', { count: summary.conflicts }) }}
              </div>
              <div class="text-body-2 mt-2">
                <v-icon size="16" class="mr-1">mdi-lightbulb-outline</v-icon>
                {{ tm('conflictAlert.hint') }}
              </div>
            </v-alert>

            <CommandTable
              :items="filteredCommands"
              :expanded-groups="expandedGroups"
              :loading="loading"
              @toggle-expand="toggleGroupExpand"
              @toggle-command="handleToggleCommand"
              @rename="openRenameDialog"
              @view-details="openDetailsDialog"
              @update-permission="handleUpdatePermission"
            />
          </div>

          <div v-else class="component-section">
            <div class="tool-control-bar">
              <div class="tool-search-wrap">
                <v-text-field
                  v-model="toolSearch"
                  prepend-inner-icon="mdi-magnify"
                  :label="tmTool('functionTools.search')"
                  variant="solo"
                  density="compact"
                  hide-details
                  clearable
                  class="tool-search-field"
                />
              </div>

              <div class="tool-stats">
                <div class="component-stat-pill">
                  <v-icon size="18" color="primary" class="mr-1">mdi-function-variant</v-icon>
                  <span class="text-body-2 text-medium-emphasis mr-1">{{ tmTool('functionTools.summary.total') }}:</span>
                  <span class="text-body-1 font-weight-bold text-primary">{{ toolSummary.total }}</span>
                </div>
                <div class="component-stat-pill component-stat-pill--success">
                  <v-icon size="18" color="success" class="mr-1">mdi-check-circle-outline</v-icon>
                  <span class="text-body-2 text-medium-emphasis mr-1">{{ tmTool('functionTools.summary.active') }}:</span>
                  <span class="text-body-1 font-weight-bold text-success">{{ toolSummary.active }}</span>
                </div>
                <div class="component-stat-pill component-stat-pill--error">
                  <v-icon size="18" color="error" class="mr-1">mdi-close-circle-outline</v-icon>
                  <span class="text-body-2 text-medium-emphasis mr-1">{{ tmTool('functionTools.summary.inactive') }}:</span>
                  <span class="text-body-1 font-weight-bold text-error">{{ toolSummary.inactive }}</span>
                </div>

                <v-checkbox
                  v-model="showBuiltinTools"
                  :label="tmTool('functionTools.filter.showBuiltin')"
                  density="compact"
                  hide-details
                  class="builtin-tools-checkbox"
                />
              </div>
            </div>

            <ToolTable
              :items="filteredTools"
              :loading="toolsLoading"
              @toggle-tool="handleToggleTool"
              @update-permission="handleUpdateToolPermission"
            />
          </div>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>

  <!-- 重命名对话框 -->
  <RenameDialog
    :show="renameDialog.show"
    @update:show="renameDialog.show = $event"
    :new-name="renameDialog.newName"
    @update:new-name="renameDialog.newName = $event"
    :aliases="renameDialog.aliases"
    @update:aliases="renameDialog.aliases = $event"
    :command="renameDialog.command"
    :loading="renameDialog.loading"
    @confirm="handleConfirmRename"
  />

  <!-- 详情对话框 -->
  <DetailsDialog
    :show="detailsDialog.show"
    @update:show="detailsDialog.show = $event"
    :command="detailsDialog.command"
  />

  <!-- Snackbar -->
  <v-snackbar :timeout="2000" elevation="6" :color="snackbar.color" v-model="snackbar.show">
    {{ snackbar.message }}
  </v-snackbar>
</template>

<style scoped>
.component-panel {
  margin: 0;
}

.component-panel-card {
  background: transparent;
}

.component-panel-body {
  padding: 4px 0 0;
}

.component-mode-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}

.component-mode-toggle {
  overflow: hidden;
  border: 1px solid #dce8ef;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.component-mode-toggle :deep(.v-btn) {
  min-width: 112px;
  height: 36px;
  letter-spacing: 0;
  font-weight: 700;
}

.component-mode-toggle :deep(.v-btn--active) {
  background: #eaf6fd;
  color: rgb(var(--v-theme-primary));
}

.component-loading {
  max-width: 220px;
  flex: 1 1 160px;
  border-radius: 999px;
}

.component-section {
  overflow: hidden;
  border: 1px solid #dce7ef;
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.045);
  display: flex;
  height: clamp(580px, calc(100vh - 250px), 760px);
  min-height: 0;
  flex-direction: column;
}

.component-section :deep(.command-table-card),
.component-section :deep(.tool-table-card) {
  flex: 1 1 0;
  height: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.component-section :deep(.command-data-table),
.component-section :deep(.tool-table) {
  flex: 1 1 0;
  height: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.component-section :deep(.v-table__wrapper) {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

.tool-control-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid #e3edf3;
  background: linear-gradient(180deg, #f8fbfd 0%, #ffffff 100%);
}

.tool-search-wrap {
  flex: 1 1 320px;
  min-width: 260px;
  max-width: 430px;
}

.tool-search-field :deep(.v-field) {
  min-height: 38px;
  border: 1px solid #d9e6ee;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: none;
}

.tool-search-field :deep(.v-field--focused) {
  border-color: #9ed2ee;
  box-shadow: 0 0 0 3px rgba(66, 165, 217, 0.12);
}

.tool-search-field :deep(.v-field__input) {
  min-height: 38px;
  padding-top: 0;
  padding-bottom: 0;
  color: #263545;
  font-size: 13px;
}

.tool-search-field :deep(.v-field__prepend-inner) {
  color: rgb(var(--v-theme-primary));
}

.tool-stats {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.component-stat-pill {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 6px 11px;
  border: 1px solid #d9e6ee;
  border-radius: 999px;
  background: #ffffff;
  color: #526171;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.component-stat-pill--success {
  border-color: #cbeedb;
  background: #f3fbf6;
}

.component-stat-pill--error {
  border-color: #f6d5d5;
  background: #fff7f7;
}

.builtin-tools-checkbox {
  flex: none;
}

.builtin-tools-checkbox :deep(.v-selection-control) {
  min-height: auto;
}

@media (max-width: 760px) {
  .component-mode-bar,
  .tool-control-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .component-mode-toggle {
    width: 100%;
  }

  .component-mode-toggle :deep(.v-btn) {
    flex: 1 1 0;
  }

  .tool-search-wrap {
    max-width: none;
    min-width: 0;
    width: 100%;
  }
}
</style>
