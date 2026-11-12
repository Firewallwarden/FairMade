import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ApiError, createApiClient } from '../src/services/http.ts'

test('sends JSON with explicit bearer auth and no cookie credentials', async () => {
  let called = false
  const request = createApiClient('/api/v1/', async (url, options) => {
    called = true
    assert.equal(url, '/api/v1/example')
    assert.equal(options?.body, '{"amount":"12.01"}')
    assert.equal(new Headers(options?.headers).get('Authorization'), 'Bearer synthetic-test-token')
    assert.equal(new Headers(options?.headers).get('Content-Type'), 'application/json')
    assert.equal(options?.credentials, 'omit')
    assert.equal(options?.cache, 'no-store')
    return Response.json({ ok: true })
  })
  assert.deepEqual(await request('/example', (value) => value, { method: 'POST', json: { amount: '12.01' }, token: 'synthetic-test-token' }), { ok: true })
  assert.equal(called, true)
})

test('supports 204 responses without JSON parsing', async () => {
  const request = createApiClient('/api/v1', async () => new Response(null, { status: 204 }))
  assert.equal(await request('/logout', (value) => value), undefined)
})

test('preserves domain error codes and exposes only validation location/message', async () => {
  const domain = createApiClient('', async () => Response.json({ detail: { code: 'REVISION_CONFLICT', message: 'Reload before editing.' } }, { status: 409 }))
  await assert.rejects(domain('/example', (value) => value), (error: unknown) => error instanceof ApiError && error.code === 'REVISION_CONFLICT' && error.status === 409)
  const invalid = createApiClient('', async () => Response.json({ detail: [{ loc: ['body', 'costs', 0, 'amount'], msg: 'Invalid decimal', input: 'must not be forwarded' }] }, { status: 422 }))
  await assert.rejects(invalid('/example', (value) => value), (error: unknown) => {
    assert.ok(error instanceof ApiError)
    assert.deepEqual(error.issues, [{ field: 'body.costs.0.amount', message: 'Invalid decimal' }])
    assert.equal(JSON.stringify(error).includes('must not be forwarded'), false)
    return true
  })
})

test('handles unreachable APIs, unreadable responses and contract mismatches', async () => {
  const unreachable = createApiClient('', async () => { throw new TypeError('Internal network detail') })
  await assert.rejects(unreachable('/example', (value) => value), (error: unknown) => error instanceof ApiError && error.status === 0 && !error.message.includes('Internal network detail'))
  const html = createApiClient('', async () => new Response('<html>proxy failure</html>', { status: 502 }))
  await assert.rejects(html('/example', (value) => value), /unreadable response/)
  const mismatch = createApiClient('', async () => Response.json({ wrong: true }))
  await assert.rejects(mismatch('/example', () => { throw new Error('wrong schema') }), /does not match/)
})

test('keeps cancellation distinguishable from API failure', async () => {
  const request = createApiClient('', async () => { throw new DOMException('Aborted', 'AbortError') })
  await assert.rejects(request('/example', (value) => value), { name: 'AbortError' })
})
