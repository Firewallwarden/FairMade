import { choice, list, money, nullable, object, text } from './decode.ts'
export const compositionKinds = [
  'ingredient',
  'material',
  'packaging',
  'other',
] as const
export const compositionUnits = [
  'g',
  'kg',
  'ml',
  'l',
  'egg',
  'dozen',
  'loaf',
  'item',
] as const
export type CompositionDisclosure = {
  completeness: 'partial' | 'seller_declared_complete'
  items: {
    label: string
    kind: (typeof compositionKinds)[number]
    reported_role: string | null
    reported_specification: string | null
    declared_quantity: {
      value: string
      unit: (typeof compositionUnits)[number]
    } | null
  }[]
}
export function decodeComposition(value: unknown): CompositionDisclosure {
  const data = object(value)
  return {
    completeness: choice(data.completeness, [
      'partial',
      'seller_declared_complete',
    ] as const),
    items: list(data.items, (value) => {
      const item = object(value)
      return {
        label: text(item.label),
        kind: choice(item.kind, compositionKinds),
        reported_role: nullable(item.reported_role, text),
        reported_specification: nullable(item.reported_specification, text),
        declared_quantity: nullable(item.declared_quantity, (value) => {
          const quantity = object(value)
          return {
            value: money(quantity.value),
            unit: choice(quantity.unit, compositionUnits),
          }
        }),
      }
    }),
  }
}
