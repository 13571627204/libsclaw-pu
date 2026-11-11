import { buildTranslationBundle } from './buildTranslationBundle';

const modules = import.meta.glob('../locales/zh-CN/**/*.json', {
  eager: true,
  import: 'default',
});

export default buildTranslationBundle(modules);
