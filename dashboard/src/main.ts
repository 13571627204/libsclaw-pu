import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import { router } from './router';
import vuetify from './plugins/vuetify';
import confirmPlugin from './plugins/confirmPlugin';
import { setupI18n } from './i18n/composables';
import '@/scss/style.scss';
import { setupHttpClient } from './api/http';
import { waitForRouterReadyInBackground } from './utils/routerReadiness.mjs';
import { installRoutePrefetch } from './utils/routePrefetch.mjs';

setupHttpClient();

/**
 * 挂载后初始化主题。
 * 职责：
 *   - 同步 Vuetify theme 名称与 store 中的 uiTheme
 *   - 应用自定义 primary/secondary 色
 * 注意：暗色已全局禁用，uiTheme 恒为 PurpleTheme，
 *       无需再监听系统色彩模式变化。
 */
function setupThemeSync(pinia: ReturnType<typeof createPinia>) {
  import('./stores/customizer').then(({ useCustomizerStore }) => {
    const customizer = useCustomizerStore(pinia);

    // 1. 强制对齐到亮色主题，清除历史 dark 残留
    if (customizer.uiTheme !== 'PurpleTheme') {
      customizer.uiTheme = 'PurpleTheme';
      localStorage.setItem('uiTheme', 'PurpleTheme');
    }

    // 2. 将 Vuetify 主题对齐到 store
    vuetify.theme.global.name.value = customizer.uiTheme;

    // 3. 应用用户自定义色
    const storedPrimary = localStorage.getItem('themePrimary');
    const storedSecondary = localStorage.getItem('themeSecondary');
    if (storedPrimary || storedSecondary) {
      const themes = vuetify.theme.themes.value;
      ['PurpleTheme', 'PurpleThemeDark'].forEach((name) => {
        const theme = themes[name];
        if (!theme?.colors) return;
        if (storedPrimary) theme.colors.primary = storedPrimary;
        if (storedSecondary) theme.colors.secondary = storedSecondary;
        if (storedPrimary && theme.colors.darkprimary) theme.colors.darkprimary = storedPrimary;
        if (storedSecondary && theme.colors.darksecondary) theme.colors.darksecondary = storedSecondary;
      });
    }
  });
}

async function bootstrap() {
  try {
    await setupI18n();
    console.log('🌍 新i18n系统初始化完成');
  } catch (error) {
    console.error('❌ 新i18n系统初始化失败:', error);
  }

  const app = createApp(App);
  const pinia = createPinia();
  app.use(pinia);
  app.use(router);
  app.use(vuetify);
  app.use(confirmPlugin);

  let routerReady = false;
  try {
    await router.isReady();
    routerReady = true;
  } catch (error) {
    console.warn('Initial route did not become ready before mount:', error);
  }

  app.mount('#app');
  installRoutePrefetch(router);
  if (!routerReady) {
    waitForRouterReadyInBackground(router);
  }

  setupThemeSync(pinia);
}

void bootstrap();
