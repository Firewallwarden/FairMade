import { privateRequest } from './session'
import { page } from './decode'
import { decodeMaterial, decodeMaterialMovement } from './material-contract'
import type { MaterialMovementInput, materialUnits } from './material-contract'
export const getMaterials = (offset: number, signal?: AbortSignal) =>
  privateRequest(
    `/seller/materials?limit=20&offset=${offset}`,
    page(decodeMaterial),
    { signal },
  )
export const getMaterial = (id: string, signal?: AbortSignal) =>
  privateRequest(`/seller/materials/${id}`, decodeMaterial, { signal })
export const createMaterial = (data: {
  name: string
  notes: string | null
  unit: (typeof materialUnits)[number]
}) =>
  privateRequest('/seller/materials', decodeMaterial, {
    method: 'POST',
    json: data,
  })
export const editMaterial = (
  id: string,
  revision: number,
  name: string,
  notes: string | null,
) =>
  privateRequest(`/seller/materials/${id}`, decodeMaterial, {
    method: 'PUT',
    json: { expected_revision: revision, name, notes },
  })
export const getMaterialMovements = (
  id: string,
  offset: number,
  signal?: AbortSignal,
) =>
  privateRequest(
    `/seller/materials/${id}/movements?limit=20&offset=${offset}`,
    page(decodeMaterialMovement),
    { signal },
  )
export const createMaterialMovement = (
  id: string,
  request: MaterialMovementInput,
) =>
  privateRequest(`/seller/materials/${id}/movements`, decodeMaterialMovement, {
    method: 'POST',
    json: request,
  })
