import { useState } from 'react'
import { Brand } from './Brand'
import { LeafSprig } from './LeafSprig'
import type { AccountRole } from '../types/account'

export function Header({ role }: { role: AccountRole }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const links = [
    {
      label: role === 'buyer' ? 'The market' : 'For our makers',
      href: '#marketplace',
    },
    { label: 'How it works', href: '#how-it-works' },
    { label: 'Our promise', href: '#our-promise' },
    { label: 'Cost calculator', href: '#/pricing' },
  ]
  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <div className="announcement">
        A little more local. A little more understanding. <LeafSprig /> Welcome
        to FairMade.
      </div>
      <header className="site-header page-width">
        <Brand />
        <nav className="desktop-nav" aria-label="Main navigation">
          {links.map((link) => (
            <a key={link.href} href={link.href}>
              {link.label}
            </a>
          ))}
        </nav>
        <div className="header-actions">
          <a className="button-primary header-account" href="#create-account">
            Create an account <span aria-hidden="true">↗</span>
          </a>
          <button
            className="menu-button"
            type="button"
            aria-expanded={menuOpen}
            aria-controls="mobile-navigation"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {menuOpen ? 'Close' : 'Menu'}
          </button>
        </div>
        {menuOpen && (
          <nav
            id="mobile-navigation"
            className="mobile-nav"
            aria-label="Mobile navigation"
          >
            {links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMenuOpen(false)}
              >
                {link.label}
              </a>
            ))}
            <a href="#create-account" onClick={() => setMenuOpen(false)}>
              Create an account ↗
            </a>
          </nav>
        )}
      </header>
    </>
  )
}
