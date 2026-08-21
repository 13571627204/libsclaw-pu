import test from 'node:test';
import assert from 'node:assert/strict';
import { access, readFile } from 'node:fs/promises';

const configPageSource = await readFile(
  new URL('../src/views/ConfigPage.vue', import.meta.url),
  'utf8',
);
const extensionPageSource = await readFile(
  new URL('../src/views/ExtensionPage.vue', import.meta.url),
  'utf8',
);
const installedPluginsSource = await readFile(
  new URL('../src/views/extension/InstalledPluginsTab.vue', import.meta.url),
  'utf8',
);
const marketPluginsSource = await readFile(
  new URL('../src/views/extension/MarketPluginsTab.vue', import.meta.url),
  'utf8',
);
const personaFormSource = await readFile(
  new URL('../src/components/shared/PersonaForm.vue', import.meta.url),
  'utf8',
);
const platformPageSource = await readFile(
  new URL('../src/views/PlatformPage.vue', import.meta.url),
  'utf8',
);
const addNewPlatformSource = await readFile(
  new URL('../src/components/platform/AddNewPlatform.vue', import.meta.url),
  'utf8',
);
const configItemRendererSource = await readFile(
  new URL('../src/components/shared/ConfigItemRenderer.vue', import.meta.url),
  'utf8',
);
const personaSelectorSource = await readFile(
  new URL('../src/components/shared/PersonaSelector.vue', import.meta.url),
  'utf8',
);
const platformUtilsSource = await readFile(
  new URL('../src/utils/platformUtils.js', import.meta.url),
  'utf8',
);
const pluginPlatformChipSource = await readFile(
  new URL('../src/components/shared/PluginPlatformChip.vue', import.meta.url),
  'utf8',
);
const zhShared = JSON.parse(
  await readFile(new URL('../src/i18n/locales/zh-CN/core/shared.json', import.meta.url), 'utf8'),
);
const enShared = JSON.parse(
  await readFile(new URL('../src/i18n/locales/en-US/core/shared.json', import.meta.url), 'utf8'),
);

test('config page defines and updates unsaved state consistently', () => {
  const computedDefinitions = configPageSource.match(/hasUnsavedChanges\(\)\s*{/g) ?? [];
  const dataDefinitions = configPageSource.match(/hasUnsavedChanges:\s*false/g) ?? [];

  assert.equal(computedDefinitions.length + dataDefinitions.length, 1);
  assert.match(
    configPageSource,
    /config_data:\s*{[\s\S]*?deep:\s*true[\s\S]*?this\.hasUnsavedChanges\s*=\s*this\.configHasChanges/,
  );
  assert.match(
    configPageSource,
    /onConfigSaved\(\)\s*{[\s\S]*?this\.hasUnsavedChanges\s*=\s*false/,
  );
});

test('extension and persona templates do not use removed Vuetify components', () => {
  assert.doesNotMatch(extensionPageSource, /<\/?v-tab-item\b/);
  assert.doesNotMatch(installedPluginsSource, /<\/?v-tab-item\b/);
  assert.doesNotMatch(marketPluginsSource, /<\/?v-tab-item\b/);
  assert.doesNotMatch(personaFormSource, /<\/?v-chip-text\b/);
});

test('platform dialog listens only to declared refresh events', () => {
  assert.doesNotMatch(platformPageSource, /@update="getConfig"/);
  assert.match(platformPageSource, /@refresh-config="getConfig"/);
  assert.match(addNewPlatformSource, /emits:\s*\[[^\]]*"refresh-config"[^\]]*\]/);
  assert.match(addNewPlatformSource, /\$emit\("refresh-config"\)/);
});

test('persona selector edit action is translated in primary locales', () => {
  assert.equal(zhShared.personaSelector.editPersona, '编辑当前人格');
  assert.equal(enShared.personaSelector.editPersona, 'Edit current persona');
  assert.match(personaSelectorSource, /tm\(['"]personaSelector\.editPersona['"]\)/);
});

test('platform icon assets and fallback glyph exist', async () => {
  const assetPaths = [
    ...platformUtilsSource.matchAll(
      /new URL\(['"](@\/assets\/images\/platform_logos\/[^'"]+)['"]/g,
    ),
  ].map((match) => match[1]);

  assert.ok(assetPaths.length > 0);
  await Promise.all(
    assetPaths.map((assetPath) =>
      access(new URL(`../src/${assetPath.slice(2)}`, import.meta.url)),
    ),
  );

  assert.match(addNewPlatformSource, /<img\s+v-if="getPlatformIcon\(/);

  const fallbackIcons = [pluginPlatformChipSource, addNewPlatformSource].map((source) =>
    source.match(/<v-icon\s+v-else\s+icon="(mdi-[^"]+)"/)?.[1],
  );
  assert.ok(fallbackIcons.every(Boolean));

  const mdiCss = await readFile(
    new URL('../node_modules/@mdi/font/css/materialdesignicons.css', import.meta.url),
    'utf8',
  );
  for (const fallbackIcon of fallbackIcons) {
    assert.match(mdiCss, new RegExp(`\\.${fallbackIcon}::before\\s*\\{`));
  }
});

test('list config item does not receive attributes it cannot inherit', () => {
  const listConfigItemTag = configItemRendererSource.match(/<ListConfigItem[\s\S]*?\/>/)?.[0];
  assert.ok(listConfigItemTag);
  assert.doesNotMatch(listConfigItemTag, /\bclass=/);
});
