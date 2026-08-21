<template>
  <div>
    <!-- 顶部操作区域 -->
    <div class="d-flex align-center justify-space-between mb-2">
      <div class="flex-grow-1">
        <span v-if="!modelValue || modelValue.length === 0" style="color: rgb(var(--v-theme-primaryText));">
          {{ tm('pluginSetSelector.notSelected') }}
        </span>
        <span v-else-if="isAllPlugins" style="color: rgb(var(--v-theme-primaryText));">
          {{ tm('pluginSetSelector.allPlugins') }}
        </span>
        <span v-else style="color: rgb(var(--v-theme-primaryText));">
          {{ tm('pluginSetSelector.selectedCount', { count: modelValue.length }) }}
        </span>
      </div>
      <v-btn class="plugin-set-open-btn" size="small" color="primary" variant="tonal" @click="openDialog">
        {{ buttonText || tm('pluginSetSelector.buttonText') }}
      </v-btn>
    </div>
  </div>

  <!-- Plugin Set Selection Dialog -->
  <v-dialog v-model="dialog" max-width="700px">
    <v-card class="plugin-set-dialog-card">
      <v-card-title class="text-h3 pa-4 pb-0 pl-6 plugin-set-dialog-title">
        <span class="plugin-set-dialog-title__icon">
          <v-icon size="18">mdi-puzzle-outline</v-icon>
        </span>
        <span>{{ tm('pluginSetSelector.dialogTitle') }}</span>
      </v-card-title>
      
      <v-card-text class="plugin-set-dialog-body pa-4">
        <v-progress-linear v-if="loading" indeterminate color="primary"></v-progress-linear>
        
        <div v-if="!loading">
          <!-- 预设选项 -->
          <v-radio-group v-model="selectionMode" class="plugin-set-mode-list mb-4" hide-details>
            <v-radio 
              class="plugin-set-mode-radio"
              value="all" 
              :label="tm('pluginSetSelector.enableAll')" 
              color="primary"
            ></v-radio>
            <v-radio 
              class="plugin-set-mode-radio"
              value="none" 
              :label="tm('pluginSetSelector.enableNone')" 
              color="primary"
            ></v-radio>
            <v-radio 
              class="plugin-set-mode-radio"
              value="custom" 
              :label="tm('pluginSetSelector.customSelect')" 
              color="primary"
            ></v-radio>
          </v-radio-group>

          <!-- 自定义选择时显示插件列表 -->
          <div v-if="selectionMode === 'custom'" class="plugin-set-custom-list">
            <v-list v-if="pluginList.length > 0" density="compact" class="plugin-set-list">
              <v-list-item
                v-for="plugin in pluginList"
                :key="plugin.name"
                rounded="md"
                class="plugin-set-list-item ma-1">
                <template v-slot:prepend>
                  <v-checkbox
                    v-model="selectedPlugins"
                    :value="plugin.name"
                    color="primary"
                    hide-details
                  ></v-checkbox>
                </template>
                
                <v-list-item-title>{{ pluginDisplayName(plugin) }}</v-list-item-title>
                <v-list-item-subtitle>
                  {{ pluginDescription(plugin) || tm('pluginSetSelector.noDescription') }}
                  <v-chip v-if="!plugin.activated" size="x-small" color="grey" class="ml-1">
                    {{ tm('pluginSetSelector.notActivated') }}
                  </v-chip>
                </v-list-item-subtitle>
              </v-list-item>

              <div class="plugin-set-note pl-8 pt-2">
                <small>{{ tm('pluginSetSelector.note') }}</small>
              </div>
            </v-list>

            <div v-else class="plugin-set-empty text-center py-8">
              <v-icon size="64" color="grey-lighten-1">mdi-puzzle-outline</v-icon>
              <p class="text-grey mt-4">{{ tm('pluginSetSelector.noPlugins') }}</p>
            </div>
          </div>
        </div>
      </v-card-text>
            
      <v-card-actions class="plugin-set-dialog-actions pa-4">
        <v-spacer></v-spacer>
        <v-btn class="plugin-set-cancel-btn" variant="text" @click="cancelSelection">{{ tm('pluginSetSelector.cancelSelection') }}</v-btn>
        <v-btn 
          class="plugin-set-confirm-btn"
          color="primary" 
          variant="tonal"
          @click="confirmSelection">
          {{ tm('pluginSetSelector.confirmSelection') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { pluginApi } from '@/api/v1'
import { useModuleI18n } from '@/i18n/composables'
import { usePluginI18n } from '@/utils/pluginI18n'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  },
  buttonText: {
    type: String,
    default: ''
  },
  maxDisplayItems: {
    type: Number,
    default: 3
  }
})

const emit = defineEmits(['update:modelValue'])
const { tm } = useModuleI18n('core.shared')
const { pluginName, pluginDesc } = usePluginI18n()

const dialog = ref(false)
const pluginList = ref([])
const loading = ref(false)
const selectionMode = ref('custom') // 'all', 'none', 'custom'
const selectedPlugins = ref([])

const pluginDisplayName = (plugin) => pluginName(plugin) || plugin.name
const pluginDescription = (plugin) => pluginDesc(plugin)

// 判断是否为"所有插件"模式
const isAllPlugins = computed(() => {
  return props.modelValue && props.modelValue.length === 1 && props.modelValue[0] === '*'
})

// 移除插件
function removePlugin(pluginName) {
  if (props.modelValue && props.modelValue.length > 0) {
    const newValue = props.modelValue.filter(name => name !== pluginName)
    emit('update:modelValue', newValue)
  }
}

// 监听 modelValue 变化，同步内部状态
watch(() => props.modelValue, (newValue) => {
  if (!newValue || newValue.length === 0) {
    selectionMode.value = 'none'
    selectedPlugins.value = []
  } else if (newValue.length === 1 && newValue[0] === '*') {
    selectionMode.value = 'all'
    selectedPlugins.value = []
  } else {
    selectionMode.value = 'custom'
    selectedPlugins.value = [...newValue]
  }
}, { immediate: true })

async function openDialog() {
  dialog.value = true
  await loadPlugins()
}

async function loadPlugins() {
  loading.value = true
  try {
    const response = await pluginApi.list()
    if (response.data.status === 'ok') {
      // 只显示已激活且非系统的插件，并按名称排序
      pluginList.value = (response.data.data || [])
        .filter(plugin => plugin.activated && !plugin.reserved)
        .sort((a, b) => {
          const nameA = a.name || '';
          const nameB = b.name || '';
          return nameA.localeCompare(nameB);
        })
    }
  } catch (error) {
    console.error('加载插件列表失败:', error)
    pluginList.value = []
  } finally {
    loading.value = false
  }
}

function confirmSelection() {
  let newValue = []
  
  switch (selectionMode.value) {
    case 'all':
      newValue = ['*']
      break
    case 'none':
      newValue = []
      break
    case 'custom':
      newValue = [...selectedPlugins.value]
      break
  }
  
  emit('update:modelValue', newValue)
  dialog.value = false
}

function cancelSelection() {
  // 恢复到原始状态
  const currentValue = props.modelValue || []
  if (currentValue.length === 0) {
    selectionMode.value = 'none'
    selectedPlugins.value = []
  } else if (currentValue.length === 1 && currentValue[0] === '*') {
    selectionMode.value = 'all'
    selectedPlugins.value = []
  } else {
    selectionMode.value = 'custom'
    selectedPlugins.value = [...currentValue]
  }
  
  dialog.value = false
}
</script>

<style scoped>
.plugin-set-open-btn {
  min-width: 118px;
  height: 34px;
  border: 1px solid rgba(42, 143, 204, 0.16);
  border-radius: 10px !important;
  background: #eaf5fc !important;
  color: #1976a9 !important;
  font-weight: 700;
  letter-spacing: 0;
  box-shadow: none !important;
}

.plugin-set-open-btn:hover {
  border-color: rgba(42, 143, 204, 0.32);
  background: #def0fa !important;
}

.plugin-set-dialog-card {
  overflow: hidden;
  border: 1px solid rgba(42, 143, 204, 0.12);
  border-radius: 18px !important;
  background: linear-gradient(180deg, #fbfdff 0%, #f7fbfe 100%) !important;
  box-shadow: 0 22px 54px rgba(20, 42, 62, 0.18) !important;
}

.plugin-set-dialog-title {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 20px !important;
  color: #142433;
  font-size: 20px !important;
  font-weight: 800 !important;
  letter-spacing: 0;
}

.plugin-set-dialog-title__icon {
  display: inline-grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 12px;
  background: #eaf7f4;
  color: #1f8a68;
}

.plugin-set-dialog-body {
  padding: 18px 22px 8px !important;
}

.plugin-set-mode-list {
  padding: 6px;
  border: 1px solid rgba(var(--v-theme-border), 0.42);
  border-radius: 16px;
  background: #ffffff;
}

.plugin-set-mode-radio {
  min-height: 48px;
  margin: 0 0 6px;
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: 13px;
  transition:
    background-color 0.16s ease,
    border-color 0.16s ease;
}

.plugin-set-mode-radio:last-child {
  margin-bottom: 0;
}

.plugin-set-mode-radio:hover {
  border-color: rgba(42, 143, 204, 0.14);
  background: #f3f9fd;
}

.plugin-set-custom-list {
  max-height: 300px;
  overflow-y: auto;
  margin-top: 12px;
  border: 1px solid rgba(var(--v-theme-border), 0.42);
  border-radius: 16px;
  background: #ffffff;
}

.plugin-set-list {
  padding: 8px !important;
  background: transparent;
}

.plugin-set-list-item {
  border: 1px solid transparent;
  border-radius: 12px !important;
}

.v-list-item {
  transition: all 0.2s ease;
}

.v-list-item:hover {
  border-color: rgba(42, 143, 204, 0.14);
  background-color: #f3f9fd;
}

.plugin-set-note {
  color: rgba(var(--v-theme-on-surface), 0.58);
}

.plugin-set-empty {
  color: rgba(var(--v-theme-on-surface), 0.58);
}

.plugin-set-dialog-actions {
  margin-top: 12px;
  padding: 14px 22px 18px !important;
  border-top: 1px solid rgba(var(--v-theme-border), 0.36);
  background: rgba(248, 251, 253, 0.88);
}

.plugin-set-cancel-btn {
  height: 36px;
  border-radius: 10px !important;
  color: rgba(var(--v-theme-on-surface), 0.68) !important;
  font-weight: 650;
}

.plugin-set-confirm-btn {
  height: 36px;
  border-radius: 10px !important;
  background: #e8f5fc !important;
  color: #1674a8 !important;
  font-weight: 700;
  box-shadow: none !important;
}
</style>
