import { privateRequest } from './session'
import { page, object, text } from './decode'
import {
  decodeGroup,
  decodeAnimal,
  decodeLivestockHistory,
} from './livestock-contract'
import type { LivestockChange, LivestockKind } from './livestock-contract'
import { decodeProductionSummary } from './production-contract'
export const getGroups = (
  offset: number,
  signal?: AbortSignal,
  activeOnly = false,
) =>
  privateRequest(
    `/seller/livestock/groups?limit=20&offset=${offset}${activeOnly ? '&archived=false' : ''}`,
    page(decodeGroup),
    { signal },
  )
export const getAnimals = (
  offset: number,
  signal?: AbortSignal,
  activeOnly = false,
) =>
  privateRequest(
    `/seller/livestock/animals?limit=20&offset=${offset}${activeOnly ? '&status=active' : ''}`,
    page(decodeAnimal),
    { signal },
  )
export const getGroup = (id: string, signal?: AbortSignal) =>
  privateRequest(`/seller/livestock/groups/${id}`, decodeGroup, { signal })
export const getAnimal = (id: string, signal?: AbortSignal) =>
  privateRequest(`/seller/livestock/animals/${id}`, decodeAnimal, { signal })
export const saveLivestock = (
  kind: LivestockKind,
  request: LivestockChange,
  id?: string,
) =>
  privateRequest(
    `/seller/livestock/${kind}${id ? '/' + id : ''}`,
    decodeLivestockHistory,
    { method: id ? 'PUT' : 'POST', json: request },
  )
export const getLivestockHistory = (
  kind: LivestockKind,
  id: string,
  offset: number,
  signal?: AbortSignal,
) =>
  privateRequest(
    `/seller/livestock/${kind}/${id}/history?limit=20&offset=${offset}`,
    page(decodeLivestockHistory),
    { signal },
  )
export const getLivestockProduction = (
  kind: LivestockKind,
  id: string,
  offset: number,
  signal?: AbortSignal,
) =>
  privateRequest(
    `/seller/livestock/${kind}/${id}/production-records?limit=20&offset=${offset}`,
    page((value) => ({
      ...decodeProductionSummary(value),
      product_id: text(object(value).product_id),
    })),
    { signal },
  )
