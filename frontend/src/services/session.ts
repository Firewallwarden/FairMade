import { useSyncExternalStore } from 'react'
import { apiRequest } from './api'
import { ApiError } from './http'
import { createSessionStore } from './session-store'

export const sessions = createSessionStore()
export function useSession() {
  return useSyncExternalStore(sessions.subscribe, sessions.get)
}

export async function privateRequest<T>(
  path: `/${string}`,
  decode: (value: unknown) => T,
  options: {
    method?: string
    json?: unknown
    signal?: AbortSignal
    headers?: HeadersInit
    timeoutMs?: number
    raw?: Blob
    binary?: boolean
  } = {},
) {
  const session = sessions.get()
  if (!session || session.expiresAt <= Date.now()) {
    sessions.clear(session?.token)
    throw new ApiError('Please sign in to continue.', 401)
  }
  try {
    const result = await apiRequest(path, decode, {
      ...options,
      token: session.token,
    })
    // Discard data from an account that was logged out while this request ran.
    if (sessions.get()?.token !== session.token)
      throw new ApiError('Your session changed. Please try again.', 401)
    return result
  } catch (error) {
    if (error instanceof ApiError && error.status === 401)
      sessions.clear(session.token)
    throw error
  }
}
