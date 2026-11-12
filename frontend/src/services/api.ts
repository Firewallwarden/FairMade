import { createApiClient } from './http'

// VITE_ configuration is public. Only an API URL belongs here, never credentials.
export const apiRequest = createApiClient(import.meta.env.VITE_API_BASE_URL ?? '/api/v1')
