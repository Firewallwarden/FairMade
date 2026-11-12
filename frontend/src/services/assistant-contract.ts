import {
  choice,
  integer,
  list,
  nullable,
  object,
  text,
  timestamp,
} from './decode.ts'

export type ConversationScope =
  | { role: 'buyer'; listing_ids: string[] }
  | {
      role: 'seller'
      product_id: string
      analysis_id?: string
      pricing_review_id?: string
      supplier_report_id?: string
      history_period?: { start_date: string; end_date: string }
      insights?: { period_days: number }
      forecast?: { lookback_days: number; horizon_days: number }
      cost_calendar?: { months: number }
      recommendations?: {
        mode: 'savings' | 'quality' | 'balanced'
        cost_objective: 'purchase_outlay' | 'usable_unit'
        preferences: import('./quality-contract').QualityRule[]
      }
      include_recipe_inputs: boolean
    }

export function decodeConversation(value: unknown) {
  const data = object(value)
  const scope = object(data.scope)
  return {
    id: text(data.id),
    role: choice(data.role, ['buyer', 'seller'] as const),
    scope,
    revision: integer(data.revision),
    updated_at: timestamp(data.updated_at),
    expires_at: timestamp(data.expires_at),
  }
}
export type Conversation = ReturnType<typeof decodeConversation>

export function decodeAnswer(value: unknown) {
  const data = object(value)
  choice(data.assistant_version, ['fairmade-assistant-v1'] as const)
  choice(data.provider, ['ollama_local'] as const)
  const paragraph = (value: unknown) => {
    const item = object(value)
    return {
      text: text(item.text),
      evidence_keys: list(item.evidence_keys, text),
    }
  }
  return {
    facts: list(data.facts, paragraph),
    paragraphs: list(data.paragraphs, paragraph),
    evidence: list(data.evidence, (value) => {
      const item = object(value)
      return {
        key: text(item.key),
        title: text(item.title),
        basis: text(item.basis),
        data: object(item.data),
      }
    }),
    notices: list(data.notices, text),
    generated_at: timestamp(data.generated_at),
    model: text(data.model),
  }
}

export function decodeTurn(value: unknown) {
  const data = object(value)
  const status = choice(data.answer_status, [
    'available',
    'evidence_changed',
  ] as const)
  const answer =
    status === 'evidence_changed' ? null : nullable(data.answer, decodeAnswer)
  if (status === 'available' && !answer) throw new Error('Missing answer')
  return {
    id: text(data.id),
    revision: integer(data.revision),
    request_id: text(data.request_id),
    question: text(data.question),
    answer_status: status,
    answer,
    created_at: timestamp(data.created_at),
  }
}
