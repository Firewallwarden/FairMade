import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice } from '../components/Feedback'
import {
  applyToSell,
  getApplication,
  login,
  logout,
  refreshAccount,
  register,
} from '../services/auth'
import { useSession } from '../services/session'
import { ApiError } from '../services/http'

export function AccountPage() {
  const session = useSession()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [notice, setNotice] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [application, setApplication] = useState<Awaited<
    ReturnType<typeof getApplication>
  > | null>(null)
  const [applicationLoaded, setApplicationLoaded] = useState(false)
  const [version, setVersion] = useState(0)
  const message = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!session || session.account.roles.includes('seller')) return
    const controller = new AbortController()
    getApplication(controller.signal)
      .then(setApplication)
      .catch((error) => {
        if (
          !controller.signal.aborted &&
          !(error instanceof ApiError && error.status === 404)
        )
          setError(error)
      })
      .finally(() => {
        if (!controller.signal.aborted) setApplicationLoaded(true)
      })
    return () => controller.abort()
  }, [session, version])

  useEffect(() => {
    if (notice) message.current?.focus()
  }, [error, notice])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const form = event.currentTarget
    const fields = new FormData(form)
    const password = String(fields.get('password') ?? '')
    setError(null)
    setNotice('')
    if (mode === 'register' && password !== fields.get('confirmation')) {
      setError(new Error('Your passwords must match.'))
      return
    }
    setBusy(true)
    try {
      const credentials = {
        email: String(fields.get('email') ?? '').trim(),
        password,
      }
      if (mode === 'register') {
        await register(credentials)
        setNotice(
          'Your buyer account is created. Sign in to continue. Seller access is requested separately.',
        )
        setMode('login')
      } else {
        await login(credentials)
        setNotice('Welcome back. You are signed in for this browser session.')
      }
      form.reset()
    } catch (error) {
      setError(error)
    } finally {
      setBusy(false)
    }
  }

  async function action(operation: () => Promise<unknown>, success: string) {
    setBusy(true)
    setError(null)
    setNotice('')
    try {
      await operation()
      setNotice(success)
    } catch (error) {
      setError(error)
    } finally {
      setBusy(false)
    }
  }

  return (
    <WorkspaceLayout
      title={session ? 'Your place at the market.' : 'Make yourself at home.'}
      intro="One account for buying, with seller access added after manual review."
    >
      <div ref={message} tabIndex={-1}>
        <ErrorNotice error={error} />
        {notice && (
          <p role="status" className="calculator-notice">
            {notice}
          </p>
        )}
      </div>
      {!session ? (
        <section className="workspace-panel account-panel">
          <div className="workspace-actions">
            <button
              type="button"
              className="calculator-secondary"
              aria-pressed={mode === 'login'}
              disabled={busy}
              onClick={() => {
                setMode('login')
                setError(null)
                setNotice('')
              }}
            >
              Sign in
            </button>
            <button
              type="button"
              className="calculator-secondary"
              aria-pressed={mode === 'register'}
              disabled={busy}
              onClick={() => {
                setMode('register')
                setError(null)
                setNotice('')
              }}
            >
              Create account
            </button>
          </div>
          <h2>
            {mode === 'login' ? 'Welcome back.' : 'Start with a buyer account.'}
          </h2>
          <form key={mode} onSubmit={submit} aria-busy={busy}>
            <fieldset
              disabled={busy}
              className="calculator-form account-fields"
            >
              <legend className="sr-only">
                {mode === 'login' ? 'Sign in' : 'Create account'}
              </legend>
              <label className="calculator-field" htmlFor="account-email">
                Email
                <input
                  id="account-email"
                  name="email"
                  type="email"
                  required
                  maxLength={320}
                  autoComplete="email"
                />
              </label>
              <label className="calculator-field" htmlFor="account-password">
                Password (12–128 characters)
                <input
                  id="account-password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  minLength={12}
                  maxLength={128}
                  autoComplete={
                    mode === 'login' ? 'current-password' : 'new-password'
                  }
                />
              </label>
              {mode === 'register' && (
                <label
                  className="calculator-field"
                  htmlFor="account-confirmation"
                >
                  Confirm password
                  <input
                    id="account-confirmation"
                    name="confirmation"
                    type={showPassword ? 'text' : 'password'}
                    required
                    minLength={12}
                    maxLength={128}
                    autoComplete="new-password"
                  />
                </label>
              )}
              <label className="workspace-check">
                <input
                  type="checkbox"
                  checked={showPassword}
                  onChange={(event) => setShowPassword(event.target.checked)}
                />
                Show password
              </label>
              <button className="button-primary" type="submit">
                {busy
                  ? 'Please wait…'
                  : mode === 'login'
                    ? 'Sign in'
                    : 'Create buyer account'}
              </button>
            </fieldset>
          </form>
          <p className="workspace-muted">
            Your session stays in memory. Reloading or closing this page signs
            you out locally. Sessions expire after the backend’s fixed 24-hour
            limit; they are never automatically extended.
          </p>
        </section>
      ) : (
        <>
          <section className="workspace-panel">
            <h2>Good to see you.</h2>
            <p>{session.account.email}</p>
            <p>Current access: {session.account.roles.join(', ')}.</p>
            <div className="workspace-actions">
              <button
                className="calculator-secondary"
                disabled={busy}
                onClick={() =>
                  action(refreshAccount, 'Account access refreshed.')
                }
              >
                Refresh account access
              </button>
              <button
                className="calculator-secondary"
                disabled={busy}
                onClick={() =>
                  action(logout, 'Signed out. The server session was revoked.')
                }
              >
                Sign out
              </button>
            </div>
            <p className="workspace-muted">
              Expires {new Date(session.expiresAt).toLocaleString()}. Reloading
              requires sign-in again.
            </p>
          </section>
          <section className="workspace-panel">
            <h2>A place for your kind of good.</h2>
            {session.account.roles.includes('seller') ? (
              <>
                <p>
                  Your account has seller access. This is not a certification of
                  identity or product quality.
                </p>
                <a className="button-primary" href="#/seller">
                  Open seller workspace
                </a>
              </>
            ) : !applicationLoaded ? (
              <p role="status">Checking your seller application…</p>
            ) : application ? (
              <>
                <p>
                  Application: <strong>{application.status}</strong>
                </p>
                {application.decision && (
                  <p>Administrator’s decision: {application.decision.reason}</p>
                )}
                {application.status === 'pending' && (
                  <p>
                    A separate administrator must review your request. Applying
                    does not grant seller access.
                  </p>
                )}
                {application.status === 'approved' && (
                  <p>
                    Refresh account access to load your current server roles.
                  </p>
                )}
                {application.status === 'denied' && (
                  <p>
                    This decision is final in the local MVP. Reapplication is
                    not available.
                  </p>
                )}
                <button
                  className="calculator-secondary"
                  disabled={busy}
                  onClick={() => {
                    setApplicationLoaded(false)
                    setVersion(version + 1)
                  }}
                >
                  Check application status
                </button>
              </>
            ) : (
              <>
                <p>
                  Request seller access for manual administrator review. No
                  verification documents or criteria are collected here.
                </p>
                <button
                  className="button-primary"
                  disabled={busy}
                  onClick={() =>
                    action(async () => {
                      setApplication(await applyToSell())
                    }, 'Seller application submitted for manual review.')
                  }
                >
                  Request seller access
                </button>
              </>
            )}
          </section>
        </>
      )}
    </WorkspaceLayout>
  )
}
