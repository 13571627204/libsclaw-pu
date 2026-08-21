<script setup lang="ts">
import { useI18n, useModuleI18n } from '@/i18n/composables';
import type { CommandItem, TypeInfo } from '../types';

const { t } = useI18n();
const { tm } = useModuleI18n('features/command');

// Props
defineProps<{
  show: boolean;
  command: CommandItem | null;
}>();

// Emits
const emit = defineEmits<{
  (e: 'update:show', value: boolean): void;
}>();

// 获取类型信息
const getTypeInfo = (type: string): TypeInfo => {
  switch (type) {
    case 'group':
      return { text: tm('type.group'), color: 'info', icon: 'mdi-folder-outline' };
    case 'sub_command':
      return { text: tm('type.subCommand'), color: 'secondary', icon: 'mdi-subdirectory-arrow-right' };
    default:
      return { text: tm('type.command'), color: 'primary', icon: 'mdi-console-line' };
  }
};

// 获取权限颜色
const getPermissionColor = (permission: string): string => {
  switch (permission) {
    case 'admin': return 'error';
    default: return 'success';
  }
};

// 获取权限标签
const getPermissionLabel = (permission: string): string => {
  switch (permission) {
    case 'admin': return tm('permission.admin');
    default: return tm('permission.everyone');
  }
};
</script>

<template>
  <v-dialog :model-value="show" @update:model-value="emit('update:show', $event)" max-width="560">
    <v-card v-if="command" class="details-dialog-card">
      <div class="details-dialog-header">
        <div class="details-dialog-eyebrow">{{ tm('dialogs.details.title') }}</div>
        <div class="details-command-title">
          <span class="details-command-marker">
            <v-icon size="15">mdi-console-line</v-icon>
          </span>
          {{ command.effective_command }}
        </div>
        <v-btn
          icon="mdi-close"
          variant="text"
          size="small"
          class="details-dialog-close"
          @click="emit('update:show', false)"
        />
        <div class="details-summary">
          <v-chip :color="getTypeInfo(command.type).color" size="small" variant="tonal">
            <v-icon start size="14">{{ getTypeInfo(command.type).icon }}</v-icon>
            {{ getTypeInfo(command.type).text }}
          </v-chip>
          <v-chip :color="getPermissionColor(command.permission)" size="small" variant="tonal">
            {{ getPermissionLabel(command.permission) }}
          </v-chip>
          <v-chip v-if="command.has_conflict" color="warning" size="small" variant="tonal">
            {{ tm('status.conflict') }}
          </v-chip>
        </div>
      </div>

      <v-card-text class="details-dialog-body">
        <div class="details-list">
          <div class="details-row">
            <span class="details-label">{{ tm('dialogs.details.handler') }}</span>
            <code>{{ command.handler_name }}</code>
          </div>
          <div class="details-row details-row--path">
            <span class="details-label">{{ tm('dialogs.details.module') }}</span>
            <code>{{ command.module_path }}</code>
          </div>
          <div class="details-row">
            <span class="details-label">{{ tm('dialogs.details.originalCommand') }}</span>
            <code>{{ command.original_command }}</code>
          </div>
          <div class="details-row">
            <span class="details-label">{{ tm('dialogs.details.effectiveCommand') }}</span>
            <code>{{ command.effective_command }}</code>
          </div>
          <div v-if="command.parent_signature" class="details-row">
            <span class="details-label">{{ tm('dialogs.details.parentGroup') }}</span>
            <code>{{ command.parent_signature }}</code>
          </div>
        </div>

        <div v-if="command.aliases.length > 0" class="details-chip-section">
          <div class="details-label">{{ tm('dialogs.details.aliases') }}</div>
          <div class="details-chip-list">
            <v-chip v-for="alias in command.aliases" :key="alias" size="small" variant="tonal" color="primary">
              {{ alias }}
            </v-chip>
          </div>
        </div>

        <div v-if="command.is_group && command.sub_commands?.length > 0" class="details-chip-section">
          <div class="details-label">{{ tm('dialogs.details.subCommands') }}</div>
          <div class="details-chip-list">
            <v-chip
              v-for="sub in command.sub_commands"
              :key="sub.handler_full_name"
              size="small"
              variant="outlined"
              color="primary"
            >
              {{ sub.current_fragment }}
            </v-chip>
          </div>
        </div>
      </v-card-text>

      <v-card-actions class="details-dialog-actions">
        <v-spacer />
        <v-btn class="details-dialog-action" color="primary" variant="tonal" @click="emit('update:show', false)">
          {{ t('core.actions.close') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.details-dialog-card {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-primary), 0.16);
  border-radius: 18px !important;
  background:
    linear-gradient(180deg, rgba(var(--v-theme-primary), 0.055), transparent 160px),
    rgb(var(--v-theme-surface));
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.2) !important;
}

.details-dialog-header {
  position: relative;
  padding: 24px 72px 18px 28px;
  border-bottom: 1px solid rgba(var(--v-theme-border), 0.54);
}

.details-dialog-eyebrow {
  margin-bottom: 7px;
  color: rgba(var(--v-theme-on-surface), 0.56);
  font-size: 12px;
  font-weight: 760;
  letter-spacing: 0;
}

.details-command-title {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 8px;
  color: rgba(var(--v-theme-on-surface), 0.9);
  font-size: 17px;
  font-weight: 760;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.details-command-marker {
  display: inline-flex;
  width: 24px;
  height: 24px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(var(--v-theme-primary), 0.16);
  border-radius: 8px;
  background: rgba(var(--v-theme-primary), 0.09);
  color: rgb(var(--v-theme-primary));
}

.details-dialog-close {
  position: absolute;
  top: 20px;
  right: 24px;
  border-radius: 10px !important;
  color: rgba(var(--v-theme-on-surface), 0.58);
}

.details-dialog-close:hover {
  background: rgba(var(--v-theme-primary), 0.08);
  color: rgb(var(--v-theme-primary));
}

.details-dialog-body {
  max-height: min(60vh, 480px);
  overflow-y: auto;
  padding: 18px 28px 8px !important;
}

.details-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.details-list {
  display: grid;
  border: 1px solid rgba(var(--v-theme-border), 0.54);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.82);
  overflow: hidden;
}

.details-row {
  display: grid;
  grid-template-columns: 104px minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  min-width: 0;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(var(--v-theme-border), 0.48);
}

.details-row:last-child {
  border-bottom: 0;
}

.details-row--path {
  align-items: start;
}

.details-label {
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
}

.details-chip-section {
  margin-top: 10px;
  padding: 12px 14px;
  border: 1px solid rgba(var(--v-theme-border), 0.54);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
}

.details-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.details-dialog-actions {
  gap: 10px;
  padding: 10px 28px 22px !important;
  border-top: 1px solid rgba(var(--v-theme-border), 0.54);
  background: rgba(255, 255, 255, 0.82);
}

.details-dialog-action {
  min-width: 92px;
  height: 40px !important;
  max-height: 40px;
  border: 1px solid rgba(var(--v-theme-primary), 0.14);
  border-radius: 8px !important;
  font-weight: 650;
  letter-spacing: 0;
}

code {
  display: inline-block;
  max-width: 100%;
  padding: 3px 7px;
  border-radius: 7px;
  background-color: rgba(var(--v-theme-on-surface), 0.055);
  color: rgba(var(--v-theme-on-surface), 0.76);
  font-size: 0.9em;
  line-height: 1.45;
  overflow-wrap: anywhere;
  vertical-align: middle;
  white-space: normal;
}

.details-row:not(.details-row--path) code {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 700px) {
  .details-row {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .details-dialog-header,
  .details-dialog-body,
  .details-dialog-actions {
    padding-inline: 18px !important;
  }
}
</style>
