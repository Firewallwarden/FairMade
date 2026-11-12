import { spawn } from 'node:child_process'
import { resolve, join } from 'node:path'
import { fileURLToPath } from 'node:url'
const root = resolve(fileURLToPath(new URL('../..', import.meta.url)))
const python = process.env.E2E_PYTHON ?? (process.platform === 'win32'
  ? join(process.env.LOCALAPPDATA, 'FairMade/runtime/venv/Scripts/python.exe') : 'python3')
const child = spawn(python, [join(root, 'frontend/e2e/server.py')], {
  cwd: root, stdio: 'inherit', env: { ...process.env, PYTHONPATH: join(root, 'backend/src') },
})
child.on('error', () => { console.error('Cannot start test Python; set E2E_PYTHON to an installed backend environment.'); process.exit(1) })
child.on('exit', code => process.exit(code ?? 1))
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal))
