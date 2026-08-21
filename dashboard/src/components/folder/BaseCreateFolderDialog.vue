<template>
    <v-dialog v-model="showDialog" max-width="520px">
        <v-card class="folder-dialog-card">
            <v-card-title class="text-h3 pa-4 pb-0 pl-6 folder-dialog-title">
                <span class="folder-dialog-title-icon">
                    <v-icon size="22">mdi-folder-plus</v-icon>
                </span>
                <span>{{ labels.title }}</span>
            </v-card-title>
            <v-card-text class="folder-dialog-body">
                <v-form ref="form" v-model="formValid" @submit.prevent="submitForm" :disabled="loading">
                    <v-text-field v-model="formData.name" :label="mergedLabels.nameLabel"
                        :rules="[(v: any) => !!v || mergedLabels.nameRequired]" variant="outlined"
                        density="comfortable" autofocus class="folder-dialog-field mb-3" />

                    <v-textarea v-model="formData.description" :label="labels.descriptionLabel" variant="outlined"
                        rows="3" density="comfortable" hide-details class="folder-dialog-field" />
                </v-form>
            </v-card-text>
            <v-card-actions class="folder-dialog-actions">
                <v-spacer />
                <v-btn variant="tonal" class="folder-dialog-secondary-btn" @click="closeDialog">
                    {{ labels.cancelButton }}
                </v-btn>
                <v-btn color="primary" variant="flat" class="folder-dialog-primary-btn" @click="submitForm" :loading="loading" :disabled="!formValid">
                    {{ labels.createButton }}
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue';
import type { CreateFolderData } from './types';

interface DefaultLabels {
    title: string;
    nameLabel: string;
    descriptionLabel: string;
    nameRequired: string;
    cancelButton: string;
    createButton: string;
}

const defaultLabels: DefaultLabels = {
    title: '创建文件夹',
    nameLabel: '名称',
    descriptionLabel: '描述',
    nameRequired: '请输入文件夹名称',
    cancelButton: '取消',
    createButton: '创建'
};

export default defineComponent({
    name: 'BaseCreateFolderDialog',
    props: {
        modelValue: {
            type: Boolean,
            default: false
        },
        parentFolderId: {
            type: String as PropType<string | null>,
            default: null
        },
        labels: {
            type: Object as PropType<Partial<DefaultLabels>>,
            default: () => ({})
        }
    },
    emits: ['update:modelValue', 'create'],
    data() {
        return {
            formValid: false,
            loading: false,
            formData: {
                name: '',
                description: ''
            }
        };
    },
    computed: {
        showDialog: {
            get(): boolean {
                return this.modelValue;
            },
            set(value: boolean) {
                this.$emit('update:modelValue', value);
            }
        },
        mergedLabels(): DefaultLabels {
            return { ...defaultLabels, ...this.labels };
        }
    },
    watch: {
        modelValue(newValue: boolean) {
            if (newValue) {
                this.resetForm();
            }
        }
    },
    methods: {
        resetForm() {
            this.formData = {
                name: '',
                description: ''
            };
            if (this.$refs.form) {
                (this.$refs.form as any).resetValidation();
            }
        },

        closeDialog() {
            this.showDialog = false;
        },

        async submitForm() {
            if (!this.formValid) return;

            const data: CreateFolderData = {
                name: this.formData.name,
                description: this.formData.description || undefined,
                parent_id: this.parentFolderId
            };

            this.$emit('create', data);
        },

        setLoading(value: boolean) {
            this.loading = value;
        }
    }
});
</script>

<style scoped>
.folder-dialog-card {
    border: 1px solid rgba(var(--v-theme-border), 0.68);
    border-radius: 16px !important;
    background:
        linear-gradient(180deg, rgba(31, 151, 111, 0.045), transparent 180px),
        rgb(var(--v-theme-surface));
    box-shadow: 0 24px 70px rgba(15, 23, 42, 0.18) !important;
    overflow: hidden;
}

.folder-dialog-title {
    display: flex;
    min-height: 68px;
    align-items: center;
    gap: 12px;
    padding: 18px 24px 16px !important;
    border-bottom: 1px solid rgba(var(--v-theme-border), 0.54);
    background: rgba(255, 255, 255, 0.82);
    color: rgba(var(--v-theme-on-surface), 0.92);
    font-size: 1.18rem !important;
    font-weight: 720 !important;
    letter-spacing: 0;
}

.folder-dialog-title-icon {
    display: inline-flex;
    width: 38px;
    height: 38px;
    flex: 0 0 38px;
    align-items: center;
    justify-content: center;
    border: 1px solid rgba(31, 151, 111, 0.18);
    border-radius: 10px;
    background: rgba(228, 247, 240, 0.92);
    color: #17795c;
}

.folder-dialog-body {
    padding: 20px 24px 10px !important;
    background: rgba(248, 250, 252, 0.62);
}

.folder-dialog-field :deep(.v-field) {
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.96);
}

.folder-dialog-field :deep(.v-field__outline) {
    --v-field-border-opacity: 0.2;
}

.folder-dialog-field :deep(.v-field--focused .v-field__outline) {
    --v-field-border-opacity: 0.48;
}

.folder-dialog-actions {
    gap: 10px;
    padding: 14px 24px 20px !important;
    border-top: 1px solid rgba(var(--v-theme-border), 0.54);
    background: rgba(255, 255, 255, 0.88);
}

.folder-dialog-primary-btn,
.folder-dialog-secondary-btn {
    height: 40px !important;
    max-height: 40px;
    border-radius: 8px !important;
    padding: 0 18px !important;
    font-weight: 650;
    letter-spacing: 0;
}

.folder-dialog-secondary-btn {
    border: 1px solid rgba(var(--v-theme-border), 0.76);
    background: rgba(255, 255, 255, 0.9) !important;
    color: rgba(var(--v-theme-on-surface), 0.74) !important;
}

.folder-dialog-primary-btn {
    background: #17795c !important;
    color: #fff !important;
}

.folder-dialog-primary-btn:hover {
    background: #12684f !important;
}
</style>
