import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const knowledgeBaseDetailSource = await readFile(
  new URL('../src/views/knowledge-base/KBDetail.vue', import.meta.url),
  'utf8',
);

const navigationTabs = Array.from(
  knowledgeBaseDetailSource.matchAll(/<v-tab\b[^>]*\bvalue="([^"]+)"[^>]*>/g),
  ([, value]) => value,
);
const contentPanels = Array.from(
  knowledgeBaseDetailSource.matchAll(
    /<v-window-item\b[^>]*\bvalue="([^"]+)"[^>]*>/g,
  ),
  ([, value]) => value,
);

test('knowledge base detail exposes only the requested navigation tabs', () => {
  assert.deepEqual(navigationTabs, ['overview', 'documents', 'graph']);
});

test('knowledge base detail keeps hidden tab capabilities and export action', () => {
  assert.deepEqual(contentPanels, [
    'overview',
    'documents',
    'wiki',
    'graph',
    'retrieval',
    'settings',
  ]);
  assert.match(knowledgeBaseDetailSource, /<WikiTab\b/);
  assert.match(knowledgeBaseDetailSource, /<RetrievalTab\b/);
  assert.match(knowledgeBaseDetailSource, /<SettingsTab\b/);
  assert.match(knowledgeBaseDetailSource, /const activeTab = ref\('overview'\)/);
  assert.match(
    knowledgeBaseDetailSource,
    /const openWikiPage = \(path: string\) => \{[\s\S]*?activeTab\.value = 'wiki'[\s\S]*?\}/,
  );
  assert.match(
    knowledgeBaseDetailSource,
    /<v-btn\b[^>]*@click="exportWiki"[^>]*>[\s\S]*?导出知识库[\s\S]*?<\/v-btn>/,
  );
});

test('knowledge base overview hides the embedding model status card', () => {
  assert.doesNotMatch(
    knowledgeBaseDetailSource,
    /<h2>\{\{ t\('overview\.embeddingModel'\) \}\}<\/h2>/,
  );
});
