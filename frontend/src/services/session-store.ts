import type { Account } from './account-contract.ts'

export type Session = { token: string; expiresAt: number; account: Account }

// Tokens live only in this closure. No browser storage, cookies or refresh policy.
export function createSessionStore() {
  let current: Session | null = null
  let expiry: ReturnType<typeof setTimeout> | undefined
  const listeners = new Set<() => void>()
  const publish = () => listeners.forEach((listener) => listener())

  function clear(token?: string) {
    if (token !== undefined && current?.token !== token) return
    clearTimeout(expiry)
    current = null
    publish()
  }

  return {
    get: () => current,
    subscribe(listener: () => void) {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    set(session: Session) {
      clearTimeout(expiry)
      if (session.expiresAt <= Date.now()) {
        clear()
        return
      }
      current = session
      expiry = setTimeout(
        () => clear(session.token),
        session.expiresAt - Date.now(),
      )
      publish()
    },
    clear,
  }
}
