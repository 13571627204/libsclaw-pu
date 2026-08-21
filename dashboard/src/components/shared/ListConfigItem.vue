<template>
  <div class="list-config-inline d-flex align-center justify-space-between ga-2">
    <div v-if="isSingleItemMode" class="flex-grow-1 d-flex align-center ga-2">
      <v-text-field
        v-model="singleItemValue"
        hide-details
        variant="outlined"
        density="compact"
        class="flex-grow-1"
      ></v-text-field>
    </div>
    <div v-else>
      <span v-if="!modelValue || modelValue.length === 0" style="color: rgb(var(--v-theme-primaryText));">
        {{ t('core.common.list.noItems') }}
      </span>
      <div v-else class="d-flex flex-wrap ga-2">
        <v-chip v-for="item in displayItems" :key="item" size="x-small" label color="primary">
          {{ item.length > 20 ? item.slice(0, 20) + '...' : item }}
        </v-chip>
        <v-chip v-if="modelValue.length > maxDisplayItems" size="x-small" label color="grey-lighten-1">
          +{{ modelValue.length - maxDisplayItems }}
        </v-chip>
      </div>
    </div>
    <v-btn class="list-config-open-btn" size="small" color="primary" variant="tonal" @click="openDialog">
      {{ preferSingleItem ? t('core.common.list.addMore') : (buttonText || t('core.common.list.modifyButton')) }}
    </v-btn>
  </div>

  <!-- List Management Dialog -->
  <v-dialog v-model="dialog" max-width="600px">
    <v-card class="list-config-dialog-card">
      <v-card-title class="text-h3 pa-4 pb-0 pl-6 list-config-dialog-title">
        <span class="list-config-dialog-title__icon">
          <v-icon size="18">mdi-format-list-bulleted-square</v-icon>
        </span>
        <span>{{ dialogTitle || t('core.common.list.editTitle') }}</span>
      </v-card-title>
      
      <!-- Add new item section - moved to top -->
      <v-card-text class="list-config-dialog-input pa-4 pb-2">
        <div class="list-config-add-row d-flex align-center ga-2">
          <v-text-field 
            v-model="newItem" 
            :label="t('core.common.list.addItemPlaceholder')" 
            @keyup.enter="addItem" 
            clearable 
            hide-details
            variant="outlined" 
            density="compact" 
            :placeholder="t('core.common.list.inputPlaceholder')"
            class="flex-grow-1 list-config-text-field">
          </v-text-field>
          <v-btn
            class="list-config-add-btn"
            @click="addItem"
            variant="tonal"
            color="primary"
            size="small"
            :disabled="!newItem.trim()">
            {{ t('core.common.list.addButton') }}
          </v-btn>
          <v-btn 
            class="list-config-import-btn"
            @click="showBatchImport = true" 
            variant="tonal" 
            color="primary"
            size="small">
            <v-icon size="small">mdi-import</v-icon>
            {{ t('core.common.list.batchImport') }}
          </v-btn>
        </div>
      </v-card-text>

      <v-card-text class="list-config-dialog-list pa-0">
        <v-list v-if="localItems.length > 0" density="compact" class="list-config-items">
          <v-list-item
            v-for="(item, index) in localItems"
            :key="index"
            rounded="md"
            class="ma-1 list-item-clickable"
            @click="startEdit(index, item)">
            <v-list-item-title v-if="editIndex !== index" class="item-text">
              {{ item }}
            </v-list-item-title>
            <v-text-field 
              v-else
              v-model="editItem" 
              hide-details 
              variant="outlined" 
              density="compact"
              @keyup.enter="saveEdit" 
              @keyup.esc="cancelEdit"
              @click.stop
              autofocus
            ></v-text-field>
            
            <template v-slot:append>
              <div class="d-flex">
                <v-btn
                  v-if="editIndex === index"
                  @click.stop="saveEdit" 
                  variant="text"
                  color="success" 
                  icon 
                  size="small">
                  <v-icon>mdi-check</v-icon>
                </v-btn>
                <v-btn
                  @click.stop="editIndex === index ? cancelEdit() : removeItem(index)" 
                  variant="text"
                  :color="editIndex === index ? 'error' : 'default'"
                  icon 
                  size="small">
                  <v-icon>mdi-close</v-icon>
                </v-btn>
              </div>
            </template>
          </v-list-item>
        </v-list>
        
        <div v-else class="list-config-empty text-center py-8">
          <v-icon size="64" color="grey-lighten-1">mdi-format-list-bulleted</v-icon>
          <p class="text-grey mt-4">{{ t('core.common.list.noItemsHint') }}</p>
        </div>
      </v-card-text>

      <v-card-actions class="list-config-dialog-actions pa-4">
        <v-spacer></v-spacer>
        <v-btn class="list-config-cancel-btn" variant="text" @click="cancelDialog">{{ t('core.common.cancel') }}</v-btn>
        <v-btn class="list-config-confirm-btn" color="primary" variant="tonal" @click="confirmDialog">{{ t('core.common.confirm') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Batch Import Dialog -->
  <v-dialog v-model="showBatchImport" max-width="600px">
    <v-card class="list-config-dialog-card">
      <v-card-title class="text-h3 pa-4 pb-0 pl-6 list-config-dialog-title">
        <span class="list-config-dialog-title__icon">
          <v-icon size="18">mdi-import</v-icon>
        </span>
        <span>{{ t('core.common.list.batchImportTitle') }}</span>
      </v-card-title>
      
      <v-card-text class="list-config-dialog-input">
        <v-textarea
          v-model="batchImportText"
          :label="t('core.common.list.batchImportLabel')"
          :placeholder="t('core.common.list.batchImportPlaceholder')"
          rows="10"
          variant="outlined"
          :hint="t('core.common.list.batchImportHint')"
          persistent-hint
        ></v-textarea>
      </v-card-text>

      <v-card-actions class="list-config-dialog-actions pa-4">
        <v-spacer></v-spacer>
        <v-btn class="list-config-cancel-btn" variant="text" @click="cancelBatchImport">{{ t('core.common.cancel') }}</v-btn>
        <v-btn class="list-config-confirm-btn" color="primary" variant="tonal" @click="confirmBatchImport">
          {{ t('core.common.list.batchImportButton', { count: batchImportPreviewCount }) }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useI18n } from '@/i18n/composables'

const { t } = useI18n()

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  },
  label: {
    type: String,
    default: ''
  },
  buttonText: {
    type: String,
    default: ''
  },
  dialogTitle: {
    type: String,
    default: ''
  },
  maxDisplayItems: {
    type: Number,
    default: 1
  },
  preferSingleItem: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue'])

const dialog = ref(false)
const localItems = ref([])
const originalItems = ref([])
const newItem = ref('')
const editIndex = ref(-1)
const editItem = ref('')
const showBatchImport = ref(false)
const batchImportText = ref('')
const isSingleItemMode = computed(() => (props.modelValue?.length ?? 0) <= 1 && props.preferSingleItem)
const singleItemValue = computed({
  get: () => props.modelValue?.[0] ?? '',
  set: (value) => {
    // 仅当值为完全空字符串（未输入任何字符）时清空数组，
    // 允许包含空格（如 "hello world"）以及纯空格（如 " "）通过
    if (value === '') {
      emit('update:modelValue', [])
      return
    }

    const newItems = [...(props.modelValue || [])]
    if (newItems.length === 0) {
      newItems.push(value)
    } else {
      newItems[0] = value
    }

    emit('update:modelValue', newItems)
  }
})

// 计算要显示的项目
const displayItems = computed(() => {
  return props.modelValue.slice(0, props.maxDisplayItems)
})

// 计算批量导入的项目数量
const batchImportPreviewCount = computed(() => {
  if (!batchImportText.value) return 0
  return batchImportText.value
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0)
    .length
})

// 监听 modelValue 变化，同步到 localItems，并清理空字符串
watch(() => props.modelValue, (newValue) => {
  localItems.value = [...(newValue || [])]
  
  // 自动清理只包含空字符串或纯空格的条目（纯空格在配置中无意义，此过滤为预期兜底行为）
  if (newValue && newValue.length > 0) {
    const filtered = newValue.filter(item => typeof item === 'string' ? item.trim() !== '' : true)
    if (filtered.length !== newValue.length) {
      // 使用 nextTick 确保父组件已准备好接收更新
      nextTick(() => {
        emit('update:modelValue', filtered)
      })
    }
  }
}, { immediate: true })

function openDialog() {
  localItems.value = [...(props.modelValue || [])]
  originalItems.value = [...(props.modelValue || [])]
  dialog.value = true
  editIndex.value = -1
  editItem.value = ''
  newItem.value = ''
}

function addItem() {
  if (newItem.value.trim() !== '') {
    localItems.value.push(newItem.value.trim())
    newItem.value = ''
  }
}

function removeItem(index) {
  localItems.value.splice(index, 1)
}

function startEdit(index, item) {
  editIndex.value = index
  editItem.value = item
}

function saveEdit() {
  if (editItem.value.trim() !== '') {
    localItems.value[editIndex.value] = editItem.value.trim()
    cancelEdit()
  }
}

function cancelEdit() {
  editIndex.value = -1
  editItem.value = ''
}

function confirmDialog() {
  // 过滤空字符串，同时处理非字符串类型
  const filteredItems = localItems.value.filter(item => typeof item === 'string' ? item.trim() !== '' : true)
  emit('update:modelValue', filteredItems)
  dialog.value = false
}

function cancelDialog() {
  localItems.value = [...originalItems.value]
  editIndex.value = -1
  editItem.value = ''
  newItem.value = ''
  dialog.value = false
}

function confirmBatchImport() {
  if (batchImportText.value.trim()) {
    const newItems = batchImportText.value
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0)
    
    localItems.value.push(...newItems)
    batchImportText.value = ''
    showBatchImport.value = false
  }
}

function cancelBatchImport() {
  batchImportText.value = ''
  showBatchImport.value = false
}
</script>

<style scoped>
.list-config-inline {
  min-width: 0;
}

.list-config-open-btn {
  min-width: 82px;
  height: 34px;
  border: 1px solid rgba(42, 143, 204, 0.16);
  border-radius: 10px !important;
  background: #eaf5fc !important;
  color: #1976a9 !important;
  font-weight: 700;
  letter-spacing: 0;
  box-shadow: none !important;
}

.list-config-open-btn:hover {
  border-color: rgba(42, 143, 204, 0.32);
  background: #def0fa !important;
}

.list-config-dialog-card {
  overflow: hidden;
  border: 1px solid rgba(42, 143, 204, 0.12);
  border-radius: 18px !important;
  background: linear-gradient(180deg, #fbfdff 0%, #f7fbfe 100%) !important;
  box-shadow: 0 22px 54px rgba(20, 42, 62, 0.18) !important;
}

.list-config-dialog-title {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 20px !important;
  color: #142433;
  font-size: 20px !important;
  font-weight: 800 !important;
  letter-spacing: 0;
}

.list-config-dialog-title__icon {
  display: inline-grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 12px;
  background: #e8f5fc;
  color: #1d86bf;
}

.list-config-dialog-input {
  padding: 18px 22px 12px !important;
}

.list-config-add-row {
  padding: 12px;
  border: 1px solid rgba(42, 143, 204, 0.12);
  border-radius: 14px;
  background: #ffffff;
}

.list-config-add-btn,
.list-config-import-btn,
.list-config-confirm-btn {
  height: 36px;
  border-radius: 10px !important;
  background: #e8f5fc !important;
  color: #1674a8 !important;
  font-weight: 700;
  box-shadow: none !important;
}

.list-config-import-btn {
  background: #eef7f3 !important;
  color: #237b5e !important;
}

.list-config-cancel-btn {
  height: 36px;
  border-radius: 10px !important;
  color: rgba(var(--v-theme-on-surface), 0.68) !important;
  font-weight: 650;
}

.list-config-dialog-list {
  max-height: 360px;
  overflow-y: auto;
  margin: 2px 22px 0;
  border: 1px solid rgba(var(--v-theme-border), 0.42);
  border-radius: 14px;
  background: #ffffff;
}

.list-config-items {
  padding: 8px !important;
  background: transparent;
}

.v-list-item {
  transition: all 0.2s ease;
}

.list-item-clickable {
  cursor: pointer;
  min-height: 44px;
  border: 1px solid transparent;
  border-radius: 12px !important;
}

.list-item-clickable:hover {
  border-color: rgba(42, 143, 204, 0.14);
  background-color: #f3f9fd;
}

.item-text {
  user-select: none;
  color: #21313f;
  font-weight: 560;
}

.v-chip {
  margin: 2px;
}

.list-config-empty {
  color: rgba(var(--v-theme-on-surface), 0.58);
}

.list-config-dialog-actions {
  margin-top: 12px;
  padding: 14px 22px 18px !important;
  border-top: 1px solid rgba(var(--v-theme-border), 0.36);
  background: rgba(248, 251, 253, 0.88);
}

@media (max-width: 600px) {
  .list-config-add-row {
    align-items: stretch !important;
    flex-direction: column;
  }

  .list-config-add-btn,
  .list-config-import-btn {
    width: 100%;
  }
}
</style>
