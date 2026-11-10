export const costCategories = ['materials', 'packaging', 'transport', 'utilities', 'equipment', 'overhead', 'risk_reserve', 'other'] as const
export type CostCategory = typeof costCategories[number]
export type BatchCost = { label: string; category: CostCategory; amount: string }
export type LaborCost = { label: string; hours: string; hourly_rate: string }

export interface PricingRequest {
  currency: 'USD'
  sellable_units: number
  costs: BatchCost[]
  labor: LaborCost[]
  payment_fees: { rate: string; fixed_per_order: string; units_per_order: number }
  target_margin: { minimum: string; maximum: string }
  proposed_prices: string[]
}

export interface PricingResponse {
  calculation_version: 'production-economics-v1'
  currency: 'USD'
  basis: 'seller_supplied_unverified'
  costs: {
    category_totals: Partial<Record<CostCategory, string>>
    labor_total: string
    batch_total: string
    unit_cost: string
  }
  fixed_fee_per_unit: string
  break_even_price: string
  sustainable_price_range: { minimum: string; maximum: string }
  scenarios: {
    price: string; processing_fee_per_unit: string; profit_per_unit: string; batch_profit: string
    margin: string | null; markup: string | null; below_break_even: boolean; below_target_margin: boolean
  }[]
  warnings: { code: string; message: string }[]
  assumptions: string[]
}
