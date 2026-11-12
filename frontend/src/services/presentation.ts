import { apiRequest } from './api'
import { privateRequest } from './session'
import { empty, integer, list, object, page, text } from './decode'
import { decodeCard } from './catalog-contract'
import {
  decodePhoto,
  decodePublicStorefront,
  decodeStorefront,
  decodeStorefrontContent,
  validatePhoto,
} from './presentation-contract'
import type { StorefrontInput } from './presentation-contract'

export const getPhotos = (id: string, signal?: AbortSignal) =>
  privateRequest(`/products/${id}/photos?limit=10`, page(decodePhoto), {
    signal,
  })
export const getPhotoContent = (
  id: string,
  photo: string,
  signal?: AbortSignal,
) =>
  privateRequest(
    `/products/${id}/photos/${photo}/content`,
    (value) => {
      if (!(value instanceof Blob)) throw new Error('Expected image')
      return value
    },
    { binary: true, signal },
  )
export function uploadPhoto(id: string, file: File) {
  validatePhoto(file)
  return privateRequest(`/products/${id}/photos`, decodePhoto, {
    method: 'POST',
    raw: file,
    headers: { 'Content-Type': file.type },
  })
}
export const deletePhoto = (id: string, photo: string) =>
  privateRequest(`/products/${id}/photos/${photo}`, empty, { method: 'DELETE' })
export const getOwnStorefronts = (signal?: AbortSignal) =>
  privateRequest('/seller/storefronts?limit=20', page(decodeStorefront), {
    signal,
  })
export const saveStorefront = (
  data: StorefrontInput,
  id?: string,
  revision?: number,
) =>
  privateRequest(
    id ? `/seller/storefronts/${id}` : '/seller/storefronts',
    decodeStorefront,
    {
      method: id ? 'PUT' : 'POST',
      json: id ? { ...data, expected_revision: revision } : data,
    },
  )
export const getStorefrontPreview = (id: string) =>
  privateRequest(`/seller/storefronts/${id}/preview`, (value) => {
    const data = object(value)
    const payload = object(data.payload)
    return {
      revision: integer(data.revision),
      preview_hash: text(data.preview_hash),
      payload: {
        ...decodeStorefrontContent(payload),
        notices: list(payload.notices, text),
      },
    }
  })
export const publishStorefront = (id: string, revision: number, hash: string) =>
  privateRequest(`/seller/storefronts/${id}/publish`, decodePublicStorefront, {
    method: 'POST',
    json: { expected_revision: revision, preview_hash: hash, approved: true },
  })
export const withdrawStorefront = (id: string) =>
  privateRequest(`/seller/storefronts/${id}/withdraw`, empty, {
    method: 'POST',
  })
export function browseStorefronts(
  q: string,
  location: string,
  offset: number,
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({ limit: '12', offset: String(offset) })
  if (q) query.set('q', q)
  if (location) query.set('location', location)
  return apiRequest(`/storefronts?${query}`, page(decodePublicStorefront), {
    signal,
  })
}
export const getPublicStorefront = (id: string, signal?: AbortSignal) =>
  apiRequest(`/storefronts/${id}`, decodePublicStorefront, { signal })
export const getStorefrontListings = (
  id: string,
  offset: number,
  signal?: AbortSignal,
) =>
  apiRequest(
    `/storefronts/${id}/listings?limit=12&offset=${offset}`,
    page(decodeCard),
    { signal },
  )
export const searchNearbyStorefronts = (
  input: { latitude: string; longitude: string; radius: string; q: string },
  offset: number,
  signal?: AbortSignal,
) =>
  apiRequest(
    '/discovery/storefronts',
    (value) => {
      const data = object(value)
      return {
        ...page((value) => {
          const row = object(value)
          return {
            ...decodePublicStorefront(row.storefront),
            distance: text(row.estimated_distance_km),
          }
        })(data),
        notices: list(data.notices, text),
      }
    },
    {
      method: 'POST',
      signal,
      json: {
        origin: { latitude: input.latitude, longitude: input.longitude },
        radius_km: input.radius,
        ...(input.q && { q: input.q }),
        limit: 12,
        offset,
      },
    },
  )
