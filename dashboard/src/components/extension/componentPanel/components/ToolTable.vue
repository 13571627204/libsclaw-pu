<script setup lang="ts">
import { computed } from 'vue';
import { useModuleI18n } from '@/i18n/composables';
import type { BuiltinToolConfigTag, ToolConfigCondition, ToolItem } from '../types';

const { tm: tmTool } = useModuleI18n('features/tooluse');

const props = defineProps<{
  items: ToolItem[];
  loading?: boolean;
}>();

const emit = defineEmits<{
  (e: 'toggle-tool', tool: ToolItem): void;
  (e: 'update-permission', tool: ToolItem, permission: 'admin' | 'member'): void;
}>();

const toolHeaders = computed(() => [
  { title: tmTool('functionTools.title'), key: 'name', minWidth: '320px' },
  { title: tmTool('functionTools.description'), key: 'description' },
  { title: tmTool('functionTools.table.origin'), key: 'origin', sortable: false, width: '100px' },
  { title: tmTool('functionTools.table.originName'), key: 'origin_name', sortable: false, width: '140px' },
  { title: tmTool('functionTools.table.permission'), key: 'permission', sortable: false, width: '110px' },
  { title: tmTool('functionTools.table.actions'), key: 'actions', sortable: false, width: '100px' }
]);

const parameterEntries = (tool: ToolItem) => Object.entries(tool.parameters?.properties || {});

const formatConfigValue = (value: unknown) => {
  if (Array.isArray(value)) {
    return value.map(item => String(item)).join(', ');
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  return String(value);
};

const formatCondition = (condition: ToolConfigCondition) => {
  if (condition.message) {
    return condition.message;
  }

  switch (condition.operator) {
    case 'truthy':
      return tmTool('functionTools.configTags.conditions.truthy', {
        key: condition.key
      });
    case 'equals':
      return tmTool('functionTools.configTags.conditions.equals', {
        key: condition.key,
        expected: formatConfigValue(condition.expected)
      });
    case 'in':
      return tmTool('functionTools.configTags.conditions.in', {
        key: condition.key,
        expected: formatConfigValue(condition.expected)
      });
    default:
      return tmTool('functionTools.configTags.conditions.fallback', {
        key: condition.key,
        actual: formatConfigValue(condition.actual)
      });
  }
};

const enabledConfigTags = (tool: ToolItem): BuiltinToolConfigTag[] => {
  if (tool.origin !== 'builtin') return [];
  return (tool.builtin_config_tags || []).filter(tag => tag.enabled);
};

const getPermissionColor = (permission?: string): string => {
  switch (permission) {
    case 'admin':
      return 'error';
    default:
      return 'success';
  }
};

const getPermissionLabel = (permission?: string): string => {
  switch (permission) {
    case 'admin':
      return tmTool('functionTools.table.permissionAdmin');
    default:
      return tmTool('functionTools.table.permissionEveryone');
  }
};
</script>

<template>
  <v-card class="tool-table-card" variant="flat">
    <v-data-table
      :headers="toolHeaders"
      :items="items"
      item-value="name"
      hover
      show-expand
      class="tool-table"
      :loading="props.loading"
    >
      <template #item.name="{ item }">
        <div class="py-2">
          <div class="d-flex flex-wrap align-center ga-1">
            <div class="tool-name text-body-2 font-weight-medium">{{ item.name }}</div>
            <v-tooltip
              v-for="tag in enabledConfigTags(item)"
              :key="`${item.name}-${tag.conf_id}`"
              location="top"
            >
              <template #activator="{ props: tooltipProps }">
                <v-chip
                  v-bind="tooltipProps"
                  size="x-small"
                  variant="tonal"
                  color="secondary"
                  class="text-caption font-weight-medium"
                >
                  {{ tag.conf_name }}
                </v-chip>
              </template>

              <div class="tool-config-tooltip">
                <div class="text-body-2 font-weight-medium mb-2">
                  {{ tmTool('functionTools.configTags.tooltipTitle', { config: tag.conf_name }) }}
                </div>
                <div
                  v-for="(condition, index) in tag.matched_conditions"
                  :key="`${tag.conf_id}-${index}-${condition.key}`"
                  class="text-body-2 text-medium-emphasis mb-1"
                >
                  {{ formatCondition(condition) }}
                </div>
              </div>
            </v-tooltip>
          </div>
        </div>
      </template>

      <template #item.description="{ item }">
        <div class="text-body-2 text-medium-emphasis" style="max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="item.description">
          {{ item.description || '-' }}
        </div>
      </template>

      <template #item.origin="{ item }">
        <v-chip size="x-small" variant="tonal" color="info" class="text-caption font-weight-medium">
          {{ item.origin || '-' }}
        </v-chip>
      </template>

      <template #item.origin_name="{ item }">
        <div class="text-body-2 text-medium-emphasis" style="max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="item.origin_name">
          {{ item.origin_name || '-' }}
        </div>
      </template>

      <template #item.permission="{ item }">
        <v-menu location="bottom">
          <template v-slot:activator="{ props: menuProps }">
            <v-chip
              v-bind="menuProps"
              :color="getPermissionColor(item.permission)"
              size="small"
              class="font-weight-medium cursor-pointer"
              link
            >
              {{ getPermissionLabel(item.permission) }}
              <v-icon end size="14">mdi-chevron-down</v-icon>
            </v-chip>
          </template>
          <v-list density="compact">
            <v-list-item
              :value="'member'"
              @click="emit('update-permission', item, 'member')"
              :active="item.permission !== 'admin'"
            >
              <v-list-item-title>{{ tmTool('functionTools.table.permissionEveryone') }}</v-list-item-title>
            </v-list-item>
            <v-list-item
              :value="'admin'"
              @click="emit('update-permission', item, 'admin')"
              :active="item.permission === 'admin'"
            >
              <v-list-item-title>{{ tmTool('functionTools.table.permissionAdmin') }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
      </template>

      <template #item.actions="{ item }">
        <v-switch
          :model-value="item.active"
          color="primary"
          density="compact"
          hide-details
          inset
          @update:model-value="emit('toggle-tool', item)"
        />
      </template>

      <template #no-data>
        <div class="tool-empty-state">
          <div class="tool-empty-state__icon">
            <v-icon size="42">mdi-function-variant</v-icon>
          </div>
          <div class="tool-empty-state__title">{{ tmTool('functionTools.empty') }}</div>
        </div>
      </template>

      <template #expanded-row="{ item }">
        <td :colspan="toolHeaders.length + 1" class="pa-4">
          <div class="d-flex align-start ga-4">
            <v-icon size="20" color="primary">mdi-code-json</v-icon>
            <div class="flex-1">
              <div class="text-subtitle-2 font-weight-medium mb-2">{{ tmTool('functionTools.parameters') }}</div>
              <div v-if="parameterEntries(item).length === 0" class="text-caption text-medium-emphasis">
                {{ tmTool('functionTools.noParameters') }}
              </div>
              <v-table
                v-else
                density="compact"
                class="param-table"
              >
                <thead>
                  <tr>
                    <th class="text-left text-caption text-medium-emphasis">{{ tmTool('functionTools.table.paramName') }}</th>
                    <th class="text-left text-caption text-medium-emphasis" style="width: 140px;">{{ tmTool('functionTools.table.type') }}</th>
                    <th class="text-left text-caption text-medium-emphasis">{{ tmTool('functionTools.table.description') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="([paramName, param]) in parameterEntries(item)" :key="paramName">
                    <td class="font-weight-medium text-body-2">{{ paramName }}</td>
                    <td class="text-body-2">
                      <v-chip size="x-small" color="primary" class="text-caption">
                        {{ param?.type || '-' }}
                      </v-chip>
                    </td>
                    <td class="text-body-2 text-medium-emphasis">{{ param?.description || '-' }}</td>
                  </tr>
                </tbody>
              </v-table>
            </div>
          </div>
        </td>
      </template>
    </v-data-table>
  </v-card>
</template>

<style scoped>
.tool-table-card {
  overflow: hidden;
  border-radius: 0;
  background: #ffffff;
  box-shadow: none;
}

.tool-table :deep(thead th) {
  height: 46px;
  color: #506172;
  font-size: 13px;
  font-weight: 760;
  background: #fafcfd;
  border-bottom: 1px solid #e3edf3 !important;
}

.tool-table :deep(tbody tr) {
  transition: background-color 0.16s ease, box-shadow 0.16s ease;
}

.tool-table :deep(tbody tr:hover) {
  background: #f8fbfd !important;
  box-shadow: inset 3px 0 0 #8bc9ec;
}

.tool-table :deep(.v-data-table__td) {
  height: 54px;
  border-bottom: 1px solid #edf2f6 !important;
  color: #263545;
}

.tool-table :deep(.v-data-table-footer) {
  border-top: 1px solid #e3edf3;
  background: #fafcfd;
}

.tool-table :deep(.v-switch .v-selection-control) {
  min-height: 30px;
}

.param-table {
  overflow: hidden;
  border: 1px solid #dce8ef;
  border-radius: 10px;
  background: #ffffff;
}

.tool-table :deep(.v-data-table__td) {
  vertical-align: middle;
}

.tool-name {
  font-size: 0.9rem;
  line-height: 1.35;
}

.tool-empty-state {
  display: flex;
  min-height: 220px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 34px;
  color: #647486;
}

.tool-empty-state__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 76px;
  height: 76px;
  border: 1px solid #d7e8f2;
  border-radius: 20px;
  color: rgb(var(--v-theme-primary));
  background: #edf8fe;
}

.tool-empty-state__title {
  margin-top: 6px;
  color: #263545;
  font-size: 16px;
  font-weight: 760;
}

.tool-config-tooltip {
  max-width: 360px;
  padding: 4px 0;
  color: rgba(255, 255, 255, 0.92);
}

.tool-config-tooltip :deep(.text-body-2),
.tool-config-tooltip :deep(.text-medium-emphasis),
.tool-config-tooltip :deep(.font-weight-medium) {
  color: inherit !important;
}
</style>
