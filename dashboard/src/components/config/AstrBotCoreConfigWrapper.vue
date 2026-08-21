<template>
    <div :class="['config-workbench', $vuetify.display.mobile ? 'config-workbench--mobile' : 'config-workbench--desktop']">
        <v-tabs v-model="tab" :direction="$vuetify.display.mobile ? 'horizontal' : 'vertical'"
            :align-tabs="$vuetify.display.mobile ? 'left' : 'start'" color="primary" class="config-tabs">
            <v-tab v-for="section in visibleSections" :key="section.key" :value="section.key"
                class="config-tab-item">
                {{ tm(section.value['name']) }}
            </v-tab>
        </v-tabs>
        <v-tabs-window v-model="tab" class="config-tabs-window" :style="readonly ? 'pointer-events: none; opacity: 0.6;' : ''">
            <v-tabs-window-item v-for="section in visibleSections" :key="section.key" :value="section.key">
                <v-container fluid class="config-section-container">
                    <div v-for="(val2, key2, index2) in section.value['metadata']" :key="key2">
                        <!-- Support both traditional and JSON selector metadata -->
                        <AstrBotConfigV4
                            :metadata="{ [key2]: section.value['metadata'][key2] }"
                            :iterable="config_data"
                            :metadataKey="key2"
                            :search-keyword="searchKeyword"
                        >
                        </AstrBotConfigV4>
                    </div>
                </v-container>
            </v-tabs-window-item>

        </v-tabs-window>
    </div>
    <v-container v-if="visibleSections.length === 0" fluid class="px-0">
        <v-alert type="info" variant="tonal" class="config-no-result">
            {{ tm('search.noResult') }}
        </v-alert>
    </v-container>
</template>

<script>
import AstrBotConfigV4 from '@/components/shared/AstrBotConfigV4.vue';
import { useModuleI18n } from '@/i18n/composables';

export default {
  name: 'AstrBotCoreConfigWrapper',
  components: {
    AstrBotConfigV4
  },
  props: {
    metadata: {
      type: Object,
      required: true,
      default: () => ({})
    },
    config_data: {
      type: Object,
      required: true,
      default: () => ({})
    },
    readonly: {
      type: Boolean,
      default: false
    },
    searchKeyword: {
      type: String,
      default: ''
    }
  },
  setup() {
    const { tm: tmConfig } = useModuleI18n('features/config');
    const { tm: tmMetadata } = useModuleI18n('features/config-metadata');
    
    const tm = (key) => {
      const metadataResult = tmMetadata(key);
      if (!metadataResult.startsWith('[MISSING:') && !metadataResult.startsWith('[INVALID:')) {
        return metadataResult;
      }
      return tmConfig(key);
    };
    
    return {
      tm
    };
  },
  data() {
    return {
      tab: null, // 当前激活的配置标签页 key
    }
  },
  computed: {
    normalizedSearchKeyword() {
      return String(this.searchKeyword || '').trim().toLowerCase();
    },
    visibleSections() {
      if (!this.metadata || typeof this.metadata !== 'object') {
        return [];
      }
      const allSections = Object.entries(this.metadata)
        .filter(([, value]) => !value?.invisible)
        .map(([key, value]) => ({ key, value }));
      if (!this.normalizedSearchKeyword) {
        return allSections;
      }
      return allSections.filter((section) => this.sectionHasSearchMatch(section.value));
    }
  },
  watch: {
    visibleSections(newSections) {
      const sectionKeys = newSections.map((section) => section.key);
      if (!sectionKeys.includes(this.tab)) {
        this.tab = sectionKeys[0] ?? null;
      }
    }
  },
  mounted() {
    const sectionKeys = this.visibleSections.map((section) => section.key);
    this.tab = sectionKeys[0] ?? null;
  },
  methods: {
    sectionHasSearchMatch(section) {
      const keyword = this.normalizedSearchKeyword;
      if (!keyword) {
        return true;
      }
      const sectionMetadata = section?.metadata || {};
      return Object.values(sectionMetadata).some((metaItem) => this.metaObjectHasSearchMatch(metaItem, keyword));
    },
    metaObjectHasSearchMatch(metaObject, keyword) {
      if (!metaObject || typeof metaObject !== 'object') {
        return false;
      }
      if (metaObject.invisible) {
        return false;
      }
      const target = [
        this.tm(metaObject.description || ''),
        this.tm(metaObject.hint || ''),
        ...Object.entries(metaObject.items || {}).flatMap(([itemKey, itemMeta]) => {
          if (itemMeta?.invisible) {
            return [];
          }
          return [
            itemKey,
            this.tm(itemMeta?.description || ''),
            this.tm(itemMeta?.hint || '')
          ];
        })
      ]
        .join(' ')
        .toLowerCase();

      return target.includes(keyword);
    }
  }
}
</script>

<style>
.config-workbench {
  display: flex;
  gap: 18px;
  align-items: flex-start;
}

.config-workbench--desktop {
  width: 100%;
}

.config-tabs {
  border: 1px solid rgba(var(--v-theme-border), 0.7);
  border-radius: 14px;
  background: rgba(var(--v-theme-surface), 0.82);
  padding: 6px;
}

.config-tab-item {
  justify-content: flex-start !important;
  min-height: 44px !important;
  border-radius: 8px !important;
  color: rgba(var(--v-theme-on-surface), 0.78);
  font-size: 14px !important;
  font-weight: 680 !important;
  letter-spacing: 0 !important;
}

.config-tabs .v-tab--selected {
  background: rgba(var(--v-theme-primary), 0.1);
  color: rgb(var(--v-theme-primary));
}

.config-tabs-window {
  min-width: 0;
}

.config-section-container {
  padding: 0 !important;
}

.config-no-result {
  border-radius: 14px;
}

@media (min-width: 768px) {
  .config-tabs {
    display: flex;
    flex: 0 0 150px;
    margin: 0;
    position: sticky;
    top: 0;
  }

  .config-tabs-window {
    flex: 1;
  }

  .config-tabs .v-tab {
    justify-content: flex-start !important;
    text-align: left;
    min-height: 48px;
  }
}

@media (max-width: 767px) {
.config-workbench {
    flex-direction: column;
    gap: 14px;
  }

  .config-tabs {
    width: 100%;
    overflow-x: auto;
  }

  .config-tabs-window {
    width: 100%;
    margin-top: 0;
  }
}
</style>
