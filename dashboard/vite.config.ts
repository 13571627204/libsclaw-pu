import { readFileSync } from 'fs';
import { hostname } from 'os';
import { fileURLToPath, URL } from 'url';
import { createLogger, defineConfig, type Logger, type Plugin } from 'vite';
import vue from '@vitejs/plugin-vue';
import vuetify from 'vite-plugin-vuetify';
import webfontDl from 'vite-plugin-webfont-dl';
// @ts-ignore — .mjs not in TS project scope; Vite resolves this at runtime
import { runMdiSubset } from './scripts/subset-mdi-font.mjs';

const t2iShikiRuntimePath = fileURLToPath(
  new URL('../astrbot/core/utils/t2i/template/shiki_runtime.iife.js', import.meta.url)
);
const devBackendPort = Number(process.env.LIBSCLAW_DEV_BACKEND_PORT ?? 6185);
const devFrontendPort = Number(process.env.LIBSCLAW_DEV_FRONTEND_PORT ?? 3007);
const devHostname = hostname().toLowerCase();

// The Python backend boots slower than Vite; during that window every proxied
// API request logs an ECONNREFUSED error. Silence those, keep real errors.
const viteLogger = createLogger();
const quietProxyLogger: Logger = {
  ...viteLogger,
  error(msg, options) {
    if (String(msg).includes('ECONNREFUSED')) return;
    viteLogger.error(msg, options);
  }
};

// Vite plugin: run MDI icon font subsetting (build only)
function mdiSubset() {
  return {
    name: 'vite-plugin-mdi-subset',
    async buildStart() {
      console.log('\n🔧 Running MDI icon font subsetting...');
      await runMdiSubset();
    },
  };
}

function t2iShikiRuntimeAsset(): Plugin {
  return {
    name: 'vite-plugin-t2i-shiki-runtime',
    configureServer(server) {
      server.middlewares.use('/t2i/shiki_runtime.iife.js', (_req, res) => {
        try {
          res.statusCode = 200;
          res.setHeader('Content-Type', 'text/javascript; charset=utf-8');
          res.end(readFileSync(t2iShikiRuntimePath));
        } catch (error) {
          res.statusCode = 404;
          res.end(`T2I Shiki runtime not found: ${error instanceof Error ? error.message : String(error)}`);
        }
      });
    },
    generateBundle() {
      try {
        this.emitFile({
          type: 'asset',
          fileName: 't2i/shiki_runtime.iife.js',
          source: readFileSync(t2iShikiRuntimePath)
        });
      } catch (error) {
        this.warn(
          `Skipping T2I Shiki runtime asset because it could not be read: ${
            error instanceof Error ? error.message : String(error)
          }`
        );
      }
    }
  };
}

// https://vitejs.dev/config/
export default defineConfig(({ command }) => ({
  customLogger: quietProxyLogger,
  plugins: [
    // Only run MDI subsetting during production builds, skip in dev server
    ...(command === 'build' ? [mdiSubset()] : []),
    t2iShikiRuntimeAsset(),
    vue({
      template: {
        compilerOptions: {
          isCustomElement: (tag) => ['v-list-recognize-title'].includes(tag)
        }
      }
    }),
    vuetify({
      autoImport: true
    }),
    webfontDl()
  ],
  resolve: {
    alias: [
      {
        find: /^shiki$/,
        replacement: fileURLToPath(new URL('./src/utils/shikiLimitedBundle.js', import.meta.url))
      },
      {
        find: /^stream-monaco$/,
        replacement: fileURLToPath(new URL('./src/utils/streamMonacoDisabled.js', import.meta.url))
      },
      {
        find: 'mermaid',
        replacement: 'mermaid/dist/mermaid.js'
      },
      {
        find: '@',
        replacement: fileURLToPath(new URL('./src', import.meta.url))
      }
    ]
  },
  css: {
    preprocessorOptions: {
      scss: {}
    }
  },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 1024 * 1024 // Set the limit to 1 MB
  },
  optimizeDeps: {
    exclude: ['vuetify'],
    entries: ['./src/**/*.vue']
  },
  server: {
    host: '0.0.0.0',
    port: devFrontendPort,
    strictPort: true,
    // 局域网 IP 会随网络变化；允许用本机计算机名访问（如 http://LEO:3007），地址固定不变
    allowedHosts: [devHostname, `${devHostname}.local`],
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${devBackendPort}/`,
        changeOrigin: true,
        ws: true,
        // 配图/批量生成等长耗时请求可达十几分钟，避免代理层提前断开导致 Network Error
        timeout: 30 * 60 * 1000,
        proxyTimeout: 30 * 60 * 1000,
        // Backend not up yet (booting/restarting): answer 503 with a marker
        // header instead of Vite's default 500, so the client can retry.
        configure: (proxy) => {
          proxy.on('error', (_err, _req, res) => {
            if (!('writeHead' in res) || res.headersSent || res.writableEnded) return;
            res.writeHead(503, {
              'Content-Type': 'application/json; charset=utf-8',
              'X-Backend-Unavailable': '1'
            });
            res.end(JSON.stringify({ status: 'error', message: '后端服务启动中，请稍候' }));
          });
        }
      }
    }
  }
}));
