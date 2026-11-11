import { buildTranslationBundle } from './buildTranslationBundle';

const modules = import.meta.glob('../locales/ru-RU/**/*.json', {
  eager: true,
  import: 'default',
});

export default buildTranslationBundle(modules);
