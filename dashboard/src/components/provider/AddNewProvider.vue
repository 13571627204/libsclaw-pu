<template>
    <v-dialog v-model="showDialog" max-width="1000px">
        <v-card class="add-provider-dialog">
            <v-card-title class="add-provider-dialog__title">
                {{ tm('dialogs.addProvider.title') }}
            </v-card-title>
            <v-card-text class="add-provider-dialog__body">
                <v-tabs v-model="activeProviderTab" class="add-provider-tabs">
                    <v-tab value="agent_runner" class="font-weight-medium px-3">
                        <v-icon start>mdi-cogs</v-icon>
                        {{ tm('dialogs.addProvider.tabs.agentRunner') }}
                    </v-tab>
                    <v-tab value="speech_to_text" class="font-weight-medium px-3">
                        <v-icon start>mdi-microphone-message</v-icon>
                        {{ tm('dialogs.addProvider.tabs.speechToText') }}
                    </v-tab>
                    <v-tab value="text_to_speech" class="font-weight-medium px-3">
                        <v-icon start>mdi-volume-high</v-icon>
                        {{ tm('dialogs.addProvider.tabs.textToSpeech') }}
                    </v-tab>
                    <v-tab value="embedding" class="font-weight-medium px-3">
                        <v-icon start>mdi-code-json</v-icon>
                        {{ tm('dialogs.addProvider.tabs.embedding') }}
                    </v-tab>
                    <v-tab value="rerank" class="font-weight-medium px-3">
                        <v-icon start>mdi-compare-vertical</v-icon>
                        {{ tm('dialogs.addProvider.tabs.rerank') }}
                    </v-tab>
                </v-tabs>

                <v-window v-model="activeProviderTab" class="add-provider-window">
                    <v-window-item
                        v-for="tabType in ['chat_completion', 'agent_runner', 'speech_to_text', 'text_to_speech', 'embedding', 'rerank']"
                        :key="tabType" :value="tabType">
                        <div class="add-provider-grid">
                            <div v-for="(template, name) in getTemplatesByType(tabType)" :key="name">
                                <v-card variant="outlined" hover class="provider-card"
                                    @click="selectProviderTemplate(name)">
                                    <div class="provider-card-content">
                                        <div class="provider-card-text">
                                            <v-card-title class="provider-card-title">{{ name }}</v-card-title>
                                            <v-card-text
                                                class="text-caption text-medium-emphasis provider-card-description">
                                                {{ getProviderDescription(template, name) }}
                                            </v-card-text>
                                        </div>
                                        <div class="provider-card-logo">
                                            <img :src="getProviderIcon(template.provider)"
                                                v-if="getProviderIcon(template.provider)" class="provider-logo-img">
                                            <div v-else class="provider-logo-fallback">
                                                {{ name[0].toUpperCase() }}
                                            </div>
                                        </div>
                                    </div>
                                </v-card>
                            </div>
                            <div v-if="Object.keys(getTemplatesByType(tabType)).length === 0">
                                <v-alert type="info" variant="tonal" class="add-provider-empty">
                                    {{ tm('dialogs.addProvider.noTemplates') }}
                                </v-alert>
                            </div>
                        </div>
                    </v-window-item>
                </v-window>
            </v-card-text>
            <v-card-actions class="add-provider-dialog__actions">
                <v-spacer></v-spacer>
                <v-btn variant="tonal" class="add-provider-cancel" @click="closeDialog">
                    {{ tm('dialogs.config.cancel') }}
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script>
import { useModuleI18n } from '@/i18n/composables';
import { getProviderIcon, getProviderDescription } from '@/utils/providerUtils';

const AVAILABLE_PROVIDER_TABS = ['agent_runner', 'speech_to_text', 'text_to_speech', 'embedding', 'rerank'];

export default {
    name: 'AddNewProvider',
    props: {
        show: {
            type: Boolean,
            default: false
        },
        metadata: {
            type: Object,
            default: () => ({})
        },
        currentProviderType: {
            type: String,
            default: 'agent_runner'
        }
    },
    emits: ['update:show', 'select-template'],
    setup() {
        const { tm } = useModuleI18n('features/provider');
        return { tm };
    },
    data() {
        return {
            activeProviderTab: 'agent_runner'
        };
    },
    computed: {
        showDialog: {
            get() {
                return this.show;
            },
            set(value) {
                this.$emit('update:show', value);
            }
        },
    },
    watch: {
        show(value) {
            if (value) {
                this.syncActiveProviderTab();
            }
        },
        currentProviderType() {
            if (this.showDialog) {
                this.syncActiveProviderTab();
            }
        }
    },
    methods: {
        syncActiveProviderTab() {
            this.activeProviderTab = AVAILABLE_PROVIDER_TABS.includes(this.currentProviderType)
                ? this.currentProviderType
                : 'agent_runner';
        },

        closeDialog() {
            this.showDialog = false;
        },

        // 按提供商类型获取模板列表
        getTemplatesByType(type) {
            const templates = this.metadata.provider.config_template || {};
            const filtered = {};

            for (const [name, template] of Object.entries(templates)) {
                if (template.provider_type === type) {
                    filtered[name] = template;
                }
            }

            return filtered;
        },

        // 从工具函数导入
        getProviderIcon,

        // 获取提供商简介
        getProviderDescription(template, name) {
            return getProviderDescription(template, name, this.tm);
        },

        // 选择提供商模板
        selectProviderTemplate(name) {
            this.$emit('select-template', name);
            this.closeDialog();
        }
    }
}
</script>

<style scoped>
.add-provider-dialog {
    border: 1px solid rgba(var(--v-theme-border), 0.7);
    border-radius: 18px !important;
    background:
        linear-gradient(180deg, rgba(var(--v-theme-primary), 0.04), transparent 180px),
        rgb(var(--v-theme-surface));
    box-shadow: 0 24px 70px rgba(17, 24, 39, 0.16) !important;
    overflow: hidden;
}

.add-provider-dialog__title {
    padding: 22px 24px 14px;
    color: rgb(var(--v-theme-primaryText));
    font-size: 1.35rem;
    font-weight: 720;
    line-height: 1.25;
    letter-spacing: 0;
}

.add-provider-dialog__body {
    overflow-y: auto;
    padding: 12px 24px 8px !important;
}

.add-provider-tabs {
    min-height: 52px;
    border: 1px solid rgba(var(--v-theme-border), 0.7);
    border-radius: 12px;
    background: rgba(var(--v-theme-surface), 0.84);
    padding: 3px;
}

.add-provider-tabs :deep(.v-slide-group__content) {
    gap: 4px;
}

.add-provider-tabs :deep(.v-tab) {
    min-height: 44px;
    border-radius: 8px;
    letter-spacing: 0;
}

.add-provider-tabs :deep(.v-tab--selected) {
    background: rgba(var(--v-theme-primary), 0.1);
}

.add-provider-window {
    margin-top: 18px;
}

.add-provider-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
}

.add-provider-empty {
    border-radius: 12px;
}

.provider-card {
    transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
    height: 100%;
    cursor: pointer;
    overflow: hidden;
    position: relative;
    border-color: rgba(var(--v-theme-border), 0.7) !important;
    border-radius: 14px !important;
    background: rgba(var(--v-theme-surface), 0.96) !important;
    box-shadow: 0 12px 32px rgba(17, 24, 39, 0.05);
}

.provider-card:hover {
    transform: translateY(-2px);
    border-color: rgba(var(--v-theme-primary), 0.38) !important;
    box-shadow: 0 16px 36px rgba(17, 24, 39, 0.08);
}

.provider-card-content {
    display: flex;
    align-items: center;
    height: 100px;
    padding: 16px;
    position: relative;
    z-index: 2;
}

.provider-card-text {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
}

.provider-card-title {
    font-size: 15px;
    font-weight: 650;
    margin-bottom: 4px;
    padding: 0;
    letter-spacing: 0;
}

.provider-card-description {
    padding: 0;
    margin: 0;
}

.provider-card-logo {
    position: absolute;
    right: 0;
    top: 0;
    bottom: 0;
    width: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1;
    background: linear-gradient(90deg, transparent, rgba(var(--v-theme-on-surface), 0.03));
}

.provider-logo-img {
    width: 54px;
    height: 54px;
    opacity: 0.72;
    object-fit: contain;
}

.provider-logo-fallback {
    width: 50px;
    height: 50px;
    border-radius: 14px;
    background: rgba(var(--v-theme-primary), 0.1);
    color: rgb(var(--v-theme-primary));
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    font-weight: bold;
}

.add-provider-dialog__actions {
    padding: 12px 24px 20px !important;
}

.add-provider-cancel {
    min-width: 96px;
    height: 42px;
    max-height: 42px;
    border-radius: 8px;
    border: 1px solid rgba(var(--v-theme-border), 0.9);
    background: rgba(var(--v-theme-surface), 0.92);
    color: rgba(var(--v-theme-on-surface), 0.74);
    font-weight: 600;
    letter-spacing: 0;
}

.add-provider-cancel:hover {
    border-color: rgba(var(--v-theme-primary), 0.32);
    background: rgba(var(--v-theme-primary), 0.08);
    color: rgb(var(--v-theme-primary));
}

@media (max-width: 760px) {
    .add-provider-dialog__title {
        padding: 18px 18px 10px;
    }

    .add-provider-dialog__body {
        padding: 10px 18px 6px !important;
    }

    .add-provider-tabs {
        overflow-x: auto;
    }

    .add-provider-grid {
        grid-template-columns: 1fr;
    }

    .add-provider-dialog__actions {
        padding: 10px 18px 18px !important;
    }
}
</style>
