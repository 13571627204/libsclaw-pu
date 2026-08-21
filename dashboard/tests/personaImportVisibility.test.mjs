import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const personaManagerSource = await readFile(
  new URL('../src/views/persona/PersonaManager.vue', import.meta.url),
  'utf8',
);

test('persona manager hides the import persona button', () => {
  assert.doesNotMatch(personaManagerSource, /tm\('buttons\.import'\)/);
  assert.doesNotMatch(personaManagerSource, /persona-action-btn--import/);
  assert.match(personaManagerSource, /tm\('buttons\.create'\)/);
  assert.match(personaManagerSource, /tm\('folder\.createButton'\)/);
});
