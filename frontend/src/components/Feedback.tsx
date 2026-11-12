import { useEffect, useRef } from 'react'
import { ApiError } from '../services/http'

export function ErrorNotice({ error }: { error: unknown }) {
  const notice = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (error) notice.current?.focus()
  }, [error])
  if (!error) return null
  return (
    <div className="calculator-error" role="alert" tabIndex={-1} ref={notice}>
      <p>
        {error instanceof Error
          ? error.message
          : 'Something went wrong. Please try again.'}
      </p>
      {error instanceof ApiError && error.issues.length > 0 && (
        <ul>
          {error.issues.map((issue, index) => (
            <li key={index}>
              {issue.field.replace(/^body\.?/, '')}: {issue.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function SignInPrompt() {
  return (
    <div className="workspace-empty">
      <h2>Make yourself at home.</h2>
      <p>Sign in to use this part of FairMade.</p>
      <a className="button-primary" href="#/account">
        Sign in or create an account
      </a>
    </div>
  )
}
