<script setup lang="ts">
import { computed, onBeforeUnmount, shallowRef, watch } from "vue";
import { knowledgeApi } from "@/api/v1";

interface Props {
  modelValue: boolean;
  kbId: string;
}

interface WikiImportEntry {
  id: number;
  file: File;
  path: string;
  archive: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  imported: [];
  busy: [value: boolean];
}>();

const fileInput = shallowRef<HTMLInputElement | null>(null);
const directoryInput = shallowRef<HTMLInputElement | null>(null);
const entries = shallowRef<WikiImportEntry[]>([]);
const overwrite = shallowRef(false);
const importing = shallowRef(false);
const errorMessage = shallowRef("");
const successMessage = shallowRef("");
const statusMessage = shallowRef("");
const progress = shallowRef({ current: 0, total: 0 });
let pollTimer: number | null = null;
let nextEntryId = 0;

const previewEntries = computed(() => entries.value.slice(0, 100));
const hiddenEntryCount = computed(() =>
  Math.max(0, entries.value.length - previewEntries.value.length),
);
const totalSize = computed(() =>
  entries.value.reduce((total, entry) => total + entry.file.size, 0),
);
const progressValue = computed(() => {
  if (progress.value.total <= 0) return 0;
  return Math.min(100, (progress.value.current / progress.value.total) * 100);
});

const setImporting = (value: boolean) => {
  importing.value = value;
  emit("busy", value);
};

const stopPolling = () => {
  if (pollTimer !== null) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
};

const reset = () => {
  stopPolling();
  entries.value = [];
  overwrite.value = false;
  errorMessage.value = "";
  successMessage.value = "";
  statusMessage.value = "";
  progress.value = { current: 0, total: 0 };
  if (fileInput.value) fileInput.value.value = "";
  if (directoryInput.value) directoryInput.value.value = "";
};

const updateModelValue = (value: boolean) => {
  if (importing.value && !value) return;
  emit("update:modelValue", value);
};

const close = () => {
  if (importing.value) return;
  emit("update:modelValue", false);
};

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 2)} ${units[unitIndex]}`;
};

const isMarkdown = (name: string) => {
  const normalized = name.toLowerCase();
  return (
    normalized.endsWith(".md") ||
    normalized.endsWith(".markdown") ||
    normalized.endsWith(".mdx")
  );
};

const addEntries = (newEntries: WikiImportEntry[]) => {
  const merged = [...entries.value];
  newEntries.forEach((entry) => {
    if (entry.archive) {
      merged.push(entry);
      return;
    }
    const existingIndex = merged.findIndex(
      (existing) => !existing.archive && existing.path === entry.path,
    );
    if (existingIndex >= 0) merged[existingIndex] = entry;
    else merged.push(entry);
  });
  entries.value = merged;
  errorMessage.value = "";
  successMessage.value = "";
};

const selectFiles = (event: Event) => {
  const target = event.target as HTMLInputElement;
  const files = Array.from(target.files || []);
  const accepted = files
    .filter(
      (file) =>
        isMarkdown(file.name) || file.name.toLowerCase().endsWith(".zip"),
    )
    .map((file) => {
      const archive = file.name.toLowerCase().endsWith(".zip");
      nextEntryId += 1;
      return {
        id: nextEntryId,
        file,
        path: archive ? "" : file.name,
        archive,
      };
    });
  addEntries(accepted);
  if (accepted.length !== files.length) {
    errorMessage.value = `已忽略 ${
      files.length - accepted.length
    } 个不支持的文件。`;
  }
  target.value = "";
};

const selectDirectory = (event: Event) => {
  const target = event.target as HTMLInputElement;
  const files = Array.from(target.files || []);
  const accepted: WikiImportEntry[] = [];
  let ignored = 0;

  files.forEach((file) => {
    if (!isMarkdown(file.name)) {
      ignored += 1;
      return;
    }
    const parts = file.webkitRelativePath
      .replace(/\\/g, "/")
      .split("/")
      .filter(Boolean);
    const path = parts.length > 1 ? parts.slice(1).join("/") : file.name;
    nextEntryId += 1;
    accepted.push({ id: nextEntryId, file, path, archive: false });
  });

  addEntries(accepted);
  if (ignored > 0) {
    errorMessage.value = `已忽略文件夹中的 ${ignored} 个非 Markdown 文件。`;
  }
  target.value = "";
};

const removeEntry = (id: number) => {
  entries.value = entries.value.filter((entry) => entry.id !== id);
};

const finishImport = (message: string) => {
  stopPolling();
  setImporting(false);
  statusMessage.value = "";
  progress.value = { current: 0, total: 0 };
  successMessage.value = message;
  emit("imported");
};

const failImport = (message: string) => {
  stopPolling();
  setImporting(false);
  statusMessage.value = "";
  errorMessage.value = message;
};

const pollTask = async (taskId: string) => {
  try {
    const response = await knowledgeApi.task(taskId);
    if (response.data.status !== "ok") {
      failImport(response.data.message || "读取导入任务状态失败。");
      return;
    }

    const task = response.data.data;
    const taskStatus = task?.status;
    if (taskStatus === "completed") {
      const importedCount =
        task.result?.imported_count ??
        task.result?.success_count ??
        task.result?.page_count;
      finishImport(
        typeof importedCount === "number"
          ? `Wiki 导入完成，共导入 ${importedCount} 个页面。`
          : "Wiki 导入完成。",
      );
      return;
    }
    if (taskStatus === "failed") {
      const taskError = task.error?.message || task.error || "Wiki 导入失败。";
      failImport(String(taskError));
      return;
    }

    const taskProgress = task?.progress || {};
    statusMessage.value =
      taskProgress.stage ||
      (taskStatus === "pending" ? "等待处理..." : "正在导入 Wiki...");
    progress.value = {
      current: Number(taskProgress.current || taskProgress.file_index || 0),
      total: Number(taskProgress.total || taskProgress.file_count || 0),
    };
    pollTimer = window.setTimeout(() => void pollTask(taskId), 750);
  } catch (error: any) {
    failImport(
      error.response?.data?.message ||
        error.message ||
        "读取导入任务状态失败。",
    );
  }
};

const submit = async () => {
  if (entries.value.length === 0 || importing.value) return;

  errorMessage.value = "";
  successMessage.value = "";
  statusMessage.value = "正在提交导入任务...";
  progress.value = { current: 0, total: entries.value.length };
  setImporting(true);

  try {
    const formData = new FormData();
    entries.value.forEach((entry) => {
      formData.append("files", entry.file);
      formData.append("paths", entry.path);
    });
    formData.append("overwrite", String(overwrite.value));

    const response = await knowledgeApi.importWiki(props.kbId, formData);
    if (response.data.status !== "ok") {
      failImport(response.data.message || "创建 Wiki 导入任务失败。");
      return;
    }

    const taskId = response.data.data?.task_id;
    if (!taskId) {
      finishImport("Wiki 导入完成。");
      return;
    }
    statusMessage.value = "等待导入任务开始...";
    await pollTask(taskId);
  } catch (error: any) {
    failImport(
      error.response?.data?.message ||
        error.message ||
        "创建 Wiki 导入任务失败。",
    );
  }
};

watch(
  () => props.modelValue,
  (open) => {
    if (open && !importing.value) reset();
  },
);

onBeforeUnmount(() => {
  stopPolling();
  if (importing.value) emit("busy", false);
});
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    max-width="760"
    :persistent="importing"
    @update:model-value="updateModelValue"
  >
    <v-card class="wiki-import-dialog">
      <v-card-title class="wiki-import-header">
        <div class="wiki-import-title">
          <span class="wiki-import-title__icon">
            <v-icon size="22">mdi-folder-upload-outline</v-icon>
          </span>
          <div>
            <h3>导入 Wiki</h3>
            <p>导入 Markdown、ZIP 或文件夹，自动保留目录结构。</p>
          </div>
        </div>
        <v-spacer />
        <v-btn
          icon="mdi-close"
          variant="text"
          :disabled="importing"
          class="wiki-import-close"
          @click="close"
        />
      </v-card-title>

      <v-card-text class="wiki-import-body">
        <div class="wiki-import-tip">
          <v-icon size="18">mdi-information-outline</v-icon>
          <span>
            支持多个 Markdown、ZIP 压缩包或整个文件夹；文件夹根目录会被去掉，分类结构会完整保留。单次原始文件总量最多 512 MiB，ZIP 展开后最多 2 GiB。
          </span>
        </div>

        <div class="import-actions">
          <v-btn
            prepend-icon="mdi-file-multiple-outline"
            variant="tonal"
            :disabled="importing"
            class="wiki-import-picker"
            @click="fileInput?.click()"
          >
            选择 Markdown / ZIP
          </v-btn>
          <v-btn
            prepend-icon="mdi-folder-upload-outline"
            variant="tonal"
            :disabled="importing"
            class="wiki-import-picker wiki-import-picker--folder"
            @click="directoryInput?.click()"
          >
            选择文件夹
          </v-btn>
          <input
            ref="fileInput"
            type="file"
            hidden
            multiple
            accept=".md,.markdown,.mdx,.zip"
            @change="selectFiles"
          />
          <input
            ref="directoryInput"
            type="file"
            hidden
            multiple
            accept=".md,.markdown,.mdx"
            webkitdirectory=""
            directory=""
            @change="selectDirectory"
          />
        </div>

        <v-alert
          v-if="errorMessage"
          type="error"
          variant="tonal"
          density="compact"
          class="wiki-import-alert"
        >
          {{ errorMessage }}
        </v-alert>
        <v-alert
          v-if="successMessage"
          type="success"
          variant="tonal"
          density="compact"
          class="wiki-import-alert"
        >
          {{ successMessage }}
        </v-alert>

        <div v-if="entries.length > 0" class="selected-files">
          <div class="selected-files__header">
            <div>
              <strong>已选择 {{ entries.length }} 个文件</strong>
              <span>共 {{ formatFileSize(totalSize) }}</span>
            </div>
            <v-btn
              size="small"
              variant="text"
              :disabled="importing"
              class="selected-files__clear"
              @click="entries = []"
            >
              清空
            </v-btn>
          </div>
          <v-list class="file-preview" density="compact">
            <v-list-item
              v-for="entry in previewEntries"
              :key="entry.id"
              class="file-preview__item"
              :title="entry.path || entry.file.name"
              :subtitle="formatFileSize(entry.file.size)"
            >
              <template #prepend>
                <span class="file-preview__icon">
                  <v-icon size="18">
                    {{ entry.archive ? 'mdi-folder-zip-outline' : 'mdi-language-markdown-outline' }}
                  </v-icon>
                </span>
              </template>
              <template #append>
                <v-btn
                  icon="mdi-close"
                  size="small"
                  variant="text"
                  :disabled="importing"
                  class="file-preview__remove"
                  @click="removeEntry(entry.id)"
                />
              </template>
            </v-list-item>
          </v-list>
          <p
            v-if="hiddenEntryCount > 0"
            class="selected-files__more"
          >
            仅预览前 100 个文件，另有 {{ hiddenEntryCount }} 个文件也会导入。
          </p>
        </div>

        <div class="wiki-import-option">
          <v-checkbox
            v-model="overwrite"
            label="覆盖知识库中路径相同的页面"
            color="primary"
            density="compact"
            hide-details
            :disabled="importing"
          />
        </div>

        <div v-if="importing" class="wiki-import-progress">
          <div>
            {{ statusMessage }}
          </div>
          <v-progress-linear
            color="primary"
            :indeterminate="progress.total <= 0"
            :model-value="progressValue"
            rounded
          />
        </div>
      </v-card-text>

      <v-card-actions class="wiki-import-actions">
        <v-spacer />
        <v-btn variant="text" :disabled="importing" class="wiki-import-cancel" @click="close">取消</v-btn>
        <v-btn
          color="primary"
          variant="flat"
          :loading="importing"
          :disabled="entries.length === 0"
          class="wiki-import-submit"
          @click="submit"
        >
          开始导入
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.wiki-import-dialog {
  border: 1px solid #dceaf3;
  border-radius: 16px !important;
  overflow: hidden;
}

.wiki-import-header {
  align-items: flex-start;
  background: #fbfdff;
  border-bottom: 1px solid #e3edf5;
  display: flex;
  padding: 20px 26px 16px !important;
}

.wiki-import-title {
  align-items: center;
  display: flex;
  gap: 12px;
}

.wiki-import-title__icon {
  align-items: center;
  background: #eaf6fd;
  border: 1px solid #cce8f8;
  border-radius: 12px;
  color: #2f96cf;
  display: flex;
  flex: 0 0 auto;
  height: 42px;
  justify-content: center;
  width: 42px;
}

.wiki-import-title h3 {
  color: #152638;
  font-size: 1.22rem;
  font-weight: 850;
  line-height: 1.35;
  margin: 0;
}

.wiki-import-title p {
  color: #647482;
  font-size: 0.86rem;
  line-height: 1.45;
  margin: 3px 0 0;
}

.wiki-import-close {
  background: #f1f6fa;
  border-radius: 10px;
  color: #425766;
}

.wiki-import-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px 26px 16px !important;
}

.wiki-import-tip {
  align-items: flex-start;
  background: #eef9ff;
  border: 1px solid #cce8f8;
  border-radius: 12px;
  color: #247fac;
  display: flex;
  font-size: 0.88rem;
  font-weight: 650;
  gap: 10px;
  line-height: 1.65;
  padding: 12px 14px;
}

.import-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.wiki-import-picker {
  border-radius: 10px;
  color: #247fac;
  font-weight: 800;
  letter-spacing: 0;
}

.wiki-import-picker--folder {
  color: #23805e;
}

.wiki-import-alert {
  border-radius: 12px;
}

.selected-files {
  background: #ffffff;
  border: 1px solid #dceaf3;
  border-radius: 14px;
  padding: 12px;
}

.selected-files__header {
  align-items: center;
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.selected-files__header strong {
  color: #152638;
  display: block;
  font-size: 0.92rem;
  font-weight: 850;
  line-height: 1.35;
}

.selected-files__header span {
  color: #657785;
  display: block;
  font-size: 0.78rem;
  line-height: 1.35;
  margin-top: 2px;
}

.selected-files__clear {
  border-radius: 9px;
  color: #2f89be;
  font-weight: 800;
}

.file-preview {
  background: #f8fcff;
  border: 1px solid #e2edf5;
  border-radius: 12px;
  max-height: 260px;
  overflow-y: auto;
  padding: 4px;
}

.file-preview__item {
  border-radius: 10px !important;
  margin: 2px 0;
  min-height: 50px;
}

.file-preview__item:hover {
  background: #eef8ff;
}

.file-preview__icon {
  align-items: center;
  background: #eaf6fd;
  border: 1px solid #cce8f8;
  border-radius: 8px;
  color: #2f96cf;
  display: flex;
  height: 28px;
  justify-content: center;
  width: 28px;
}

.file-preview__item :deep(.v-list-item-title) {
  color: #152638;
  font-size: 0.9rem;
  font-weight: 750;
  line-height: 1.35;
}

.file-preview__item :deep(.v-list-item-subtitle) {
  color: #6d7c88;
  font-size: 0.78rem;
  opacity: 1;
}

.file-preview__remove {
  border-radius: 9px;
  color: #5e6e7a;
}

.selected-files__more {
  color: #657785;
  font-size: 0.8rem;
  line-height: 1.45;
  margin: 9px 0 0;
}

.wiki-import-option {
  background: #fbfdff;
  border: 1px solid #e2edf5;
  border-radius: 12px;
  padding: 8px 10px;
}

.wiki-import-option :deep(.v-label) {
  color: #263d4f;
  font-size: 0.9rem;
  font-weight: 700;
  opacity: 1;
}

.wiki-import-progress {
  color: #657785;
  display: flex;
  flex-direction: column;
  font-size: 0.82rem;
  gap: 8px;
}

.wiki-import-actions {
  background: #fbfdff;
  border-top: 1px solid #e3edf5;
  padding: 14px 26px 18px !important;
}

.wiki-import-cancel,
.wiki-import-submit {
  border-radius: 10px;
  font-weight: 800;
  letter-spacing: 0;
  min-width: 92px;
}

.wiki-import-submit {
  box-shadow: 0 8px 18px rgba(47, 150, 207, 0.16);
}
</style>
