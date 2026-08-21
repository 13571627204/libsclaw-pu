import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const consolePageSource = await readFile(
  new URL('../src/views/ConsolePage.vue', import.meta.url),
  'utf8',
);

test('console page keeps the displayer and removes legacy controls', () => {
  assert.match(consolePageSource, /<ConsoleDisplayer\b/);
  assert.doesNotMatch(consolePageSource, /自动滚动已开启|自动滚动已关闭/);
  assert.doesNotMatch(consolePageSource, /autoScroll\.(?:enabled|disabled)/);
  assert.doesNotMatch(consolePageSource, /console-autoscroll-card/);
  assert.doesNotMatch(consolePageSource, /pipInstall\.button/);
  assert.doesNotMatch(consolePageSource, /console-pip-btn/);
  assert.doesNotMatch(consolePageSource, /<v-dialog\b[\s\S]*pipDialog/);
});
