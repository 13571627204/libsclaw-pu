import { buildTranslationBundle } from './buildTranslationBundle';

const modules = import.meta.glob('../locales/en-US/**/*.json', {
  eager: true,
  import: 'default',
});

export default buildTranslationBundle(modules);
