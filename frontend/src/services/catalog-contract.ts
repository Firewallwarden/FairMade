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
import { decodeRule } from './quality-contract.ts'
import { decodeComposition } from './composition-contract.ts'

export function decodeProductInfo(value: unknown) {
  const data = object(value)
  return {
    title: text(data.title),
    product_type: choice(data.product_type, [
      'sourdough',
      'eggs',
      'other',
    ] as const),
    selling_unit: text(data.selling_unit),
    description: nullable(data.description, text),
  }
}

export function decodePrice(value: unknown) {
  const data = object(value)
  return {
    currency: choice(data.currency, ['USD'] as const),
    amount: money(data.amount),
  }
}

export function decodePassport(value: unknown) {
  const data = object(value)
  choice(data.passport_version, ['fair-price-passport-v1'] as const)
  choice(data.basis, ['seller_reported_unverified'] as const)
  return {
    product: decodeProductInfo(data.product),
    price: decodePrice(data.price),
    reviewed_on: text(data.reviewed_on),
    composition: nullable(data.composition, decodeComposition),
    costs: nullable(data.costs, (value) => {
      const costs = object(value)
      const totals = object(costs.category_costs_per_unit)
      return {
        category_costs_per_unit: Object.fromEntries(
          Object.entries(totals).map(([key, value]) => [key, money(value)]),
        ),
        labor_per_unit: nullable(costs.labor_per_unit, money),
        unit_cost: nullable(costs.unit_cost, money),
      }
    }),
    quality_requirements: nullable(data.quality_requirements, (value) =>
      list(value, decodeRule),
    ),
    quality_summary: nullable(data.quality_summary, (value) => {
      const quality = object(value)
      return {
        status: text(quality.status),
        evaluation_count: integer(quality.evaluation_count),
        failed_count: integer(quality.failed_count),
        unknown_or_unevaluated_count: integer(
          quality.unknown_or_unevaluated_count,
        ),
        outdated_count: integer(quality.outdated_count),
      }
    }),
    market_context: nullable(data.market_context, (value) => {
      const market = object(value)
      return {
        status: text(market.status),
        included_count: integer(market.included_count),
        quantity: nullable(market.quantity, (value) => {
          const quantity = object(value)
          return { value: money(quantity.value), unit: text(quantity.unit) }
        }),
        minimum: nullable(market.minimum, money),
        maximum: nullable(market.maximum, money),
      }
    }),
    notices: list(data.notices, text),
  }
}
export type Passport = ReturnType<typeof decodePassport>

export function decodeCatalogContent(value: unknown) {
  const data = object(value)
  choice(data.listing_version, ['marketplace-listing-v1'] as const)
  return {
    product: decodeProductInfo(data.product),
    price: decodePrice(data.price),
    seller_display_name: text(data.seller_display_name),
    location: nullable(data.location, text),
    summary: nullable(data.summary, text),
    notices: list(data.notices, text),
    passport_id: text(data.passport_id),
    passport_payload_hash: text(data.passport_payload_hash),
    selling_quantity: nullable(data.selling_quantity, (value) => {
      const quantity = object(value)
      return { value: money(quantity.value), unit: text(quantity.unit) }
    }),
    photos:
      data.photos == null
        ? []
        : list(data.photos, (value) => {
            const photo = object(value)
            return {
              id: text(photo.id),
              src: text(photo.src),
              alt_text: text(photo.alt_text),
              width: integer(photo.width),
              height: integer(photo.height),
            }
          }),
    unit_price: nullable(data.unit_price, (value) => {
      const unit = object(value)
      return {
        amount: nullable(unit.amount, money),
        reference_unit: text(unit.reference_unit),
        status: text(unit.status),
      }
    }),
  }
}

export function decodeCard(value: unknown) {
  const data = object(value)
  const availability = object(data.availability)
  return {
    id: text(data.id),
    published_revision: integer(data.published_revision),
    published_at: timestamp(data.published_at),
    payload: decodeCatalogContent(data.payload),
    availability: {
      status: choice(availability.status, [
        'available',
        'unavailable',
        'unknown',
      ] as const),
      available_units: nullable(availability.available_units, integer),
      notice: text(availability.notice),
    },
  }
}
export type CatalogCard = ReturnType<typeof decodeCard>

export function decodeDetail(value: unknown) {
  const data = object(value)
  const publication = object(data.passport)
  return { ...decodeCard(data), passport: decodePassport(publication.payload) }
}

export function decodePayPalConfig(value: unknown) {
  const data = object(value)
  choice(data.environment, ['sandbox'] as const)
  choice(data.merchant_mode, ['shared'] as const)
  choice(data.currency, ['USD'] as const)
  return {
    enabled: boolean(data.enabled),
    client_id: nullable(data.client_id, text),
  }
}
