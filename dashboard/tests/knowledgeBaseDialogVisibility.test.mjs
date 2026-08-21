import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const knowledgeBaseListSource = await readFile(
  new URL('../src/views/knowledge-base/KBList.vue', import.meta.url),
  'utf8',
);

test('knowledge base dialog hides embedding and rerank model selectors', () => {
  assert.doesNotMatch(
    knowledgeBaseListSource,
    /<v-select\b[^>]*v-model="formData\.embedding_provider_id"/s,
  );
  assert.doesNotMatch(
    knowledgeBaseListSource,
    /<v-select\b[^>]*v-model="formData\.rerank_provider_id"/s,
  );
  assert.doesNotMatch(
    knowledgeBaseListSource,
    /providerApi\.listByProviderType\('embedding,rerank'\)/,
  );
});

test('knowledge base dialog keeps model ids in the save payload', () => {
  assert.match(
    knowledgeBaseListSource,
    /embedding_provider_id:\s*kb\.embedding_provider_id/,
  );
  assert.match(
    knowledgeBaseListSource,
    /rerank_provider_id:\s*kb\.rerank_provider_id/,
  );
  assert.match(
    knowledgeBaseListSource,
    /embedding_provider_id:\s*formData\.value\.embedding_provider_id/,
  );
  assert.match(
    knowledgeBaseListSource,
    /rerank_provider_id:\s*formData\.value\.rerank_provider_id/,
  );
});

test('knowledge base dialog keeps its basic form controls', () => {
  assert.match(knowledgeBaseListSource, /v-model="formData\.kb_name"/);
  assert.match(knowledgeBaseListSource, /v-model="formData\.description"/);
  assert.match(knowledgeBaseListSource, /showEmojiPicker = true/);
  assert.match(knowledgeBaseListSource, /@click="submitForm"/);
});

test('knowledge base list hides the legacy knowledge base entry', () => {
  assert.doesNotMatch(knowledgeBaseListSource, /class="kb-legacy-link"/);
  assert.doesNotMatch(knowledgeBaseListSource, /\/alkaid\/knowledge-base/);
  assert.doesNotMatch(knowledgeBaseListSource, /切换到旧版知识库/);
  assert.doesNotMatch(knowledgeBaseListSource, /\.kb-legacy-link\b/);
  assert.match(knowledgeBaseListSource, /@click="loadKnowledgeBases\(true\)"/);
  assert.match(knowledgeBaseListSource, /@click="showCreateDialog = true"/);
  assert.match(knowledgeBaseListSource, /@click="navigateToDetail\(kb\.kb_id\)"/);
  assert.match(knowledgeBaseListSource, /@click\.stop="editKB\(kb\)"/);
  assert.match(knowledgeBaseListSource, /@click\.stop="confirmDelete\(kb\)"/);
});
