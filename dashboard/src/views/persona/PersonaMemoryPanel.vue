<template>
  <v-dialog :model-value="modelValue" max-width="820px" @update:model-value="close">
    <v-card>
      <v-card-title class="text-h3 pa-4 pb-0 pl-6 d-flex align-center justify-space-between">
        <div class="d-flex align-center">
          <v-icon class="mr-2" color="primary">mdi-brain</v-icon>
          <span>{{ tm('memory.title', { id: personaId }) }}</span>
        </div>
        <v-btn icon="mdi-close" variant="text" :disabled="saving" @click="close()" />
      </v-card-title>

      <v-card-text class="pt-4">
        <v-alert type="info" variant="tonal" class="mb-4" density="comfortable">
          {{ tm('memory.description') }}
        </v-alert>

        <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-4" closable
          @click:close="errorMessage = ''">
          {{ errorMessage }}
        </v-alert>

        <v-skeleton-loader v-if="loading" type="paragraph, paragraph, paragraph" />
        <v-textarea v-else v-model="content" :label="tm('memory.fieldLabel')"
          :hint="tm('memory.fieldHint')" persistent-hint variant="outlined" rows="15" auto-grow
          :maxlength="maxChars" :counter="maxChars" spellcheck="false" />
      </v-card-text>

      <v-card-actions class="px-6 pb-5">
        <span class="text-caption text-medium-emphasis">{{ tm('memory.autoSaveHint') }}</span>
        <v-spacer />
        <v-btn variant="text" :disabled="saving" @click="close()">
          {{ tm('buttons.cancel') }}
        </v-btn>
        <v-btn color="primary" variant="tonal" :loading="saving" :disabled="loading || !changed"
          @click="save">
          {{ tm('buttons.save') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, shallowRef, watch } from 'vue';
import { personaApi } from '@/api/v1';
import { useModuleI18n } from '@/i18n/composables';

const props = defineProps<{
  modelValue: boolean;
  personaId: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
  saved: [message: string];
}>();

const { tm } = useModuleI18n('features/persona');
const maxChars = 32000;
const content = shallowRef('');
const originalContent = shallowRef('');
const loading = shallowRef(false);
const saving = shallowRef(false);
const errorMessage = shallowRef('');
const changed = computed(() => content.value.trim() !== originalContent.value);

function close(value = false) {
  if (saving.value) return;
  emit('update:modelValue', value);
}

async function loadMemory() {
  if (!props.personaId) return;
  loading.value = true;
  errorMessage.value = '';
  content.value = '';
  originalContent.value = '';
  try {
    const response = await personaApi.get(props.personaId);
    if (response.data.status !== 'ok') {
      throw new Error(response.data.message || tm('memory.loadError'));
    }
    const memory = String(response.data.data?.memory || '').trim();
    content.value = memory;
    originalContent.value = memory;
  } catch (error: any) {
    errorMessage.value = error.response?.data?.message || error.message || tm('memory.loadError');
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (!props.personaId || !changed.value) return;
  saving.value = true;
  errorMessage.value = '';
  try {
    const memory = content.value.trim();
    const response = await personaApi.update(props.personaId, { memory });
    if (response.data.status !== 'ok') {
      throw new Error(response.data.message || tm('memory.saveError'));
    }
    content.value = memory;
    originalContent.value = memory;
    emit('saved', tm('memory.saveSuccess'));
    emit('update:modelValue', false);
  } catch (error: any) {
    errorMessage.value = error.response?.data?.message || error.message || tm('memory.saveError');
  } finally {
    saving.value = false;
  }
}

watch(
  [() => props.modelValue, () => props.personaId],
  ([open]) => {
    if (open) void loadMemory();
  },
);
</script>
