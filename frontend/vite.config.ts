import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

const apiProxyTarget = process.env.VITE_DEV_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    watch: {
      // Docker Desktop 的 Windows/macOS bind mount 不透传 inotify 事件，
      // 容器内需用轮询感知文件变化（由 compose 注入 CHOKIDAR_USEPOLLING=true）；
      // 本地直跑 `npm run dev` 时保持默认的事件监听，无额外开销。
      usePolling: process.env.CHOKIDAR_USEPOLLING === 'true',
      interval: 300,
    },
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
        // SSE 流式问答（/chat/stream）：剥离压缩/定长响应头，确保增量即时透传、不被代理缓冲
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            if (String(proxyRes.headers['content-type'] ?? '').includes('text/event-stream')) {
              delete proxyRes.headers['content-encoding']
              delete proxyRes.headers['content-length']
            }
          })
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.spec.ts'],
  },
})
