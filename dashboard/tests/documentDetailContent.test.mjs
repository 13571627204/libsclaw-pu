import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const documentDetailSource = await readFile(
  new URL('../src/views/knowledge-base/DocumentDetail.vue', import.meta.url),
  'utf8',
);

test('document detail displays full document content and keeps chunk loading', () => {
  assert.match(
    documentDetailSource,
    /knowledgeApi\.wikiPage\(kbId\.value, document\.value\.file_path\)/,
  );
  assert.match(documentDetailSource, /const rawContent = contentResponse\.data\.data\?\.content \|\| ''/);
  assert.match(documentDetailSource, /Original Content/);
  assert.match(documentDetailSource, /contentWithoutFrontmatter/);
  assert.match(documentDetailSource, /Source\|来源/);
  assert.match(documentDetailSource, /Category\|Knowledge Relations/);
  assert.match(documentDetailSource, /t\('content\.title'\)/);
  assert.match(
    documentDetailSource,
    /<MarkdownRender\s+:content="documentContent"\s+:typewriter="false"\s+html-policy="escape"\s*\/>/,
  );
  assert.match(documentDetailSource, /knowledgeApi\.chunks\(kbId\.value,/);
  assert.match(
    documentDetailSource,
    /if \(contentResponse\.data\.status !== 'ok'\) \{\s*throw new Error\(/,
  );
  assert.match(documentDetailSource, /console\.error\('Failed to load document content:', error\)/);
  assert.match(documentDetailSource, /showSnackbar\('加载文档原文失败', 'error'\)/);
});
