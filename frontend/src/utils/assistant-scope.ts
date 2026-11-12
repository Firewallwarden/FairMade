import type { ConversationScope } from '../services/assistant-contract.ts'
import { fieldValue } from './form.ts'

export function sellerConversationScope(
  productId: string,
  fields: FormData,
): Extract<ConversationScope, { role: 'seller' }> {
  const scope: Extract<ConversationScope, { role: 'seller' }> = {
    role: 'seller',
    product_id: productId,
    include_recipe_inputs: fields.has('assistant-recipe'),
  }
  const analysis = fieldValue(fields, 'assistant-analysis')
  const review = fieldValue(fields, 'assistant-review')
  const supplier = fieldValue(fields, 'assistant-supplier-report')
  if (analysis) scope.analysis_id = analysis
  if (review) scope.pricing_review_id = review
  if (supplier) scope.supplier_report_id = supplier
  if (fields.has('assistant-history')) {
    const start = fieldValue(fields, 'assistant-history-start')
    const end = fieldValue(fields, 'assistant-history-end')
    const startTime = Date.parse(start + 'T00:00:00Z'),
      endTime = Date.parse(end + 'T00:00:00Z')
    if (
      !Number.isFinite(startTime) ||
      !Number.isFinite(endTime) ||
      new Date(startTime).toISOString().slice(0, 10) !== start ||
      new Date(endTime).toISOString().slice(0, 10) !== end ||
      endTime - startTime < 86400000 ||
      endTime - startTime > 366 * 86400000
    )
      throw new Error(
        'Choose an exclusive history end date 1–366 days after a valid start date.',
      )
    scope.history_period = { start_date: start, end_date: end }
  }
  if (fields.has('assistant-insights'))
    scope.insights = {
      period_days: count(fields, 'assistant-insight-days', 1, 90),
    }
  if (fields.has('assistant-forecast'))
    scope.forecast = {
      lookback_days: count(fields, 'assistant-lookback', 14, 90),
      horizon_days: count(fields, 'assistant-horizon', 1, 30),
    }
  if (fields.has('assistant-calendar'))
    scope.cost_calendar = {
      months: count(fields, 'assistant-calendar-months', 1, 36),
    }
  if (fields.has('assistant-recommendations')) {
    if (!supplier)
      throw new Error(
        'Choose a saved supplier report before requesting recommendation context.',
      )
    const mode = fieldValue(fields, 'assistant-priority')
    const objective = fieldValue(fields, 'assistant-objective')
    if (mode !== 'savings' && mode !== 'quality' && mode !== 'balanced')
      throw new Error('Choose a supported recommendation priority.')
    if (objective !== 'purchase_outlay' && objective !== 'usable_unit')
      throw new Error('Choose a supported cost objective.')
    scope.recommendations = { mode, cost_objective: objective, preferences: [] }
  }
  return scope
}
function count(fields: FormData, name: string, min: number, max: number) {
  const raw = fieldValue(fields, name)
  const value = raw === '' ? NaN : Number(raw)
  if (!Number.isSafeInteger(value) || value < min || value > max)
    throw new Error(
      `Choose a whole number from ${min} to ${max} for ${name.replace('assistant-', '').replaceAll('-', ' ')}.`,
    )
  return value
}
