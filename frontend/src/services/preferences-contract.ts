import {
  boolean,
  choice,
  integer,
  list,
  money,
  nullable,
  object,
  text,
  timestamp,
} from './decode.ts'
export type BuyerPreferences = {
  budget_per_item: string | null
  product_types: ('sourdough' | 'eggs' | 'other')[]
  location: string | null
  excluded_listing_ids: string[]
}
export function decodePreferences(value: unknown): BuyerPreferences {
  const data = object(value)
  return {
    budget_per_item: nullable(data.budget_per_item, money),
    product_types: list(data.product_types, (value) =>
      choice(value, ['sourdough', 'eggs', 'other'] as const),
    ),
    location: nullable(data.location, text),
    excluded_listing_ids: list(data.excluded_listing_ids, text),
  }
}
export function decodeBuyerProfile(value: unknown) {
  const data = object(value),
    preferences = decodePreferences(data.preferences)
  const enabled = boolean(data.enabled)
  if (
    !enabled &&
    (preferences.budget_per_item !== null ||
      preferences.location !== null ||
      preferences.product_types.length ||
      preferences.excluded_listing_ids.length)
  )
    throw new Error('Disabled profile retained preferences')
  return {
    revision: integer(data.revision),
    enabled,
    preferences,
    status: choice(data.status, ['enabled', 'disabled', 'expired'] as const),
    expires_at: nullable(data.expires_at, timestamp),
    notices: list(data.notices, text),
  }
}
export function decodeMemoryProposal(value: unknown) {
  const data = object(value)
  return {
    profile_revision: integer(data.profile_revision),
    preferences: decodePreferences(data.preferences),
    notices: list(data.notices, text),
  }
}
