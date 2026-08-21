<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useModuleI18n } from '@/i18n/composables';
import type { CommandItem } from '../types';

const { tm } = useModuleI18n('features/command');

// Props
const props = defineProps<{
  show: boolean;
  command: CommandItem | null;
  newName: string;
  aliases: string[];
  loading: boolean;
}>();

// Emits
const emit = defineEmits<{
  (e: 'update:show', value: boolean): void;
  (e: 'update:newName', value: string): void;
  (e: 'update:aliases', value: string[]): void;
  (e: 'confirm'): void;
}>();

const addAlias = () => {
  emit('update:aliases', [...props.aliases, '']);
};

const removeAlias = (index: number) => {
  const newAliases = [...props.aliases];
  newAliases.splice(index, 1);
  emit('update:aliases', newAliases);
};

const updateAlias = (index: number, value: string) => {
  const newAliases = [...props.aliases];
  newAliases[index] = value;
  emit('update:aliases', newAliases);
};

const hasAliases = computed(() => (props.aliases || []).some(a => (a ?? '').toString().trim()));
const showAliasEditor = ref(false);
const aliasEditorEverOpened = ref(false);

watch(
  () => props.show,
  (open) => {
    if (!open) return;
    // 如果已有别名则默认展开，否则默认收起
    showAliasEditor.value = hasAliases.value;
  },
);

watch(showAliasEditor, (open) => {
  if (open) aliasEditorEverOpened.value = true;
});
</script>

<template>
  <v-dialog :model-value="show" @update:model-value="emit('update:show', $event)" max-width="560">
    <v-card class="rename-dialog-card">
      <div class="rename-dialog-header">
        <div class="rename-dialog-heading">
          <span class="rename-dialog-icon">
            <v-icon size="20">mdi-pencil-outline</v-icon>
          </span>
          <div class="rename-dialog-title-copy">
            <div class="rename-dialog-title">{{ tm('dialogs.rename.title') }}</div>
            <code v-if="command" class="rename-dialog-current">{{ command.effective_command }}</code>
          </div>
        </div>
        <v-btn
          icon="mdi-close"
          variant="text"
          size="small"
          class="rename-dialog-close"
          @click="emit('update:show', false)"
        />
      </div>

      <v-card-text class="rename-dialog-body">
        <section class="rename-primary-section">
          <div class="rename-section-label">{{ tm('dialogs.rename.newName') }}</div>
          <v-text-field
            :model-value="newName"
            @update:model-value="emit('update:newName', $event)"
            :placeholder="tm('dialogs.rename.newName')"
            variant="outlined"
            density="compact"
            autofocus
            hide-details
            class="rename-name-field"
          />
        </section>

        <section class="rename-alias-section">
          <div
            class="rename-alias-toggle"
            role="button"
            tabindex="0"
            @click="showAliasEditor = !showAliasEditor"
            @keydown.enter.prevent="showAliasEditor = !showAliasEditor"
            @keydown.space.prevent="showAliasEditor = !showAliasEditor"
          >
            <div class="rename-alias-title">
              <span>{{ tm('dialogs.rename.aliases') }}</span>
              <small>{{ aliases.filter(alias => alias.trim()).length }} 个别名</small>
            </div>
            <v-icon size="20">{{ showAliasEditor ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
          </div>
          <v-slide-y-transition>
            <div v-if="aliasEditorEverOpened" v-show="showAliasEditor" class="rename-alias-editor">
              <div v-for="(alias, index) in aliases" :key="index" class="rename-alias-row">
                <v-text-field
                  :model-value="alias"
                  @update:model-value="updateAlias(index, $event)"
                  variant="outlined"
                  density="compact"
                  hide-details
                  class="rename-alias-field"
                />
                <v-btn
                  icon="mdi-delete-outline"
                  variant="text"
                  color="error"
                  density="compact"
                  class="rename-alias-delete"
                  @click="removeAlias(index)"
                />
              </div>
              <v-btn
                prepend-icon="mdi-plus"
                variant="tonal"
                color="primary"
                block
                size="small"
                class="rename-add-alias-btn"
                @click="addAlias"
              >
                {{ tm('dialogs.rename.addAlias') }}
              </v-btn>
            </div>
          </v-slide-y-transition>
        </section>
      </v-card-text>
      <v-card-actions class="rename-dialog-actions">
        <v-spacer />
        <v-btn class="rename-dialog-cancel" variant="text" @click="emit('update:show', false)">
          {{ tm('dialogs.rename.cancel') }}
        </v-btn>
        <v-btn
          class="rename-dialog-confirm"
          color="primary"
          variant="tonal"
          :loading="loading"
          @click="emit('confirm')"
        >
          {{ tm('dialogs.rename.confirm') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.rename-dialog-card {
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-primary), 0.16);
  border-radius: 18px !important;
  background:
    linear-gradient(180deg, rgba(var(--v-theme-primary), 0.055), transparent 150px),
    rgb(var(--v-theme-surface));
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.2) !important;
}

.rename-dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 24px 26px 16px;
  border-bottom: 1px solid rgba(var(--v-theme-border), 0.54);
}

.rename-dialog-heading {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 14px;
}

.rename-dialog-icon {
  display: inline-flex;
  width: 40px;
  height: 40px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(var(--v-theme-primary), 0.16);
  border-radius: 12px;
  background: rgba(var(--v-theme-primary), 0.1);
  color: rgb(var(--v-theme-primary));
}

.rename-dialog-title-copy {
  min-width: 0;
}

.rename-dialog-title {
  color: rgb(var(--v-theme-primaryText));
  font-size: 1.22rem;
  font-weight: 760;
  line-height: 1.28;
  letter-spacing: 0;
}

.rename-dialog-current {
  display: inline-block;
  max-width: 380px;
  margin-top: 7px;
  overflow: hidden;
  padding: 3px 8px;
  border-radius: 7px;
  background: rgba(var(--v-theme-primary), 0.08);
  color: rgb(var(--v-theme-primary));
  font-size: 13px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rename-dialog-close {
  flex: 0 0 auto;
  border-radius: 10px !important;
  color: rgba(var(--v-theme-on-surface), 0.58);
}

.rename-dialog-close:hover {
  background: rgba(var(--v-theme-primary), 0.08);
  color: rgb(var(--v-theme-primary));
}

.rename-dialog-body {
  padding: 18px 26px 12px !important;
}

.rename-primary-section,
.rename-alias-section {
  border: 1px solid rgba(var(--v-theme-border), 0.56);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.82);
}

.rename-primary-section {
  padding: 14px;
}

.rename-section-label {
  margin-bottom: 8px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 12px;
  font-weight: 760;
  line-height: 1.35;
}

.rename-name-field :deep(.v-field),
.rename-alias-field :deep(.v-field) {
  border-radius: 10px;
  background: rgba(248, 251, 253, 0.78);
}

.rename-name-field :deep(.v-field__input),
.rename-alias-field :deep(.v-field__input) {
  min-height: 42px;
  padding-top: 8px;
  padding-bottom: 8px;
}

.rename-alias-section {
  margin-top: 12px;
  overflow: hidden;
}

.rename-alias-toggle {
  display: flex;
  min-height: 54px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  cursor: pointer;
}

.rename-alias-title {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
  color: rgba(var(--v-theme-on-surface), 0.82);
  font-size: 14px;
  font-weight: 720;
}

.rename-alias-title small {
  color: rgba(var(--v-theme-on-surface), 0.5);
  font-size: 12px;
  font-weight: 600;
}

.rename-alias-editor {
  padding: 0 14px 14px;
  border-top: 1px solid rgba(var(--v-theme-border), 0.48);
}

.rename-alias-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.rename-alias-field {
  flex: 1 1 auto;
  min-width: 0;
}

.rename-alias-delete {
  border-radius: 8px !important;
}

.rename-add-alias-btn {
  height: 38px !important;
  margin-top: 12px;
  border: 1px solid rgba(var(--v-theme-primary), 0.14);
  border-radius: 9px !important;
  font-weight: 650;
  letter-spacing: 0;
}

.rename-dialog-actions {
  gap: 10px;
  padding: 10px 26px 22px !important;
  border-top: 1px solid rgba(var(--v-theme-border), 0.54);
  background: rgba(255, 255, 255, 0.82);
}

.rename-dialog-cancel,
.rename-dialog-confirm {
  min-width: 92px;
  height: 40px !important;
  max-height: 40px;
  border-radius: 8px !important;
  font-weight: 650;
  letter-spacing: 0;
}

.rename-dialog-cancel {
  color: rgba(var(--v-theme-on-surface), 0.72);
}

.rename-dialog-cancel:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.rename-dialog-confirm {
  border: 1px solid rgba(var(--v-theme-primary), 0.14);
}

@media (max-width: 640px) {
  .rename-dialog-header,
  .rename-dialog-body,
  .rename-dialog-actions {
    padding-inline: 18px !important;
  }
}
</style>
