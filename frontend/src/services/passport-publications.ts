import { privateRequest } from './session'
import { empty } from './decode'

export const withdrawPassportPublication = (productId: string, draftId: string, publicationId: string) =>
  privateRequest(`/products/${productId}/passports/${draftId}/publications/${publicationId}/withdraw`, empty, { method: 'POST' })
