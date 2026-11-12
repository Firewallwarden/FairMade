import { privateRequest } from './session'
import { integer, object, page, text, timestamp } from './decode'
import { decodeHistoricalEvaluation } from './quality-history-contract'

export const getQualityHistory = (id: string, offset: number, signal?: AbortSignal) =>
  privateRequest(`/products/${id}/quality-evaluations?limit=20&offset=${offset}`, page(value => {
    const data = object(value)
    return { id: text(data.id), candidate_label: text(data.candidate_label), created_at: timestamp(data.created_at), rule_revision: integer(data.rule_revision), status: text(data.status) }
  }), { signal })
export const getHistoricalEvaluation = (id: string, evaluation: string, signal?: AbortSignal) =>
  privateRequest(`/products/${id}/quality-evaluations/${evaluation}`, decodeHistoricalEvaluation, { signal })
