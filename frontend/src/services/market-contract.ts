import { choice, integer, list, nullable, object, text } from './decode.ts'
export const catalogSorts = [
  'newest',
  'price_asc',
  'price_desc',
  'quality',
  'unit_price',
  'value',
] as const
export function decodeOrdering(value: unknown) {
  if (value == null) return null
  const data = object(value)
  choice(data.policy_version, ['catalog-ordering-v1'] as const)
  return {
    mode: choice(data.mode, catalogSorts),
    candidate_count: integer(data.candidate_count),
    compared_count: integer(data.compared_count),
    not_compared_count: integer(data.not_compared_count),
    reference_unit: nullable(data.reference_unit, text),
    notices: list(data.notices, text),
    items: list(data.items, (value) => {
      const item = object(value)
      return {
        listing_id: text(item.listing_id),
        comparison_status: choice(item.comparison_status, [
          'ordered',
          'not_compared',
        ] as const),
        quality_status: choice(item.quality_status, [
          'undisclosed',
          'not_provided',
          'needs_attention',
          'claims_match_unverified',
        ] as const),
        reasons: list(item.reasons, text),
      }
    }),
  }
}
