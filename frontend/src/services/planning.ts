import { privateRequest } from './session'
import { decodeBasket, decodeBundles } from './planning-contract'
import type { BasketRequest, BundleRequest } from './planning-contract'
export const optimizeBasket = (request: BasketRequest) =>
  privateRequest('/buyer/baskets/optimize', decodeBasket, {
    method: 'POST',
    json: request,
  })
export const suggestBundles = (request: BundleRequest, seller: boolean) =>
  privateRequest(
    `/${seller ? 'seller' : 'buyer'}/bundles/suggest`,
    decodeBundles,
    { method: 'POST', json: request },
  )
