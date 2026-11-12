import type { CostCategory } from './pricing'
import type { QualityClaim } from '../services/quality-contract'

export const productTypes = ['sourdough', 'eggs', 'other'] as const
export const sellingUnits = [
  'g',
  'kg',
  'ml',
  'l',
  'egg',
  'dozen',
  'loaf',
  'item',
] as const
export const comparisonUnits = [
  'g',
  'kg',
  'egg',
  'dozen',
  'loaf',
  'item',
] as const
export const sourceKinds = [
  'website',
  'in_person',
  'document',
  'other',
] as const
export type ProductType = (typeof productTypes)[number]
export type Quantity = { value: string; unit: (typeof comparisonUnits)[number] }

export type EvaluationRequest = {
  candidate_label: string
  expected_revision: number
  claims: Record<string, QualityClaim>
}

export type PassportRequest = {
  composition?:
    | import('../services/composition-contract').CompositionDisclosure
    | null
  review_id: string
  title: string
  price: string
  public_description?: string | null
  disclosures: {
    cost_categories?: CostCategory[]
    include_labor?: boolean
    include_unit_cost?: boolean
    include_quality_requirements?: boolean
    include_quality_summary?: boolean
    include_market_context?: boolean
    include_composition?: boolean
  }
}

export type ListingRequest = {
  passport_publication_id: string
  seller_display_name: string
  location?: string | null
  summary?: string | null
  photos?: { photo_id: string; alt_text: string }[] | null
  selling_quantity?: {
    value: string
    unit: (typeof sellingUnits)[number]
  } | null
  expected_revision?: number
}

export type ObservationRequest = {
  label: string
  product_type: ProductType
  currency: 'USD'
  price: string
  quantity: Quantity
  source: {
    name: string
    kind: (typeof sourceKinds)[number]
    reference: string
  }
  location: string
  observed_on: string
  quality_notes?: string | null
}

export type ComparisonRequest = {
  observation_ids: string[]
  target_quantity: Quantity
  max_age_days: number
}
