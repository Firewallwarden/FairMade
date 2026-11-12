import {
  choice,
  integer,
  list,
  nullable,
  object,
  text,
  timestamp,
} from './decode.ts'

export function decodeAccount(value: unknown) {
  const data = object(value)
  return {
    id: text(data.id),
    email: text(data.email),
    roles: list(data.roles, (role) =>
      choice(role, ['buyer', 'seller', 'admin'] as const),
    ),
  }
}

export type Account = ReturnType<typeof decodeAccount>

export function decodeToken(value: unknown) {
  const data = object(value)
  const accessToken = text(data.access_token)
  if (!accessToken) throw new Error('Empty token')
  return {
    accessToken,
    tokenType: choice(data.token_type, ['bearer'] as const),
    expiresAt: timestamp(data.expires_at),
  }
}

export function decodeApplication(value: unknown) {
  const data = object(value)
  return {
    id: text(data.id),
    status: choice(data.status, ['pending', 'approved', 'denied'] as const),
    submittedAt: timestamp(data.submitted_at),
    revision: integer(data.revision),
    decision: nullable(data.decision, (value) => {
      const decision = object(value)
      return {
        outcome: choice(decision.outcome, ['approved', 'denied'] as const),
        reason: text(decision.reason),
        createdAt: timestamp(decision.created_at),
        basis: choice(decision.basis, ['manual_administrator_review'] as const),
      }
    }),
  }
}
