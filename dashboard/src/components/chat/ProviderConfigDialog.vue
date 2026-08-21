<template>
  <v-dialog
    v-model="dialog"
    max-width="1600"
  >
    <v-card class="provider-config-dialog">
      <div class="provider-config-dialog__body">
        <ProviderChatCompletionPanel
          class="provider-config-dialog__page"
          :show-border="false"
        />
      </div>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed } from 'vue'
import ProviderChatCompletionPanel from '@/components/provider/ProviderChatCompletionPanel.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])
const dialog = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})
</script>

<style scoped>
.provider-config-dialog {
  width: 100%;
  height: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-border), 0.72);
  border-radius: 18px;
  box-shadow: 0 24px 70px rgba(17, 24, 39, 0.18);
}

.provider-config-dialog__body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.provider-config-dialog__page {
  flex: 1;
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
}

:deep(.v-overlay__content) {
  width: min(1180px, calc(100vw - 96px));
  height: min(720px, calc(100dvh - 96px));
  max-width: calc(100vw - 96px);
  max-height: calc(100dvh - 96px);
  margin: 0;
}

@media (max-width: 960px) {
  .provider-config-dialog {
    border-radius: 16px;
  }

  :deep(.v-overlay__content) {
    width: calc(100dvw - 24px);
    height: calc(100dvh - 24px);
    max-width: calc(100dvw - 24px);
    max-height: calc(100dvh - 24px);
  }
}

@media (max-width: 600px) {
  .provider-config-dialog {
    border-radius: 0;
  }

  .provider-config-dialog__body {
    overflow: auto;
  }

  :deep(.v-overlay__content) {
    width: 100dvw;
    height: 100dvh;
    max-width: 100dvw;
    max-height: 100dvh;
  }
}
</style>
