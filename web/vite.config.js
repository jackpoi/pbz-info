import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { viteSingleFile } from 'vite-plugin-singlefile'

// 版本号唯一来源：app/__init__.py 的 __version__。
// 前端只读它，不再维护第二份；exe 文件属性由 tools/build_assets.py 从同一处派生。
const appInit = fileURLToPath(new URL('../app/__init__.py', import.meta.url))
const version = (readFileSync(appInit, 'utf-8').match(/__version__\s*=\s*["']([^"']+)["']/) || [])[1] || '0.0.0'

// 产物必须是**单个** index.html：pywebview 用 file:// 加载它，
// 而 file:// 下 <script type="module" src> 会被 CORS 拦掉。
export default defineConfig({
  plugins: [vue(), viteSingleFile()],
  base: './',
  define: {
    __APP_VERSION__: JSON.stringify(version),
  },
  build: {
    target: 'es2020',
    outDir: 'dist',
    cssCodeSplit: false,
    assetsInlineLimit: 100_000_000,
    reportCompressedSize: false,
  },
})
