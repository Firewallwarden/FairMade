import { Component } from 'react'
import type { ReactNode } from 'react'
import { WorkspaceLayout } from './WorkspaceLayout'

export class PageBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    if (this.state.failed)
      return (
        <WorkspaceLayout title="This page needs another try.">
          <p role="alert">
            The page could not load. Reload to get the latest application files.
            You may need to sign in again.
          </p>
          <p>Check saved records before repeating a submission or payment.</p>
          <button
            className="button-primary"
            onClick={() => window.location.reload()}
          >
            Reload application
          </button>
        </WorkspaceLayout>
      )
    return this.props.children
  }
}
