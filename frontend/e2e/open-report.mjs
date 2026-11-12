import { readdirSync, statSync, existsSync } from 'node:fs'
import { join, resolve, dirname } from 'node:path'
import { createRequire } from 'node:module'
import { spawn } from 'node:child_process'
const root = resolve('.e2e')
const reports = readdirSync(root).filter(name => /^[a-f0-9-]{36}$/i.test(name))
  .map(name => ({ name, path: join(root, name, 'report') }))
  .filter(report => existsSync(join(report.path, 'index.html')))
  .sort((a, b) => statSync(join(b.path, 'index.html')).mtimeMs - statSync(join(a.path, 'index.html')).mtimeMs)
const report = process.argv[2] ? reports.find(report => report.name === process.argv[2]) : reports[0]
if (!report) throw new Error('No completed browser report found. Run the suite first.')
const require = createRequire(import.meta.url)
const cli = join(dirname(require.resolve('@playwright/test/package.json')), 'cli.js')
const child = spawn(process.execPath, [cli, 'show-report', report.path], { stdio: 'inherit' })
child.on('exit', code => process.exit(code ?? 1))
