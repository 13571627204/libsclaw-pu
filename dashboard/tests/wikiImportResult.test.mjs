import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import ts from 'typescript';

const source = await readFile(
  new URL('../src/views/knowledge-base/components/WikiImportDialog.vue', import.meta.url),
  'utf8',
);
const script = source.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1];
const compiled = ts.transpileModule(
  script.replace(/^import .*;\r?$/gm, '') +
    '\nglobalThis.subject = { pollTask, successMessage, errorMessage, skippedEntries, importing, skippedReasonLabel, reset };',
  { compilerOptions: { target: ts.ScriptTarget.ES2022 } },
).outputText;

function createSubject(result) {
  const events = [];
  const context = {
    shallowRef: (value) => ({ value }),
    computed: (read) => ({ get value() { return read(); } }),
    defineProps: () => ({ modelValue: true, kbId: 'test-wiki' }),
    defineEmits: () => (...args) => events.push(args),
    watch() {},
    onBeforeUnmount() {},
    window: { clearTimeout() {} },
    knowledgeApi: {
      task: async () => ({
        data: { status: 'ok', data: { status: 'completed', result } },
      }),
    },
  };
  vm.runInNewContext(compiled, context);
  return { ...context.subject, events };
}

test('duplicate-only import completes and explains preserved pages', async () => {
  const subject = createSubject({
    imported_count: 0,
    skipped_count: 1,
    skipped: [{ path: '中睿26年医健产业蓝皮书.md', reason: 'exists' }],
  });
  subject.importing.value = true;
  await subject.pollTask('duplicate-import');
  assert.match(subject.successMessage.value, /导入完成，共导入 0 个页面/);
  assert.match(subject.successMessage.value, /已跳过 1 个文件/);
  assert.equal(subject.skippedEntries.value[0].path, '中睿26年医健产业蓝皮书.md');
  assert.equal(subject.skippedReasonLabel('exists'), '同路径页面已存在，保留原内容');
  assert.equal(subject.errorMessage.value, '');
  assert.equal(subject.importing.value, false);
  assert.ok(subject.events.some(([event]) => event === 'imported'));
});

test('mixed import reports imported and skipped counts independently', async () => {
  const subject = createSubject({
    imported_count: 2,
    skipped_count: 3,
    skipped: [
      { path: 'existing.md', reason: 'exists' },
      { path: 'image.png', reason: 'unsupported' },
      { path: '_index.md', reason: 'reserved' },
    ],
  });
  await subject.pollTask('mixed-import');
  assert.match(subject.successMessage.value, /共导入 2 个页面/);
  assert.match(subject.successMessage.value, /已跳过 3 个文件/);
  assert.equal(subject.skippedReasonLabel('unsupported'), '不支持的文件类型');
  assert.equal(subject.skippedReasonLabel('reserved'), '系统保留页面');
  subject.reset();
  assert.equal(subject.skippedEntries.value.length, 0);
  assert.equal(subject.successMessage.value, '');
});

test('older task results without skipped entries still complete', async () => {
  const subject = createSubject({ success_count: 1 });
  await subject.pollTask('legacy-import');
  assert.equal(subject.successMessage.value, 'Wiki 导入完成，共导入 1 个页面。');
  assert.equal(subject.skippedEntries.value.length, 0);
});

test('malformed skipped entries do not prevent a completed result', async () => {
  const subject = createSubject({
    imported_count: 0,
    skipped: [null, 'invalid', { path: 3 }, { path: 'kept.md', reason: 'exists' }],
  });
  await subject.pollTask('malformed-result');
  assert.equal(subject.errorMessage.value, '');
  assert.equal(subject.skippedEntries.value.length, 1);
  assert.match(subject.successMessage.value, /已跳过 1 个文件/);
});

test('default overwrite remains opt-in and skipped filenames use escaped interpolation', () => {
  assert.match(source, /const overwrite = shallowRef\(false\)/);
  assert.match(source, /默认跳过路径相同的已有页面，保留原内容/);
  assert.match(source, /\{\{ entry\.path \}\}/);
});
