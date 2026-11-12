import { privateRequest } from './session'
import { ApiError } from './http'
import { page } from './decode'
import {
  decodeRecipe,
  decodeRecipeCosting,
  decodeRecipeCostingSummary,
  decodeProduction,
  decodeProductionSummary,
} from './production-contract'
import type { RecipeData, ProductionInput } from './production-contract'
export async function getRecipe(product: string, signal?: AbortSignal) {
  try {
    return await privateRequest(`/products/${product}/recipe`, decodeRecipe, {
      signal,
    })
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}
export const saveRecipe = (
  product: string,
  data: RecipeData,
  revision?: number,
) =>
  privateRequest(`/products/${product}/recipe`, decodeRecipe, {
    method: revision === undefined ? 'POST' : 'PUT',
    json:
      revision === undefined ? data : { ...data, expected_revision: revision },
  })
export const getRecipeCostings = (
  product: string,
  offset: number,
  signal?: AbortSignal,
) =>
  privateRequest(
    `/products/${product}/recipe/costings?limit=20&offset=${offset}`,
    page(decodeRecipeCostingSummary),
    { signal },
  )
export const getRecipeCosting = (product: string, id: string) =>
  privateRequest(
    `/products/${product}/recipe/costings/${id}`,
    decodeRecipeCosting,
  )
export const createRecipeCosting = (
  product: string,
  revision: number,
  requestId: string,
) =>
  privateRequest(`/products/${product}/recipe/costings`, decodeRecipeCosting, {
    method: 'POST',
    json: { expected_revision: revision, request_id: requestId },
  })
export const getProductionRecords = (
  product: string,
  offset: number,
  includeCorrected: boolean,
  signal?: AbortSignal,
) =>
  privateRequest(
    `/products/${product}/production-records?limit=20&offset=${offset}&include_corrected=${includeCorrected}`,
    page(decodeProductionSummary),
    { signal },
  )
export const getProductionRecord = (product: string, id: string) =>
  privateRequest(
    `/products/${product}/production-records/${id}`,
    decodeProduction,
  )
export const createProductionRecord = (
  product: string,
  request: ProductionInput,
) =>
  privateRequest(`/products/${product}/production-records`, decodeProduction, {
    method: 'POST',
    json: request,
  })
