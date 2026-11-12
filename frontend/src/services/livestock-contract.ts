import {
  boolean,
  choice,
  integer,
  nullable,
  object,
  text,
  timestamp,
} from './decode.ts'
export const animalStatuses = ['active', 'departed', 'deceased'] as const
export const animalSexes = ['unknown', 'female', 'male'] as const
export type LivestockKind = 'groups' | 'animals'
type Change = { request_id: string; occurred_on: string; reason: string }
export type GroupFields = {
  name: string
  breed: string | null
  notes: string | null
  reported_headcount: number | null
  headcount_on: string | null
  archived: boolean
}
export type AnimalFields = {
  identifier: string
  name: string | null
  breed: string | null
  sex: (typeof animalSexes)[number]
  born_on: string | null
  acquired_on: string | null
  status: (typeof animalStatuses)[number]
  group_id: string | null
  notes: string | null
}
export type LivestockChange = Change &
  (GroupFields | AnimalFields) & {
    species?: string
    expected_revision?: number
  }
function identity(value: unknown) {
  const data = object(value)
  choice(data.basis, ['seller_reported_unverified'] as const)
  return {
    id: text(data.id),
    species: text(data.species),
    revision: integer(data.revision),
  }
}
export function decodeGroup(value: unknown) {
  const d = object(value)
  return {
    ...identity(d),
    name: text(d.name),
    breed: nullable(d.breed, text),
    notes: nullable(d.notes, text),
    reported_headcount: nullable(d.reported_headcount, integer),
    headcount_on: nullable(d.headcount_on, text),
    archived: boolean(d.archived),
    registered_active_animals: integer(d.registered_active_animals),
  }
}
export function decodeAnimal(value: unknown) {
  const d = object(value)
  return {
    ...identity(d),
    identifier: text(d.identifier),
    name: nullable(d.name, text),
    breed: nullable(d.breed, text),
    notes: nullable(d.notes, text),
    sex: choice(d.sex, animalSexes),
    status: choice(d.status, animalStatuses),
    born_on: nullable(d.born_on, text),
    acquired_on: nullable(d.acquired_on, text),
    group_id: nullable(d.group_id, text),
  }
}
export function decodeLivestockHistory(value: unknown) {
  const d = object(value)
  choice(d.basis, ['seller_reported_unverified'] as const)
  return {
    id: text(d.id),
    resource_id: text(d.resource_id),
    revision: integer(d.revision),
    occurred_on: text(d.occurred_on),
    reason: text(d.reason),
    before: nullable(d.before, object),
    after: object(d.after),
    created_at: timestamp(d.created_at),
  }
}
export type Group = ReturnType<typeof decodeGroup>
export type Animal = ReturnType<typeof decodeAnimal>
