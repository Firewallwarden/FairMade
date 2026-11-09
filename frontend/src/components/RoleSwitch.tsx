import type { AccountRole } from '../types/account'

export function RoleSwitch({
  role,
  onChange,
}: {
  role: AccountRole
  onChange: (role: AccountRole) => void
}) {
  return (
    <div
      className="role-switch"
      role="group"
      aria-label="Choose your homepage experience"
    >
      <button
        type="button"
        aria-pressed={role === 'buyer'}
        onClick={() => onChange('buyer')}
      >
        I’m here to shop <span aria-hidden="true">↗</span>
      </button>
      <button
        type="button"
        aria-pressed={role === 'seller'}
        onClick={() => onChange('seller')}
      >
        I’m here to sell <span aria-hidden="true">↗</span>
      </button>
    </div>
  )
}
