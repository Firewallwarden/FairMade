import { choice, list, money, nullable, object, text, timestamp } from './decode.ts'

export function decodeSalesOrder(value: unknown) {
  const data = object(value)
  choice(data.environment, ['sandbox'] as const)
  choice(data.merchant_mode, ['shared'] as const)
  choice(data.currency, ['USD'] as const)
  return {
    order_id: text(data.order_id), created_at: timestamp(data.created_at), captured_at: timestamp(data.captured_at),
    gross_sales: money(data.gross_sales), completed_refunds: money(data.completed_refunds),
    processing_fee: nullable(data.processing_fee, money),
    fee_basis: choice(data.fee_basis, ['provider_fee', 'derived_from_provider_net', 'unavailable'] as const),
    after_refunds_and_fee: nullable(data.after_refunds_and_fee, money),
    estimated_production_cost: nullable(data.estimated_production_cost, money),
    estimated_profit: nullable(data.estimated_profit, money), estimated_margin: nullable(data.estimated_margin, money),
    profit_unavailable_reasons: list(data.profit_unavailable_reasons, text),
    cost_snapshot: nullable(data.cost_snapshot, object), warnings: list(data.warnings, text),
  }
}
