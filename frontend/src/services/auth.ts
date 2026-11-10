import { apiRequest } from './api'
import {
  decodeAccount,
  decodeApplication,
  decodeToken,
} from './account-contract'
import { empty } from './decode'
import { privateRequest, sessions } from './session'

type Credentials = { email: string; password: string }

export function register(credentials: Credentials) {
  return apiRequest('/auth/register', decodeAccount, {
    method: 'POST',
    json: credentials,
  })
}

export async function login(credentials: Credentials) {
  const token = await apiRequest('/auth/login', decodeToken, {
    method: 'POST',
    json: credentials,
  })
  try {
    const account = await apiRequest('/auth/me', decodeAccount, {
      token: token.accessToken,
    })
    sessions.set({
      token: token.accessToken,
      expiresAt: Date.parse(token.expiresAt),
      account,
    })
  } catch (error) {
    await apiRequest('/auth/logout', empty, {
      method: 'POST',
      token: token.accessToken,
    }).catch(() => {})
    throw error
  }
}

export async function refreshAccount() {
  const account = await privateRequest('/auth/me', decodeAccount)
  const current = sessions.get()
  if (current) sessions.set({ ...current, account })
}

export async function logout() {
  const current = sessions.get()
  try {
    if (current)
      await apiRequest('/auth/logout', empty, {
        method: 'POST',
        token: current.token,
      })
  } finally {
    sessions.clear(current?.token)
  }
}

export const getApplication = (signal?: AbortSignal) =>
  privateRequest('/seller-applications/me', decodeApplication, { signal })
export const applyToSell = () =>
  privateRequest('/seller-applications', decodeApplication, {
    method: 'POST',
    json: {},
  })
