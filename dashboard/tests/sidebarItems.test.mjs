import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import ts from 'typescript';

const sidebarItemsSource = await readFile(
  new URL('../src/layouts/full/vertical-sidebar/sidebarItem.ts', import.meta.url),
  'utf8',
);
const { outputText } = ts.transpileModule(sidebarItemsSource, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
});
const sidebarItemsModule = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
);
const { default: sidebarItems, MORE_GROUP_KEY } = sidebarItemsModule;
const sidebarCustomizationSource = await readFile(
  new URL('../src/utils/sidebarCustomization.js', import.meta.url),
  'utf8',
);
const { resolveSidebarItems } = await import(
  `data:text/javascript;base64,${Buffer.from(
    sidebarCustomizationSource.replace(
      /import \{ MORE_GROUP_KEY \} from [^;]+;/,
      `const MORE_GROUP_KEY = ${JSON.stringify(MORE_GROUP_KEY)};`,
    ),
  ).toString('base64')}`
);

test('sidebar exposes only Skills and components from extension navigation', () => {
  const visibleTitles = [
    'core.navigation.extensionTabs.skills',
    'core.navigation.extensionTabs.components',
  ];
  const visibleExtensionItems = sidebarItems
    .filter(({ title }) => visibleTitles.includes(title))
    .map(({ title, to }) => ({ title, to }));

  assert.deepEqual(visibleExtensionItems, [
    {
      title: 'core.navigation.extensionTabs.skills',
      to: '/extension#skills',
    },
    {
      title: 'core.navigation.extensionTabs.components',
      to: '/extension#components',
    },
  ]);

  const allItems = [...sidebarItems];
  for (const item of allItems) {
    allItems.push(...(item.children ?? []));
  }

  assert.deepEqual(
    allItems
      .filter(({ title }) => visibleTitles.includes(title))
      .map(({ title, to }) => ({ title, to })),
    visibleExtensionItems,
  );

  const hiddenTitles = new Set([
    'core.navigation.extension',
    'core.navigation.extensionTabs.installed',
    'core.navigation.extensionTabs.market',
    'core.navigation.extensionTabs.mcp',
  ]);
  const hiddenRoutes = new Set([
    '/extension#installed',
    '/extension#market',
    '/extension#mcp',
  ]);
  assert.deepEqual(
    allItems.filter(
      ({ title, to }) =>
        (title && hiddenTitles.has(title)) || (to && hiddenRoutes.has(to)),
    ),
    [],
  );
});

test('sidebar promotes selected more items and hides the remaining entries', () => {
  const promotedItems = [
    {
      title: 'core.navigation.cron',
      to: '/cron',
    },
    {
      title: 'core.navigation.console',
      to: '/console',
    },
  ];
  const promotedTitles = new Set(promotedItems.map(({ title }) => title));
  const visiblePromotedItems = sidebarItems
    .filter(({ title }) => title && promotedTitles.has(title))
    .map(({ title, to }) => ({ title, to }));

  assert.deepEqual(visiblePromotedItems, promotedItems);

  const allItems = [...sidebarItems];
  for (const item of allItems) {
    allItems.push(...(item.children ?? []));
  }

  assert.deepEqual(
    allItems
      .filter(({ title }) => title && promotedTitles.has(title))
      .map(({ title, to }) => ({ title, to })),
    visiblePromotedItems,
  );

  assert.equal(
    sidebarItems.some(({ title }) => title === MORE_GROUP_KEY),
    false,
  );

  const hiddenTitles = new Set([
    'core.navigation.groups.more',
    'core.navigation.sessionManagement',
    'core.navigation.subagent',
    'core.navigation.dashboard',
    'core.navigation.trace',
    'core.navigation.conversation',
  ]);
  const hiddenRoutes = new Set([
    '/session-management',
    '/subagent',
    '/dashboard/default',
    '/trace',
    '/conversation',
  ]);
  assert.deepEqual(
    allItems.filter(
      ({ title, to }) =>
        (title && hiddenTitles.has(title)) || (to && hiddenRoutes.has(to)),
    ),
    [],
  );
});

test('sidebar migrates promoted items from legacy customization', () => {
  const legacyCustomization = {
    mainItems: [
      'core.navigation.welcome',
      'core.navigation.platforms',
      'core.navigation.providers',
      'core.navigation.config',
      'core.navigation.extension',
      'core.navigation.knowledgeBase',
      'core.navigation.persona',
    ],
    moreItems: [
      'core.navigation.conversation',
      'core.navigation.sessionManagement',
      'core.navigation.cron',
      'core.navigation.subagent',
      'core.navigation.dashboard',
      'core.navigation.console',
      'core.navigation.trace',
    ],
  };

  const { merged, normalizedMainKeys, normalizedMoreKeys } = resolveSidebarItems(
    sidebarItems,
    legacyCustomization,
    { assembleMoreGroup: true },
  );

  assert.deepEqual(
    normalizedMainKeys.slice(-2),
    [
      'core.navigation.cron',
      'core.navigation.console',
    ],
  );
  assert.deepEqual(normalizedMoreKeys, []);
  assert.equal(merged.some(({ title }) => title === MORE_GROUP_KEY), false);
});
