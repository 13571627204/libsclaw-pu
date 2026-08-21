<template>
    <div class="dashboard-page persona-page-shell">
        <v-container fluid class="dashboard-shell persona-page pa-4 pa-md-6">
            <!-- 页面标题 -->
            <div class="persona-page-header">
                <div class="persona-page-header-copy">
                    <h1 class="dashboard-title">
                        {{ t('core.navigation.persona') }}
                    </h1>
                    <p class="dashboard-subtitle">
                        {{ tm('page.description') }}
                    </p>
                </div>
            </div>

            <!-- 主容器组件 -->
            <PersonaManager />
        </v-container>
    </div>
</template>

<script>
import { useI18n, useModuleI18n } from '@/i18n/composables';
import { PersonaManager } from '@/views/persona';

export default {
    name: 'PersonaPage',
    components: {
        PersonaManager
    },
    setup() {
        const { t } = useI18n();
        const { tm } = useModuleI18n('features/persona');
        return { t, tm };
    }
};
</script>

<style scoped>
@import "@/styles/dashboard-shell.css";

.persona-page-shell {
    padding-bottom: 40px;
    background:
        linear-gradient(180deg, rgba(var(--v-theme-primary), 0.045), transparent 260px),
        rgb(var(--v-theme-background));
}

.persona-page {
    max-width: 1460px;
    width: 100%;
}

.persona-page-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 24px;
    margin-bottom: 20px;
    padding: 2px 2px 0;
}

.persona-page-header-copy {
    min-width: 0;
}

@media (max-width: 768px) {
    .persona-page {
        padding: 16px;
    }
}
</style>
