export function publicMediaUrl(path: string): string | undefined {
  // Backend media paths are local API routes; reject arbitrary URL schemes.
  if (!path.startsWith('/api/v1/')) return undefined
  const base = import.meta.env.VITE_API_BASE_URL
  if (!base || !/^https?:\/\//.test(base)) return path
  return new URL(path, base).href
}
