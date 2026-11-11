import zhCN from './bundles/zh-CN';
import type { TranslationBundle } from './bundles/buildTranslationBundle';
import type { Locale } from './types';

export const DEFAULT_LOCALE: Locale = 'zh-CN';
export const defaultTranslations = zhCN;

const translationCache = new Map<Locale, TranslationBundle>([
  [DEFAULT_LOCALE, defaultTranslations],
]);

const translationLoaders: Record<Locale, () => Promise<TranslationBundle>> = {
  'zh-CN': async () => defaultTranslations,
  'en-US': async () => (await import('./bundles/en-US')).default,
  'ru-RU': async () => (await import('./bundles/ru-RU')).default,
};

export function isSupportedLocale(value: unknown): value is Locale {
  return typeof value === 'string' && value in translationLoaders;
}

export async function loadTranslationBundle(
  locale: Locale,
): Promise<TranslationBundle> {
  const cached = translationCache.get(locale);
  if (cached) {
    return cached;
  }

  const bundle = await translationLoaders[locale]();
  translationCache.set(locale, bundle);
  return bundle;
}

export type TranslationData = TranslationBundle;
