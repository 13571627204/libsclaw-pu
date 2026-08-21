<template>
  <div class="provider-page">
    <v-container fluid class="provider-shell">
      <section class="provider-hero">
        <div class="provider-hero__copy">
          <h1 class="provider-hero__title">
            {{ tm('title') }}
          </h1>
          <p class="provider-hero__subtitle">
            {{ tm('subtitle') }}
          </p>
        </div>
        <v-btn
          v-if="selectedProviderType !== 'chat_completion'"
          color="primary"
          prepend-icon="mdi-plus"
          variant="flat"
          class="provider-hero__action"
          @click="showAddProviderDialog = true"
        >
          {{ tm('providers.addProvider') }}
        </v-btn>
      </section>

      <section class="provider-content">
        <v-tabs
          v-if="showAllProviderTypes"
          v-model="selectedProviderType"
          bg-color="transparent"
          class="mb-4"
        >
          <v-tab
            v-for="type in visibleProviderTypes"
            :key="type.value"
            :value="type.value"
            class="font-weight-medium px-3"
          >
            <v-icon start>{{ type.icon }}</v-icon>
            {{ type.label }}
          </v-tab>
        </v-tabs>

        <div v-if="selectedProviderType === 'chat_completion'" class="provider-workbench">
          <div class="provider-workbench__sidebar">
            <ProviderSourcesPanel
              :displayed-provider-sources="displayedProviderSources"
              :selected-provider-source="selectedProviderSource"
              :available-source-types="availableSourceTypes"
              :tm="tm"
              :resolve-source-icon="resolveSourceIcon"
              :get-source-display-name="getSourceDisplayName"
              @add-provider-source="addProviderSource"
              @select-provider-source="selectProviderSource"
              @delete-provider-source="deleteProviderSource"
            />
          </div>

          <div class="provider-workbench__divider"></div>

          <div class="provider-workbench__main">
            <div v-if="selectedProviderSource" class="provider-config-shell">
              <div class="provider-config-header">
                <div class="provider-config-headline">
                  <div class="provider-config-title">{{ selectedProviderSource.id }}</div>
                  <div class="provider-config-subtitle">
                    {{ selectedProviderSource.api_base || 'N/A' }}
                  </div>
                </div>

                <div class="provider-config-actions">
                  <v-btn
                    color="primary"
                    prepend-icon="mdi-content-save-outline"
                    :loading="savingSource"
                    :disabled="!isSourceModified"
                    variant="flat"
                    class="provider-config-save"
                    @click="saveProviderSource"
                  >
                    {{ tm('providerSources.save') }}
                  </v-btn>
                </div>
              </div>

              <v-divider></v-divider>

              <div class="provider-config-body">
                <section class="provider-section">
                  <div class="provider-section-head">
                    <div class="provider-section-title">{{ tm('providers.settings') }}</div>
                  </div>
                  <AstrBotConfig
                    v-if="basicSourceConfig"
                    :iterable="basicSourceConfig"
                    :metadata="providerSourceSchema"
                    metadataKey="provider"
                    :is-editing="true"
                  />
                </section>

                <v-divider v-if="advancedSourceConfig"></v-divider>

                <section v-if="advancedSourceConfig" class="provider-section">
                  <div class="provider-section-head">
                    <div class="provider-section-title">{{ tm('providerSources.advancedConfig') }}</div>
                  </div>
                  <AstrBotConfig
                    :iterable="advancedSourceConfig"
                    :metadata="providerSourceSchema"
                    metadataKey="provider"
                    :is-editing="true"
                  />
                </section>

                <v-divider></v-divider>

                <section class="provider-section provider-section--models">
                  <ProviderModelsPanel
                    :entries="filteredMergedModelEntries"
                    :available-count="availableModels.length"
                    v-model:model-search="modelSearch"
                    :loading-models="loadingModels"
                    :is-source-modified="isSourceModified"
                    :supports-image-input="supportsImageInput"
                    :supports-audio-input="supportsAudioInput"
                    :supports-tool-call="supportsToolCall"
                    :supports-reasoning="supportsReasoning"
                    :format-context-limit="formatContextLimit"
                    :testing-providers="testingProviders"
                    :tm="tm"
                    @fetch-models="fetchAvailableModels"
                    @open-manual-model="openManualModelDialog"
                    @open-provider-edit="openProviderEdit"
                    @toggle-provider-enable="toggleProviderEnable"
                    @test-provider="testProvider"
                    @delete-provider="deleteProvider"
                    @add-model-provider="openModelAddDialog"
                  />
                </section>
              </div>
            </div>

            <div v-else class="provider-empty-state">
              <v-icon size="48" color="grey-lighten-1">mdi-cursor-default-click</v-icon>
              <p class="mt-2">{{ tm('providerSources.selectHint') }}</p>
            </div>
          </div>
        </div>

        <template v-else>
          <div v-if="filteredProviders.length === 0" class="provider-empty-state provider-empty-state--catalog">
            <v-icon size="46" color="primary">mdi-api-off</v-icon>
            <p>{{ getEmptyText() }}</p>
          </div>
          <div v-else class="provider-grid">
            <div v-for="(provider, index) in filteredProviders" :key="index" class="provider-card-shell">
              <item-card
                :item="provider"
                title-field="id"
                enabled-field="enable"
                :loading="isProviderTesting(provider.id)"
                :bglogo="getProviderIcon(provider.provider)"
                :show-copy-button="true"
                @toggle-enabled="toggleProviderEnable(provider, !provider.enable)"
                @delete="deleteProvider"
                @edit="configExistingProvider"
                @copy="copyProvider"
              >
                <template #item-details="{ item }">
                  <v-tooltip v-if="getProviderStatus(item.id)" location="top" max-width="300">
                    <template #activator="{ props }">
                      <v-chip v-bind="props" :color="getStatusColor(getProviderStatus(item.id).status)" size="small">
                        <v-icon start size="small">
                          {{
                            getProviderStatus(item.id).status === 'available'
                              ? 'mdi-check-circle'
                              : getProviderStatus(item.id).status === 'unavailable'
                                ? 'mdi-alert-circle'
                                : 'mdi-clock-outline'
                          }}
                        </v-icon>
                        {{ getStatusText(getProviderStatus(item.id).status) }}
                      </v-chip>
                    </template>
                    <span v-if="getProviderStatus(item.id).status === 'unavailable'">
                      {{ getProviderStatus(item.id).error }}
                    </span>
                    <span v-else>{{ getStatusText(getProviderStatus(item.id).status) }}</span>
                  </v-tooltip>
                </template>

                <template #actions="{ item }">
                  <v-btn
                    style="z-index: 100000;"
                    variant="tonal"
                    color="info"
                    size="small"
                    class="provider-card-action"
                    :loading="isProviderTesting(item.id)"
                    @click="testSingleProvider(item)"
                  >
                    {{ tm('availability.test') }}
                  </v-btn>
                </template>
              </item-card>
            </div>
          </div>
        </template>
      </section>
    </v-container>

    <AddNewProvider
      v-model:show="showAddProviderDialog"
      :metadata="configSchema"
      :current-provider-type="selectedProviderType"
      @select-template="selectProviderTemplate"
    />

    <v-dialog v-model="showManualModelDialog" max-width="400">
      <v-card>
        <v-card-title class="text-h3 pa-4 pb-0 pl-6">
          {{ tm('models.manualDialogTitle') }}
        </v-card-title>
        <v-card-text class="py-4">
          <v-text-field
            v-model="manualModelId"
            :label="tm('models.manualDialogModelLabel')"
            flat
            variant="solo-filled"
            autofocus
            clearable
          ></v-text-field>
          <v-text-field
            :model-value="manualProviderId"
            flat
            variant="solo-filled"
            :label="tm('models.manualDialogPreviewLabel')"
            persistent-hint
            :hint="tm('models.manualDialogPreviewHint')"
          ></v-text-field>
        </v-card-text>
        <v-card-actions class="pa-4">
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="showManualModelDialog = false">取消</v-btn>
          <v-btn color="primary" variant="tonal" @click="confirmManualModel">添加</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showProviderCfg" width="920" persistent>
      <v-card class="provider-modal">
        <v-card-title class="text-h3 pa-4 pb-0 pl-6 provider-modal__title">
          <span class="provider-modal__title-icon">
            <v-icon size="22">mdi-tune-variant</v-icon>
          </span>
          <span class="provider-modal__title-text">
            {{ updatingMode ? tm('dialogs.config.editTitle') : tm('dialogs.config.addTitle') + ` ${newSelectedProviderName} ` + tm('dialogs.config.provider') }}
          </span>
        </v-card-title>
        <v-card-text class="py-4 provider-modal__body">
          <AstrBotConfig
            :iterable="newSelectedProviderConfig"
            :metadata="configSchema"
            metadataKey="provider"
            :is-editing="updatingMode"
          />
        </v-card-text>

        <v-divider></v-divider>

        <v-card-actions class="pa-4 provider-modal__actions">
          <v-spacer></v-spacer>
          <v-btn class="provider-modal__cancel" variant="text" :disabled="loading" @click="showProviderCfg = false">
            {{ tm('dialogs.config.cancel') }}
          </v-btn>
          <v-btn class="provider-modal__save" color="primary" variant="tonal" :loading="loading" @click="newProvider">
            {{ tm('dialogs.config.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showProviderEditDialog" width="860">
      <v-card class="provider-modal provider-modal--model">
        <v-card-title class="text-h3 pa-4 pb-0 pl-6 provider-modal__title">
          <span class="provider-modal__title-icon">
            <v-icon size="22">mdi-cube-outline</v-icon>
          </span>
          <span class="provider-modal__title-text">{{ providerEditDialogTitle }}</span>
        </v-card-title>
        <v-card-text class="py-4 provider-modal__body">
          <AstrBotConfig
            v-if="providerEditData"
            :iterable="providerEditData"
            :metadata="providerModelConfigSchema"
            metadataKey="provider"
            :is-editing="true"
          />
        </v-card-text>
        <v-card-actions class="pa-4 provider-modal__actions">
          <v-spacer></v-spacer>
          <v-btn
            class="provider-modal__cancel"
            variant="text"
            :disabled="savingProviders.includes(providerEditData?.id)"
            @click="showProviderEditDialog = false"
          >
            {{ tm('dialogs.config.cancel') }}
          </v-btn>
          <v-btn
            class="provider-modal__save"
            color="primary"
            variant="tonal"
            :loading="savingProviders.includes(providerEditData?.id)"
            @click="saveEditedProvider"
          >
            {{ tm('dialogs.config.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000" location="top">
      {{ snackbar.message }}
    </v-snackbar>

    <v-dialog v-model="providerDeleteDialog.show" max-width="460" persistent>
      <v-card class="provider-delete-dialog">
        <v-card-title class="provider-delete-dialog__title">
          <span class="provider-delete-dialog__icon">
            <v-icon size="24">mdi-trash-can-outline</v-icon>
          </span>
          <span>删除模型</span>
        </v-card-title>
        <v-card-text class="provider-delete-dialog__body">
          <p class="provider-delete-dialog__message">{{ providerDeleteDialog.message }}</p>
          <div v-if="providerDeleteDialog.providerId" class="provider-delete-dialog__target">
            {{ providerDeleteDialog.providerId }}
          </div>
        </v-card-text>
        <v-card-actions class="provider-delete-dialog__actions">
          <v-spacer></v-spacer>
          <v-btn class="provider-delete-dialog__cancel" variant="text" @click="resolveProviderDelete(false)">
            取消
          </v-btn>
          <v-btn class="provider-delete-dialog__confirm" color="error" variant="tonal" @click="resolveProviderDelete(true)">
            确定删除
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showAgentRunnerDialog" max-width="520" persistent>
      <v-card>
        <v-card-title class="text-h3 pa-4 pb-0 pl-6 d-flex align-center">
          <v-icon start class="me-2">mdi-information</v-icon>
          请前往「配置文件」页测试 Agent 执行器
        </v-card-title>
        <v-card-text class="py-4 text-body-1 text-medium-emphasis">
          Agent 执行器的测试请在「配置文件」页进行。
          <ol class="ml-4 mt-4 mb-4">
            <li>找到对应的配置文件并打开。</li>
            <li>找到 Agent 执行方式部分，修改执行器后点击保存。</li>
            <li>点击右下角的 💬 聊天按钮进行测试。</li>
          </ol>
          要让机器人应用这个 Agent 执行器，你也需要前往修改 Agent 执行器。
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="grey" variant="text" @click="showAgentRunnerDialog = false">好的</v-btn>
          <v-btn color="primary" variant="tonal" @click="goToConfigPage">点击前往</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { providerApi } from '@/api/v1'
import { useModuleI18n } from '@/i18n/composables'
import AstrBotConfig from '@/components/shared/AstrBotConfig.vue'
import ItemCard from '@/components/shared/ItemCard.vue'
import AddNewProvider from '@/components/provider/AddNewProvider.vue'
import ProviderModelsPanel from '@/components/provider/ProviderModelsPanel.vue'
import ProviderSourcesPanel from '@/components/provider/ProviderSourcesPanel.vue'
import { useProviderModelConfigDialog } from '@/composables/useProviderModelConfigDialog'
import { useProviderSources } from '@/composables/useProviderSources'
import { getProviderIcon } from '@/utils/providerUtils'

const props = defineProps({
  defaultTab: {
    type: String,
    default: 'chat_completion'
  },
  showAllProviderTypes: {
    type: Boolean,
    default: false
  }
})

const { tm } = useModuleI18n('features/provider')
const router = useRouter()

const snackbar = ref({
  show: false,
  message: '',
  color: 'success'
})
const providerDeleteDialog = ref({
  show: false,
  message: '',
  providerId: '',
  resolve: null
})

function showMessage(message, color = 'success') {
  snackbar.value = { show: true, message, color }
}

function openProviderDeleteDialog(provider, message) {
  providerDeleteDialog.value = {
    show: true,
    message,
    providerId: provider?.id || '',
    resolve: null
  }

  return new Promise((resolve) => {
    providerDeleteDialog.value.resolve = resolve
  })
}

function resolveProviderDelete(confirmed) {
  const resolve = providerDeleteDialog.value.resolve
  providerDeleteDialog.value.show = false
  providerDeleteDialog.value.resolve = null
  if (resolve) resolve(confirmed)
}

const {
  providers,
  selectedProviderType,
  selectedProviderSource,
  availableModels,
  loadingModels,
  savingSource,
  testingProviders,
  isSourceModified,
  configSchema,
  providerSourceSchema,
  manualModelId,
  modelSearch,
  providerTypes,
  availableSourceTypes,
  displayedProviderSources,
  filteredMergedModelEntries,
  filteredProviders,
  basicSourceConfig,
  advancedSourceConfig,
  manualProviderId,
  resolveSourceIcon,
  getSourceDisplayName,
  supportsImageInput,
  supportsAudioInput,
  supportsToolCall,
  supportsReasoning,
  formatContextLimit,
  updateDefaultTab,
  selectProviderSource,
  addProviderSource,
  deleteProviderSource,
  saveProviderSource,
  fetchAvailableModels,
  buildModelProviderConfig,
  deleteProvider,
  modelAlreadyConfigured,
  testProvider,
  loadConfig
} = useProviderSources({
  defaultTab: props.showAllProviderTypes ? props.defaultTab : 'chat_completion',
  tm,
  showMessage,
  confirmDeleteProvider: openProviderDeleteDialog
})

const visibleProviderTypes = computed(() =>
  props.showAllProviderTypes
    ? providerTypes.value
    : providerTypes.value.filter((type) => type.value === 'chat_completion')
)

const showAddProviderDialog = ref(false)
const showProviderCfg = ref(false)
const newSelectedProviderName = ref('')
const newSelectedProviderConfig = ref({})
const newProviderOriginalId = ref('')
const updatingMode = ref(false)
const loading = ref(false)
const providerStatuses = ref([])
const showAgentRunnerDialog = ref(false)
const showManualModelDialog = ref(false)

const {
  showProviderEditDialog,
  providerEditData,
  savingProviders,
  providerModelConfigSchema,
  providerEditDialogTitle,
  openProviderEdit,
  openModelAddDialog,
  saveEditedProvider
} = useProviderModelConfigDialog({
  selectedProviderSource,
  configSchema,
  buildModelProviderConfig,
  modelAlreadyConfigured,
  loadConfig,
  tm,
  showMessage
})

function openManualModelDialog() {
  if (!selectedProviderSource.value) {
    showMessage(tm('providerSources.selectHint'), 'error')
    return
  }
  manualModelId.value = ''
  showManualModelDialog.value = true
}

async function confirmManualModel() {
  const modelId = manualModelId.value.trim()
  if (!selectedProviderSource.value) {
    showMessage(tm('providerSources.selectHint'), 'error')
    return
  }
  if (!modelId) {
    showMessage(tm('models.manualModelRequired'), 'error')
    return
  }
  if (modelAlreadyConfigured(modelId)) {
    showMessage(tm('models.manualModelExists'), 'error')
    return
  }
  showManualModelDialog.value = false
  openModelAddDialog(modelId)
}

watch(
  [() => props.defaultTab, () => props.showAllProviderTypes],
  ([defaultTab, showAllProviderTypes]) => {
    updateDefaultTab(showAllProviderTypes ? defaultTab : 'chat_completion')
  }
)

function getEmptyText() {
  return tm('providers.empty.typed', { type: selectedProviderType.value })
}

function selectProviderTemplate(name) {
  newSelectedProviderName.value = name
  newProviderOriginalId.value = ''
  showProviderCfg.value = true
  updatingMode.value = false
  newSelectedProviderConfig.value = JSON.parse(JSON.stringify(
    configSchema.value.provider.config_template[name] || {}
  ))
}

function configExistingProvider(provider) {
  newSelectedProviderName.value = provider.id
  newProviderOriginalId.value = provider.id
  newSelectedProviderConfig.value = {}

  let templates = configSchema.value.provider.config_template || {}
  let defaultConfig = {}
  for (let key in templates) {
    if (templates[key]?.type === provider.type) {
      defaultConfig = templates[key]
      break
    }
  }

  const mergeConfigWithOrder = (target, source, reference) => {
    if (source && typeof source === 'object' && !Array.isArray(source)) {
      for (let key in source) {
        if (source.hasOwnProperty(key)) {
          if (typeof source[key] === 'object' && source[key] !== null) {
            target[key] = Array.isArray(source[key]) ? [...source[key]] : { ...source[key] }
          } else {
            target[key] = source[key]
          }
        }
      }
    }

    for (let key in reference) {
      if (typeof reference[key] === 'object' && reference[key] !== null) {
        if (!(key in target)) {
          if (Array.isArray(reference[key])) {
            target[key] = [...reference[key]]
          } else {
            target[key] = {}
          }
        }
        if (!Array.isArray(reference[key])) {
          mergeConfigWithOrder(
            target[key],
            source && source[key] ? source[key] : {},
            reference[key]
          )
        }
      } else if (!(key in target)) {
        target[key] = reference[key]
      }
    }
  }

  if (defaultConfig) {
    mergeConfigWithOrder(newSelectedProviderConfig.value, provider, defaultConfig)
  }

  showProviderCfg.value = true
  updatingMode.value = true
}

async function newProvider() {
  loading.value = true
  const wasUpdating = updatingMode.value
  try {
    if (wasUpdating) {
      const res = await providerApi.update(
        newProviderOriginalId.value || newSelectedProviderName.value,
        newSelectedProviderConfig.value
      )
      if (res.data.status === 'error') {
        showMessage(res.data.message || '更新失败!', 'error')
        return
      }
      showMessage(res.data.message || '更新成功!')
      if (wasUpdating) {
        updatingMode.value = false
      }
    } else {
      const res = await providerApi.create(newSelectedProviderConfig.value)
      if (res.data.status === 'error') {
        showMessage(res.data.message || '添加失败!', 'error')
        return
      }
      showMessage(res.data.message || '添加成功!')
    }
    showProviderCfg.value = false
  } catch (err) {
    showMessage(err.response?.data?.message || err.message, 'error')
  } finally {
    loading.value = false
    await loadConfig()
  }
}

async function copyProvider(providerToCopy) {
  const newProviderConfig = JSON.parse(JSON.stringify(providerToCopy))

  const generateUniqueId = (baseId) => {
    let newId = `${baseId}_copy`
    let counter = 1
    const existingIds = providers.value.map(p => p.id)
    while (existingIds.includes(newId)) {
      newId = `${baseId}_copy_${counter}`
      counter++
    }
    return newId
  }
  newProviderConfig.id = generateUniqueId(providerToCopy.id)
  newProviderConfig.enable = false

  loading.value = true
  try {
    const res = await providerApi.create(newProviderConfig)
    showMessage(res.data.message || `成功复制并创建了 ${newProviderConfig.id}`)
    await loadConfig()
  } catch (err) {
    showMessage(err.response?.data?.message || err.message, 'error')
  } finally {
    loading.value = false
  }
}

async function toggleProviderEnable(provider, value) {
  provider.enable = value

  try {
    const res = await providerApi.setEnabled(provider.id, { enabled: value })

    if (res.data.status === 'error') {
      throw new Error(res.data.message)
    }
    showMessage(res.data.message || tm('messages.success.statusUpdate'))
  } catch (error) {
    showMessage(error.response?.data?.message || error.message || tm('providerSources.saveError'), 'error')
  } finally {
    await loadConfig()
  }
}

function isProviderTesting(providerId) {
  return testingProviders.value.includes(providerId)
}

function getProviderStatus(providerId) {
  return providerStatuses.value.find(s => s.id === providerId)
}

async function testSingleProvider(provider) {
  if (isProviderTesting(provider.id)) return

  testingProviders.value.push(provider.id)

  const statusIndex = providerStatuses.value.findIndex(s => s.id === provider.id)
  const pendingStatus = {
    id: provider.id,
    name: provider.id,
    status: 'pending',
    error: null
  }
  if (statusIndex !== -1) {
    providerStatuses.value.splice(statusIndex, 1, pendingStatus)
  } else {
    providerStatuses.value.unshift(pendingStatus)
  }

  try {
    if (!provider.enable) {
      throw new Error('该提供商未被用户启用')
    }
    if (provider.provider_type === 'agent_runner') {
      showAgentRunnerDialog.value = true
      providerStatuses.value = providerStatuses.value.filter(s => s.id !== provider.id)
      return
    }

    const startTime = performance.now()
    const res = await providerApi.test(provider.id)
    if (!res.data || res.data.status !== 'ok') {
      throw new Error(res.data?.message || `Failed to check status for ${provider.id}`)
    }

    const result = res.data.data
    if (!result) {
      throw new Error(`Failed to check status for ${provider.id}`)
    }

    const index = providerStatuses.value.findIndex(s => s.id === provider.id)
    if (index !== -1) {
      providerStatuses.value.splice(index, 1, result)
    }

    const isAvailable = result.status === 'available' && result.error == null
    if (!isAvailable) {
      throw new Error(result.error || tm('models.testError'))
    }

    const latency = Math.max(0, Math.round(performance.now() - startTime))
    showMessage(tm('models.testSuccessWithLatency', { id: provider.id, latency }))
  } catch (err) {
    const errorMessage = err.response?.data?.message || err.message || tm('models.testError')
    const index = providerStatuses.value.findIndex(s => s.id === provider.id)
    const failedStatus = {
      id: provider.id,
      name: provider.id,
      status: 'unavailable',
      error: errorMessage
    }
    if (index !== -1) {
      providerStatuses.value.splice(index, 1, failedStatus)
    }
    showMessage(errorMessage, 'error')
  } finally {
    const index = testingProviders.value.indexOf(provider.id)
    if (index > -1) {
      testingProviders.value.splice(index, 1)
    }
  }
}

function getStatusColor(status) {
  switch (status) {
    case 'available':
      return 'success'
    case 'unavailable':
      return 'error'
    case 'pending':
      return 'grey'
    default:
      return 'default'
  }
}

function getStatusText(status) {
  const messages = {
    available: tm('availability.available'),
    unavailable: tm('availability.unavailable'),
    pending: tm('availability.pending')
  }
  return messages[status] || status
}

function goToConfigPage() {
  router.push('/config')
  showAgentRunnerDialog.value = false
}
</script>

<style scoped>
.provider-page {
  --provider-surface: rgb(var(--v-theme-surface));
  --provider-border: rgba(var(--v-theme-border), 0.7);
  min-height: 100%;
  background:
    linear-gradient(180deg, rgba(var(--v-theme-primary), 0.08), transparent 280px),
    rgb(var(--v-theme-background));
}

.provider-shell {
  max-width: 1200px;
  padding: 24px;
}

.provider-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
  padding: 18px 2px 20px;
  border: 1px solid var(--provider-border);
  border-width: 0 0 1px;
}

.provider-hero__copy {
  min-width: 0;
}

.provider-hero__title {
  margin: 0;
  color: rgb(var(--v-theme-primaryText));
  font-size: 1.65rem;
  font-weight: 730;
  line-height: 1.25;
  letter-spacing: 0;
}

.provider-hero__subtitle {
  margin: 6px 0 0;
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 0.9rem;
  line-height: 1.55;
}

.provider-hero__action,
.provider-config-save {
  height: 46px;
  max-height: 46px;
  flex: 0 0 auto;
  padding: 0 18px;
  border-radius: 8px;
  box-shadow: 0 8px 18px rgba(var(--v-theme-primary), 0.18);
}

.provider-content :deep(.v-tabs) {
  min-height: 52px;
  border: 1px solid rgba(var(--v-theme-border), 0.7);
  border-radius: 12px;
  background: rgba(var(--v-theme-surface), 0.78);
  padding: 3px;
}

.provider-content :deep(.v-tab) {
  min-height: 38px;
  border-radius: 8px;
  letter-spacing: 0;
}

.provider-content :deep(.v-tab--selected) {
  background: rgba(var(--v-theme-primary), 0.1);
}

.provider-workbench {
  border: 1px solid var(--provider-border);
  border-radius: 18px;
  background: rgba(var(--v-theme-surface), 0.96);
  box-shadow: 0 18px 48px rgba(17, 24, 39, 0.08);
  display: grid;
  grid-template-columns: minmax(280px, 320px) 1px minmax(0, 1fr);
  height: clamp(560px, calc(100vh - 260px), 700px);
  min-height: 0;
  overflow: hidden;
}

.provider-workbench__sidebar,
.provider-workbench__main {
  min-width: 0;
  min-height: 0;
}

.provider-workbench__divider {
  background: rgba(var(--v-theme-border), 0.7);
}

.provider-workbench__main {
  display: flex;
  overflow: hidden;
}

.provider-config-shell {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.provider-config-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 18px 22px 16px;
  background: rgba(var(--v-theme-surface), 0.94);
}

.provider-config-headline {
  min-width: 0;
}

.provider-config-title {
  font-size: 20px;
  line-height: 1.1;
  font-weight: 680;
  letter-spacing: 0;
  overflow-wrap: anywhere;
}

.provider-config-subtitle {
  margin-top: 6px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 13px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.provider-config-actions {
  flex-shrink: 0;
}

.provider-config-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.provider-section {
  padding: 18px 22px;
}

.provider-section--models {
  padding-top: 16px;
}

.provider-section-head {
  margin-bottom: 10px;
}

.provider-section-title {
  font-size: 16px;
  font-weight: 650;
  line-height: 1.4;
  letter-spacing: 0;
}

.provider-empty-state {
  flex: 1;
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: rgba(var(--v-theme-on-surface), 0.56);
}

.provider-empty-state p {
  margin: 0;
  font-size: 14px;
}

.provider-empty-state--catalog {
  min-height: 260px;
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.16);
  border-radius: 18px;
  background: rgba(var(--v-theme-surface), 0.84);
  box-shadow: 0 18px 48px rgba(17, 24, 39, 0.05);
}

.provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
}

.provider-card-shell {
  min-width: 0;
}

.provider-card-shell :deep(.v-card),
.provider-card-shell :deep(.item-card) {
  border-color: rgba(var(--v-theme-border), 0.7) !important;
  border-radius: 16px !important;
  background: rgba(var(--v-theme-surface), 0.96) !important;
  box-shadow: 0 18px 48px rgba(17, 24, 39, 0.08) !important;
}

.provider-card-shell :deep(.v-card-title),
.provider-card-shell :deep(.text-h3),
.provider-card-shell :deep(.text-h4) {
  letter-spacing: 0 !important;
}

.provider-card-action {
  border-radius: 8px;
}

.provider-modal {
  max-height: min(86vh, 820px);
  border: 1px solid rgba(var(--v-theme-border), 0.78);
  border-radius: 18px !important;
  background:
    linear-gradient(180deg, rgba(var(--v-theme-primary), 0.055), transparent 160px),
    rgb(var(--v-theme-surface));
  box-shadow: 0 24px 68px rgba(15, 23, 42, 0.18) !important;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.provider-modal__title {
  min-height: 76px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 22px 28px 18px !important;
  color: rgb(var(--v-theme-primaryText));
  font-size: 1.35rem !important;
  font-weight: 740;
  letter-spacing: 0;
  line-height: 1.25;
}

.provider-modal__title-icon {
  width: 42px;
  height: 42px;
  border: 1px solid rgba(var(--v-theme-primary), 0.16);
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.1);
}

.provider-modal__title-text {
  min-width: 0;
  overflow-wrap: anywhere;
}

.provider-modal__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px 28px 18px !important;
}

.provider-modal__actions {
  padding: 14px 28px 20px !important;
  gap: 10px;
  background: rgba(var(--v-theme-surface), 0.94);
}

.provider-modal__cancel,
.provider-modal__save {
  min-width: 92px;
  height: 42px;
  max-height: 42px;
  border-radius: 8px;
  font-weight: 650;
  letter-spacing: 0;
}

.provider-modal__cancel {
  color: rgba(var(--v-theme-on-surface), 0.72);
}

.provider-modal__cancel:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.provider-modal__save {
  border: 1px solid rgba(var(--v-theme-primary), 0.16);
  box-shadow: 0 8px 18px rgba(var(--v-theme-primary), 0.12);
}

.provider-modal :deep(.config-section) {
  display: none;
}

.provider-modal :deep(.v-card-text.px-0.py-1) {
  padding: 0 !important;
}

.provider-modal :deep(.object-config) {
  border: 1px solid rgba(var(--v-theme-border), 0.72);
  border-radius: 14px;
  background: rgba(var(--v-theme-surface), 0.94);
  overflow: hidden;
}

.provider-modal :deep(.config-row) {
  min-height: 60px;
  padding: 10px 16px;
  border-radius: 0;
  align-items: center;
  transition: background-color 0.16s ease;
}

.provider-modal :deep(.config-row:hover) {
  background: rgba(var(--v-theme-primary), 0.035);
}

.provider-modal :deep(.property-info) {
  padding-right: 18px;
}

.provider-modal :deep(.property-info .v-list-item) {
  padding-inline: 0;
  min-height: auto;
}

.provider-modal :deep(.property-name) {
  color: rgb(var(--v-theme-primaryText));
  font-size: 14px;
  font-weight: 700;
  line-height: 1.35;
}

.provider-modal :deep(.property-hint) {
  margin-top: 5px;
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 12px;
  line-height: 1.45;
  white-space: normal;
}

.provider-modal :deep(.config-input) {
  padding: 6px 0 6px 12px;
}

.provider-modal :deep(.config-divider) {
  margin: 0 16px;
  border-color: rgba(var(--v-theme-border), 0.62);
}

.provider-modal :deep(.v-field) {
  border-radius: 9px;
  background: rgb(var(--v-theme-surface));
}

.provider-modal :deep(.v-field__outline) {
  color: rgba(var(--v-theme-on-surface), 0.2);
}

.provider-modal :deep(.v-field--focused .v-field__outline) {
  color: rgba(var(--v-theme-primary), 0.62);
}

.provider-modal :deep(.v-field__input) {
  min-height: 40px;
  padding-top: 8px;
  padding-bottom: 8px;
  font-size: 14px;
}

.provider-modal :deep(.v-switch .v-selection-control) {
  min-height: 38px;
}

.provider-modal :deep(.v-switch .v-switch__track) {
  opacity: 1;
  background: rgba(var(--v-theme-on-surface), 0.18);
}

.provider-modal :deep(.v-switch .v-selection-control--dirty .v-switch__track) {
  background: rgba(var(--v-theme-primary), 0.55);
}

.provider-modal :deep(.config-input .d-flex.align-center.gap-2) {
  gap: 10px;
}

.provider-modal :deep(.config-input .d-flex.align-center.gap-2 .v-btn) {
  height: 38px;
  min-width: 86px;
  border-radius: 8px;
  margin-left: 0 !important;
  font-weight: 650;
  letter-spacing: 0;
}

.provider-modal--model {
  max-height: min(82vh, 720px);
}

.provider-delete-dialog {
  border: 1px solid rgba(var(--v-theme-error), 0.18);
  border-radius: 18px !important;
  background:
    linear-gradient(180deg, rgba(var(--v-theme-error), 0.055), transparent 150px),
    rgb(var(--v-theme-surface));
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.22) !important;
  overflow: hidden;
}

.provider-delete-dialog__title {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 24px 26px 12px !important;
  color: rgb(var(--v-theme-primaryText));
  font-size: 1.22rem;
  font-weight: 740;
  line-height: 1.3;
  letter-spacing: 0;
}

.provider-delete-dialog__icon {
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

.provider-delete-dialog__body {
  padding: 10px 26px 18px !important;
}

.provider-delete-dialog__message {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), 0.76);
  font-size: 15px;
  line-height: 1.65;
}

.provider-delete-dialog__target {
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

.provider-delete-dialog__actions {
  padding: 2px 26px 24px !important;
  gap: 10px;
}

.provider-delete-dialog__cancel,
.provider-delete-dialog__confirm {
  min-width: 92px;
  height: 42px;
  max-height: 42px;
  border-radius: 8px;
  font-weight: 650;
  letter-spacing: 0;
}

.provider-delete-dialog__cancel {
  color: rgba(var(--v-theme-on-surface), 0.72);
}

.provider-delete-dialog__cancel:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.provider-delete-dialog__confirm {
  border: 1px solid rgba(var(--v-theme-error), 0.18);
}

@media (max-width: 960px) {
  .provider-shell {
    padding: 16px;
  }

  .provider-hero {
    align-items: stretch;
    flex-direction: column;
    min-height: auto;
    padding: 10px 0 16px;
  }

  .provider-hero__action {
    width: 100%;
  }

  .provider-workbench {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1px auto;
    min-height: auto;
  }

  .provider-workbench__divider {
    height: 1px;
  }

  .provider-config-header {
    flex-direction: column;
    align-items: stretch;
    padding: 16px;
  }

  .provider-config-actions :deep(.v-btn) {
    width: 100%;
  }

  .provider-section {
    padding: 16px;
  }
}

@media (max-width: 600px) {
  .provider-shell {
    padding: 8px;
  }

  .provider-content :deep(.v-tabs) {
    overflow-x: auto;
  }

  .provider-workbench {
    border-radius: 16px;
    overflow: visible;
  }

  .provider-workbench__main {
    overflow: visible;
  }

  .provider-config-body {
    overflow-y: visible;
  }

  .provider-config-title {
    font-size: 18px;
  }

  .provider-empty-state {
    min-height: 260px;
    padding: 24px;
  }

  .provider-grid {
    grid-template-columns: 1fr;
  }

  .provider-modal {
    max-height: 92vh;
    border-radius: 16px !important;
  }

  .provider-modal__title {
    min-height: auto;
    padding: 18px 18px 14px !important;
    font-size: 1.2rem !important;
  }

  .provider-modal__body {
    padding: 6px 18px 14px !important;
  }

  .provider-modal :deep(.config-row) {
    padding: 12px 14px;
  }

  .provider-modal :deep(.config-input) {
    padding: 8px 0 2px;
  }

  .provider-modal__actions {
    padding: 12px 18px 18px !important;
  }
}
</style>
