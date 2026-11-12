import { privateRequest } from './session'
import { choice, integer, list, object, page, text } from './decode'

function decodeDraft(value: unknown) {
  const data = object(value)
  return { id: text(data.id), revision: integer(data.revision), preview_hash: text(data.preview_hash), state: choice(data.state, ['draft', 'approved'] as const), generated_text: text(data.generated_text), description: text(data.description), notices: list(data.notices, text) }
}
export const getDescriptionDrafts = (id: string, offset: number, signal?: AbortSignal) => privateRequest(`/products/${id}/description-drafts?limit=20&offset=${offset}`, page(decodeDraft), { signal })
export const generateDescription = (id: string, tone: 'plain' | 'friendly', requestId: string) => privateRequest(`/products/${id}/description-drafts`, decodeDraft, { method: 'POST', json: { request_id: requestId, tone }, timeoutMs: 150000 })
export const editDescription = (id: string, draft: string, revision: number, description: string) => privateRequest(`/products/${id}/description-drafts/${draft}`, decodeDraft, { method: 'PUT', json: { expected_revision: revision, description } })
export const approveDescription = (id: string, draft: string, revision: number, hash: string) => privateRequest(`/products/${id}/description-drafts/${draft}/approve`, decodeDraft, { method: 'POST', json: { expected_revision: revision, preview_hash: hash, approved: true } })
