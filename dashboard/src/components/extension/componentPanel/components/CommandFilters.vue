<script setup lang="ts">
import { computed } from 'vue';
import { useModuleI18n } from '@/i18n/composables';
import { normalizeTextInput } from '@/utils/inputValue';

const { tm } = useModuleI18n('features/command');

// Props
const props = defineProps<{
  availablePlugins: string[];
  hasSystemPluginConflict: boolean;
  effectiveShowSystemPlugins: boolean;
  pluginFilter: string;
  typeFilter: string;
  permissionFilter: string;
  statusFilter: string;
  showSystemPlugins: boolean;
  searchQuery: string;
}>();

// Emits
const emit = defineEmits<{
  (e: 'update:pluginFilter', value: string): void;
  (e: 'update:typeFilter', value: string): void;
  (e: 'update:permissionFilter', value: string): void;
  (e: 'update:statusFilter', value: string): void;
  (e: 'update:showSystemPlugins', value: boolean): void;
  (e: 'update:searchQuery', value: string): void;
}>();

// Computed items for selects
const pluginItems = computed(() => [
  { title: tm('filters.all'), value: 'all' },
  ...props.availablePlugins.map(p => ({ title: p, value: p }))
]);

const typeItems = [
  { title: tm('filters.all'), value: 'all' },
  { title: tm('type.group'), value: 'group' },
  { title: tm('type.command'), value: 'command' },
  { title: tm('type.subCommand'), value: 'sub_command' }
];

const permissionItems = [
  { title: tm('filters.all'), value: 'all' },
  { title: tm('permission.everyone'), value: 'everyone' },
  { title: tm('permission.admin'), value: 'admin' }
];

const statusItems = [
  { title: tm('filters.all'), value: 'all' },
  { title: tm('filters.enabled'), value: 'enabled' },
  { title: tm('filters.disabled'), value: 'disabled' },
  { title: tm('filters.conflict'), value: 'conflict' }
];

</script>

<template>
  <!-- 过滤器行 -->
  <v-row class="command-filter-grid" align="center">
    <v-col cols="12" sm="6" md="3">
      <div class="command-filter-item">
        <div class="command-filter-label">{{ tm('filters.byPlugin') }}</div>
        <v-select
          :model-value="pluginFilter"
          @update:model-value="emit('update:pluginFilter', $event)"
          :items="pluginItems"
          :aria-label="tm('filters.byPlugin')"
          density="compact"
          variant="solo"
          hide-details
          class="command-filter-field"
        />
      </div>
    </v-col>
    <v-col cols="12" sm="6" md="2">
      <div class="command-filter-item">
        <div class="command-filter-label">{{ tm('filters.byType') }}</div>
        <v-select
          :model-value="typeFilter"
          @update:model-value="emit('update:typeFilter', $event)"
          :items="typeItems"
          :aria-label="tm('filters.byType')"
          density="compact"
          variant="solo"
          hide-details
          class="command-filter-field"
        />
      </div>
    </v-col>
    <v-col cols="12" sm="6" md="2">
      <div class="command-filter-item">
        <div class="command-filter-label">{{ tm('filters.byPermission') }}</div>
        <v-select
          :model-value="permissionFilter"
          @update:model-value="emit('update:permissionFilter', $event)"
          :items="permissionItems"
          :aria-label="tm('filters.byPermission')"
          density="compact"
          variant="solo"
          hide-details
          class="command-filter-field"
        />
      </div>
    </v-col>
    <v-col cols="12" sm="6" md="2">
      <div class="command-filter-item">
        <div class="command-filter-label">{{ tm('filters.byStatus') }}</div>
        <v-select
          :model-value="statusFilter"
          @update:model-value="emit('update:statusFilter', $event)"
          :items="statusItems"
          :aria-label="tm('filters.byStatus')"
          density="compact"
          variant="solo"
          hide-details
          class="command-filter-field"
        />
      </div>
    </v-col>
  </v-row>

  <!-- 搜索栏 + 统计信息行 -->
  <div class="command-filter-toolbar">
    <div class="command-search-wrap">
      <v-text-field
        :model-value="searchQuery"
        @update:model-value="emit('update:searchQuery', normalizeTextInput($event))"
        @click:clear="emit('update:searchQuery', '')"
        density="compact"
        :placeholder="tm('search.placeholder')"
        :aria-label="tm('search.placeholder')"
        prepend-inner-icon="mdi-magnify"
        clearable
        variant="solo"
        hide-details
        single-line
        class="command-search-field"
      />
    </div>
    <div class="command-filter-stats">
      <slot name="stats"></slot>
      <v-checkbox
        :model-value="effectiveShowSystemPlugins"
        @update:model-value="emit('update:showSystemPlugins', !!$event)"
        :label="tm('filters.showSystemPlugins')"
        density="compact"
        hide-details
        :disabled="hasSystemPluginConflict"
        class="system-plugin-checkbox"
      >
        <template v-slot:label>
          <span class="text-body-2">{{ tm('filters.showSystemPlugins') }}</span>
          <v-tooltip v-if="hasSystemPluginConflict" location="top">
            <template v-slot:activator="{ props: tooltipProps }">
              <v-icon v-bind="tooltipProps" size="16" color="warning" class="ml-1">mdi-alert-circle</v-icon>
            </template>
            {{ tm('filters.systemPluginConflictHint') }}
          </v-tooltip>
        </template>
      </v-checkbox>
    </div>
  </div>
</template>

<style scoped>
.command-filter-grid {
  flex: 0 0 auto;
  align-content: flex-start;
  margin: 0;
  padding: 14px 18px 6px;
  background: linear-gradient(180deg, #f8fbfd 0%, #ffffff 100%);
}

.command-filter-grid :deep(.v-col) {
  padding-top: 6px;
  padding-bottom: 6px;
}

.command-filter-item {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.command-filter-label {
  color: #425466;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.2;
}

.command-filter-field :deep(.v-field),
.command-search-field :deep(.v-field) {
  min-height: 38px;
  border: 1px solid #d9e6ee;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: none;
}

.command-filter-field :deep(.v-field--focused),
.command-search-field :deep(.v-field--focused) {
  border-color: #9ed2ee;
  box-shadow: 0 0 0 3px rgba(66, 165, 217, 0.12);
}

.command-filter-field :deep(.v-field__input),
.command-search-field :deep(.v-field__input) {
  min-height: 38px;
  padding-top: 0;
  padding-bottom: 0;
  color: #263545;
  font-size: 13px;
}

.command-search-field :deep(.v-field__prepend-inner) {
  color: rgb(var(--v-theme-primary));
}

.command-filter-toolbar {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 18px 14px;
  border-bottom: 1px solid #e3edf3;
  background: #ffffff;
}

.command-search-wrap {
  flex: 1 1 320px;
  min-width: 260px;
  max-width: 430px;
}

.command-filter-stats {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.command-filter-stats :deep(.d-flex.align-center) {
  min-height: 34px;
  padding: 6px 11px;
  border: 1px solid #d9e6ee;
  border-radius: 999px;
  background: #ffffff;
  color: #526171;
}

.system-plugin-checkbox {
  flex: none;
  min-height: 34px;
  padding: 0 10px 0 6px;
  border: 1px solid #d9e6ee;
  border-radius: 999px;
  background: #ffffff;
}

.system-plugin-checkbox :deep(.v-selection-control) {
  min-height: auto;
}

@media (max-width: 760px) {
  .command-filter-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .command-search-wrap {
    max-width: none;
    min-width: 0;
    width: 100%;
  }
}
</style>
