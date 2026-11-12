import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

function sourceIdentity() {
  const supplied = process.env.FAIRMADE_SOURCE_REVISION
  if (supplied && /^[a-f0-9]{40}$/i.test(supplied))
    return { revision: supplied, state: 'exported-snapshot' }
  try {
    const cwd = fileURLToPath(new URL('.', import.meta.url))
    const revision = execFileSync('git', ['rev-parse', 'HEAD'], { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
    const changes = execFileSync('git', ['status', '--porcelain', '--', 'src', 'index.html', 'vite.config.ts', 'package.json', 'package-lock.json'], { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
    return { revision, state: changes ? 'modified' : 'clean' }
  } catch {
    return { revision: 'unknown', state: 'unknown' }
  }
}
export default defineConfig({
  plugins: [react(), tailwindcss(), {
    name: 'fairmade-source-identity',
    transformIndexHtml() {
      const identity = sourceIdentity()
      return [
        { tag: 'meta', attrs: { name: 'fairmade-source-revision', content: identity.revision }, injectTo: 'head' },
        { tag: 'meta', attrs: { name: 'fairmade-source-state', content: identity.state }, injectTo: 'head' },
      ]
    },
  }],
  server: {
    proxy: { '/api': { target: process.env.FAIRMADE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000', changeOrigin: true } },
  },
})
