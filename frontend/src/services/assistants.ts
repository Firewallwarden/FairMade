import { privateRequest } from './session'
import { empty, page } from './decode'
import { decodeConversation, decodeTurn } from './assistant-contract'
import type { ConversationScope } from './assistant-contract'

const base = '/assistants/conversations' as const
export const getConversations = (offset: number, signal?: AbortSignal) => privateRequest(`${base}?limit=20&offset=${offset}`, page(decodeConversation), { signal })
export const getConversation = (id: string, signal?: AbortSignal) => privateRequest(`${base}/${id}`, decodeConversation, { signal })
export const getTurns = (id: string, offset: number, signal?: AbortSignal) => privateRequest(`${base}/${id}/turns?limit=20&offset=${offset}`, page(decodeTurn), { signal })
export const createConversation = (scope: ConversationScope, requestId: string) => privateRequest(base, decodeConversation, { method: 'POST', json: { scope, request_id: requestId } })
export const sendTurn = (id: string, request: { request_id: string; expected_revision: number; question: string }) => privateRequest(`${base}/${id}/turns`, decodeTurn, { method: 'POST', json: request, timeoutMs: 150000 })
export const deleteConversation = (id: string) => privateRequest(`${base}/${id}`, empty, { method: 'DELETE' })
