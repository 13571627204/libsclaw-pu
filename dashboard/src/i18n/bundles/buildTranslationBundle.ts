export type TranslationBundle = Record<string, any>;

const LEGACY_KEY_ALIASES: Record<string, string> = {
  'features/tool-use': 'features/tooluse',
};

/**
 * Convert locale JSON modules into the nested object consumed by useI18n().
 * Each locale owns a separate bundle so Vite can keep unused languages out of
 * the initial dashboard chunk.
 */
export function buildTranslationBundle(
  modules: Record<string, unknown>,
): TranslationBundle {
  const bundle: TranslationBundle = {};

  for (const [modulePath, moduleValue] of Object.entries(modules)) {
    const relativePath = modulePath
      .replace(/^.*\/locales\/[^/]+\//, '')
      .replace(/\.json$/, '');
    const normalizedPath = LEGACY_KEY_ALIASES[relativePath] || relativePath;
    const segments = normalizedPath.split('/').filter(Boolean);

    if (segments.length === 0) {
      continue;
    }

    let target = bundle;
    for (const segment of segments.slice(0, -1)) {
      if (!target[segment] || typeof target[segment] !== 'object') {
        target[segment] = {};
      }
      target = target[segment];
    }

    const finalKey = segments[segments.length - 1];
    target[finalKey] = moduleValue;
  }

  return bundle;
}
