import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const providerPageSource = await readFile(
  new URL('../src/views/ProviderPage.vue', import.meta.url),
  'utf8',
);
const providerSelectorSource = await readFile(
  new URL('../src/components/shared/ProviderSelector.vue', import.meta.url),
  'utf8',
);
const providerSourcesSource = await readFile(
  new URL('../src/composables/useProviderSources.ts', import.meta.url),
  'utf8',
);

test('provider page hides non-chat provider types by default', () => {
  assert.match(
    providerPageSource,
    /<v-tabs\b(?=[^>]*\bv-if="showAllProviderTypes")[^>]*>/,
  );
  assert.match(providerPageSource, /v-for="type in visibleProviderTypes"/);
  assert.match(
    providerPageSource,
    /showAllProviderTypes:\s*{\s*type:\s*Boolean,\s*default:\s*false,?\s*}/s,
  );
  assert.match(
    providerPageSource,
    /const visibleProviderTypes = computed\(\(\) =>[\s\S]*?showAllProviderTypes[\s\S]*?type\.value === 'chat_completion'[\s\S]*?\);?/,
  );
  assert.match(
    providerPageSource,
    /defaultTab:\s*props\.showAllProviderTypes\s*\?\s*props\.defaultTab\s*:\s*'chat_completion'/,
  );
  assert.match(
    providerPageSource,
    /updateDefaultTab\(showAllProviderTypes\s*\?\s*defaultTab\s*:\s*'chat_completion'\)/,
  );
});

test('provider selector keeps access to every provider type', () => {
  assert.match(
    providerSelectorSource,
    /<ProviderPage\b[\s\S]*?:show-all-provider-types="true"[\s\S]*?\/>/,
  );
});

test('provider source advanced settings hide custom request headers', () => {
  assert.match(
    providerSourcesSource,
    /const excluded = new Set\(\[[^\]]*'custom_headers'[^\]]*\]\)/s,
  );
});

test('provider subtitles only describe chat model configuration', async () => {
  const expectedSubtitles = {
    'zh-CN': '可以在“对话”中配置对话模型。',
    'en-US': 'Can configure chat models in "Chat Completion".',
    'ru-RU': 'Настройка AI моделей для диалогов.',
  };

  for (const [locale, expectedSubtitle] of Object.entries(expectedSubtitles)) {
    const content = await readFile(
      new URL(`../src/i18n/locales/${locale}/features/provider.json`, import.meta.url),
      'utf8',
    );
    const messages = JSON.parse(content.replace(/^\uFEFF/, ''));

    assert.equal(messages.subtitle, expectedSubtitle, `${locale} subtitle`);
  }
});
