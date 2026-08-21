<template>
  <div class="welcome-page">
    <v-container fluid class="welcome-shell">
      <section class="welcome-hero">
        <div class="welcome-hero__content">
          <div class="welcome-brand">
            <span class="welcome-brand__mark">
              <img src="@/assets/images/icon-no-shadow.svg" alt="LibsClaw Logo">
            </span>
            <span class="welcome-brand__name">LibsClaw</span>
          </div>
          <h1 class="welcome-title">
            {{ greetingText }} <span aria-hidden="true">{{ greetingEmoji }}</span>
          </h1>
        </div>

      </section>

      <section class="setup-grid" :aria-label="tm('onboard.title')">
        <v-card
          class="setup-step"
          :class="{ 'setup-step--completed': providerStepState === 'completed' }"
          elevation="0"
          border
        >
          <div class="setup-step__header">
            <div class="setup-step__index">01</div>
          </div>
          <div class="setup-step__body">
            <div class="setup-step__icon">
              <v-icon icon="mdi-brain" size="24" />
            </div>
            <h2>{{ tm('onboard.step1Title') }}</h2>
            <p>{{ tm('onboard.step1Desc') }}</p>
          </div>
          <v-btn color="primary" variant="flat" block class="setup-step__action" @click="openProviderDialog">
            {{ tm('onboard.configure') }}
          </v-btn>
        </v-card>

        <v-card
          class="setup-step"
          :class="{ 'setup-step--completed': platformStepState === 'completed' }"
          elevation="0"
          border
        >
          <div class="setup-step__header">
            <div class="setup-step__index">02</div>
          </div>
          <div class="setup-step__body">
            <div class="setup-step__icon setup-step__icon--platform">
              <v-icon icon="mdi-forum-outline" size="24" />
            </div>
            <h2>{{ tm('onboard.step2Title') }}</h2>
          </div>
          <v-btn
            color="primary"
            variant="flat"
            block
            class="setup-step__action"
            :loading="loadingPlatformDialog"
            @click="openPlatformDialog"
          >
            {{ tm('onboard.configure') }}
          </v-btn>
        </v-card>

        <v-card
          class="setup-step"
          :class="{ 'setup-step--completed': computerAccessStepState === 'completed' }"
          elevation="0"
          border
        >
          <div class="setup-step__header">
            <div class="setup-step__index">03</div>
            <v-btn
              icon="mdi-help-circle-outline"
              variant="text"
              density="comfortable"
              size="small"
              @click="showComputerAccessHelpDialog = true"
            />
          </div>
          <div class="setup-step__body">
            <div class="setup-step__icon setup-step__icon--access">
              <v-icon icon="mdi-laptop-account" size="24" />
            </div>
            <h2>{{ tm('onboard.step3Title') }}</h2>
            <p>{{ tm('onboard.step3Desc') }}</p>
          </div>
          <v-select
            v-model="computerAccessRuntime"
            :items="computerAccessOptions"
            item-title="title"
            item-value="value"
            :label="tm('onboard.step3SelectLabel')"
            :loading="savingComputerAccess"
            :disabled="savingComputerAccess"
            hide-details
            density="comfortable"
            variant="outlined"
            class="computer-access-select"
          />
        </v-card>
      </section>

      <section v-if="showAnnouncement" class="announcement-section">
        <v-card class="welcome-card pa-6" elevation="0" border>
          <div class="mb-4 text-h3 font-weight-bold">
            {{ tm('announcement.title') }}
          </div>
          <MarkdownRender
            :content="welcomeAnnouncement"
            :typewriter="false"
            class="welcome-announcement-markdown markdown-content"
          />
        </v-card>
      </section>
    </v-container>

    <AddNewPlatform v-model:show="showAddPlatformDialog" :metadata="platformMetadata" :config_data="platformConfigData"
      @refresh-config="loadPlatformConfigBase" />
    <ProviderConfigDialog v-model="showProviderDialog" />
    <v-dialog v-model="showComputerAccessHelpDialog" max-width="680">
      <v-card class="computer-access-help-card" elevation="0">
        <v-card-title class="computer-access-help-title">
          <span class="computer-access-help-title__icon">
            <v-icon icon="mdi-laptop-account" size="22" />
          </span>
          <span>{{ tm('onboard.step3HelpTitle') }}</span>
        </v-card-title>
        <v-card-text class="computer-access-help-body">
          <ol class="computer-access-help-list">
            <li>{{ tm('onboard.step3HelpItem1') }}</li>
            <li>{{ tm('onboard.step3HelpItem2') }}</li>
            <li>{{ tm('onboard.step3HelpItem3') }}</li>
          </ol>
        </v-card-text>
        <v-card-actions class="computer-access-help-actions">
          <v-spacer />
          <v-btn
            color="primary"
            variant="tonal"
            class="computer-access-help-close"
            @click="showComputerAccessHelpDialog = false"
          >
            {{ tm('onboard.step3HelpClose') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue';
import axios from 'axios';
import AddNewPlatform from '@/components/platform/AddNewPlatform.vue';
import ProviderConfigDialog from '@/components/chat/ProviderConfigDialog.vue';
import { configProfileApi, providerApi, systemConfigApi } from '@/api/v1';
import { useI18n, useModuleI18n } from '@/i18n/composables';
import { useToast } from '@/utils/toast';
import { MarkdownRender } from 'markstream-vue';
import 'markstream-vue/index.css';

type StepState = 'pending' | 'completed' | 'skipped';
type ComputerAccessRuntime = 'local' | 'none';

const { tm } = useModuleI18n('features/welcome');
const { locale } = useI18n();
const { success: showSuccess, error: showError } = useToast();

const showAddPlatformDialog = ref(false);
const showProviderDialog = ref(false);
const showComputerAccessHelpDialog = ref(false);
const loadingPlatformDialog = ref(false);

const platformMetadata = ref<Record<string, any>>({});
const platformConfigData = ref<Record<string, any>>({});
const platformCountBeforeOpen = ref(0);
const providerCountBeforeOpen = ref(0);

const platformStepState = ref<StepState>('pending');
const providerStepState = ref<StepState>('pending');
const computerAccessStepState = ref<StepState>('pending');
const computerAccessRuntime = ref<ComputerAccessRuntime>('none');
const savedComputerAccessRuntime = ref<ComputerAccessRuntime>('none');
const savingComputerAccess = ref(false);
const welcomeAnnouncementRaw = ref<unknown>(null);

function resolveWelcomeAnnouncement(raw: unknown, currentLocale: string) {
  if (typeof raw === 'string') {
    return raw.trim();
  }

  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return '';
  }

  const localeMap = raw as Record<string, unknown>;
  const normalized = currentLocale.replace('-', '_');
  const preferredKeys =
    normalized.startsWith('zh')
      ? [normalized, 'zh_CN', 'zh-CN', 'zh', 'en_US', 'en-US', 'en']
      : [normalized, 'en_US', 'en-US', 'en', 'zh_CN', 'zh-CN', 'zh'];

  for (const key of preferredKeys) {
    const value = localeMap[key];
    if (typeof value === 'string' && value.trim().length > 0) {
      return value.trim();
    }
  }

  return '';
}

const welcomeAnnouncement = computed(() =>
  resolveWelcomeAnnouncement(welcomeAnnouncementRaw.value, locale.value)
);
const showAnnouncement = computed(() => welcomeAnnouncement.value.length > 0);

const springFestivalDates: Record<number, string> = {
  2025: '01-29',
  2026: '02-17',
  2027: '02-06',
  2028: '01-26',
  2029: '02-13',
  2030: '02-03'
}

function isSpringFestival() {
  const now = new Date();
  const year = now.getFullYear();
  const dateStr = springFestivalDates[year];

  if (!dateStr) return false;

  const [month, day] = dateStr.split('-').map(Number);
  const festivalDate = new Date(year, month - 1, day);

  const start = new Date(festivalDate);
  start.setDate(festivalDate.getDate() - 5);

  const end = new Date(festivalDate);
  end.setDate(festivalDate.getDate() + 5);

  // start of day for comparison
  const nowTime = now.setHours(0, 0, 0, 0);
  const startTime = start.setHours(0, 0, 0, 0);
  const endTime = end.setHours(0, 0, 0, 0);

  return nowTime >= startTime && nowTime <= endTime;
}

function isExactSpringFestivalDay() {
  const now = new Date();
  const year = now.getFullYear();
  const dateStr = springFestivalDates[year];

  if (!dateStr) return false;

  const [month, day] = dateStr.split('-').map(Number);
  const festivalDate = new Date(year, month - 1, day);

  const nowTime = new Date(now).setHours(0, 0, 0, 0);
  const festivalTime = festivalDate.setHours(0, 0, 0, 0);

  return nowTime === festivalTime;
}

const greetingEmoji = computed(() => {
  if (isExactSpringFestivalDay()) {
    return '🧨';
  }
  const hour = new Date().getHours();
  if (hour >= 0 && hour < 5) {
    return '😴';
  }
  return '😊';
});

const greetingText = computed(() => {
  if (isSpringFestival()) {
    return tm('greeting.newYear');
  }
  const hour = new Date().getHours();
  if (hour < 12) return tm('greeting.morning');
  if (hour < 18) return tm('greeting.afternoon');
  return tm('greeting.evening');
});

async function loadPlatformConfigBase() {
  const res = await systemConfigApi.runtime();
  const payload = (res.data.data || {}) as any;
  platformMetadata.value = payload.metadata || {};
  platformConfigData.value = payload.config || {};
}

async function fetchDefaultConfig() {
  const res = await configProfileApi.get('default');
  return (res.data?.data as any)?.config || {};
}

function getChatProvidersFromTemplatePayload(payload: any) {
  const providers = payload?.providers || [];
  const sources = payload?.provider_sources || [];
  const sourceMap = new Map();
  sources.forEach((s: any) => sourceMap.set(s.id, s.provider_type));

  return providers.filter((provider: any) => {
    if (provider.provider_type) {
      return provider.provider_type === 'chat_completion';
    }
    if (provider.provider_source_id) {
      const type = sourceMap.get(provider.provider_source_id);
      if (type === 'chat_completion') return true;
    }
    return String(provider.type || '').includes('chat_completion');
  });
}

async function fetchChatProviders() {
  const response = await providerApi.schema();
  if (response.data.status !== 'ok') {
    throw new Error(response.data.message || tm('onboard.providerLoadFailed'));
  }
  return getChatProvidersFromTemplatePayload(response.data.data);
}

function pickDefaultProviderId(providers: any[]) {
  if (!providers.length) return '';
  const enabledProvider = providers.find((provider) => provider.enable !== false);
  return (enabledProvider || providers[0]).id || '';
}

async function syncDefaultConfigProviderIfNeeded() {
  const providers = await fetchChatProviders();
  if (!providers.length) return;

  const targetProviderId = pickDefaultProviderId(providers);
  if (!targetProviderId) return;

  const configData = await fetchDefaultConfig();
  if (!configData.provider_settings) {
    configData.provider_settings = {};
  }

  if (configData.provider_settings.default_provider_id === targetProviderId) return;

  configData.provider_settings.default_provider_id = targetProviderId;

  const updateRes = await configProfileApi.update('default', configData);
  if (updateRes.data.status !== 'ok') {
    throw new Error(updateRes.data.message || tm('onboard.providerUpdateFailed'));
  }

  showSuccess(tm('onboard.providerDefaultUpdated', { id: targetProviderId }));
}

function normalizeComputerAccessRuntime(runtime: unknown): ComputerAccessRuntime {
  return runtime === 'local' || runtime === 'sandbox' ? 'local' : 'none';
}

function syncComputerAccessRuntime(configData: any) {
  const providerSettings = configData?.provider_settings || {};
  const currentRuntime = providerSettings?.computer_use_runtime;
  const normalizedRuntime = normalizeComputerAccessRuntime(currentRuntime);

  computerAccessRuntime.value = normalizedRuntime;
  savedComputerAccessRuntime.value = normalizedRuntime;
  computerAccessStepState.value =
    currentRuntime === 'local' || currentRuntime === 'none' || currentRuntime === 'sandbox'
      ? 'completed'
      : 'pending';
}

const computerAccessOptions = computed(() => [
  { title: tm('onboard.step3Allow'), value: 'local' },
  { title: tm('onboard.step3Deny'), value: 'none' }
]);

async function saveComputerAccessRuntime() {
  savingComputerAccess.value = true;
  try {
    const configData = await fetchDefaultConfig();
    if (!configData.provider_settings) {
      configData.provider_settings = {};
    }

    configData.provider_settings.computer_use_runtime = computerAccessRuntime.value;

    const updateRes = await configProfileApi.update('default', configData);
    if (updateRes.data.status !== 'ok') {
      throw new Error(updateRes.data.message || tm('onboard.computerAccessUpdateFailed'));
    }

    savedComputerAccessRuntime.value = computerAccessRuntime.value;
    computerAccessStepState.value = 'completed';
    showSuccess(
      tm(
        computerAccessRuntime.value === 'local'
          ? 'onboard.computerAccessAllowed'
          : 'onboard.computerAccessDenied'
      )
    );
  } catch (err: any) {
    showError(err?.response?.data?.message || err?.message || tm('onboard.computerAccessUpdateFailed'));
  } finally {
    savingComputerAccess.value = false;
  }
}

async function loadWelcomeAnnouncement() {
  // 云端公告已在此发行版中禁用，不请求外部服务。
  welcomeAnnouncementRaw.value = null;
}

onMounted(async () => {
  await loadWelcomeAnnouncement();

  try {
    await loadPlatformConfigBase();
    if ((platformConfigData.value.platform || []).length > 0) {
      platformStepState.value = 'completed';
    }
  } catch (e) {
    console.error(e);
  }

  try {
    const providers = await fetchChatProviders();
    if (providers.length > 0) {
      providerStepState.value = 'completed';
    }
  } catch (e) {
    console.error(e);
  }

  try {
    const defaultConfig = await fetchDefaultConfig();
    syncComputerAccessRuntime(defaultConfig);
  } catch (e) {
    console.error(e);
  }
});

async function openPlatformDialog() {
  loadingPlatformDialog.value = true;
  try {
    await loadPlatformConfigBase();
    platformCountBeforeOpen.value = (platformConfigData.value.platform || []).length;
    showAddPlatformDialog.value = true;
  } catch (err: any) {
    showError(err?.response?.data?.message || err?.message || tm('onboard.platformLoadFailed'));
  } finally {
    loadingPlatformDialog.value = false;
  }
}

async function openProviderDialog() {
  try {
    const providers = await fetchChatProviders();
    providerCountBeforeOpen.value = providers.length;
    showProviderDialog.value = true;
  } catch (err: any) {
    showError(err?.response?.data?.message || err?.message || tm('onboard.providerLoadFailed'));
  }
}

watch(showAddPlatformDialog, async (visible, wasVisible) => {
  if (!wasVisible || visible) return;
  try {
    await loadPlatformConfigBase();
    const newCount = (platformConfigData.value.platform || []).length;
    if (newCount > platformCountBeforeOpen.value) {
      platformStepState.value = 'completed';
    }
  } catch (err: any) {
    showError(err?.response?.data?.message || err?.message || tm('onboard.platformLoadFailed'));
  }
});

watch(showProviderDialog, async (visible, wasVisible) => {
  if (!wasVisible || visible) return;
  try {
    const providers = await fetchChatProviders();
    if (providers.length > providerCountBeforeOpen.value) {
      providerStepState.value = 'completed';
      await syncDefaultConfigProviderIfNeeded();
    }
  } catch (err: any) {
    showError(err?.response?.data?.message || err?.message || tm('onboard.providerUpdateFailed'));
  }
});

watch(computerAccessRuntime, async (value, oldValue) => {
  if (value === oldValue) return;
  if (value === savedComputerAccessRuntime.value) return;
  if (savingComputerAccess.value) return;

  try {
    await saveComputerAccessRuntime();
  } catch {
    computerAccessRuntime.value = savedComputerAccessRuntime.value;
  }
});
</script>

<style scoped>
.welcome-page {
  min-height: 100%;
  background:
    linear-gradient(180deg, rgba(var(--v-theme-primary), 0.08), transparent 280px),
    rgb(var(--v-theme-background));
}

.welcome-shell {
  max-width: 1200px;
  padding: 24px;
}

.welcome-hero {
  margin-bottom: 24px;
}

.welcome-hero__content,
.setup-step,
.welcome-card {
  border: 1px solid rgba(var(--v-theme-border), 0.7);
  box-shadow: 0 18px 48px rgba(17, 24, 39, 0.08);
}

.welcome-hero__content {
  position: relative;
  overflow: hidden;
  min-height: 260px;
  padding: 32px;
  border-radius: 18px;
  background:
    radial-gradient(circle at 88% 18%, rgba(var(--v-theme-info), 0.16), transparent 32%),
    linear-gradient(135deg, rgba(var(--v-theme-surface), 0.98), rgba(var(--v-theme-lightprimary), 0.8));
}

.welcome-brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 32px;
}

.welcome-brand__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 10px 28px rgba(17, 24, 39, 0.14);
}

.welcome-brand__mark img {
  width: 32px;
  height: 32px;
}

.welcome-brand__name {
  color: rgb(var(--v-theme-primaryText));
  font-size: 0.875rem;
  font-weight: 700;
  letter-spacing: 0;
}

.welcome-title {
  max-width: 760px;
  margin: 0;
  color: rgb(var(--v-theme-primaryText));
  font-size: clamp(2rem, 4vw, 3.4rem);
  font-weight: 760;
  line-height: 1.08;
  letter-spacing: 0;
  text-wrap: pretty;
}

.welcome-subtitle {
  max-width: 560px;
  margin: 18px 0 0;
  color: rgba(var(--v-theme-on-surface), 0.72);
  font-size: 1rem;
  line-height: 1.8;
  text-wrap: pretty;
}

.setup-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  margin-bottom: 24px;
}

.setup-step {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 320px;
  padding: 22px;
  border-radius: 16px;
  background: rgba(var(--v-theme-surface), 0.96);
}

.setup-step--completed {
  border-color: rgba(var(--v-theme-success), 0.36);
}

.setup-step__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 32px;
}

.setup-step__index {
  color: rgba(var(--v-theme-on-surface), 0.34);
  font-size: 0.86rem;
  font-weight: 800;
  line-height: 1;
}

.setup-step__body {
  flex: 1;
  margin: 24px 0 22px;
}

.setup-step__action {
  height: 46px;
  max-height: 46px;
}

.setup-step__action :deep(.v-btn__content) {
  line-height: 1;
}

.computer-access-select :deep(.v-field) {
  min-height: 56px;
}

.computer-access-select :deep(.v-field__input) {
  min-height: 56px;
  padding-top: 18px;
  padding-bottom: 6px;
}

.setup-step__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  margin-bottom: 18px;
  border-radius: 15px;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.12);
}

.setup-step__icon--platform {
  color: #8d4f2b;
  background: rgba(159, 95, 58, 0.14);
}

.setup-step__icon--access {
  color: #0f766e;
  background: rgba(15, 118, 110, 0.13);
}

.setup-step h2 {
  margin: 0;
  color: rgb(var(--v-theme-primaryText));
  font-size: 1.1rem;
  font-weight: 720;
  line-height: 1.35;
  letter-spacing: 0;
  text-wrap: pretty;
}

.setup-step p {
  margin: 10px 0 0;
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 0.875rem;
  line-height: 1.65;
  text-wrap: pretty;
}

.announcement-section {
  margin-bottom: 24px;
}

.welcome-card {
  border-radius: 16px;
  background: rgba(var(--v-theme-surface), 0.96);
}

.welcome-announcement-markdown {
  line-height: 1.7;
}

.computer-access-select {
  height: 56px;
  width: 100%;
  min-width: 0;
}

.computer-access-help-card {
  overflow: hidden;
  border: 1px solid #cfe5f4;
  border-radius: 20px;
  background: #f7fbfe;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.18);
}

.computer-access-help-title {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 24px 28px 16px;
  color: rgb(var(--v-theme-primaryText));
  font-size: 1.28rem;
  font-weight: 760;
  line-height: 1.3;
  letter-spacing: 0;
}

.computer-access-help-title__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  border: 1px solid #bfe0f4;
  border-radius: 14px;
  color: rgb(var(--v-theme-primary));
  background: #e5f4fd;
}

.computer-access-help-body {
  padding: 0 28px 6px;
}

.computer-access-help-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  counter-reset: access-help;
  list-style: none;
}

.computer-access-help-list li {
  position: relative;
  min-height: 52px;
  padding: 14px 16px 14px 54px;
  border: 1px solid #d9e5ec;
  border-radius: 14px;
  color: rgba(var(--v-theme-on-surface), 0.82);
  background: #ffffff;
  font-size: 0.94rem;
  line-height: 1.65;
}

.computer-access-help-list li::before {
  position: absolute;
  top: 14px;
  left: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 9px;
  color: rgb(var(--v-theme-primary));
  background: #e6f5fc;
  font-size: 0.78rem;
  font-weight: 800;
  content: counter(access-help, decimal-leading-zero);
  counter-increment: access-help;
}

.computer-access-help-actions {
  padding: 14px 28px 24px;
}

.computer-access-help-close {
  min-width: 86px;
  height: 42px;
  border: 1px solid #bfe0f4;
  border-radius: 12px;
  background: #e6f3fc;
  color: #1574a9;
  font-weight: 700;
}

.computer-access-help-close :deep(.v-btn__overlay) {
  display: none;
}

@media (max-width: 1100px) {
  .setup-grid {
    grid-template-columns: 1fr;
  }

  .welcome-hero__content,
  .setup-step {
    min-height: auto;
  }
}

@media (max-width: 600px) {
  .welcome-shell {
    padding: 16px;
  }

  .welcome-hero {
    margin-bottom: 16px;
  }

  .welcome-hero__content,
  .setup-step {
    padding: 20px;
    border-radius: 14px;
  }

  .welcome-title {
    font-size: 2rem;
  }
}
</style>
