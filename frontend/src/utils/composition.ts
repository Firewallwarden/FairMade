import { choice } from '../services/decode.ts'
import {
  compositionKinds,
  compositionUnits,
} from '../services/composition-contract.ts'
import type { CompositionDisclosure } from '../services/composition-contract.ts'
import { fieldValue } from './form.ts'
export function readComposition(
  fields: FormData,
): CompositionDisclosure | null {
  if (!fields.has('include_composition')) return null
  const keys = fields.getAll('composition-row').map(String)
  if (keys.length < 1 || keys.length > 20)
    throw new Error(
      'Declare 1–20 finished-product components, or leave composition private.',
    )
  return {
    completeness: choice(fieldValue(fields, 'composition-completeness'), [
      'partial',
      'seller_declared_complete',
    ] as const),
    items: keys.map((key) => {
      const quantity = fieldValue(fields, `composition-quantity-${key}`),
        unit = fieldValue(fields, `composition-unit-${key}`)
      if (Boolean(quantity) !== Boolean(unit))
        throw new Error(
          'Supply both declared quantity and unit, or leave both blank.',
        )
      return {
        label: fieldValue(fields, `composition-label-${key}`),
        kind: choice(
          fieldValue(fields, `composition-kind-${key}`),
          compositionKinds,
        ),
        reported_role: fieldValue(fields, `composition-role-${key}`) || null,
        reported_specification:
          fieldValue(fields, `composition-spec-${key}`) || null,
        declared_quantity: quantity
          ? { value: quantity, unit: choice(unit, compositionUnits) }
          : null,
      }
    }),
  }
}
