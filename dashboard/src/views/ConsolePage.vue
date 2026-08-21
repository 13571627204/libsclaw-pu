<script setup>
import ConsoleDisplayer from '@/components/shared/ConsoleDisplayer.vue';
import { useModuleI18n } from '@/i18n/composables';

const { tm } = useModuleI18n('features/console');
</script>

<template>
  <div class="console-page">
    <div class="console-header">
      <div class="console-title-block">
        <div class="console-title-line">
          <h1 class="console-title">{{ tm('title') }}</h1>
          <v-chip size="small" variant="tonal" color="primary" class="console-title-chip">
            {{ tm('streamLabel') }}
          </v-chip>
        </div>
        <p class="console-subtitle">
          {{ tm('debugHint.text') }}
        </p>
      </div>
    </div>
    <ConsoleDisplayer ref="consoleDisplayer" class="console-display" />
  </div>
</template>
<script>
export default {
  name: 'ConsolePage',
  components: {
    ConsoleDisplayer
  },
  data() {
    return {
      autoScrollEnabled: localStorage.getItem('console_auto_scroll') !== 'false',
    }
  },
  mounted() {
    if (this.$refs.consoleDisplayer) {
      this.$refs.consoleDisplayer.autoScroll = this.autoScrollEnabled;
    }
  },
  watch: {
    autoScrollEnabled(val) {
      localStorage.setItem('console_auto_scroll', val);
      if (this.$refs.consoleDisplayer) {
        this.$refs.consoleDisplayer.autoScroll = val;
      }
    }
  },
}

</script>

<style scoped>
.console-page {
  min-height: 100%;
  margin: 0 auto;
  max-width: 1480px;
  padding: 24px 28px 32px;
  width: 100%;
  background:
    linear-gradient(180deg, rgba(239, 248, 254, 0.72) 0%, rgba(255, 255, 255, 0) 260px),
    rgb(var(--v-theme-background));
}

.console-header {
  align-items: center;
  display: flex;
  gap: 18px;
  justify-content: space-between;
  margin-bottom: 16px;
  padding: 0 2px 14px;
  border-bottom: 1px solid rgba(var(--v-theme-border), 0.54);
}

.console-title-block {
  min-width: 0;
}

.console-title-line {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.console-title {
  margin: 0;
  color: rgb(var(--v-theme-primaryText));
  font-size: 21px;
  font-weight: 720;
  letter-spacing: 0;
  line-height: 1.25;
}

.console-title-chip {
  border-radius: 999px !important;
  background: rgba(var(--v-theme-primary), 0.09) !important;
  font-weight: 650;
}

.console-subtitle {
  margin: 7px 0 0;
  color: rgba(var(--v-theme-on-surface), 0.66);
  font-size: 13px;
  line-height: 1.6;
}

.console-display {
  height: calc(100vh - 185px);
  width: 100%;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

.fade-in {
  animation: fadeIn 0.2s ease-in-out;
}

@media (max-width: 768px) {
  .console-page {
    padding: 16px;
  }

  .console-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }

  .console-display {
    height: calc(100vh - 240px);
  }
}
</style>
