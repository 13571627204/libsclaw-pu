<template>
  <v-dialog v-model="isOpen" max-width="460">
    <v-card class="confirm-dialog-card" :class="{ 'confirm-dialog-card--delete': isDeleteConfirm }">
      <v-card-title class="text-h3 pa-4 pb-0 pl-6 confirm-dialog-title">
        <span class="confirm-dialog-title__icon">
          <v-icon size="22">{{ confirmIcon }}</v-icon>
        </span>
        <span>{{ displayTitle }}</span>
      </v-card-title>
      <v-card-text class="confirm-dialog-body">
        <p class="confirm-dialog-message">{{ message }}</p>
        <div v-if="deleteTarget" class="confirm-dialog-target">{{ deleteTarget }}</div>
      </v-card-text>
      <v-card-actions class="confirm-dialog-actions">
        <v-spacer></v-spacer>
        <v-btn class="confirm-dialog-btn confirm-dialog-btn--cancel" variant="text" @click="handleCancel">
          {{ t('core.common.dialog.cancelButton') }}
        </v-btn>
        <v-btn class="confirm-dialog-btn confirm-dialog-btn--confirm" color="error" variant="tonal" @click="handleConfirm">
          {{ confirmButtonText }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed, ref } from "vue";
import { useI18n } from '@/i18n/composables';

const { t } = useI18n();

const isOpen = ref(false);
const title = ref("");
const message = ref("");
let resolvePromise = null; // ✅ 确保 Promise 句柄可用

const isDeleteConfirm = computed(() => /删除|移除|delete|remove|uninstall/i.test(`${title.value} ${message.value}`));
const confirmIcon = computed(() => isDeleteConfirm.value ? 'mdi-trash-can-outline' : 'mdi-alert-outline');
const displayTitle = computed(() => isDeleteConfirm.value ? '删除确认' : title.value);
const confirmButtonText = computed(() => isDeleteConfirm.value ? '确定删除' : t('core.common.dialog.confirmButton'));
const deleteTarget = computed(() => {
  if (!isDeleteConfirm.value) return '';

  const patterns = [
    /删除(?:模型提供商|模型|平台适配器|平台|会话|项目|文件|文件夹|插件|服务器|子代理|规则|文档|数据|备份)?\s*[「“"]?(.+?)[」”"]?\s*(?:吗|么|\?|？|$)/,
    /移除(?:模型提供商|模型|平台适配器|平台|会话|项目|文件|文件夹|插件|服务器|子代理|规则|文档|数据|备份)?\s*[「“"]?(.+?)[」”"]?\s*(?:吗|么|\?|？|$)/,
    /(?:delete|remove|uninstall)\s+["']?(.+?)["']?\s*(?:\?|$)/i
  ];

  for (const pattern of patterns) {
    const match = message.value.match(pattern);
    const target = match?.[1]?.trim();
    if (target) return target.replace(/[。.!！]$/, '');
  }

  return '';
});

const open = (options) => {
  title.value = options.title || t('core.common.dialog.confirmTitle');
  message.value = options.message || t('core.common.dialog.confirmMessage');
  isOpen.value = true;

  return new Promise((resolve) => {
    resolvePromise = resolve; // ✅ 赋值 Promise 解析方法
  });
};

const handleConfirm = () => {
  isOpen.value = false;
  if (resolvePromise) resolvePromise(true); // ✅ 解析 Promise
};

const handleCancel = () => {
  isOpen.value = false;
  if (resolvePromise) resolvePromise(false); // ✅ 解析 Promise
};

defineExpose({ open }); // ✅ 确保 `confirmPlugin.ts` 可以访问 `open`
</script>

<style scoped>
.confirm-dialog-card {
  border: 1px solid rgba(var(--v-theme-error), 0.18);
  border-radius: 18px !important;
  background:
    linear-gradient(180deg, rgba(var(--v-theme-error), 0.055), transparent 150px),
    rgb(var(--v-theme-surface));
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.22) !important;
  overflow: hidden;
}

.confirm-dialog-title {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 24px 26px 12px !important;
  color: rgb(var(--v-theme-primaryText));
  font-size: 1.22rem !important;
  font-weight: 740;
  line-height: 1.3;
  letter-spacing: 0;
}

.confirm-dialog-title__icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  color: rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-error), 0.1);
  border: 1px solid rgba(var(--v-theme-error), 0.18);
}

.confirm-dialog-body {
  padding: 10px 26px 18px !important;
}

.confirm-dialog-message {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), 0.76);
  font-size: 15px;
  line-height: 1.65;
}

.confirm-dialog-target {
  margin-top: 14px;
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-theme-error), 0.13);
  border-radius: 10px;
  color: rgba(var(--v-theme-error), 0.92);
  background: rgba(var(--v-theme-error), 0.06);
  font-size: 13px;
  font-weight: 650;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.confirm-dialog-actions {
  padding: 2px 26px 24px !important;
  gap: 10px;
}

.confirm-dialog-btn {
  min-width: 92px;
  height: 42px;
  max-height: 42px;
  border-radius: 8px;
  font-weight: 650;
  letter-spacing: 0;
}

.confirm-dialog-btn--cancel {
  color: rgba(var(--v-theme-on-surface), 0.72);
}

.confirm-dialog-btn--cancel:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.confirm-dialog-btn--confirm {
  border: 1px solid rgba(var(--v-theme-error), 0.18);
}
</style>
