import { defineAsyncComponent } from 'vue';

/**
 * Monaco 编辑器的异步封装。
 *
 * monaco-editor 体积有数 MB，静态 import 会让所有引用它的路由 chunk
 * 都带上编辑器代码。这里通过 defineAsyncComponent 把 monaco 本体与
 * 初始化插件（@/plugins/monaco）拆到独立的异步 chunk，仅在编辑器
 * 真正渲染时才加载。
 */
const AsyncMonacoEditor = defineAsyncComponent(async () => {
  await import('@/plugins/monaco');
  const mod = await import('@guolao/vue-monaco-editor');
  return mod.VueMonacoEditor;
});

export default AsyncMonacoEditor;
