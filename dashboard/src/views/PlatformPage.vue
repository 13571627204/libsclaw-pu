<template>
  <div class="platform-page">
    <v-container fluid class="platform-shell">
      <section class="platform-hero">
        <div class="platform-hero__copy">
          <div>
            <h1 class="platform-hero__title">
              {{ tm('title') }}
            </h1>
            <p class="platform-hero__subtitle">
              {{ tm('subtitle') }}
            </p>
          </div>
        </div>
        <v-btn
          color="primary"
          prepend-icon="mdi-plus"
          variant="flat"
          class="platform-hero__action"
          @click="updatingMode = false; showAddPlatformDialog = true"
        >
          {{ tm('addAdapter') }}
        </v-btn>
      </section>

      <section>
        <div v-if="(config_data.platform || []).length === 0" class="platform-empty-state">
          <v-icon size="46" color="primary">mdi-connection</v-icon>
          <p>{{ tm('emptyText') }}</p>
        </div>

        <div v-else class="platform-grid">
          <div v-for="(platform, index) in config_data.platform || []" :key="index" class="platform-card-shell">
            <item-card :item="platform" title-field="id" enabled-field="enable"
              variant="outlined"
              :bglogo="getPlatformIcon(platform.type || platform.id)"
              :disable-toggle="isPlatformExpired(platform)"
              :toggle-tooltip="getPlatformToggleTooltip(platform)"
              @toggle-enabled="platformStatusChange"
              @delete="deletePlatform" @edit="editPlatform">
              <template #item-details="{ item }">
                <!-- 平台运行状态 - 只在非运行状态或有错误时显示 -->
                <div class="platform-status-row mb-2" v-if="getPlatformStat(item.id) && (getPlatformStat(item.id)?.status !== 'running' || getPlatformStat(item.id)?.error_count > 0)">
                  <!-- 状态 chip - 只在非 running 状态时显示 -->
                  <v-chip
                    v-if="getPlatformStat(item.id)?.status !== 'running'"
                    size="small"
                    :color="getStatusColor(getPlatformStat(item.id)?.status)"
                    variant="tonal"
                    class="status-chip"
                  >
                    <v-icon size="small" start>{{ getStatusIcon(getPlatformStat(item.id)?.status) }}</v-icon>
                    {{ tm('runtimeStatus.' + (getPlatformStat(item.id)?.status || 'unknown')) }}
                  </v-chip>
                  <!-- 错误数量提示 -->
                  <v-chip
                    v-if="getPlatformStat(item.id)?.error_count > 0"
                    size="small"
                    color="error"
                    variant="tonal"
                    class="error-chip"
                    :class="{ 'ms-2': getPlatformStat(item.id)?.status !== 'running' }"
                    @click.stop="showErrorDetails(item)"
                  >
                    <v-icon size="small" start>mdi-bug</v-icon>
                    {{ getPlatformStat(item.id)?.error_count }} {{ tm('runtimeStatus.errors') }}
                  </v-chip>
                </div>
                <div
                  class="platform-qr-chip"
                  v-if="hasQrPayload(item.id)"
                >
                  <v-chip
                    size="small"
                    color="primary"
                    variant="tonal"
                    class="platform-qr-chip-item"
                    @click.stop="openPlatformQrDialog(item.id)"
                  >
                    <v-icon size="small" start>mdi-qrcode</v-icon>
                    {{ tm('platformQr.show') }}
                  </v-chip>
                </div>
                <div class="platform-meta-row">
                  <v-chip
                    size="small"
                    :color="isPlatformExpired(item) ? 'error' : 'primary'"
                    variant="tonal"
                    class="platform-expiry-chip"
                  >
                    {{ getPlatformExpiryText(item) }}
                  </v-chip>
                </div>
                <div v-if="getPlatformNote(item)" class="platform-note">
                  <div class="platform-note__body">{{ getPlatformNote(item) }}</div>
                </div>
                <div v-if="getPlatformStat(item.id)?.unified_webhook && item.webhook_uuid" class="webhook-info">
                  <v-chip
                    size="small"
                    color="primary"
                    variant="tonal"
                    class="webhook-chip"
                    @click.stop="openWebhookDialog(item.webhook_uuid)"
                  >
                    <v-icon size="small" start>mdi-webhook</v-icon>
                    {{ tm('viewWebhook') }}
                  </v-chip>
                </div>
              </template>
            </item-card>
          </div>
        </div>
      </section>

    </v-container>

    <!-- 添加平台适配器对话框 -->
    <AddNewPlatform v-model:show="showAddPlatformDialog" :metadata="metadata" :config_data="config_data" ref="addPlatformDialog"
      :updating-mode="updatingMode" :updating-platform-config="updatingPlatformConfig"
      @show-toast="showToast" @refresh-config="getConfig"/>

    <!-- Webhook URL 对话框 -->
    <v-dialog v-model="showWebhookDialog" max-width="600">
      <v-card>
        <v-card-title class="text-h3 pa-4 pb-0 pl-6 d-flex align-center">
          <v-icon class="me-2" color="primary">mdi-webhook</v-icon>
          {{ tm('webhookDialog.title') }}
        </v-card-title>
        <v-card-text class="px-4 pb-2">
          <p class="text-body-2 text-medium-emphasis mb-3">{{ tm('webhookDialog.description') }}</p>
          <v-text-field
            :model-value="currentWebhookUrl"
            readonly
            variant="outlined"
            hide-details
            class="webhook-url-field"
          >
            <template v-slot:append-inner>
              <v-btn
                icon
                size="small"
                variant="text"
                @click="copyWebhookUrl(currentWebhookUuid)"
              >
                <v-icon>mdi-content-copy</v-icon>
              </v-btn>
            </template>
          </v-text-field>
        </v-card-text>
        <v-card-actions class="pa-4 pt-2">
          <v-spacer></v-spacer>
          <v-btn variant="tonal" color="primary" @click="showWebhookDialog = false">
            {{ tm('webhookDialog.close') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showQrDialog" max-width="480">
      <v-card>
        <v-card-title class="text-h3 pa-4 pb-0 pl-6 d-flex align-center">
          <v-icon class="me-2">mdi-qrcode</v-icon>
          {{ tm('platformQr.title') }}
        </v-card-title>
        <v-card-text class="px-4 pb-4">
          <div class="platform-qr-status">
            {{ tm('platformQr.status') }}: {{ getPlatformQrLoginStat(currentQrPlatformId)?.qr_status || tm('platformQr.waiting') }}
          </div>
          <QrCodeViewer
            :value="(getPlatformQrLoginStat(currentQrPlatformId)?.qrcode_img_content || getPlatformQrLoginStat(currentQrPlatformId)?.qrcode || '')"
            :alt="tm('platformQr.title')"
          />
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer></v-spacer>
          <v-btn variant="tonal" color="primary" @click="showQrDialog = false">
            {{ tm('platformQr.close') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 错误详情对话框 -->
    <v-dialog v-model="showErrorDialog" max-width="700">
      <v-card>
        <v-card-title class="text-h3 pa-4 pb-0 pl-6 d-flex align-center">
          <v-icon class="me-2" color="error">mdi-alert-circle</v-icon>
          {{ tm('errorDialog.title') }}
        </v-card-title>
        <v-card-text class="px-4 pb-4" v-if="currentErrorPlatform">
          <div class="mb-3">
            <strong>{{ tm('errorDialog.platformId') }}:</strong> {{ currentErrorPlatform.id }}
          </div>
          <div class="mb-3">
            <strong>{{ tm('errorDialog.errorCount') }}:</strong> {{ currentErrorPlatform.error_count }}
          </div>
          <div v-if="currentErrorPlatform.last_error" class="error-details">
            <div class="mb-2">
              <strong>{{ tm('errorDialog.lastError') }}:</strong>
            </div>
            <v-alert type="error" variant="tonal" class="mb-3">
              <div class="error-message">{{ currentErrorPlatform.last_error.message }}</div>
              <div class="error-time text-caption text-medium-emphasis mt-1">
                {{ tm('errorDialog.occurredAt') }}: {{ new Date(currentErrorPlatform.last_error.timestamp).toLocaleString() }}
              </div>
            </v-alert>
            <div v-if="currentErrorPlatform.last_error.traceback">
              <div class="mb-2">
                <strong>{{ tm('errorDialog.traceback') }}:</strong>
              </div>
              <pre class="traceback-box">{{ currentErrorPlatform.last_error.traceback }}</pre>
            </div>
          </div>
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer></v-spacer>
          <v-btn variant="tonal" color="primary" @click="showErrorDialog = false">
            {{ tm('errorDialog.close') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 消息提示 -->
    <v-snackbar :timeout="3000" elevation="6" :color="save_message_success" v-model="save_message_snack"
      location="top">
      {{ save_message }}
    </v-snackbar>
  </div>
</template>

<script>
import { botApi, fileApi, systemConfigApi } from '@/api/v1';
import AstrBotConfig from '@/components/shared/AstrBotConfig.vue';
import WaitingForRestart from '@/components/shared/WaitingForRestart.vue';
import ItemCard from '@/components/shared/ItemCard.vue';
import AddNewPlatform from '@/components/platform/AddNewPlatform.vue';
import QrCodeViewer from '@/components/shared/QrCodeViewer.vue';
import { useCommonStore } from '@/stores/common';
import { useI18n, useModuleI18n, mergeDynamicTranslations } from '@/i18n/composables';
import { getPlatformIcon } from '@/utils/platformUtils';
import {
  askForConfirmation as askForConfirmationDialog,
  useConfirmDialog
} from '@/utils/confirmDialog';
import { copyToClipboard } from '@/utils/clipboard';

export default {
  name: 'PlatformPage',
  components: {
    AstrBotConfig,
    WaitingForRestart,
    ItemCard,
    AddNewPlatform,
    QrCodeViewer,
  },
  setup() {
    const { t } = useI18n();
    const { tm } = useModuleI18n('features/platform');
    const confirmDialog = useConfirmDialog();

    return {
      t,
      tm,
      confirmDialog
    };
  },
  data() {
    return {
      config_data: {},
      fetched: false,
      metadata: {},
      showAddPlatformDialog: false,

      updatingPlatformConfig: {},
      updatingMode: false,

      save_message_snack: false,
      save_message: "",
      save_message_success: "success",

      showWebhookDialog: false,
      currentWebhookUuid: '',

      // 平台统计信息
      platformStats: {},
      statsRefreshInterval: null,

      // 错误详情对话框
      showErrorDialog: false,
      currentErrorPlatform: null,
      showQrDialog: false,
      currentQrPlatformId: "",

      store: useCommonStore()
    }
  },

  watch: {
    showIdConflictDialog(newValue) {
      if (!newValue && this.idConflictResolve) {
        this.idConflictResolve(false);
        this.idConflictResolve = null;
      }
    },

    showOneBotEmptyTokenWarnDialog(newValue) {
      if (!newValue && this.oneBotEmptyTokenWarningResolve) {
        this.oneBotEmptyTokenWarningResolve(true);
        this.oneBotEmptyTokenWarningResolve = null;
      }
    }
  },

  mounted() {
    this.getConfig();
    this.getPlatformStats();
    // 每 5 秒刷新一次平台状态
    this.statsRefreshInterval = setInterval(() => {
      this.getPlatformStats();
    }, 5000);
    
    // 监听语言切换事件，重新加载配置以获取插件的 i18n 数据
    window.addEventListener('astrbot-locale-changed', this.handleLocaleChange);
  },

  beforeUnmount() {
    if (this.statsRefreshInterval) {
      clearInterval(this.statsRefreshInterval);
    }
    // 移除语言切换事件监听器
    window.removeEventListener('astrbot-locale-changed', this.handleLocaleChange);
  },

  methods: {
    // 处理语言切换事件，重新加载配置以获取插件的 i18n 数据
    handleLocaleChange() {
      this.getConfig();
    },

    // 从工具函数导入
    getPlatformIcon(platform_id) {
      // 首先检查是否有来自插件的 logo_token
      const template = this.metadata['platform_group']?.metadata?.platform?.config_template?.[platform_id];
      if (template && template.logo_token) {
          // 通过文件服务访问插件提供的 logo
        return fileApi.tokenUrl(template.logo_token);
      }
      return getPlatformIcon(platform_id);
    },

    getConfig() {
      systemConfigApi.runtime().then((res) => {
        this.config_data = res.data.data.config;
        this.fetched = true
        this.metadata = res.data.data.metadata;

        // 将插件平台适配器的 i18n 翻译注入到前端 i18n 系统中
        const platformI18n = res.data.data.platform_i18n_translations;
        if (platformI18n && typeof platformI18n === 'object') {
          mergeDynamicTranslations('features.config-metadata', platformI18n);
        }
      }).catch((err) => {
        this.showError(err);
      });
    },

    async getPlatformStats() {
      await botApi.stats().then((res) => {
        if (res.data.status === 'ok') {
          // 将数组转换为以 id 为 key 的对象，方便查找
          const stats = {};
          for (const platform of res.data.data.platforms || []) {
            stats[platform.id] = platform;
          }
          this.platformStats = stats;
          this.syncExpiredPlatformEnabledState();
        }
      }).catch((err) => {
        console.warn('获取平台统计信息失败:', err);
      });
    },

    syncExpiredPlatformEnabledState() {
      const platforms = this.config_data.platform || [];
      let changed = false;
      for (const platform of platforms) {
        if (platform.enable && this.isPlatformExpired(platform)) {
          platform.enable = false;
          changed = true;
        }
      }
      if (changed) {
        this.config_data = {
          ...this.config_data,
          platform: [...platforms],
        };
      }
    },

    getPlatformStat(platformId) {
      return this.platformStats[platformId] || null;
    },

    hasQrPayload(platformId) {
      const stat = this.getPlatformQrLoginStat(platformId);
      return Boolean(stat?.qrcode_img_content || stat?.qrcode);
    },

    getPlatformQrLoginStat(platformId) {
      const stat = this.getPlatformStat(platformId);
      if (stat?.weixin_oc) {
        return stat.weixin_oc;
      }
      if (stat && typeof stat === "object") {
        for (const value of Object.values(stat)) {
          if (value && typeof value === "object" && ("qrcode_img_content" in value || "qrcode" in value)) {
            return value;
          }
        }
      }
      return null;
    },

    openPlatformQrDialog(platformId) {
      this.currentQrPlatformId = platformId;
      this.showQrDialog = true;
    },

    getPlatformNote(platform) {
      return String(platform?.note || "").trim();
    },

    parsePlatformExpiresAt(value) {
      if (!value) {
        return null;
      }
      const date = new Date(String(value));
      return Number.isNaN(date.getTime()) ? null : date;
    },

    isPlatformExpired(platform) {
      const expiresAt = this.parsePlatformExpiresAt(platform?.expires_at);
      return expiresAt ? expiresAt.getTime() <= Date.now() : false;
    },

    getPlatformExpiryText(platform) {
      const expiresAt = this.parsePlatformExpiresAt(platform?.expires_at);
      if (!expiresAt) {
        return this.tm('platformExpiry.permanent');
      }
      const text = expiresAt.toLocaleString();
      return this.isPlatformExpired(platform)
        ? this.tm('platformExpiry.expiredAt', { time: text })
        : this.tm('platformExpiry.expiresAt', { time: text });
    },

    getPlatformToggleTooltip(platform) {
      if (this.isPlatformExpired(platform)) {
        return this.tm('messages.expiredCannotEnable');
      }
      return '';
    },

    getStatusColor(status) {
      switch (status) {
        case 'running': return 'success';
        case 'error': return 'error';
        case 'pending': return 'warning';
        case 'stopped': return 'grey';
        default: return 'grey';
      }
    },

    getStatusIcon(status) {
      switch (status) {
        case 'running': return 'mdi-check-circle';
        case 'error': return 'mdi-alert-circle';
        case 'pending': return 'mdi-clock-outline';
        case 'stopped': return 'mdi-stop-circle';
        default: return 'mdi-help-circle';
      }
    },

    showErrorDetails(platform) {
      const stat = this.getPlatformStat(platform.id);
      if (stat && stat.error_count > 0) {
        this.currentErrorPlatform = stat;
        this.showErrorDialog = true;
      }
    },

    findPlatformTemplate(platform) {
      const templates = this.metadata?.platform_group?.metadata?.platform?.config_template || {};

      if (platform?.type && templates[platform.type]) {
        return templates[platform.type];
      }
      if (platform?.id && templates[platform.id]) {
        return templates[platform.id];
      }

      for (const template of Object.values(templates)) {
        if (template?.type === platform?.type) {
          return template;
        }
      }
      return null;
    },

    mergeConfigWithTemplate(sourceConfig, templateConfig) {
      const merge = (source, reference) => {
        const target = {};
        const sourceObj = source && typeof source === 'object' && !Array.isArray(source) ? source : {};
        const referenceObj = reference && typeof reference === 'object' && !Array.isArray(reference) ? reference : null;

        if (!referenceObj) {
          for (const [key, value] of Object.entries(sourceObj)) {
            if (Array.isArray(value)) {
              target[key] = [...value];
            } else if (value && typeof value === 'object') {
              target[key] = { ...value };
            } else {
              target[key] = value;
            }
          }
          return target;
        }

        // 1) 先按模板顺序写入，保证字段相对顺序与 template 一致
        for (const [key, refValue] of Object.entries(referenceObj)) {
          const hasSourceKey = Object.prototype.hasOwnProperty.call(sourceObj, key);
          const sourceValue = sourceObj[key];

          if (refValue && typeof refValue === 'object' && !Array.isArray(refValue)) {
            target[key] = merge(
              hasSourceKey && sourceValue && typeof sourceValue === 'object' && !Array.isArray(sourceValue)
                ? sourceValue
                : {},
              refValue
            );
            continue;
          }

          if (hasSourceKey) {
            if (Array.isArray(sourceValue)) {
              target[key] = [...sourceValue];
            } else if (sourceValue && typeof sourceValue === 'object') {
              target[key] = { ...sourceValue };
            } else {
              target[key] = sourceValue;
            }
          } else if (Array.isArray(refValue)) {
            target[key] = [...refValue];
          } else {
            target[key] = refValue;
          }
        }

        // 2) 再补充 source 中模板没有的额外字段，保持旧配置兼容性
        for (const [key, value] of Object.entries(sourceObj)) {
          if (Object.prototype.hasOwnProperty.call(referenceObj, key)) {
            continue;
          }
          if (Array.isArray(value)) {
            target[key] = [...value];
          } else if (value && typeof value === 'object') {
            target[key] = { ...value };
          } else {
            target[key] = value;
          }
        }

        return target;
      };

      return merge(sourceConfig, templateConfig);
    },

    editPlatform(platform) {
      const platformCopy = JSON.parse(JSON.stringify(platform));
      const template = this.findPlatformTemplate(platformCopy);
      this.updatingPlatformConfig = template
        ? this.mergeConfigWithTemplate(platformCopy, template)
        : platformCopy;
      this.updatingMode = true;
      this.showAddPlatformDialog = true;
      this.$nextTick(() => {
        this.$refs.addPlatformDialog.toggleShowConfigSection();
      });
    },

    async deletePlatform(platform) {
      const message = `${this.messages.deleteConfirm} ${platform.id}?`;
      if (!(await askForConfirmationDialog(message, this.confirmDialog))) {
        return;
      }

      botApi.delete(platform.id).then((res) => {
        this.getConfig();
        this.showSuccess(res.data.message || this.messages.deleteSuccess);
      }).catch((err) => {
        this.showError(err.response?.data?.message || err.message);
      });
    },

    platformStatusChange(platform) {
      if (this.isPlatformExpired(platform)) {
        this.showError(this.tm('messages.expiredCannotEnable'));
        return;
      }
      platform.enable = !platform.enable; // 切换状态

      botApi.setEnabled(platform.id, { enabled: platform.enable }).then((res) => {
        this.getConfig();
        this.showSuccess(res.data.message || this.messages.statusUpdateSuccess);
      }).catch((err) => {
        platform.enable = !platform.enable; // 发生错误时回滚状态
        this.showError(err.response?.data?.message || err.message);
      });
    },

    showToast({ message, type }) {
      if (type === 'success') {
        this.showSuccess(message);
      } else if (type === 'error') {
        this.showError(message);
      }
    },

    showSuccess(message) {
      this.save_message = message;
      this.save_message_success = "success";
      this.save_message_snack = true;
    },

    showError(message) {
      this.save_message = message;
      this.save_message_success = "error";
      this.save_message_snack = true;
    },

    getWebhookUrl(webhookUuid) {
      let callbackBase = this.config_data.callback_api_base || '';
      if (!callbackBase) {
        callbackBase = "http(s)://<your-domain-or-ip>";
      }
      if (callbackBase) {
        return `${callbackBase.replace(/\/$/, '')}/api/v1/webhooks/platforms/${webhookUuid}`;
      }
      return `/api/v1/webhooks/platforms/${webhookUuid}`;
    },

    openWebhookDialog(webhookUuid) {
      this.currentWebhookUuid = webhookUuid;
      this.showWebhookDialog = true;
    },

    async copyWebhookUrl(webhookUuid) {
      const url = this.getWebhookUrl(webhookUuid);
      const ok = await copyToClipboard(url);
      if (ok) {
        this.showSuccess(this.tm('webhookCopied'));
      } else {
        this.showError(this.tm('webhookCopyFailed'));
      }
    }
  },
  computed: {
    // 安全访问翻译的计算属性
    messages() {
      return {
        updateSuccess: this.tm('messages.updateSuccess'),
        addSuccess: this.tm('messages.addSuccess'),
        deleteSuccess: this.tm('messages.deleteSuccess'),
        statusUpdateSuccess: this.tm('messages.statusUpdateSuccess'),
        deleteConfirm: this.tm('messages.deleteConfirm')
      };
    },
    currentWebhookUrl() {
      return this.getWebhookUrl(this.currentWebhookUuid);
    }
  }
}
</script>

<style scoped>
.platform-page {
  min-height: 100%;
  background:
    linear-gradient(180deg, rgba(var(--v-theme-primary), 0.08), transparent 280px),
    rgb(var(--v-theme-background));
}

.platform-shell {
  max-width: 1200px;
  padding: 24px;
}

.platform-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 20px;
  padding: 18px 2px 20px;
  border: 1px solid rgba(var(--v-theme-border), 0.7);
  border-width: 0 0 1px;
}

.platform-hero__copy {
  display: flex;
  align-items: center;
  gap: 18px;
  min-width: 0;
}

.platform-hero__title {
  margin: 0;
  color: rgb(var(--v-theme-primaryText));
  font-size: 1.65rem;
  font-weight: 730;
  line-height: 1.25;
  letter-spacing: 0;
}

.platform-hero__subtitle {
  margin: 6px 0 0;
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 0.9rem;
  line-height: 1.55;
}

.platform-hero__action {
  height: 46px;
  max-height: 46px;
  flex: 0 0 auto;
  padding: 0 18px;
  border-radius: 8px;
  box-shadow: 0 8px 18px rgba(var(--v-theme-primary), 0.18);
}

.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
}

.platform-card-shell {
  min-width: 0;
}

.platform-card-shell :deep(.v-card),
.platform-card-shell :deep(.item-card) {
  border-color: rgba(var(--v-theme-border), 0.7) !important;
  border-radius: 16px !important;
  background: rgba(var(--v-theme-surface), 0.96) !important;
  box-shadow: 0 18px 48px rgba(17, 24, 39, 0.08) !important;
}

.platform-card-shell :deep(.v-card-title),
.platform-card-shell :deep(.text-h3),
.platform-card-shell :deep(.text-h4) {
  letter-spacing: 0 !important;
}

.platform-card-shell :deep(.v-switch) {
  flex: 0 0 auto;
}

.platform-card-shell :deep(.v-switch .v-selection-control) {
  min-height: 34px;
}

.platform-card-shell :deep(.v-switch .v-selection-control__wrapper) {
  width: 54px;
  height: 32px;
}

.platform-card-shell :deep(.v-switch .v-switch__track) {
  width: 50px;
  height: 28px;
  border: 1px solid #d2e2ec;
  border-radius: 999px;
  background: #eef4f8;
  opacity: 1;
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.08);
  transition: background-color 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.platform-card-shell :deep(.v-switch .v-switch__thumb) {
  width: 22px;
  height: 22px;
  color: #ffffff;
  background: #ffffff;
  box-shadow: 0 4px 10px rgba(15, 23, 42, 0.2);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.platform-card-shell :deep(.v-switch .v-selection-control--dirty .v-switch__track) {
  border-color: #75b9de;
  background: linear-gradient(135deg, #80c5e8, #2f96cf);
  box-shadow: inset 0 1px 2px rgba(15, 74, 111, 0.18), 0 8px 18px rgba(47, 150, 207, 0.22);
}

.platform-card-shell :deep(.v-switch .v-selection-control--dirty .v-switch__thumb) {
  box-shadow: 0 4px 12px rgba(22, 107, 154, 0.28);
}

.platform-card-shell :deep(.v-switch:hover .v-switch__track) {
  border-color: #aad2e9;
}

.platform-card-shell :deep(.v-switch .v-selection-control--disabled) {
  opacity: 0.62;
}

.platform-empty-state {
  display: flex;
  min-height: 260px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.16);
  border-radius: 18px;
  background: rgba(var(--v-theme-surface), 0.84);
  color: rgba(var(--v-theme-on-surface), 0.62);
  box-shadow: 0 18px 48px rgba(17, 24, 39, 0.05);
}

.platform-empty-state p {
  margin: 0;
  font-size: 14px;
}

.webhook-info {
  margin-top: 4px;
}

.platform-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.platform-expiry-chip {
  max-width: 100%;
}

.platform-note {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  max-width: min(100%, 218px);
  min-height: 28px;
  margin-top: 8px;
  padding: 5px 12px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  border-radius: 999px;
  background: rgba(var(--v-theme-on-surface), 0.035);
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 12px;
  line-height: 1.3;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.62);
}

.platform-note__body {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.webhook-chip {
  cursor: pointer;
}

.platform-status-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.status-chip {
  font-size: 12px;
}

.error-chip {
  cursor: pointer;
  font-size: 12px;
}

.error-details {
  margin-top: 8px;
}

.error-message {
  word-break: break-word;
}

.traceback-box {
  background-color: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
}

.platform-qr-chip {
  margin-top: 4px;
}

.platform-qr-status {
  font-size: 13px;
  margin-bottom: 10px;
  color: rgba(0, 0, 0, 0.7);
}

@media (max-width: 760px) {
  .platform-shell {
    padding: 16px;
  }

  .platform-hero {
    align-items: stretch;
    flex-direction: column;
    min-height: auto;
    padding: 10px 0 16px;
  }

  .platform-hero__copy {
    align-items: flex-start;
  }

  .platform-hero__action {
    width: 100%;
  }

  .platform-grid {
    grid-template-columns: 1fr;
  }
}
</style>
