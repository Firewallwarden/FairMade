import { choice, integer, list, money, nullable, object, text } from './decode.ts'

export function decodePhoto(value: unknown) {
  const data = object(value)
  return { id: text(data.id), width: integer(data.width), height: integer(data.height), byte_count: integer(data.byte_count) }
}
export function validatePhoto(file: { type: string; size: number }) {
  if (!['image/jpeg', 'image/png'].includes(file.type)) throw new Error('Choose a JPEG or PNG image.')
  if (!file.size || file.size > 5 * 1024 * 1024) throw new Error('Choose a nonempty image no larger than 5 MiB.')
}

export type StorefrontInput = {
  display_name: string; description: string | null; location: string | null
  approximate_area: { label: string; latitude: string; longitude: string; basis: 'seller_chosen_approximate' } | null
}
export function decodeStorefrontContent(value: unknown) {
  const data = object(value)
  return {
    display_name: text(data.display_name), description: nullable(data.description, text), location: nullable(data.location, text),
    approximate_area: nullable(data.approximate_area, (value) => {
      const area = object(value)
      return { label: text(area.label), latitude: money(area.latitude), longitude: money(area.longitude), basis: choice(area.basis, ['seller_chosen_approximate'] as const) }
    }),
  }
}
export function decodeStorefront(value: unknown) {
  const data = object(value)
  return { id: text(data.id), revision: integer(data.revision), state: choice(data.state, ['draft', 'published', 'withdrawn'] as const), content: decodeStorefrontContent(data.content) }
}
export function decodePublicStorefront(value: unknown) {
  const data = object(value)
  const payload = object(data.payload)
  choice(payload.basis, ['seller_reported_unverified'] as const)
  return { id: text(data.id), payload: { ...decodeStorefrontContent(payload), notices: list(payload.notices, text) } }
}
