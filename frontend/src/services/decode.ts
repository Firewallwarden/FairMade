export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    throw new Error('Expected object')
  return value as Record<string, unknown>
}

export function text(value: unknown): string {
  if (typeof value !== 'string') throw new Error('Expected text')
  return value
}

export function integer(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value))
    throw new Error('Expected integer')
  return value
}

export function boolean(value: unknown): boolean {
  if (typeof value !== 'boolean') throw new Error('Expected boolean')
  return value
}

export function money(value: unknown): string {
  const result = text(value)
  if (!/^-?\d+(\.\d+)?$/.test(result) || !Number.isFinite(Number(result)))
    throw new Error('Expected decimal')
  return result
}

export function choice<const T extends readonly string[]>(
  value: unknown,
  options: T,
): T[number] {
  const result = text(value)
  if (!options.includes(result)) throw new Error('Unsupported value')
  return result as T[number]
}

export function list<T>(value: unknown, decode: (item: unknown) => T): T[] {
  if (!Array.isArray(value)) throw new Error('Expected list')
  return value.map(decode)
}

export function nullable<T>(
  value: unknown,
  decode: (item: unknown) => T,
): T | null {
  return value === null || value === undefined ? null : decode(value)
}

export function timestamp(value: unknown): string {
  const result = text(value)
  if (!Number.isFinite(Date.parse(result)))
    throw new Error('Expected timestamp')
  return result
}

export function page<T>(decode: (item: unknown) => T) {
  return (value: unknown) => {
    const data = object(value)
    return {
      items: list(data.items, decode),
      limit: integer(data.limit),
      offset: integer(data.offset),
    }
  }
}

export function empty(value: unknown): void {
  if (value !== undefined) throw new Error('Expected empty response')
}
