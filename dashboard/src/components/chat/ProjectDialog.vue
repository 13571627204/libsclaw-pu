<template>
    <v-dialog v-model="isOpen" max-width="560" @update:model-value="handleDialogChange">
        <v-card class="project-dialog-card">
            <v-card-title class="project-dialog-title-wrap">
                <span class="project-dialog-kicker">{{ tm('project.title') }}</span>
                <span class="project-dialog-title">{{ dialogTitle }}</span>
                <span class="project-dialog-subtitle">{{ dialogSubtitle }}</span>
            </v-card-title>
            <v-card-text class="project-dialog-content">
                <div class="project-dialog-section">
                    <v-text-field
                        v-model="form.emoji"
                        :label="tm('project.emoji')"
                        variant="outlined"
                        density="comfortable"
                        hide-details
                    />
                    <v-text-field
                        v-model="form.title"
                        :label="tm('project.name')"
                        variant="outlined"
                        density="comfortable"
                        hide-details
                        autofocus
                        @keyup.enter="handleSave"
                    />
                    <v-textarea
                        v-model="form.description"
                        :label="tm('project.description')"
                        variant="outlined"
                        density="comfortable"
                        hide-details
                        rows="3"
                    />
                </div>

                <div class="project-dialog-section project-dialog-section--muted">
                    <v-select
                        v-model="form.workspace_type"
                        :items="workspaceTypeItems"
                        item-title="label"
                        item-value="value"
                        :label="tm('project.workspace.type')"
                        variant="outlined"
                        density="comfortable"
                        hide-details
                    />
                    <v-text-field
                        v-if="form.workspace_type === 'custom'"
                        v-model="form.workspace_path"
                        :label="tm('project.workspace.path')"
                        variant="outlined"
                        density="comfortable"
                        hide-details
                    />
                </div>
                <v-alert
                    v-if="props.errorMessage"
                    class="mt-3"
                    type="error"
                    variant="tonal"
                    density="compact"
                >
                    {{ props.errorMessage }}
                </v-alert>
            </v-card-text>
            <v-card-actions class="project-dialog-actions">
                <v-btn
                    variant="tonal"
                    class="project-dialog-cancel"
                    :disabled="props.saving"
                    @click="handleCancel"
                >
                    {{ t('core.common.cancel') }}
                </v-btn>
                <v-btn
                    variant="flat"
                    color="primary"
                    class="project-dialog-save"
                    :disabled="!canSave || props.saving"
                    :loading="props.saving"
                    @click="handleSave"
                >
                    {{ t('core.common.save') }}
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n, useModuleI18n } from '@/i18n/composables';

export type WorkspaceType = 'session' | 'project' | 'custom';

export interface Project {
    project_id: string;
    title: string;
    emoji?: string;
    description?: string;
    workspace_type?: WorkspaceType;
    workspace_path?: string | null;
    resolved_workspace_path?: string | null;
    created_at: string;
    updated_at: string;
}

export interface ProjectFormData {
    emoji: string;
    title: string;
    description: string;
    workspace_type: WorkspaceType;
    workspace_path: string;
}

interface Props {
    modelValue: boolean;
    project?: Project | null;
    errorMessage?: string;
    saving?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    modelValue: false,
    project: null,
    errorMessage: '',
    saving: false
});

const emit = defineEmits<{
    'update:modelValue': [value: boolean];
    save: [formData: ProjectFormData, projectId?: string];
}>();

const { t } = useI18n();
const { tm } = useModuleI18n('features/chat');

const isOpen = ref(props.modelValue);
const isEditing = ref(false);
const form = ref<ProjectFormData>({
    emoji: '📁',
    title: '',
    description: '',
    workspace_type: 'project',
    workspace_path: ''
});
const workspaceTypeItems = computed(() => [
    { label: tm('project.workspace.project'), value: 'project' },
    { label: tm('project.workspace.session'), value: 'session' },
    { label: tm('project.workspace.custom'), value: 'custom' }
]);
const dialogTitle = computed(() => isEditing.value ? tm('project.edit') : tm('project.createDialogTitle'));
const dialogSubtitle = computed(() => isEditing.value ? tm('project.editSubtitle') : tm('project.createDialogSubtitle'));
const canSave = computed(() => {
    if (!form.value.title.trim()) return false;
    if (form.value.workspace_type !== 'custom') return true;
    return form.value.workspace_path.trim().length > 0;
});

watch(() => props.modelValue, (newVal) => {
    isOpen.value = newVal;
    if (newVal) {
        if (props.project) {
            isEditing.value = true;
            form.value = {
                emoji: props.project.emoji || '📁',
                title: props.project.title,
                description: props.project.description || '',
                workspace_type: props.project.workspace_type || 'session',
                workspace_path: props.project.workspace_path || ''
            };
        } else {
            isEditing.value = false;
            form.value = {
                emoji: '📁',
                title: '',
                description: '',
                workspace_type: 'project',
                workspace_path: ''
            };
        }
    }
});

watch(() => form.value.workspace_type, (workspaceType) => {
    if (workspaceType !== 'custom') {
        form.value.workspace_path = '';
    }
});

function handleDialogChange(value: boolean) {
    emit('update:modelValue', value);
}

function handleCancel() {
    isOpen.value = false;
    emit('update:modelValue', false);
}

function handleSave() {
    if (!canSave.value) {
        return;
    }

    emit('save', {
        ...form.value,
        workspace_path: form.value.workspace_path.trim()
    }, props.project?.project_id);
}

</script>

<style scoped>
.project-dialog-card {
    overflow: hidden;
    border: 1px solid rgba(42, 143, 204, 0.16);
    border-radius: 18px !important;
    background: #ffffff;
    box-shadow: 0 22px 58px rgba(15, 52, 77, 0.18) !important;
}

.project-dialog-title-wrap {
    display: flex;
    flex-direction: column;
    gap: 5px;
    padding: 22px 26px 18px;
    border-bottom: 1px solid rgba(42, 143, 204, 0.12);
    background: linear-gradient(180deg, #f5fbff 0%, #ffffff 100%);
}

.project-dialog-kicker {
    width: fit-content;
    padding: 3px 9px;
    border: 1px solid rgba(42, 143, 204, 0.14);
    border-radius: 999px;
    background: rgba(42, 143, 204, 0.08);
    color: #2388c2;
    font-size: 12px;
    font-weight: 700;
}

.project-dialog-title {
    color: #122234;
    font-size: 22px;
    font-weight: 800;
    line-height: 1.25;
}

.project-dialog-subtitle {
    color: #6a7a89;
    font-size: 13px;
    line-height: 1.5;
}

.project-dialog-content {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 18px 26px 20px !important;
}

.project-dialog-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.project-dialog-section--muted {
    padding: 14px;
    border: 1px solid rgba(42, 143, 204, 0.12);
    border-radius: 14px;
    background: #f7fbfe;
}

.project-dialog-content :deep(.v-field) {
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.96);
}

.project-dialog-actions {
    gap: 10px;
    justify-content: flex-end;
    padding: 16px 26px 20px !important;
    border-top: 1px solid rgba(42, 143, 204, 0.1);
    background: #fbfdff;
}

.project-dialog-cancel {
    min-width: 84px;
    color: #52616f !important;
}

.project-dialog-save {
    min-width: 92px;
    box-shadow: 0 8px 18px rgba(42, 143, 204, 0.16);
}
</style>
