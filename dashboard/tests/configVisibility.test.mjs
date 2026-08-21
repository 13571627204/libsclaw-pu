import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const configRendererSource = await readFile(
  new URL('../src/components/shared/AstrBotConfigV4.vue', import.meta.url),
  'utf8',
);
const configWrapperSource = await readFile(
  new URL('../src/components/config/AstrBotCoreConfigWrapper.vue', import.meta.url),
  'utf8',
);

test('AI config renderer excludes invisible sections and fields from layout', () => {
  assert.match(
    configRendererSource,
    /if \(sectionMeta\?\.invisible\)\s*{\s*return false\s*}/s,
  );
  assert.match(
    configRendererSource,
    /Object\.entries\(sectionItems\)\.filter\(\(\[itemKey, itemMeta\]\) =>\s*{[\s\S]*?if \(itemMeta\?\.invisible\)\s*{\s*return false\s*}/,
  );
  assert.match(
    configRendererSource,
    /const hasVisibleItems = Object\.entries\(sectionItems\)\.some\([\s\S]*?!itemMeta\?\.invisible && shouldShowItem\(itemMeta, itemKey\)/,
  );
  assert.match(
    configRendererSource,
    /<v-list-item-subtitle\b(?=[^>]*\bv-if="metadata\[metadataKey\]\?\.hint")[^>]*>/,
  );
});

test('config search excludes invisible sections and fields', () => {
  assert.match(
    configWrapperSource,
    /if \(metaObject\.invisible\)\s*{\s*return false;?\s*}/s,
  );
  assert.match(
    configWrapperSource,
    /Object\.entries\(metaObject\.items \|\| \{\}\)\.flatMap\(\(\[itemKey, itemMeta\]\) =>\s*{[\s\S]*?if \(itemMeta\?\.invisible\)\s*{\s*return \[\];\s*}/,
  );
});

test('config tabs exclude invisible top-level groups', () => {
  assert.match(
    configWrapperSource,
    /Object\.entries\(this\.metadata\)\s*\.filter\(\(\[, value\]\) => !value\?\.invisible\)/,
  );
});
