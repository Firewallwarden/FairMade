import { boolean, choice, integer, list, money, nullable, object, text } from './decode.ts'
import { decodeComposition } from './composition-contract.ts'
import { costCategories } from '../types/pricing.ts'

export function decodeEditablePassport(value: unknown) {
  const draft = object(value)
  const content = object(draft.content)
  const disclosures = object(content.disclosures)
  return {
    id: text(draft.id),
    revision: integer(draft.revision),
    content: {
      review_id: text(content.review_id),
      title: text(content.title),
      price: money(content.price),
      public_description: nullable(content.public_description, text),
      composition: nullable(content.composition, decodeComposition),
      disclosures: {
        cost_categories: list(disclosures.cost_categories, value => choice(value, costCategories)),
        include_labor: boolean(disclosures.include_labor),
        include_unit_cost: boolean(disclosures.include_unit_cost),
        include_quality_requirements: boolean(disclosures.include_quality_requirements),
        include_quality_summary: boolean(disclosures.include_quality_summary),
        include_market_context: boolean(disclosures.include_market_context),
        include_composition: boolean(disclosures.include_composition),
      },
    },
  }
}
