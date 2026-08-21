<template>
    <BaseFolderCard
        :folder="folder"
        :accept-drop-types="['persona']"
        :labels="{
            open: tm('folder.contextMenu.open'),
            rename: tm('folder.contextMenu.rename'),
            moveTo: tm('folder.contextMenu.moveTo'),
            delete: tm('folder.contextMenu.delete')
        }"
        @click="$emit('click')"
        @contextmenu.native.prevent="$emit('contextmenu', $event)"
        @open="$emit('open')"
        @rename="$emit('rename')"
        @move="$emit('move')"
        @delete="$emit('delete')"
        @item-dropped="onItemDropped"
    />
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue';
import { useModuleI18n } from '@/i18n/composables';
import BaseFolderCard from '@/components/folder/BaseFolderCard.vue';
import type { Folder } from '@/components/folder/types';

export default defineComponent({
    name: 'FolderCard',
    components: { BaseFolderCard },
    props: {
        folder: {
            type: Object as PropType<Folder>,
            required: true
        }
    },
    emits: ['click', 'contextmenu', 'open', 'rename', 'move', 'delete', 'persona-dropped'],
    setup() {
        const { tm } = useModuleI18n('features/persona');
        return { tm };
    },
    methods: {
        onItemDropped(data: { item_id: string; item_type: string; target_folder_id: string | null; source_data?: any }) {
            if (data.item_type === 'persona') {
                this.$emit('persona-dropped', {
                    persona_id: data.item_id,
                    target_folder_id: data.target_folder_id ?? this.folder.folder_id
                });
            }
        }
    }
});
</script>

<style scoped>
.folder-card,
:deep(.base-folder-card) {
    cursor: pointer;
    border: 1px solid rgba(var(--v-theme-border), 0.52);
    border-radius: 14px !important;
    background:
        linear-gradient(180deg, rgba(255, 248, 235, 0.7), rgba(255, 255, 255, 0.92)),
        rgb(var(--v-theme-surface));
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.035);
    overflow: hidden;
    transition:
        border-color 0.16s ease,
        box-shadow 0.16s ease,
        transform 0.16s ease;
}

.folder-card:hover,
:deep(.base-folder-card:hover) {
    border-color: rgba(209, 139, 35, 0.22);
    box-shadow: 0 14px 30px rgba(15, 23, 42, 0.06);
    transform: translateY(-1px);
}

:deep(.base-folder-card .v-card-text) {
    padding: 16px !important;
}

:deep(.base-folder-card .v-icon) {
    color: #d18b23 !important;
}

.folder-card.drag-over {
    background-color: rgba(var(--v-theme-primary), 0.15);
    border: 2px dashed rgb(var(--v-theme-primary));
    transform: scale(1.02);
}

.folder-info {
    min-width: 0;
}
</style>
