import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const personaFormSource = await readFile(
  new URL('../src/components/shared/PersonaForm.vue', import.meta.url),
  'utf8',
);

test('persona form shows the preset dialogs panel only while editing', () => {
  const dialogsPanelTag = personaFormSource.match(
    /<v-expansion-panel\b(?=[^>]*\bvalue="dialogs")[^>]*>/,
  )?.[0];

  assert.ok(dialogsPanelTag, 'the editable preset dialogs panel must remain');
  assert.match(dialogsPanelTag, /\bv-if="editingPersona"/);
});

test('persona form expands dialogs on desktop only while editing', () => {
  const defaultExpandedPanelsMethod = personaFormSource.match(
    /getDefaultExpandedPanels\(\)\s*\{([\s\S]*?)\n\s*\},/,
  )?.[1];

  assert.ok(defaultExpandedPanelsMethod, 'default panel logic must remain');
  assert.match(defaultExpandedPanelsMethod, /smAndDown/);
  assert.match(defaultExpandedPanelsMethod, /editingPersona[\s\S]*dialogs/);
  assert.doesNotMatch(
    defaultExpandedPanelsMethod,
    /:\s*\['tools',\s*'skills',\s*'dialogs'\]\s*;/,
  );
});

test('persona form keeps dialog data, tools, skills, and save capabilities', () => {
  assert.match(personaFormSource, /initForm\(\)\s*\{[\s\S]*?begin_dialogs:\s*\[\]/);
  assert.match(personaFormSource, /v-model="personaForm\.begin_dialogs\[index\]"/);
  assert.match(
    personaFormSource,
    /begin_dialogs:\s*\[\.\.\.\(persona\.begin_dialogs \|\| \[\]\)\]/,
  );
  assert.match(
    personaFormSource,
    /if \(this\.personaForm\.begin_dialogs\.length > 0\)[\s\S]*?dialogRequired/,
  );
  assert.match(
    personaFormSource,
    /personaApi\.update\(this\.personaForm\.persona_id, this\.personaForm\)/,
  );
  assert.match(personaFormSource, /personaApi\.create\(this\.personaForm\)/);
  assert.match(personaFormSource, /<v-expansion-panel value="tools">/);
  assert.match(personaFormSource, /<v-expansion-panel value="skills">/);
  assert.match(personaFormSource, /@click="savePersona"/);
});
