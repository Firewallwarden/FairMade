import {
  choice,
  integer,
  money,
  nullable,
  object,
  text,
  timestamp,
} from './decode.ts'
export const materialUnits = ['g', 'ml', 'item'] as const
export const movementKinds = [
  'receipt',
  'usage',
  'waste',
  'adjustment',
] as const
export type MaterialMovementInput = {
  request_id: string
  expected_revision: number
  kind: (typeof movementKinds)[number]
  quantity: string
  unit: 'g' | 'kg' | 'ml' | 'l' | 'item'
  occurred_on: string
  reason: string
}
export function decodeMaterial(value: unknown) {
  const data = object(value)
  choice(data.basis, ['seller_reported_unverified'] as const)
  return {
    id: text(data.id),
    name: text(data.name),
    notes: nullable(data.notes, text),
    unit: choice(data.unit, materialUnits),
    on_hand: money(data.on_hand),
    revision: integer(data.revision),
  }
}
export function decodeMaterialMovement(value: unknown) {
  const data = object(value)
  choice(data.basis, ['seller_reported_unverified'] as const)
  return {
    id: text(data.id),
    revision: integer(data.revision),
    kind: choice(data.kind, movementKinds),
    material_name: text(data.material_name),
    unit: choice(data.unit, materialUnits),
    before: money(data.before),
    after: money(data.after),
    delta: money(data.delta),
    request: object(data.request),
    created_at: timestamp(data.created_at),
  }
}
