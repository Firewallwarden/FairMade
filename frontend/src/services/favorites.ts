import { privateRequest } from './session'
import { boolean, empty, nullable, object, page, text } from './decode'
import { decodeCard } from './catalog-contract'

function decodeFavorite(value: unknown) {
  const data = object(value)
  return {
    id: text(data.id),
    listing_id: text(data.listing_id),
    listing_visible: boolean(data.listing_visible),
    listing: nullable(data.listing, decodeCard),
  }
}
export const getFavorites = (offset: number, signal?: AbortSignal) =>
  privateRequest(`/favorites?limit=20&offset=${offset}`, page(decodeFavorite), {
    signal,
  })
export const saveFavorite = (listingId: string) =>
  privateRequest('/favorites', decodeFavorite, {
    method: 'POST',
    json: { listing_id: listingId },
  })
export const removeFavorite = (id: string) =>
  privateRequest(`/favorites/${id}`, empty, { method: 'DELETE' })
