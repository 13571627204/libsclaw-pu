// 构建后把核心版本号写入 dist/assets/version，
// 供后端启动时校验 WebUI 与核心版本是否匹配。
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const pyproject = readFileSync(join(root, '..', 'pyproject.toml'), 'utf-8');
const match = pyproject.match(/^version = "([^"]+)"/m);
if (!match) {
  console.error('[write-dist-version] 无法从 pyproject.toml 解析版本号');
  process.exit(1);
}
const version = `v${match[1]}`;
const assetsDir = join(root, 'dist', 'assets');
mkdirSync(assetsDir, { recursive: true });
writeFileSync(join(assetsDir, 'version'), version);
console.log(`[write-dist-version] dist/assets/version = ${version}`);
