// Future HTTP requests share this helper. No backend requests are made yet.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'
export async function apiRequest<T>(path: `/${string}`, options?: RequestInit): Promise<T> {
 const response = await fetch(`${API_BASE_URL}${path}`, options)
 if (!response.ok) throw new Error(`Request failed (${response.status})`)
 return response.json() as Promise<T>
}
