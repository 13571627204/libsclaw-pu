<template>
    <div class="conversation-page">
        <v-container fluid class="conversation-shell">
            <!-- 对话列表部分 -->
            <div class="conversation-page-head">
                <div class="conversation-title-block">
                    <span class="conversation-toolbar-title">{{ tm('history.title') }}</span>
                    <v-chip size="small" variant="tonal" color="primary" class="conversation-count-chip">
                        {{ pagination.total || 0 }}
                    </v-chip>
                </div>
                <div v-if="selectedItems.length > 0" class="conversation-batch-actions">
                    <v-btn
                        color="success"
                        prepend-icon="mdi-download"
                        variant="tonal"
                        @click="exportConversations"
                        :disabled="loading"
                        size="small"
                        class="conversation-toolbar-btn">
                        {{ tm('batch.exportSelected', { count: selectedItems.length }) }}
                    </v-btn>
                    <v-btn
                        color="error"
                        prepend-icon="mdi-delete"
                        variant="tonal"
                        @click="confirmBatchDelete"
                        :disabled="loading"
                        size="small"
                        class="conversation-toolbar-btn">
                        {{ tm('batch.deleteSelected', { count: selectedItems.length }) }}
                    </v-btn>
                </div>
            </div>

            <section class="conversation-filter-bar">
                    <v-row class="conversation-filter-grid" dense>
                        <v-col cols="12" sm="6" md="3">
                            <v-combobox v-model="platformFilter" :label="tm('filters.platform')"
                                :items="availablePlatforms" chips multiple clearable variant="solo-filled" flat
                                density="compact" hide-details class="conversation-filter-control">
                                <template v-slot:selection="{ item }">
                                    <v-chip size="small" label>
                                        {{ item.title }}
                                    </v-chip>
                                </template>
                            </v-combobox>
                        </v-col>

                        <v-col cols="12" sm="6" md="3">
                            <v-select v-model="messageTypeFilter" :label="tm('filters.type')" :items="messageTypeItems"
                                chips multiple clearable variant="solo-filled" density="compact" hide-details flat
                                class="conversation-filter-control">
                                <template v-slot:selection="{ item }">
                                    <v-chip size="small" variant="solo-filled" label>
                                        {{ item.title }}
                                    </v-chip>
                                </template>
                            </v-select>
                        </v-col>

                        <v-col cols="12" sm="12" md="3">
                            <v-text-field v-model="search" prepend-inner-icon="mdi-magnify"
                                :label="tm('filters.search')" hide-details density="compact" variant="solo-filled" flat
                                clearable class="conversation-filter-control"></v-text-field>
                        </v-col>

                        <v-col cols="12" md="3" class="conversation-filter-actions-col">
                            <div class="conversation-toolbar-actions">
                                <div class="conversation-display-toggle">
                                    <span class="conversation-display-label">{{ tm('table.headers.umo') }}</span>
                                    <v-btn-toggle
                                        v-model="umoDisplayMode"
                                        mandatory
                                        density="compact"
                                        divided
                                        variant="outlined"
                                        class="umo-header-toggle"
                                    >
                                        <v-btn value="parsed" size="x-small">
                                            {{ tm('table.umoDisplay.parsed') }}
                                        </v-btn>
                                        <v-btn value="raw" size="x-small">
                                            {{ tm('table.umoDisplay.raw') }}
                                        </v-btn>
                                    </v-btn-toggle>
                                </div>
                                <v-btn color="primary" prepend-icon="mdi-refresh" variant="tonal" @click="fetchConversations"
                                    :loading="loading" size="small" class="conversation-toolbar-btn">
                                    {{ tm('history.refresh') }}
                                </v-btn>
                            </div>
                        </v-col>
                    </v-row>
            </section>

            <v-card flat class="conversation-table-card">
                <v-card-text class="conversation-table-panel">
                    <v-data-table v-model="selectedItems" :headers="tableHeaders" :items="conversations"
                        :loading="loading" style="font-size: 12px;" density="comfortable" hide-default-footer
                        class="conversation-table elevation-0" :items-per-page="pagination.page_size"
                        :items-per-page-options="pageSizeOptions" show-select return-object
                        :disabled="loading" @update:options="handleTableOptions">
                        <template v-slot:item.title="{ item }">
                            <div class="conversation-title-cell">
                                <div class="conversation-title-row">
                                    <span class="conversation-title-text">{{ item.title || tm('status.noTitle') }}</span>
                                    <v-btn
                                        icon
                                        variant="plain"
                                        size="x-small"
                                        density="compact"
                                        :ripple="false"
                                        class="conversation-inline-edit"
                                        @click.stop="editConversation(item)"
                                        :disabled="loading"
                                    >
                                        <v-icon size="14">mdi-pencil</v-icon>
                                    </v-btn>
                                </div>
                                <span class="conversation-title-meta">{{ item.cid || tm('status.unknown') }}</span>
                            </div>
                        </template>

                        <template v-slot:item.umo_source="{ item }">
                            <div class="umo-source-cell">
                                <div class="umo-source-content">
                                    <template v-if="umoDisplayMode === 'parsed'">
                                        <div class="conversation-umo-stack">
                                            <UmoDisplay v-if="hasConversationUmoReadableName(item)"
                                                v-bind="getConversationUmoDisplayProps(item)" compact
                                                :show-info="false" :show-platform="false" :show-meta="false"
                                                class="conversation-umo-display" />
                                            <div class="conversation-umo-parsed">
                                                <v-chip size="x-small" label>
                                                    {{ getConversationUmoInfo(item).platform || tm('status.unknown') }}
                                                </v-chip>
                                                <span class="umo-separator">:</span>
                                                <v-chip size="x-small" label>
                                                    {{ getMessageTypeDisplay(getConversationUmoInfo(item).message_type) }}
                                                </v-chip>
                                                <span class="umo-separator">:</span>
                                                <span class="umo-session-id">{{ getConversationUmoInfo(item).session_id || tm('status.unknown') }}</span>
                                            </div>
                                        </div>
                                    </template>
                                    <span v-else class="umo-raw-text">{{ item.user_id || tm('status.unknown') }}</span>
                                </div>
                                <v-btn
                                    icon
                                    variant="plain"
                                    size="x-small"
                                    class="umo-copy-button"
                                    @click.stop="copyUmoSource(item)"
                                >
                                    <v-icon size="16">mdi-content-copy</v-icon>
                                </v-btn>
                            </div>
                        </template>

                        <template v-slot:item.created_at="{ item }">
                            {{ formatTimestamp(item.created_at) }}
                        </template>

                        <template v-slot:item.updated_at="{ item }">
                            {{ formatTimestamp(item.updated_at) }}
                        </template>

                        <template v-slot:item.actions="{ item }">
                            <div class="actions-wrapper">
                                <v-btn icon variant="text" size="small" class="action-button action-button--view"
                                    :title="tm('actions.view')"
                                    @click="viewConversation(item)" :disabled="loading">
                                    <v-icon size="17">mdi-eye</v-icon>
                                </v-btn>
                                <v-btn icon variant="text" size="small" class="action-button action-button--delete"
                                    :title="tm('actions.delete')"
                                    @click="confirmDeleteConversation(item)" :disabled="loading">
                                    <v-icon size="17">mdi-delete-outline</v-icon>
                                </v-btn>
                            </div>
                        </template>

                        <template v-slot:no-data>
                            <div class="d-flex flex-column align-center py-6">
                                <v-icon size="64" color="grey lighten-1">mdi-chat-remove</v-icon>
                                <span class="text-subtitle-1 text-disabled mt-3">{{ tm('status.noData') }}</span>
                            </div>
                        </template>
                    </v-data-table>

                    <!-- 分页控制 -->
                    <div class="conversation-pagination">
                        <!-- 每页大小选择器 -->
                        <div class="conversation-pagination-size">
                            <div class="d-flex align-center">
                                <span class="text-caption mr-2">{{ tm('pagination.itemsPerPage') }}:</span>
                                <v-select v-model="pagination.page_size" :items="pageSizeOptions" variant="outlined"
                                    density="compact" hide-details style="max-width: 100px;"
                                    :disabled="loading" @update:model-value="onPageSizeChange"></v-select>
                            </div>
                            <div class="text-caption ml-4">
                                {{ tm('pagination.showingItems', {
                                    start: Math.min((pagination.page - 1) * pagination.page_size + 1, pagination.total),
                                    end: Math.min(pagination.page * pagination.page_size, pagination.total),
                                    total: pagination.total
                                }) }}
                            </div>
                        </div>
                        <v-pagination v-model="pagination.page" :length="pagination.total_pages" :disabled="loading"
                            @update:model-value="fetchConversations" rounded="circle" :total-visible="7"></v-pagination>
                    </div>
                </v-card-text>
            </v-card>
        </v-container>

        <!-- 对话详情对话框 -->
        <v-dialog v-model="dialogView" max-width="980px" scrollable>
            <v-card class="conversation-detail-card">
                <v-card-title class="conversation-detail-title">
                    <div class="conversation-detail-title-main">
                        <div class="conversation-detail-heading">
                            <span class="conversation-detail-name text-truncate">{{ selectedConversation?.title || tm('status.noTitle') }}</span>
                            <UmoDisplay v-if="selectedConversation?.user_id && hasConversationUmoReadableName(selectedConversation)"
                                v-bind="getConversationUmoDisplayProps(selectedConversation)" compact :show-info="false"
                                :show-platform="false" :show-meta="false" class="conversation-umo-display" />
                            <div v-if="selectedConversation?.user_id"
                                class="conversation-umo-parsed conversation-detail-umo-parsed">
                                <v-chip size="x-small" label>
                                    {{ getConversationUmoInfo(selectedConversation).platform || tm('status.unknown') }}
                                </v-chip>
                                <span class="umo-separator">:</span>
                                <v-chip size="x-small" label>
                                    {{ getMessageTypeDisplay(getConversationUmoInfo(selectedConversation).message_type) }}
                                </v-chip>
                                <span class="umo-separator">:</span>
                                <span class="umo-session-id">{{ getConversationUmoInfo(selectedConversation).session_id || tm('status.unknown') }}</span>
                            </div>
                        </div>
                    </div>
                    <v-btn icon="mdi-close" variant="text" class="conversation-detail-close-btn"
                        @click="closeHistoryDialog" />
                </v-card-title>

                <v-card-text class="conversation-detail-body">
                    <div class="conversation-detail-toolbar">
                        <v-btn variant="tonal" size="small" class="conversation-detail-mode-btn"
                            @click="isEditingHistory = !isEditingHistory">
                            <v-icon class="mr-1">{{ isEditingHistory ? 'mdi-eye' : 'mdi-pencil' }}</v-icon>
                            {{ isEditingHistory ? tm('dialogs.view.previewMode') : tm('dialogs.view.editMode') }}
                        </v-btn>
                        <v-btn v-if="isEditingHistory" variant="tonal" size="small"
                            class="conversation-detail-save-btn"
                            :loading="savingHistory" @click="saveHistoryChanges">
                            <v-icon class="mr-1">mdi-content-save</v-icon>
                            {{ tm('dialogs.view.saveChanges') }}
                        </v-btn>
                    </div>

                    <!-- 编辑模式 - Monaco编辑器 -->
                    <div v-if="isEditingHistory" class="monaco-editor-container">
                        <VueMonacoEditor v-model:value="editedHistory" theme="vs-dark" language="json" :options="{
                            automaticLayout: true,
                            fontSize: 13,
                            tabSize: 2,
                            minimap: { enabled: false },
                            scrollBeyondLastLine: false,
                            wordWrap: 'on'
                        }" @editorDidMount="onMonacoMounted" />
                    </div>

                    <!-- 预览模式 - 聊天界面 -->
                    <div v-else class="conversation-messages-container"
                        ref="messagesContainer"
                        @wheel.prevent="onContainerWheel">
                        <!-- 空对话提示 -->
                        <div v-if="conversationHistory.length === 0" class="text-center py-5">
                            <v-icon size="48" color="grey">mdi-chat-remove</v-icon>
                            <p class="text-disabled mt-2">{{ tm('status.emptyContent') }}</p>
                        </div>

                        <!-- 消息列表组件 -->
                        <MessageList v-else :messages="formattedMessages" :isDark="isDark" />
                    </div>
                </v-card-text>

                <v-card-actions class="conversation-detail-actions">
                    <v-spacer></v-spacer>
                    <v-btn variant="tonal" class="conversation-detail-footer-close" @click="closeHistoryDialog">
                        {{ tm('dialogs.view.close') }}
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <!-- 编辑对话框 -->
        <v-dialog v-model="dialogEdit" max-width="540px">
            <v-card class="conversation-edit-card">
                <v-card-title class="conversation-edit-title">
                    <span class="conversation-edit-title-icon">
                        <v-icon size="22">mdi-pencil</v-icon>
                    </span>
                    <span>{{ tm('dialogs.edit.title') }}</span>
                </v-card-title>

                <v-card-text class="conversation-edit-body">
                    <v-form ref="form" v-model="valid">
                        <v-text-field v-model="editedItem.title" :label="tm('dialogs.edit.titleLabel')"
                            :placeholder="tm('dialogs.edit.titlePlaceholder')" variant="outlined" density="comfortable"
                            class="conversation-edit-field"></v-text-field>
                    </v-form>
                </v-card-text>

                <v-card-actions class="conversation-edit-actions">
                    <v-spacer></v-spacer>
                    <v-btn variant="tonal" class="conversation-edit-cancel-btn" @click="dialogEdit = false" :disabled="loading">
                        {{ tm('dialogs.edit.cancel') }}
                    </v-btn>
                    <v-btn color="primary" variant="flat" class="conversation-edit-save-btn" @click="saveConversation" :loading="loading">
                        {{ tm('dialogs.edit.save') }}
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <!-- 删除确认对话框 -->
        <v-dialog v-model="dialogDelete" max-width="460px" persistent>
            <v-card class="conversation-delete-dialog">
                <v-card-title class="conversation-delete-dialog__title">
                    <span class="conversation-delete-dialog__icon">
                        <v-icon size="24">mdi-trash-can-outline</v-icon>
                    </span>
                    <span>删除对话</span>
                </v-card-title>

                <v-card-text class="conversation-delete-dialog__body">
                    <p class="conversation-delete-dialog__message">
                        {{ tm('dialogs.delete.message', { title: selectedConversation?.title || tm('status.noTitle') }) }}
                    </p>
                    <div class="conversation-delete-dialog__target">
                        {{ selectedConversation?.title || tm('status.noTitle') }}
                    </div>
                </v-card-text>

                <v-card-actions class="conversation-delete-dialog__actions">
                    <v-spacer></v-spacer>
                    <v-btn class="conversation-delete-dialog__cancel" variant="text" @click="dialogDelete = false" :disabled="loading">
                        {{ tm('dialogs.delete.cancel') }}
                    </v-btn>
                    <v-btn class="conversation-delete-dialog__confirm" color="error" variant="tonal" @click="deleteConversation" :loading="loading">
                        确定删除
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <!-- 批量删除确认对话框 -->
        <v-dialog v-model="dialogBatchDelete" max-width="520px" persistent>
            <v-card class="conversation-delete-dialog">
                <v-card-title class="conversation-delete-dialog__title">
                    <span class="conversation-delete-dialog__icon">
                        <v-icon size="24">mdi-trash-can-outline</v-icon>
                    </span>
                    <span>批量删除对话</span>
                </v-card-title>

                <v-card-text class="conversation-delete-dialog__body">
                    <p class="conversation-delete-dialog__message">
                        {{ tm('dialogs.batchDelete.message', { count: selectedItems.length }) }}
                    </p>

                    <!-- 显示前几个要删除的对话 -->
                    <div v-if="selectedItems.length > 0" class="conversation-delete-dialog__target conversation-delete-dialog__target--list">
                        <div
                            v-for="item in selectedItems.slice(0, 5)"
                            :key="`${item.user_id}-${item.cid}`"
                            class="conversation-delete-dialog__target-item"
                        >
                            {{ item.title || tm('status.noTitle') }}
                        </div>
                        <div v-if="selectedItems.length > 5" class="conversation-delete-dialog__target-more">
                            {{ tm('dialogs.batchDelete.andMore', { count: selectedItems.length - 5 }) }}
                        </div>
                    </div>
                </v-card-text>

                <v-card-actions class="conversation-delete-dialog__actions">
                    <v-spacer></v-spacer>
                    <v-btn class="conversation-delete-dialog__cancel" variant="text" @click="dialogBatchDelete = false" :disabled="loading">
                        {{ tm('dialogs.batchDelete.cancel') }}
                    </v-btn>
                    <v-btn class="conversation-delete-dialog__confirm" color="error" variant="tonal" @click="batchDeleteConversations" :loading="loading">
                        确定删除
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>

        <!-- 消息提示 -->
        <v-snackbar :timeout="3000" elevation="6" :color="messageType" v-model="showMessage" location="top">
            {{ message }}
        </v-snackbar>
    </div>
</template>

<script>
import { isCancel } from 'axios';
import { debounce } from 'lodash';
import { VueMonacoEditor } from '@guolao/vue-monaco-editor';
import { conversationApi } from '@/api/v1';
import { useCommonStore } from '@/stores/common';
import { useCustomizerStore } from '@/stores/customizer';
import { useI18n, useModuleI18n } from '@/i18n/composables';
import MessageList from '@/components/chat/MessageList.vue';
import UmoDisplay from '@/components/shared/UmoDisplay.vue';
import {
    askForConfirmation as askForConfirmationDialog,
    useConfirmDialog
} from '@/utils/confirmDialog';
import { copyToClipboard } from '@/utils/clipboard';

export default {
    name: 'ConversationPage',
    components: {
        VueMonacoEditor,
        MessageList,
        UmoDisplay
    },

    setup() {
        const { t, locale } = useI18n();
        const { tm } = useModuleI18n('features/conversation');
        const customizerStore = useCustomizerStore();
        const confirmDialog = useConfirmDialog();

        return {
            t,
            tm,
            locale,
            customizerStore,
            confirmDialog
        };
    },

    data() {
        return {
            // 表格数据
            conversations: [],
            search: '',
            headers: [],
            selectedItems: [], // 批量选择的项目

            // 筛选条件
            platformFilter: [],
            messageTypeFilter: [],
            lastAppliedFilters: null, // 记录上次应用的筛选条件

            // 分页数据
            pagination: {
                page: 1,
                page_size: 20,
                total: 0,
                total_pages: 0
            },
            pageSizeOptions: [10, 20, 50, 100], // 每页大小选项

            // 对话框控制
            dialogView: false,
            dialogEdit: false,
            dialogDelete: false,
            dialogBatchDelete: false, // 批量删除对话框

            // 选中的对话
            selectedConversation: null,
            conversationHistory: [],

            // 编辑表单
            editedItem: {
                user_id: '',
                cid: '',
                title: ''
            },

            // 表单验证
            valid: true,

            // 状态控制
            loading: false,
            showMessage: false,
            message: '',
            messageType: 'success',

            // 对话历史编辑
            isEditingHistory: false,
            editedHistory: '',
            savingHistory: false,
            monacoEditor: null,
            umoDisplayMode: 'parsed',

            commonStore: useCommonStore()
        }
    },

    watch: {
        // 监听筛选条件变化，使用防抖处理
        platformFilter() {
            this.debouncedApplyFilters();
        },
        messageTypeFilter() {
            this.debouncedApplyFilters();
        },
        search() {
            this.debouncedApplyFilters();
        }
    },

    created() {
        this.debouncedApplyFilters = debounce(() => {
            // 重置到第一页
            this.pagination.page = 1;
            this.fetchConversations();
        }, 300);
    },

    computed: {
        // 动态表头
        tableHeaders() {
            return [
                { title: this.tm('table.headers.title'), key: 'title', sortable: true, minWidth: '80px', width: '200px' },
                { title: this.tm('table.headers.umo'), key: 'umo_source', sortable: false, minWidth: '280px', width: '360px' },
                { title: this.tm('table.headers.createdAt'), key: 'created_at', sortable: true, width: '180px' },
                { title: this.tm('table.headers.updatedAt'), key: 'updated_at', sortable: true, width: '180px' },
                { title: this.tm('table.headers.actions'), key: 'actions', sortable: false, align: 'center' }
            ];
        },

        // 可用平台列表
        availablePlatforms() {
            const platforms = []
            // 解析 tutorial_map
            const tutorialMap = this.commonStore.tutorial_map;
            for (const platform in tutorialMap) {
                if (tutorialMap.hasOwnProperty(platform)) {
                    platforms.push({
                        title: platform,
                        value: platform
                    })
                }
            }
            return platforms;
        },

        // 可用消息类型列表
        messageTypeItems() {
            return [
                { title: this.tm('messageTypes.group'), value: 'GroupMessage' },
                { title: this.tm('messageTypes.friend'), value: 'FriendMessage' },
            ];
        },

        // 当前的筛选条件对象
        currentFilters() {
            const platforms = this.platformFilter.map(item =>
                typeof item === 'object' ? item.value : item
            );
            return {
                platforms: platforms,
                messageTypes: this.messageTypeFilter,
                search: this.search
            };
        },

        // 检测是否为暗色模式
        isDark() {
            console.log('isDark', this.customizerStore.uiTheme);
            return this.customizerStore.uiTheme === 'PurpleThemeDark';
        },

        // 将对话历史转换为 MessageList 组件期望的格式
        formattedMessages() {
            // 按 tool_call_id 索引 tool 角色消息的执行结果
            const toolResultsById = {};
            for (const msg of this.conversationHistory) {
                if (msg.role === 'tool' && msg.tool_call_id) {
                    toolResultsById[msg.tool_call_id] = msg.content;
                }
            }

            return this.conversationHistory
                // tool / system 等非聊天角色不直接渲染为气泡，避免大文本走 markdown 路径卡死页面
                .filter(msg => msg.role === 'user' || msg.role === 'assistant')
                .map(msg => {
                    console.log('处理消息:', msg.role, msg.content);

                    const messageParts = this.convertContentToMessageParts(msg.content)
                        // 丢弃 convertContentToMessageParts 兜底插入的空 plain，避免 assistant 仅有工具调用时渲染空气泡
                        .filter(part => part.type !== 'plain' || (part.text && part.text.trim()));

                    // 把 OpenAI 风格的 assistant.tool_calls 转成 MessageList 已支持的 tool_call part
                    if (msg.role === 'assistant' && Array.isArray(msg.tool_calls) && msg.tool_calls.length) {
                        const toolCalls = msg.tool_calls.map(tc => {
                            const fn = tc.function || {};
                            return {
                                id: tc.id,
                                name: fn.name || tc.name,
                                args: fn.arguments ?? tc.arguments,
                                result: toolResultsById[tc.id],
                                // 历史回放无真实耗时数据：
                                // ts: 0  → ToolCallCard.toolCallDuration 在 startTime<=0 时早退，跳过时长显示
                                // finished_ts: 1 → MessageList.toolCallStatusText 视为已完成（避免误显示"运行中"）
                                ts: 0,
                                finished_ts: 1,
                            };
                        });
                        messageParts.push({ type: 'tool_call', tool_calls: toolCalls });
                    }

                    const finalParts = messageParts.length
                        ? messageParts
                        : [{ type: 'plain', text: '' }];

                    return {
                        content: {
                            type: msg.role === 'user' ? 'user' : 'bot',
                            message: finalParts,
                        }
                    };
                });
        }
    },

    mounted() {
        this.fetchConversations();
    },

    methods: {
        // Monaco编辑器挂载后的回调
        onMonacoMounted(editor) {
            this.monacoEditor = editor;
            // 添加JSON格式校验
            editor.onDidChangeModelContent(() => {
                try {
                    JSON.parse(this.editedHistory);
                    // 有效的JSON格式
                    editor.getAction('editor.action.formatDocument').run();
                } catch (e) {
                    // 无效的JSON格式，不做处理，Monaco编辑器会自动提示
                }
            });
        },

        // 处理表格选项变更（页面大小等）
        handleTableOptions(options) {
            // 处理页面大小变更
            if (options.itemsPerPage !== this.pagination.page_size) {
                this.pagination.page_size = options.itemsPerPage;
                this.pagination.page = 1; // 重置到第一页
                this.fetchConversations();
            }
        },

        // 从会话ID解析平台和消息类型信息
        parseSessionId(userId) {
            if (!userId) return { platform: 'default', messageType: 'default', sessionId: '' };

            // 使用冒号进行分割，格式: platform:messageType:sessionId
            const parts = userId.split(':');

            if (parts.length >= 3) {
                return {
                    platform: parts[0] || 'default',
                    messageType: parts[1] || 'default',
                    sessionId: parts.slice(2).join(':') // 保留可能包含冒号的后续部分
                };
            }

            return { platform: 'default', messageType: 'default', sessionId: userId };
        },

        // 获取消息类型的显示文本
        getMessageTypeDisplay(messageType) {
            const typeMap = {
                'GroupMessage': this.tm('messageTypes.group'),
                'group': this.tm('messageTypes.group'),
                'FriendMessage': this.tm('messageTypes.friend'),
                'friend': this.tm('messageTypes.friend'),
                'private': this.tm('messageTypes.friend'),
                'default': this.tm('messageTypes.unknown')
            };

            return typeMap[messageType] || typeMap.default;
        },

        getConversationUmoInfo(item) {
            const umo = item?.user_id || item?.umo_info?.umo || '';
            const parsed = this.parseSessionId(umo);
            const info = item?.umo_info || {};
            return {
                umo,
                platform: info.platform || parsed.platform,
                message_type: info.message_type || parsed.messageType,
                session_id: info.session_id || parsed.sessionId,
                auto_name: info.auto_name || '',
                user_alias: info.user_alias || '',
                display_name: info.display_name || umo
            };
        },

        getConversationUmoDisplayProps(item) {
            const info = this.getConversationUmoInfo(item);
            return {
                umo: info.umo || this.tm('status.unknown'),
                platform: info.platform,
                messageType: info.message_type,
                sessionId: info.session_id,
                autoName: info.auto_name,
                userAlias: info.user_alias
            };
        },

        hasConversationUmoReadableName(item) {
            const info = this.getConversationUmoInfo(item);
            return Boolean(info.user_alias || info.auto_name);
        },

        formatUmoSource(item) {
            if (this.umoDisplayMode === 'raw') {
                return item?.user_id || this.tm('status.unknown');
            }

            const info = this.getConversationUmoInfo(item);
            const platform = info.platform || this.tm('status.unknown');
            const messageType = this.getMessageTypeDisplay(info.message_type);
            const sessionId = info.session_id || this.tm('status.unknown');
            return `${platform}:${messageType}:${sessionId}`;
        },

        async copyUmoSource(item) {
            const ok = await copyToClipboard(this.formatUmoSource(item));
            if (ok) {
                this.showSuccessMessage(this.tm('messages.copySuccess'));
            } else {
                this.showErrorMessage(this.tm('messages.copyError'));
            }
        },

        // 获取对话列表
        fetchConversations: (() => {
            let controller = new AbortController();

            return async function () {
                // 新请求前停止之前的请求
                controller?.abort()
                controller = new AbortController();

                this.loading = true;
                try {
                    // 准备请求参数，包含分页和筛选条件
                    const params = {
                        page: this.pagination.page,
                        page_size: this.pagination.page_size
                    };

                    // 添加筛选条件 - 处理combobox的混合数据格式
                    if (this.platformFilter.length > 0) {
                        const platforms = this.platformFilter.map(item =>
                            typeof item === 'object' ? item.value : item
                        );
                        params.platforms = platforms.join(',');
                    }

                    if (this.messageTypeFilter.length > 0) {
                        params.message_types = this.messageTypeFilter.join(',');
                    }

                    if (this.search) {
                        params.search = this.search.trim();
                    }

                    // 添加排除条件
                    params.exclude_ids = 'astrbot';
                    params.exclude_platforms = 'webchat';

                    const response = await conversationApi.list(params, {
                        signal: controller.signal,
                    });

                    this.lastAppliedFilters = { ...this.currentFilters }; // 记录已应用的筛选条件

                    if (response.data.status === "ok") {
                        const data = response.data.data;

                        if (!data || !data.conversations) {
                            console.error('API 返回数据格式不符合预期:', data);
                            this.showErrorMessage(this.tm('messages.fetchError'));
                            return;
                        }

                        // 处理会话数据，解析sessionId
                        this.conversations = (data.conversations || []).map(conv => {
                            // 为每个会话添加会话信息
                            const umoInfo = this.getConversationUmoInfo(conv);
                            conv.sessionInfo = {
                                platform: umoInfo.platform,
                                messageType: umoInfo.message_type,
                                sessionId: umoInfo.session_id
                            };
                            return conv;
                        });

                        // 更新分页信息
                        if (data.pagination) {
                            this.pagination = {
                                page: data.pagination.page || 1,
                                page_size: data.pagination.page_size || 20,
                                total: data.pagination.total || 0,
                                total_pages: data.pagination.total_pages || 1
                            };
                        } else {
                            console.warn('API 响应中没有分页信息');
                        }
                    } else {
                        this.showErrorMessage(response.data.message || this.tm('messages.fetchError'));
                    }
                } catch (error) {
                    if (isCancel(error)) return;
                    
                    console.error('获取对话列表出错:', error);
                    if (error.response) {
                        console.error('错误响应数据:', error.response.data);
                        console.error('错误状态码:', error.response.status);
                    }
                    this.showErrorMessage(error.response?.data?.message || error.message || this.tm('messages.fetchError'));
                } finally {
                    this.loading = false;
                }
            }
        })(),

        // 查看对话详情
        async viewConversation(item) {
            this.selectedConversation = item;
            this.loading = true;
            this.isEditingHistory = false;

            try {
                console.log(`正在请求对话详情，user_id=${item.user_id}, cid=${item.cid}`);
                const response = await conversationApi.get(item.user_id, item.cid);

                if (response.data.status === "ok") {
                    try {
                        const detailData = response.data.data || {};
                        const mergedConversation = { ...this.selectedConversation, ...detailData };
                        const umoInfo = this.getConversationUmoInfo(mergedConversation);
                        mergedConversation.sessionInfo = {
                            platform: umoInfo.platform,
                            messageType: umoInfo.message_type,
                            sessionId: umoInfo.session_id
                        };
                        this.selectedConversation = mergedConversation;

                        const historyData = detailData.history || '[]';
                        this.conversationHistory = JSON.parse(historyData);
                        this.editedHistory = JSON.stringify(this.conversationHistory, null, 2);
                    } catch (e) {
                        this.conversationHistory = [];
                        this.editedHistory = '[]';
                        console.error('解析对话历史失败:', e);
                    }
                    this.dialogView = true;
                } else {
                    this.showErrorMessage(response.data.message || this.tm('messages.historyError'));
                }
            } catch (error) {
                console.error('获取对话详情出错:', error);
                this.showErrorMessage(error.response?.data?.message || error.message || this.tm('messages.historyError'));
            } finally {
                this.loading = false;
            }
        },

        // 保存对话历史的修改
        async saveHistoryChanges() {
            if (!this.selectedConversation) return;

            this.savingHistory = true;

            try {
                // 验证JSON格式
                let historyJson;
                try {
                    historyJson = JSON.parse(this.editedHistory);
                } catch (e) {
                    this.showErrorMessage(this.tm('messages.invalidJson'));
                    return;
                }

                const response = await conversationApi.replaceMessages(
                    this.selectedConversation.user_id,
                    this.selectedConversation.cid,
                    {
                    history: historyJson
                    }
                );

                if (response.data.status === "ok") {
                    this.conversationHistory = historyJson;
                    this.showSuccessMessage(this.tm('messages.historySaveSuccess'));
                    this.isEditingHistory = false;
                } else {
                    this.showErrorMessage(response.data.message || this.tm('messages.historySaveError'));
                }
            } catch (error) {
                console.error('更新对话历史出错:', error);
                this.showErrorMessage(error.response?.data?.message || error.message || this.tm('messages.historySaveError'));
            } finally {
                this.savingHistory = false;
            }
        },

        // 关闭对话历史对话框
        async closeHistoryDialog() {
            if (this.isEditingHistory) {
                if (await askForConfirmationDialog(this.tm('dialogs.view.confirmClose'), this.confirmDialog)) {
                    this.dialogView = false;
                }
            } else {
                this.dialogView = false;
            }
        },

        // 编辑对话
        editConversation(item) {
            this.selectedConversation = item;
            this.editedItem = Object.assign({}, item);
            this.dialogEdit = true;
        },

        // 保存编辑后的对话
        async saveConversation() {
            if (!this.$refs.form.validate()) return;

            this.loading = true;
            try {
                const response = await conversationApi.update(
                    this.editedItem.user_id,
                    this.editedItem.cid,
                    {
                    title: this.editedItem.title
                    }
                );

                if (response.data.status === "ok") {
                    // 更新本地数据
                    const index = this.conversations.findIndex(item => item.user_id === this.editedItem.user_id && item.cid === this.editedItem.cid
                    );

                    if (index !== -1) {
                        this.conversations[index].title = this.editedItem.title;
                    }

                    this.dialogEdit = false;
                    this.showSuccessMessage(this.tm('messages.saveSuccess'));

                    // 刷新数据
                    this.fetchConversations();
                } else {
                    this.showErrorMessage(response.data.message || this.tm('messages.saveError'));
                }
            } catch (error) {
                this.showErrorMessage(error.response?.data?.message || error.message || this.tm('messages.saveError'));
            } finally {
                this.loading = false;
            }
        },

        // 确认删除对话
        confirmDeleteConversation(item) {
            this.selectedConversation = item;
            this.dialogDelete = true;
        },

        // 删除对话
        async deleteConversation() {
            this.loading = true;
            try {
                const response = await conversationApi.delete(
                    this.selectedConversation.user_id,
                    this.selectedConversation.cid
                );

                if (response.data.status === "ok") {
                    const index = this.conversations.findIndex(item => item.user_id === this.selectedConversation.user_id && item.cid === this.selectedConversation.cid
                    );

                    if (index !== -1) {
                        this.conversations.splice(index, 1);
                    }

                    this.dialogDelete = false;
                    this.showSuccessMessage(this.tm('messages.deleteSuccess'));
                } else {
                    this.showErrorMessage(response.data.message || this.tm('messages.deleteError'));
                }
            } catch (error) {
                this.showErrorMessage(error.response?.data?.message || error.message || this.tm('messages.deleteError'));
            } finally {
                this.loading = false;
                this.selectedItems = this.selectedItems.filter(item =>
                    !(item.user_id === this.selectedConversation.user_id && item.cid === this.selectedConversation.cid)
                );
                this.selectedConversation = null;
            }
        },

        // 处理页面大小变更
        onPageSizeChange() {
            this.pagination.page = 1; // 重置到第一页
            this.fetchConversations();
        },

        // 确认批量删除
        confirmBatchDelete() {
            if (this.selectedItems.length === 0) {
                this.showErrorMessage(this.tm('messages.noItemSelected'));
                return;
            }
            this.dialogBatchDelete = true;
        },

        // 从选择中移除项目
        removeFromSelection(item) {
            const index = this.selectedItems.findIndex(selected =>
                selected.user_id === item.user_id && selected.cid === item.cid
            );
            if (index !== -1) {
                this.selectedItems.splice(index, 1);
            }
        },

        // 批量删除对话
        async batchDeleteConversations() {
            if (this.selectedItems.length === 0) {
                this.showErrorMessage(this.tm('messages.noItemSelected'));
                return;
            }

            this.loading = true;
            try {
                // 准备批量删除的数据
                const conversations = this.selectedItems.map(item => ({
                    user_id: item.user_id,
                    cid: item.cid
                }));

                const response = await conversationApi.batchDelete({
                    conversations: conversations
                });

                if (response.data.status === "ok") {
                    const result = response.data.data;
                    this.dialogBatchDelete = false;
                    this.selectedItems = []; // 清空选择

                    // 显示结果消息
                    if (result.failed_count > 0) {
                        this.showErrorMessage(
                            this.tm('messages.batchDeletePartial', {
                                deleted: result.deleted_count,
                                failed: result.failed_count
                            })
                        );
                    } else {
                        this.showSuccessMessage(
                            this.tm('messages.batchDeleteSuccess', {
                                count: result.deleted_count
                            })
                        );
                    }

                    // 刷新列表
                    this.fetchConversations();
                } else {
                    this.showErrorMessage(response.data.message || this.tm('messages.batchDeleteError'));
                }
            } catch (error) {
                console.error('批量删除对话出错:', error);
                this.showErrorMessage(error.response?.data?.message || error.message || this.tm('messages.batchDeleteError'));
            } finally {
                this.loading = false;
            }
        },

        // 导出选中的对话
        async exportConversations() {
            if (this.selectedItems.length === 0) {
                this.showErrorMessage(this.tm('messages.noItemSelectedForExport'));
                return;
            }

            this.loading = true;
            try {
                // 准备导出的数据
                const conversations = this.selectedItems.map(item => ({
                    user_id: item.user_id,
                    cid: item.cid
                }));

                const response = await conversationApi.export({
                    conversations: conversations
                });

                // 创建一个下载链接
                const url = window.URL.createObjectURL(response.data);
                const link = document.createElement('a');
                link.href = url;
                
                // 生成文件名（使用时间戳）
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
                const filename = `conversations_export_${timestamp}.jsonl`;
                
                link.setAttribute('download', filename);
                document.body.appendChild(link);
                link.click();
                
                // 清理
                link.remove();
                window.URL.revokeObjectURL(url);
                
                this.showSuccessMessage(this.tm('messages.exportSuccess'));
            } catch (error) {
                console.error(this.tm('messages.exportError'), error);
                this.showErrorMessage(error.response?.data?.message || error.message || this.tm('messages.exportError'));
            } finally {
                this.loading = false;
            }
        },

        // 格式化时间戳
        formatTimestamp(timestamp) {
            if (!timestamp) return this.tm('status.unknown');

            const date = new Date(timestamp * 1000);
            const locale = this.locale || 'zh-CN';
            return new Intl.DateTimeFormat(locale, {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            }).format(date);
        },

        // 显示成功消息
        showSuccessMessage(message) {
            this.message = message;
            this.messageType = 'success';
            this.showMessage = true;
        },

        // 显示错误消息
        showErrorMessage(message) {
            this.message = message;
            this.messageType = 'error';
            this.showMessage = true;
        },

        // 将消息内容转换为 MessagePart[] 格式
        convertContentToMessageParts(content) {
            const parts = [];
            
            if (typeof content === 'string') {
                // 纯文本内容
                if (content.trim()) {
                    parts.push({
                        type: 'plain',
                        text: content
                    });
                }
            } else if (Array.isArray(content)) {
                // 数组格式（OpenAI 格式）
                content.forEach(item => {
                    if (item.type === 'text' && item.text) {
                        parts.push({
                            type: 'plain',
                            text: item.text
                        });
                    } else if (item.type === 'image_url' && item.image_url?.url) {
                        parts.push({
                            type: 'image',
                            embedded_url: item.image_url.url
                        });
                    }
                });
            } else if (typeof content === 'object' && content !== null) {
                // 对象格式，尝试提取文本和图片
                const textParts = [];
                for (const [key, value] of Object.entries(content)) {
                    if (typeof value === 'string' && value.trim()) {
                        textParts.push(value);
                    }
                }
                if (textParts.length > 0) {
                    parts.push({
                        type: 'plain',
                        text: textParts.join('\n')
                    });
                }
            }
            
            // 如果没有提取到任何内容，添加一个空文本
            if (parts.length === 0) {
                parts.push({
                    type: 'plain',
                    text: ''
                });
            }
            
            return parts;
        },

        // Manually handle wheel scrolling inside the dialog preview container.
        onContainerWheel(event) {
            const el = this.$refs.messagesContainer;
            if (!el) return;
            el.scrollTop += event.deltaY;
        },

        // 从内容中提取文本（保留用于其他用途）
        extractTextFromContent(content) {
            if (typeof content === 'string') {
                return content;
            } else if (Array.isArray(content)) {
                return content.filter(item => item.type === 'text')
                    .map(item => item.text)
                    .join('\n');
            } else if (typeof content === 'object') {
                return Object.values(content).filter(val => typeof val === 'string').join('');
            }
            return '';
        },

        // 从内容中提取图片URL（保留用于其他用途）
        extractImagesFromContent(content) {
            if (Array.isArray(content)) {
                return content.filter(item => item.type === 'image_url')
                    .map(item => item.image_url?.url)
                    .filter(url => url);
            }
            return [];
        }
    }
}
</script>

<style>
.conversation-page {
    min-height: 100%;
    background:
        linear-gradient(180deg, rgba(var(--v-theme-primary), 0.05), transparent 260px),
        rgb(var(--v-theme-background));
}

.conversation-shell {
    max-width: 1420px;
    padding: 22px 32px 32px !important;
}

.conversation-page-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 14px;
    padding: 0 2px;
}

.conversation-title-block {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
}

.conversation-batch-actions {
    display: inline-flex;
    align-items: center;
    gap: 8px;
}

.conversation-filter-bar {
    margin-bottom: 12px;
    border: 1px solid rgba(var(--v-theme-border), 0.52);
    border-radius: 12px;
    background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 251, 255, 0.86)),
        rgb(var(--v-theme-surface));
    padding: 12px 14px;
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.04);
}

.conversation-table-card {
    border: 1px solid rgba(var(--v-theme-border), 0.54);
    border-radius: 12px !important;
    background: rgb(var(--v-theme-surface)) !important;
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.045);
    overflow: hidden;
}

.conversation-toolbar-title {
    color: rgb(var(--v-theme-primaryText));
    font-size: 21px;
    font-weight: 720;
    line-height: 1.25;
    letter-spacing: 0;
    white-space: nowrap;
}

.conversation-count-chip {
    min-width: 32px;
    justify-content: center;
    font-weight: 650;
    border-radius: 999px;
    background: rgba(var(--v-theme-primary), 0.09) !important;
}

.conversation-filter-grid {
    min-width: 0;
    margin: 0 !important;
}

.conversation-filter-grid .v-col {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}

.conversation-filter-control .v-field {
    min-height: 42px;
    border: 1px solid rgba(var(--v-theme-border), 0.48);
    border-radius: 9px;
    background: rgba(255, 255, 255, 0.92) !important;
    box-shadow: none !important;
}

.conversation-filter-control .v-field__input {
    min-height: 42px;
    padding-top: 8px;
    padding-bottom: 8px;
}

.conversation-filter-control .v-field__prepend-inner {
    color: rgba(var(--v-theme-primary), 0.72);
}

.conversation-filter-control .v-field-label--floating {
    display: none;
}

.conversation-selected-text {
    min-width: 0;
    overflow: hidden;
    color: rgba(var(--v-theme-on-surface), 0.82);
    font-size: 13px;
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.conversation-selected-count {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 24px;
    height: 20px;
    margin-left: 6px;
    border-radius: 999px;
    background: rgba(var(--v-theme-primary), 0.09);
    color: rgb(var(--v-theme-primary));
    font-size: 11px;
    font-weight: 700;
}

.conversation-toolbar-actions {
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    width: 100%;
}

.conversation-filter-actions-col {
    display: flex;
    align-items: center;
    justify-content: flex-end;
}

.conversation-display-toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 42px;
    border: 0;
    border-radius: 0;
    background: transparent;
    padding: 0;
}

.conversation-display-label {
    color: rgba(var(--v-theme-on-surface), 0.52);
    font-size: 12px;
    font-weight: 650;
    white-space: nowrap;
}

.conversation-toolbar-btn {
    height: 42px !important;
    max-height: 42px;
    border-radius: 8px !important;
    font-weight: 650;
    letter-spacing: 0;
}

.conversation-table-panel {
    padding: 0 !important;
    background: rgb(var(--v-theme-surface));
}

.conversation-table {
    border-bottom: 1px solid rgba(var(--v-theme-border), 0.52);
}

.conversation-table .v-data-table__th {
    height: 42px !important;
    border-bottom: 1px solid rgba(var(--v-theme-border), 0.56) !important;
    background: rgba(248, 250, 252, 0.72) !important;
    color: rgba(var(--v-theme-on-surface), 0.68);
    font-size: 12px;
    font-weight: 720 !important;
    letter-spacing: 0;
    white-space: nowrap;
}

.conversation-table tbody tr {
    transition: background-color 0.16s ease;
}

.conversation-table tbody tr:hover {
    background: rgba(var(--v-theme-primary), 0.035) !important;
}

.conversation-table td {
    border-bottom: 1px solid rgba(var(--v-theme-border), 0.44) !important;
    color: rgba(var(--v-theme-on-surface), 0.82);
    padding-top: 6px !important;
    padding-bottom: 6px !important;
}

.conversation-pagination {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 12px;
    min-height: 56px;
    padding: 8px 18px;
    border-top: 1px solid rgba(var(--v-theme-border), 0.44);
    background: rgba(250, 251, 253, 0.84);
}

.conversation-pagination-size {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    border: 0;
    border-radius: 0;
    background: transparent;
    padding: 0;
}

.conversation-pagination-size .v-field {
    min-height: 32px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.9);
}

.conversation-pagination-size .v-field__input {
    min-height: 32px;
    padding-top: 4px;
    padding-bottom: 4px;
}

.conversation-pagination .v-pagination__item,
.conversation-pagination .v-pagination__prev,
.conversation-pagination .v-pagination__next {
    width: 34px;
    height: 34px;
    min-width: 34px;
}

.actions-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    min-width: 88px;
}

.action-button {
    width: 32px !important;
    height: 32px !important;
    min-width: 32px !important;
    border: 1px solid rgba(var(--v-theme-border), 0.46);
    border-radius: 9px !important;
    background: rgba(247, 250, 253, 0.9) !important;
    color: rgba(var(--v-theme-on-surface), 0.68) !important;
    opacity: 1;
    transition:
        border-color 0.16s ease,
        background-color 0.16s ease,
        color 0.16s ease,
        transform 0.16s ease,
        box-shadow 0.16s ease;
}

.action-button:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
}

.action-button--view {
    border-color: rgba(56, 143, 196, 0.18);
    background: rgba(232, 244, 252, 0.95) !important;
    color: #236f9f !important;
}

.action-button--view:hover {
    border-color: rgba(56, 143, 196, 0.34);
    background: rgba(220, 238, 249, 0.98) !important;
    color: #1f628f !important;
}

.action-button--delete {
    border-color: rgba(229, 81, 81, 0.16);
    background: rgba(255, 241, 241, 0.95) !important;
    color: #c33d3d !important;
}

.action-button--delete:hover {
    border-color: rgba(229, 81, 81, 0.32);
    background: rgba(255, 231, 231, 0.98) !important;
    color: #b42323 !important;
}

.monaco-editor-container {
    height: min(58vh, 560px);
    border: 1px solid rgba(var(--v-theme-border), 0.5);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}

/* 聊天消息容器样式 */
.conversation-messages-container {
    max-height: min(58vh, 560px);
    min-height: 420px;
    overflow-y: auto;
    padding: 18px 20px;
    border: 1px solid rgba(var(--v-theme-border), 0.48);
    border-radius: 14px;
    background:
        linear-gradient(180deg, rgba(var(--v-theme-primary), 0.025), rgba(255, 255, 255, 0.96)),
        rgb(var(--v-theme-surface));
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.86);
}

/* 让 ToolCallCard 内部的 args/result 自然展开，由外层容器统一滚动，避免双滚动条 */
.conversation-messages-container .detail-json,
.conversation-messages-container .detail-result {
    max-height: none;
    overflow: visible;
}

/* 历史回放无真实状态数据，隐藏 IPython 工具的"已完成"标签，与其它工具卡片保持一致 */
.conversation-messages-container .tool-call-inline-status {
    display: none;
}

/* 暗色模式下的聊天消息容器 */
.v-theme--dark .conversation-messages-container {
    background-color: #1e1e1e;
}

/* 对话详情卡片 */
.conversation-detail-card {
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    border: 1px solid rgba(var(--v-theme-border), 0.68);
    border-radius: 18px !important;
    background:
        linear-gradient(180deg, rgba(var(--v-theme-primary), 0.04), transparent 220px),
        rgb(var(--v-theme-surface));
    box-shadow: 0 24px 72px rgba(15, 23, 42, 0.2) !important;
    overflow: hidden;
}

.conversation-detail-title {
    display: flex;
    min-height: 98px;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    padding: 20px 24px 18px !important;
    border-bottom: 1px solid rgba(var(--v-theme-border), 0.56);
    background: rgba(255, 255, 255, 0.86);
}

.conversation-detail-title-main {
    display: flex;
    min-width: 0;
    align-items: flex-start;
    flex: 1 1 auto;
}

.conversation-detail-close-btn {
    width: 38px;
    height: 38px;
    border-radius: 10px !important;
    background: rgba(var(--v-theme-on-surface), 0.045);
    color: rgba(var(--v-theme-on-surface), 0.62);
}

.conversation-detail-close-btn:hover {
    background: rgba(var(--v-theme-primary), 0.09);
    color: rgb(var(--v-theme-primary));
}

.conversation-detail-heading {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 0;
    width: 100%;
}

.conversation-detail-name {
    color: rgba(var(--v-theme-on-surface), 0.92);
    font-size: 20px;
    font-weight: 760;
    line-height: 1.32;
    letter-spacing: 0;
}

.conversation-detail-body {
    flex: 1 1 auto;
    min-height: 0;
    padding: 16px 22px 12px !important;
    background: rgba(248, 250, 252, 0.62);
}

.conversation-detail-toolbar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 14px;
    padding: 10px 12px;
    border: 1px solid rgba(var(--v-theme-border), 0.48);
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.9);
}

.conversation-detail-mode-btn,
.conversation-detail-save-btn,
.conversation-detail-footer-close {
    height: 38px !important;
    border-radius: 8px !important;
    padding-inline: 14px !important;
    font-weight: 650;
    letter-spacing: 0;
}

.conversation-detail-mode-btn {
    border: 1px solid rgba(56, 143, 196, 0.16);
    background: rgba(232, 244, 252, 0.95) !important;
    color: #236f9f !important;
}

.conversation-detail-mode-btn:hover {
    border-color: rgba(56, 143, 196, 0.28);
    background: rgba(220, 238, 249, 0.98) !important;
    color: #1f628f !important;
}

.conversation-detail-save-btn {
    border: 1px solid rgba(31, 151, 111, 0.16);
    background: rgba(228, 247, 240, 0.95) !important;
    color: #17795c !important;
}

.conversation-detail-save-btn:hover {
    border-color: rgba(31, 151, 111, 0.3);
    background: rgba(215, 242, 232, 0.98) !important;
    color: #12684f !important;
}

.conversation-detail-actions {
    padding: 14px 22px 20px !important;
    border-top: 1px solid rgba(var(--v-theme-border), 0.54);
    background: rgba(255, 255, 255, 0.9);
}

.conversation-detail-footer-close {
    border: 1px solid rgba(var(--v-theme-border), 0.76);
    background: rgba(255, 255, 255, 0.9) !important;
    color: rgba(var(--v-theme-on-surface), 0.74) !important;
}

.conversation-detail-footer-close:hover {
    background: rgba(var(--v-theme-on-surface), 0.055) !important;
    color: rgb(var(--v-theme-on-surface)) !important;
}

.conversation-edit-card {
    border: 1px solid rgba(var(--v-theme-border), 0.68);
    border-radius: 16px !important;
    background:
        linear-gradient(180deg, rgba(var(--v-theme-primary), 0.045), transparent 180px),
        rgb(var(--v-theme-surface));
    box-shadow: 0 24px 70px rgba(15, 23, 42, 0.18) !important;
    overflow: hidden;
}

.conversation-edit-title {
    display: flex;
    min-height: 68px;
    align-items: center;
    gap: 12px;
    padding: 18px 24px 16px !important;
    border-bottom: 1px solid rgba(var(--v-theme-border), 0.54);
    background: rgba(255, 255, 255, 0.84);
    color: rgba(var(--v-theme-on-surface), 0.92);
    font-size: 1.18rem !important;
    font-weight: 720 !important;
    letter-spacing: 0;
}

.conversation-edit-title-icon {
    display: inline-flex;
    width: 38px;
    height: 38px;
    flex: 0 0 38px;
    align-items: center;
    justify-content: center;
    border: 1px solid rgba(56, 143, 196, 0.18);
    border-radius: 10px;
    background: rgba(232, 244, 252, 0.95);
    color: #236f9f;
}

.conversation-edit-body {
    padding: 22px 24px 12px !important;
    background: rgba(248, 250, 252, 0.62);
}

.conversation-edit-field :deep(.v-field) {
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.96);
}

.conversation-edit-field :deep(.v-field__outline) {
    --v-field-border-opacity: 0.2;
}

.conversation-edit-field :deep(.v-field--focused .v-field__outline) {
    --v-field-border-opacity: 0.5;
}

.conversation-edit-actions {
    gap: 10px;
    padding: 14px 24px 20px !important;
    border-top: 1px solid rgba(var(--v-theme-border), 0.54);
    background: rgba(255, 255, 255, 0.9);
}

.conversation-edit-cancel-btn,
.conversation-edit-save-btn {
    height: 40px !important;
    max-height: 40px;
    border-radius: 8px !important;
    padding: 0 18px !important;
    font-weight: 650;
    letter-spacing: 0;
}

.conversation-edit-cancel-btn {
    border: 1px solid rgba(var(--v-theme-border), 0.76);
    background: rgba(255, 255, 255, 0.9) !important;
    color: rgba(var(--v-theme-on-surface), 0.74) !important;
}

.conversation-edit-save-btn {
    background: #236f9f !important;
    color: #fff !important;
}

.conversation-edit-save-btn:hover {
    background: #1f628f !important;
}

.conversation-delete-dialog {
    overflow: hidden;
    border: 1px solid rgba(var(--v-theme-error), 0.18);
    border-radius: 18px !important;
    background:
        linear-gradient(180deg, rgba(var(--v-theme-error), 0.055), transparent 150px),
        rgb(var(--v-theme-surface));
    box-shadow: 0 24px 64px rgba(15, 23, 42, 0.22) !important;
}

.conversation-delete-dialog__title {
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

.conversation-delete-dialog__icon {
    display: inline-flex;
    width: 42px;
    height: 42px;
    flex: 0 0 auto;
    align-items: center;
    justify-content: center;
    border: 1px solid rgba(var(--v-theme-error), 0.18);
    border-radius: 12px;
    background: rgba(var(--v-theme-error), 0.1);
    color: rgb(var(--v-theme-error));
}

.conversation-delete-dialog__body {
    padding: 10px 26px 18px !important;
}

.conversation-delete-dialog__message {
    margin: 0;
    color: rgba(var(--v-theme-on-surface), 0.76);
    font-size: 15px;
    line-height: 1.65;
}

.conversation-delete-dialog__target {
    margin-top: 14px;
    padding: 10px 12px;
    overflow-wrap: anywhere;
    border: 1px solid rgba(var(--v-theme-error), 0.13);
    border-radius: 10px;
    background: rgba(var(--v-theme-error), 0.06);
    color: rgba(var(--v-theme-error), 0.92);
    font-size: 13px;
    font-weight: 650;
    line-height: 1.45;
}

.conversation-delete-dialog__target--list {
    display: flex;
    flex-direction: column;
    gap: 7px;
}

.conversation-delete-dialog__target-item,
.conversation-delete-dialog__target-more {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.conversation-delete-dialog__target-more {
    color: rgba(var(--v-theme-error), 0.72);
    font-size: 12px;
}

.conversation-delete-dialog__actions {
    gap: 10px;
    padding: 2px 26px 24px !important;
}

.conversation-delete-dialog__cancel,
.conversation-delete-dialog__confirm {
    min-width: 92px;
    height: 42px;
    max-height: 42px;
    border-radius: 8px !important;
    font-weight: 650;
    letter-spacing: 0;
}

.conversation-delete-dialog__cancel {
    color: rgba(var(--v-theme-on-surface), 0.72) !important;
}

.conversation-delete-dialog__cancel:hover {
    background: rgba(var(--v-theme-on-surface), 0.06);
}

.conversation-delete-dialog__confirm {
    border: 1px solid rgba(var(--v-theme-error), 0.18);
}

.text-truncate {
    display: inline-block;
    /* max-width: 100px; */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.conversation-title-cell {
    padding: 4px 0;
    min-width: 120px;
    max-width: 190px;
}

.conversation-title-row {
    display: flex;
    align-items: center;
    gap: 2px;
    min-width: 0;
}

.conversation-title-text {
    display: inline-block;
    flex: 1;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: rgba(var(--v-theme-on-surface), 0.9);
    font-weight: 650;
}

.conversation-inline-edit {
    width: 18px;
    height: 18px;
    min-width: 18px;
    flex-shrink: 0;
    opacity: 0;
    transition: opacity 0.16s ease;
}

.conversation-table tbody tr:hover .conversation-inline-edit {
    opacity: 0.72;
}

.conversation-title-meta {
    display: block;
    color: rgba(var(--v-theme-on-surface), 0.58);
    font-size: 10px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-top: 3px;
}

.umo-header-cell {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-width: 0;
}

.umo-header-toggle {
    flex-shrink: 0;
    border-radius: 8px;
    border: 1px solid rgba(var(--v-theme-border), 0.46) !important;
    background: rgba(255, 255, 255, 0.92);
    overflow: hidden;
    box-shadow: none !important;
}

.umo-header-toggle .v-btn {
    min-width: 42px;
    height: 32px !important;
    border-radius: 0 !important;
    color: rgba(var(--v-theme-on-surface), 0.62);
    font-size: 11px;
    font-weight: 650;
    letter-spacing: 0;
}

.umo-header-toggle .v-btn--active {
    background: rgb(var(--v-theme-surface)) !important;
    color: rgb(var(--v-theme-primary)) !important;
    box-shadow: inset 0 0 0 1px rgba(var(--v-theme-primary), 0.14);
}

.umo-header-toggle .v-btn:not(.v-btn--active):hover {
    background: rgba(var(--v-theme-primary), 0.045) !important;
}

.umo-source-cell {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-width: 0;
}

.umo-source-content {
    display: flex;
    align-items: center;
    gap: 4px;
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
}

.conversation-umo-display {
    min-width: 0;
}

.conversation-umo-stack {
    display: flex;
    flex-direction: column;
    gap: 5px;
    min-width: 0;
    width: 100%;
}

.conversation-umo-parsed {
    display: flex;
    align-items: center;
    gap: 5px;
    min-width: 0;
    color: rgba(var(--v-theme-on-surface), 0.54);
    font-size: 12px;
}

.conversation-umo-parsed .v-chip {
    height: 22px;
    border: 1px solid rgba(56, 143, 196, 0.16);
    border-radius: 6px;
    background: rgba(232, 244, 252, 0.95) !important;
    color: #236f9f;
    font-size: 11px;
    font-weight: 650;
}

.conversation-umo-parsed .v-chip:nth-of-type(2) {
    border-color: rgba(31, 151, 111, 0.16);
    background: rgba(228, 247, 240, 0.95) !important;
    color: #17795c;
}

.conversation-detail-umo-parsed {
    max-width: 100%;
}

.umo-separator {
    color: rgba(var(--v-theme-on-surface), 0.34);
    flex-shrink: 0;
}

.umo-session-id,
.umo-raw-text {
    min-width: 0;
    color: rgba(var(--v-theme-on-surface), 0.55);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.umo-copy-button {
    flex-shrink: 0;
    opacity: 0.54;
}

.umo-copy-button:hover {
    opacity: 1;
}

@media (max-width: 1200px) {
    .conversation-filter-actions-col {
        flex: 0 0 100%;
        max-width: 100%;
    }

    .conversation-filter-actions-col {
        justify-content: flex-start;
    }

    .conversation-toolbar-actions {
        justify-content: flex-start;
    }
}

@media (max-width: 767px) {
    .conversation-shell {
        padding: 12px 14px 18px !important;
    }

    .conversation-page-head {
        align-items: flex-start;
        flex-direction: column;
    }

    .conversation-batch-actions {
        flex-wrap: wrap;
    }

    .conversation-toolbar-actions {
        justify-content: flex-start;
        flex-wrap: wrap;
        min-width: 0;
    }

    .conversation-pagination {
        flex-direction: column;
        align-items: stretch;
    }

    .conversation-pagination-size {
        justify-content: center;
        flex-wrap: wrap;
    }
}

/* 动画 */
@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}
</style>
