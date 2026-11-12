import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import type { AccountRole } from '../types/account'
import { Botanical } from './Botanical'

type Fields = {
  name: string
  email: string
  password: string
  confirmation: string
}
const emptyFields: Fields = {
  name: '',
  email: '',
  password: '',
  confirmation: '',
}

export function SignupPreview({
  role,
  onRoleChange,
}: {
  role: AccountRole
  onRoleChange: (role: AccountRole) => void
}) {
  const [fields, setFields] = useState<Fields>(emptyFields)
  const [errors, setErrors] = useState<Partial<Fields>>({})
  const [showPassword, setShowPassword] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const formRef = useRef<HTMLFormElement>(null)
  const statusRef = useRef<HTMLDivElement>(null)

  function update(field: keyof Fields, value: string) {
    setFields((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({
      ...current,
      [field]: undefined,
      ...(field === 'password' ? { confirmation: undefined } : {}),
    }))
    setSubmitted(false)
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors: Partial<Fields> = {}
    if (!fields.name.trim()) nextErrors.name = 'Please enter your name.'
    const emailInput = formRef.current?.elements.namedItem(
      'email',
    ) as HTMLInputElement | null
    if (!fields.email.trim())
      nextErrors.email = 'Please enter an email address.'
    else if (emailInput?.validity.typeMismatch)
      nextErrors.email = 'Please enter a valid email address.'
    if (fields.password.length < 8)
      nextErrors.password = 'Use at least 8 characters for this preview.'
    if (!fields.confirmation)
      nextErrors.confirmation = 'Please repeat your password.'
    else if (fields.password !== fields.confirmation)
      nextErrors.confirmation = 'The passwords don’t match.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) {
      setSubmitted(false)
      const firstField = formRef.current?.elements.namedItem(
        Object.keys(nextErrors)[0],
      ) as HTMLInputElement | null
      firstField?.focus()
      return
    }
    // This preview deliberately has no service call or persistent storage.
    setFields({ ...emptyFields })
    setShowPassword(false)
    setSubmitted(true)
    statusRef.current?.focus()
  }

  const input = (
    field: keyof Fields,
    label: string,
    type: string,
    autoComplete: string,
  ) => (
    <div className="form-field">
      <label htmlFor={`signup-${field}`}>{label}</label>
      <input
        id={`signup-${field}`}
        name={field}
        type={type}
        autoComplete={autoComplete}
        required
        minLength={field === 'password' ? 8 : undefined}
        value={fields[field]}
        onChange={(event) => update(field, event.target.value)}
        aria-invalid={!!errors[field]}
        aria-describedby={errors[field] ? `error-${field}` : undefined}
      />
      {errors[field] && (
        <p className="field-error" id={`error-${field}`}>
          {errors[field]}
        </p>
      )}
    </div>
  )

  return (
    <section
      id="create-account"
      className="account-section"
      aria-labelledby="account-heading"
    >
      <div className="page-width account-layout">
        <div className="account-intro">
          <p className="eyebrow">There’s a place for you here</p>
          <h2 id="account-heading">
            Pull up a chair.
            <br />
            <em>Join the market.</em>
          </h2>
          <p>
            Whether you’re bringing a basket or filling one, we’re building a
            place where good work is valued and neighbors buy with
            understanding.
          </p>
          <div className="account-note">
            <Botanical />
            <p>
              A few good ingredients.
              <br />A little local knowledge.
              <br />
              <span>A community worth growing.</span>
            </p>
          </div>
        </div>
        <div className="signup-card">
          <div className="signup-title">
            <h3>Create your account</h3>
            <span className="small-tag">Preview</span>
          </div>
          <p id="signup-preview-note" className="preview-notice">
            Try the signup preview with made-up details. Registration isn’t
            connected yet. Nothing you enter is sent or saved.
          </p>
          <form
            ref={formRef}
            noValidate
            onSubmit={submit}
            aria-describedby="signup-preview-note"
          >
            <fieldset className="account-roles">
              <legend>First, make yourself at home.</legend>
              {(['buyer', 'seller'] as const).map((value) => (
                <label className="account-role" key={value}>
                  <input
                    type="radio"
                    name="account-role"
                    value={value}
                    checked={role === value}
                    onChange={() => {
                      onRoleChange(value)
                      setSubmitted(false)
                    }}
                  />
                  <span>
                    <strong>
                      {value === 'buyer' ? 'I’m a buyer' : 'I’m a seller'}
                    </strong>
                    <small>
                      {value === 'buyer'
                        ? 'Find something good'
                        : 'Share what I make'}
                    </small>
                  </span>
                </label>
              ))}
            </fieldset>
            {input('name', 'Your name', 'text', 'name')}
            {input('email', 'Email address', 'email', 'email')}
            <div className="password-label">
              <span>Use a made-up password for this preview.</span>
              <button
                type="button"
                className="text-button"
                aria-pressed={showPassword}
                aria-controls="signup-password signup-confirmation"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? 'Hide passwords' : 'Show passwords'}
              </button>
            </div>
            {input(
              'password',
              'Password · at least 8 characters',
              showPassword ? 'text' : 'password',
              'new-password',
            )}
            {input(
              'confirmation',
              'Confirm password',
              showPassword ? 'text' : 'password',
              'new-password',
            )}
            <button className="button-primary signup-submit" type="submit">
              Preview {role} signup <span aria-hidden="true">↗</span>
            </button>
            <div
              ref={statusRef}
              role="status"
              tabIndex={-1}
              className={submitted ? 'signup-status' : undefined}
            >
              {submitted && (
                <>
                  You’ve explored the {role} signup preview. No account was
                  created. Registration is coming in a future release; your form
                  details have been cleared.
                </>
              )}
            </div>
          </form>
        </div>
      </div>
    </section>
  )
}
