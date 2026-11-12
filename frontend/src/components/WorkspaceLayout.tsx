import type { ReactNode } from 'react'
import { Brand } from './Brand'
import { useSession } from '../services/session'
import '../pages/pricing.css'
import '../workspace.css'

export function WorkspaceLayout({
  title,
  intro,
  children,
}: {
  title: string
  intro?: string
  children: ReactNode
}) {
  const session = useSession()
  const section = window.location.hash.split('/')[1]
  return (
    <div>
      <a
        className="skip-link"
        href="#workspace-main"
        onClick={(event) => {
          event.preventDefault()
          document.getElementById('workspace-main')?.focus()
        }}
      >
        Skip to content
      </a>
      <header className="site-header page-width workspace-header">
        <Brand />
        <nav aria-label="Main navigation" className="workspace-nav">
          <a href="#/assistant" aria-current={section === 'assistant' ? 'page' : undefined}>Ask FairMade</a>
          <a
            href="#/market"
            aria-current={section === 'market' ? 'page' : undefined}
          >
            The market
          </a>
          <a
            href="#/seller"
            aria-current={section === 'seller' ? 'page' : undefined}
          >
            Seller workspace
          </a>
          <a
            href="#/orders"
            aria-current={
              section === 'orders' || section === 'seller-orders'
                ? 'page'
                : undefined
            }
          >
            Orders
          </a>
          <a
            href="#/pricing"
            aria-current={section === 'pricing' ? 'page' : undefined}
          >
            Cost calculator
          </a>
          <a
            href="#/account"
            aria-current={section === 'account' ? 'page' : undefined}
          >
            {session ? 'My account' : 'Sign in'}
          </a>
        </nav>
      </header>
      <main
        id="workspace-main"
        tabIndex={-1}
        className="page-width workspace-main"
      >
        <p className="eyebrow">
          A little more local. A little more understood.
        </p>
        <h1>{title}</h1>
        {intro && <p className="workspace-intro">{intro}</p>}
        {children}
      </main>
      <footer className="page-width calculator-footer">
        FairMade local demo · USD · PayPal sandbox only · Seller-reported claims
        are unverified.
      </footer>
    </div>
  )
}
