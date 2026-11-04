import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { viteSingleFile } from 'vite-plugin-singlefile'

// 产物必须是**单个** index.html：pywebview 用 file:// 加载它，
// 而 file:// 下 <script type="module" src> 会被 CORS 拦掉。
export default defineConfig({
  plugins: [vue(), viteSingleFile()],
  base: './',
  build: {
    target: 'es2020',
    outDir: 'dist',
    cssCodeSplit: false,
    assetsInlineLimit: 100_000_000,
    reportCompressedSize: false,
  },
})
