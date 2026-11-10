import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  decodeAccount,
  decodeApplication,
  decodeToken,
} from '../src/services/account-contract.ts'
import { createSessionStore } from '../src/services/session-store.ts'

const account = {
  id: 'synthetic-account',
  email: 'buyer@example.test',
  roles: ['buyer'] as const,
}

test('account and token contracts reject role escalation and malformed expiry', () => {
  assert.equal(decodeAccount(account).roles[0], 'buyer')
  assert.throws(() => decodeAccount({ ...account, roles: ['owner'] }))
  assert.throws(() =>
    decodeToken({
      access_token: '',
      token_type: 'bearer',
      expires_at: '2026-11-09T10:00:00Z',
    }),
  )
  assert.throws(() =>
    decodeToken({
      access_token: 'synthetic',
      token_type: 'bearer',
      expires_at: 'tomorrow',
    }),
  )
})

test('pending application cannot imply seller approval', () => {
  const application = decodeApplication({
    id: 'synthetic',
    status: 'pending',
    revision: 1,
    submitted_at: '2026-11-09T10:00:00Z',
    decision: null,
  })
  assert.equal(application.status, 'pending')
  assert.equal(application.decision, null)
  assert.throws(() => decodeApplication({ status: 'verified' }))
})

test('session expiration clears memory and stale clears cannot remove a newer login', async () => {
  const store = createSessionStore()
  const user = decodeAccount(account)
  let notifications = 0
  const unsubscribe = store.subscribe(() => notifications++)
  store.set({ token: 'first', expiresAt: Date.now() + 1000, account: user })
  store.set({ token: 'second', expiresAt: Date.now() + 25, account: user })
  store.clear('first')
  assert.equal(store.get()?.token, 'second')
  await new Promise((resolve) => setTimeout(resolve, 60))
  assert.equal(store.get(), null)
  assert.equal(notifications, 3)
  store.set({ token: 'expired', expiresAt: Date.now() - 1, account: user })
  assert.equal(store.get(), null)
  unsubscribe()
})
