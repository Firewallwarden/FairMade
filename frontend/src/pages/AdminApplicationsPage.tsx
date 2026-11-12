import { useCallback, useState } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { TextArea } from '../components/FormFields'
import { useSession } from '../services/session'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import { getAdminApplication, getAdminApplications, decideSellerApplication } from '../services/admin-applications'
import { ApiError } from '../services/http'
import { fieldValue } from '../utils/form'

export function AdminApplicationsPage({ id }: { id?: string }) {
  const session = useSession()
  return <WorkspaceLayout title="Manual seller application review.">
    {!session ? <SignInPrompt /> : !session.account.roles.includes('admin') ? <p>Administrator access is required.</p> : id ? <ApplicationDetails id={id} reviewerId={session.account.id} /> : <ApplicationQueue />}
  </WorkspaceLayout>
}
function ApplicationQueue() {
  const [state, setState] = useState('pending')
  const [offset, setOffset] = useState(0)
  const resource = useResource(useCallback(signal => getAdminApplications(state, offset, signal), [state, offset]))
  return <section className="workspace-panel">
    <h2>Seller application queue</h2>
    <p>Review intent and the approved manual process. Approval adds seller access; it does not certify identity, safety or product quality.</p>
    <label className="calculator-field">Application state<select value={state} onChange={event => { setState(event.target.value); setOffset(0) }}>
      {['pending', 'approved', 'denied', 'all'].map(value => <option key={value}>{value}</option>)}
    </select></label>
    <ErrorNotice error={resource.error} />
    {resource.loading && <p role="status">Loading private application queue…</p>}
    {resource.data && !resource.data.items.length && <p>No applications on this page.</p>}
    <ul>{resource.data?.items.map(item => <li key={item.id}>
      <a href={`#/admin-applications/${item.id}`}>{item.applicant_email}</a> · {item.status} · submitted {new Date(item.submittedAt).toLocaleString()}
    </li>)}</ul>
    <div className="workspace-actions">
      <button className="calculator-secondary" disabled={resource.loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous applications</button>
      <button className="calculator-secondary" disabled={resource.loading || !resource.data || resource.data.items.length < 20} onClick={() => setOffset(offset + 20)}>Next applications</button>
      <button className="calculator-secondary" disabled={resource.loading} onClick={resource.reload}>Refresh application queue</button>
    </div>
  </section>
}
function ApplicationDetails({ id, reviewerId }: { id: string; reviewerId: string }) {
  const resource = useResource(useCallback(signal => getAdminApplication(id, signal), [id]))
  const action = useAction()
  const [stale, setStale] = useState(false)
  const application = resource.data
  return <section className="workspace-panel">
    <a href="#/admin-applications">Back to application queue</a>
    <h2>Application review</h2>
    <ErrorNotice error={resource.error || action.error} />
    {resource.loading && <p role="status">Loading current application revision…</p>}
    {action.notice && <p role="status">{action.notice}</p>}
    {stale && <p role="alert">The saved application changed or already has a decision. Its current state has been reloaded. Review it before deciding again.</p>}
    {application && <>
      <p>Applicant: {application.applicant_email}. Account reference: {application.applicant_account_id}.</p>
      <p>Submitted {new Date(application.submittedAt).toLocaleString()} · {application.status} · revision {application.revision}.</p>
      {application.decision && <p>Final decision: {application.decision.outcome}. Reason shared with applicant: {application.decision.reason}. Recorded {new Date(application.decision.createdAt).toLocaleString()}. Basis: manual administrator review.</p>}
      {application.applicant_account_id === reviewerId && <p>You cannot review your own application.</p>}
      {application.status === 'pending' && application.applicant_account_id !== reviewerId && <form key={application.revision} onSubmit={event => {
        event.preventDefault()
        const fields = new FormData(event.currentTarget)
        const outcome = fieldValue(fields, 'application-outcome')
        if (outcome !== 'approved' && outcome !== 'denied') return
        const reason = fieldValue(fields, 'application-reason')
        if (!window.confirm(`Record a final ${outcome} decision? The reason will be visible to the applicant.`)) return
        void action.run(async () => {
          setStale(false)
          try {
            await decideSellerApplication(id, application.revision, outcome, reason)
            resource.reload()
          } catch (error) {
            if (error instanceof ApiError && error.status === 409) {
              setStale(true)
              resource.reload()
            }
            throw error
          }
        }, 'The backend recorded the final manual decision.')
      }}>
        <fieldset className="calculator-form" disabled={action.busy}>
          <legend>Final manual decision</legend>
          <label className="calculator-field">Outcome<select name="application-outcome" required defaultValue="">
            <option value="">Choose an outcome</option><option value="approved">Approve seller access</option><option value="denied">Deny application</option>
          </select></label>
          <TextArea name="application-reason" title="Reason (shared with applicant)" required minLength={1} maxLength={2000} />
          <p>Decisions are final in the local MVP. Approval does not verify identity or certify product quality. Do not include secrets or private documents in the shared reason.</p>
          <button className="button-primary" type="submit">Record final application decision</button>
        </fieldset>
      </form>}
    </>}
    <button className="calculator-secondary" disabled={resource.loading || action.busy} onClick={resource.reload}>Reload current application</button>
  </section>
}
