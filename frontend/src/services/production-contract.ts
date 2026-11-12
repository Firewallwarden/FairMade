import {
  choice,
  integer,
  list,
  money,
  nullable,
  object,
  text,
  timestamp,
} from './decode.ts'
import { costCategories } from '../types/pricing.ts'
import type { BatchCost, LaborCost, PricingRequest } from '../types/pricing.ts'
export const recipeUnits = ['g', 'kg', 'ml', 'l', 'item'] as const
export type RecipeIngredient = {
  label: string
  quantity: { value: string; unit: (typeof recipeUnits)[number] }
  purchase_quantity: { value: string; unit: (typeof recipeUnits)[number] }
  purchase_cost: string
  cost_recorded_on: string
}
export type RecipeData = {
  name: string
  currency: 'USD'
  sellable_units: number
  ingredients: RecipeIngredient[]
  other_costs: BatchCost[]
  labor: LaborCost[]
  payment_fees: PricingRequest['payment_fees']
  target_margin: PricingRequest['target_margin']
  proposed_prices: string[]
  instructions: string
}
export function decodeRecipe(value: unknown) {
  const data = object(value),
    content = object(data.content),
    fees = object(content.payment_fees),
    margin = object(content.target_margin)
  const quantity = (value: unknown) => {
    const q = object(value)
    return { value: money(q.value), unit: choice(q.unit, recipeUnits) }
  }
  const recipe: RecipeData = {
    name: text(content.name),
    currency: choice(content.currency, ['USD'] as const),
    sellable_units: integer(content.sellable_units),
    ingredients: list(content.ingredients, (value) => {
      const item = object(value)
      return {
        label: text(item.label),
        quantity: quantity(item.quantity),
        purchase_quantity: quantity(item.purchase_quantity),
        purchase_cost: money(item.purchase_cost),
        cost_recorded_on: text(item.cost_recorded_on),
      }
    }),
    other_costs: list(content.other_costs, (value) => {
      const cost = object(value)
      return {
        label: text(cost.label),
        category: choice(cost.category, costCategories),
        amount: money(cost.amount),
      }
    }),
    labor: list(content.labor, (value) => {
      const row = object(value)
      return {
        label: text(row.label),
        hours: money(row.hours),
        hourly_rate: money(row.hourly_rate),
      }
    }),
    payment_fees: {
      rate: money(fees.rate),
      fixed_per_order: money(fees.fixed_per_order),
      units_per_order: integer(fees.units_per_order),
    },
    target_margin: {
      minimum: money(margin.minimum),
      maximum: money(margin.maximum),
    },
    proposed_prices: list(content.proposed_prices, money),
    instructions: text(content.instructions),
  }
  return { revision: integer(data.revision), content: recipe }
}
export function decodeRecipeCostingSummary(value: unknown) {
  const data = object(value)
  return {
    id: text(data.id),
    recipe_revision: integer(data.recipe_revision),
    pricing_analysis_id: text(data.pricing_analysis_id),
    created_at: timestamp(data.created_at),
  }
}
export function decodeRecipeCosting(value: unknown) {
  const data = object(value),
    result = object(data.result)
  return {
    ...decodeRecipeCostingSummary(value),
    snapshot: object(data.recipe_snapshot),
    materials_total: money(result.materials_total),
    warnings: list(result.warnings, text),
    ingredients: list(result.ingredients, (value) => {
      const row = object(value)
      return {
        label: text(row.label),
        allocated_cost: money(row.allocated_cost),
      }
    }),
  }
}
export type ProductionInput = {
  request_id: string
  label: string
  kind: 'batch' | 'production_period'
  started_on: string
  completed_on: string
  selling_unit: string
  total_units: number
  sellable_units: number
  currency: 'USD'
  costs: BatchCost[]
  labor: LaborCost[]
  notes: string | null
  corrects_record_id: string | null
  correction_reason: string | null
  livestock_source: {
    kind: 'group' | 'animal'
    id: string
    expected_revision: number
  } | null
}
export function decodeProductionSummary(value: unknown) {
  const data = object(value)
  return {
    id: text(data.id),
    label: text(data.label),
    kind: choice(data.kind, ['batch', 'production_period'] as const),
    started_on: text(data.started_on),
    completed_on: text(data.completed_on),
    selling_unit: text(data.selling_unit),
    total_units: integer(data.total_units),
    sellable_units: integer(data.sellable_units),
    corrects_record_id: nullable(data.corrects_record_id, text),
  }
}
export function decodeProduction(value: unknown) {
  const data = object(value),
    result = object(data.result)
  choice(result.calculation_version, ['completed-production-costs-v1'] as const)
  return {
    ...decodeProductionSummary(value),
    snapshot: object(data.product_snapshot),
    request: object(data.request),
    livestock_snapshot: nullable(data.livestock_snapshot, object),
    result: {
      batch_total: money(result.batch_total),
      labor_total: money(result.labor_total),
      unit_cost: nullable(result.unit_cost, money),
      unsellable_units: integer(result.unsellable_units),
      yield_fraction: nullable(result.yield_fraction, money),
      category_totals: object(result.category_totals),
      warnings: list(result.warnings, text),
    },
  }
}
