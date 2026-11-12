import { readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'

const root = resolve('.e2e')
const runs = readdirSync(root).filter(name => /^[a-f0-9-]{36}$/i.test(name))
  .map(name => ({ name, path: join(root, name, 'browser-endpoints.jsonl') }))
  .filter(run => { try { return statSync(run.path).isFile() } catch { return false } })
  .sort((a, b) => statSync(b.path).mtimeMs - statSync(a.path).mtimeMs)
const run = process.argv[2] ? runs.find(run => run.name === process.argv[2]) : runs[0]
if (!run) throw new Error('No browser endpoint audit found. Run the suite first.')
const calls = readFileSync(run.path, 'utf8').trim().split('\n').map(line => JSON.parse(line))
const endpoints = new Map()
for (const call of calls) {
  const key = `${call.method} ${call.route}`
  const statuses = endpoints.get(key) ?? new Set()
  statuses.add(call.status)
  endpoints.set(key, statuses)
}
const report = {
  run: run.name,
  basis: 'Observed browser responses only; excludes API seeding and does not imply unexecuted provider coverage.',
  requests: calls.length,
  uniqueMethodRoutes: endpoints.size,
  endpoints: [...endpoints].sort(([a], [b]) => a.localeCompare(b)).map(([endpoint, statuses]) => ({ endpoint, statuses: [...statuses].sort() })),
}
writeFileSync(join(root, 'endpoint-coverage.json'), JSON.stringify(report, null, 2) + '\n')
console.log(`Observed ${report.uniqueMethodRoutes} method/routes in ${report.requests} browser responses; run ${report.run}.`)
