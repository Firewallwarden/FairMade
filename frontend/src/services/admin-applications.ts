import { privateRequest } from './session'
import { decodeApplication } from './account-contract'
import { nullable, object, page, text } from './decode'

function decodeAdminApplication(value: unknown) {
  const data = object(value)
  return { ...decodeApplication(value), applicant_account_id: text(data.applicant_account_id), applicant_email: text(data.applicant_email), decided_by_account_id: nullable(data.decided_by_account_id, text) }
}
export const getAdminApplications = (state: string, offset: number, signal?: AbortSignal) =>
  privateRequest(`/admin/seller-applications?${new URLSearchParams({ state, limit: '20', offset: String(offset) })}`, page(decodeAdminApplication), { signal })
export const getAdminApplication = (id: string, signal?: AbortSignal) =>
  privateRequest(`/admin/seller-applications/${id}`, decodeAdminApplication, { signal })
export const decideSellerApplication = (id: string, revision: number, outcome: 'approved' | 'denied', reason: string) =>
  privateRequest(`/admin/seller-applications/${id}/decision`, decodeAdminApplication, { method: 'POST', json: { expected_revision: revision, outcome, reason } })
