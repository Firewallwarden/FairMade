import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { Field, TextArea } from '../components/FormFields'
import { EvidenceDetails } from '../components/EvidenceDetails'
import { QuotePicker } from '../components/QuotePicker'
import { useAction } from '../hooks/useAction'
import { useResource } from '../hooks/useResource'
import { useSession } from '../services/session'
import {
  createSupplierProfile,
  getSupplierProfile,
  getSupplierProfiles,
  updateSupplierProfile,
  getSupplierHistory,
  getSupplierExperiences,
  getSupplierReliability,
  getSupplierExperience,
  recordSupplierExperience,
} from '../services/supplier-records'
import type {
  SupplierFields,
  SupplierExperienceInput,
} from '../services/supplier-records'
import { fieldValue } from '../utils/form'

export function SupplierRecordsPage({ id }: { id?: string }) {
  const session = useSession()
  return (
    <WorkspaceLayout
      title="Know the people behind your inputs."
      intro="Private supplier records and your reported experiences. No public ratings, certification or automatic substitutions."
    >
      {!session ? (
        <SignInPrompt />
      ) : !session.account.roles.includes('seller') ? (
        <p>Seller access is required.</p>
      ) : id ? (
        <SupplierRecord id={id} />
      ) : (
        <SupplierList />
      )}
    </WorkspaceLayout>
  )
}
function SupplierFieldsForm({ initial }: { initial?: SupplierFields }) {
  return (
    <>
      <div className="calculator-grid">
        <Field
          name="supplier-profile-name"
          title="Private supplier name"
          required
          maxLength={200}
          defaultValue={initial?.name}
        />
        <Field
          name="supplier-profile-location"
          title="Location label (optional)"
          maxLength={200}
          defaultValue={initial?.location ?? ''}
        />
        <TextArea
          name="supplier-profile-notes"
          title="Private notes (optional)"
          maxLength={2000}
          defaultValue={initial?.notes ?? ''}
        />
      </div>
      {initial && (
        <label className="workspace-check">
          <input
            name="supplier-profile-archived"
            type="checkbox"
            defaultChecked={initial.archived}
          />
          Archive this private profile; historical records remain.
        </label>
      )}
    </>
  )
}
function profileFields(fields: FormData): SupplierFields {
  return {
    name: fieldValue(fields, 'supplier-profile-name'),
    location: fieldValue(fields, 'supplier-profile-location') || null,
    notes: fieldValue(fields, 'supplier-profile-notes') || null,
    archived: fields.has('supplier-profile-archived'),
  }
}
function SupplierList() {
  const [offset, setOffset] = useState(0),
    [filter, setFilter] = useState<'all' | 'active' | 'archived'>('active')
  const resource = useResource(
    useCallback(
      (signal) => getSupplierProfiles(offset, filter, signal),
      [offset, filter],
    ),
  )
  const action = useAction()
  const [attempt, setAttempt] = useState<
    (SupplierFields & { request_id: string }) | null
  >(null)
  return (
    <>
      <a href="#/seller">← Seller workspace</a>
      <section className="workspace-panel">
        <h2>A private supplier notebook.</h2>
        <ErrorNotice error={action.error} />
        <form
          onSubmit={(event) => {
            event.preventDefault()
            const request = attempt ?? {
              ...profileFields(new FormData(event.currentTarget)),
              request_id: crypto.randomUUID(),
            }
            setAttempt(request)
            void action.run(async () => {
              const saved = await createSupplierProfile(request)
              setAttempt(null)
              window.location.hash = `/suppliers/${saved.supplier_id}`
            })
          }}
        >
          <fieldset
            className="calculator-form"
            disabled={action.busy || Boolean(attempt)}
          >
            <legend className="sr-only">Create private supplier profile</legend>
            <SupplierFieldsForm />
          </fieldset>
          <div className="workspace-actions">
            <button className="button-primary" disabled={action.busy}>
              {attempt
                ? 'Retry same profile request'
                : 'Create private supplier profile'}
            </button>
          </div>
        </form>
        {attempt && (
          <>
            <p>
              The same payload and request identifier are retained. Check the
              profile list after an uncertain result before starting a different
              request.
            </p>
            <button
              className="calculator-secondary"
              disabled={action.busy}
              onClick={() => {
                resource.reload()
                setAttempt(null)
              }}
            >
              Reload saved list before editing this request
            </button>
          </>
        )}
      </section>
      <ErrorNotice error={resource.error} />
      <label className="calculator-field">
        Profiles
        <select
          value={filter}
          onChange={(event) => {
            const value = event.target.value
            if (value === 'all' || value === 'active' || value === 'archived') {
              setFilter(value)
              setOffset(0)
            }
          }}
        >
          <option value="active">Active</option>
          <option value="archived">Archived</option>
          <option value="all">All profiles</option>
        </select>
      </label>
      {resource.loading && <p role="status">Loading private suppliers…</p>}
      {resource.data && (
        <>
          {!resource.data.items.length && <p>No profiles on this page.</p>}
          <div className="workspace-grid">
            {resource.data.items.map((item) => (
              <article className="workspace-panel" key={item.id}>
                <p className="workspace-status">
                  {item.archived ? 'Archived' : 'Active'}
                </p>
                <h2>{item.name}</h2>
                <p>{item.location ?? 'No location recorded'}</p>
                <a href={`#/suppliers/${item.id}`}>
                  View reported experience & history
                </a>
              </article>
            ))}
          </div>
        </>
      )}
      <div className="workspace-actions">
        <button
          className="calculator-secondary"
          disabled={!offset}
          onClick={() => setOffset(offset - 20)}
        >
          Previous suppliers
        </button>
        <button
          className="calculator-secondary"
          disabled={(resource.data?.items.length ?? 0) < 20}
          onClick={() => setOffset(offset + 20)}
        >
          Next suppliers
        </button>
        <button className="calculator-secondary" onClick={resource.reload}>
          Reload supplier list
        </button>
      </div>
    </>
  )
}
function SupplierRecord({ id }: { id: string }) {
  const [offset, setOffset] = useState(0),
    [query, setQuery] = useState('')
  const resource = useResource(
    useCallback(
      async (signal) => {
        const [profile, experiences, history, reliability] = await Promise.all([
          getSupplierProfile(id, signal),
          getSupplierExperiences(id, offset, query, signal),
          getSupplierHistory(id, offset, signal),
          getSupplierReliability(id, query, signal),
        ])
        return { profile, experiences, history, reliability }
      },
      [id, offset, query],
    ),
  )
  const action = useAction()
  const [snapshot, setSnapshot] = useState<Awaited<
    ReturnType<typeof getSupplierExperience>
  > | null>(null)
  return (
    <>
      <a href="#/suppliers">← Private supplier notebook</a>
      <ErrorNotice error={resource.error || action.error} />
      {resource.loading && <p role="status">Loading supplier evidence…</p>}
      <form
        onSubmit={(event) => {
          event.preventDefault()
          const fields = new FormData(event.currentTarget),
            query = new URLSearchParams()
          const start = fieldValue(fields, 'supplier-observed-from'),
            end = fieldValue(fields, 'supplier-observed-until')
          if (start) query.set('observed_from', start)
          if (end) query.set('observed_until', end)
          setQuery(query.toString())
          setOffset(0)
          setSnapshot(null)
        }}
      >
        <div className="calculator-grid">
          <Field
            name="supplier-observed-from"
            title="Observations from (optional)"
            type="date"
          />
          <Field
            name="supplier-observed-until"
            title="Observations through (optional)"
            type="date"
          />
        </div>
        <button className="calculator-secondary">
          Apply observation window
        </button>
      </form>
      {resource.data && (
        <>
          <section className="workspace-panel">
            <p className="eyebrow">Seller-reported, unverified</p>
            <h2>{resource.data.profile.name}</h2>
            <p>{resource.data.profile.location}</p>
            <p className="private-instructions">
              {resource.data.profile.notes}
            </p>
            <p>
              {resource.data.reliability.experiences_count} current
              observation(s); {resource.data.reliability.rated_count} with a
              rating. Average reported rating:{' '}
              {resource.data.reliability.average_rating === null
                ? 'Unknown'
                : resource.data.reliability.average_rating + '/5'}
              .
            </p>
            <p>
              {resource.data.reliability.on_time_count} on-time and{' '}
              {resource.data.reliability.late_count} late, from{' '}
              {resource.data.reliability.dated_deliveries_count} dated
              deliveries. Delivery timing unknown in{' '}
              {resource.data.reliability.unknown_delivery_count} observation(s).
            </p>
            <ul>
              {resource.data.reliability.notices.map((notice, index) => (
                <li key={index}>{notice}</li>
              ))}
            </ul>
            <p>
              These are your reported observations, not verified community
              reliability or proof that an input meets Quality Lock.
            </p>
            <SupplierProfileEditor
              key={resource.data.profile.revision}
              profile={resource.data.profile}
              onChanged={resource.reload}
            />
          </section>
          <SupplierExperienceForm
            key={`${id}-${resource.data.profile.revision}-${offset}-${query}`}
            profile={resource.data.profile}
            observations={resource.data.experiences.items}
            onChanged={resource.reload}
          />
          <section className="workspace-panel">
            <h2>Your current observations</h2>
            {!resource.data.experiences.items.length && (
              <p>No observations in this page/window.</p>
            )}
            {resource.data.experiences.items.map((item) => (
              <article key={item.id}>
                <h3>{item.label}</h3>
                <p>
                  Observed {item.observed_on} · Rating{' '}
                  {item.rating ?? 'not recorded'}
                  {item.rating !== null && '/5'} · Promised{' '}
                  {item.promised_on ?? 'unknown'} · Received{' '}
                  {item.received_on ?? 'unknown'}
                </p>
                {item.corrects_experience_id && (
                  <p>This is a correction; prior history remains.</p>
                )}
                <button
                  className="calculator-secondary"
                  disabled={action.busy}
                  onClick={() =>
                    action.run(async () =>
                      setSnapshot(await getSupplierExperience(id, item.id)),
                    )
                  }
                >
                  Review saved observation and source snapshot
                </button>
              </article>
            ))}
            {snapshot && (
              <details open>
                <summary>Selected saved observation</summary>
                <EvidenceDetails
                  value={{
                    reported: snapshot.request,
                    supplier_snapshot: snapshot.supplier_snapshot,
                    quote_snapshot: snapshot.quote_snapshot,
                  }}
                />
              </details>
            )}
          </section>
          <section className="workspace-panel">
            <h2>Profile change history</h2>
            {resource.data.history.items.map((event) => (
              <details key={event.revision}>
                <summary>
                  Revision {event.revision} ·{' '}
                  {new Date(event.created_at).toLocaleString()}
                </summary>
                <p>{event.reason}</p>
                <EvidenceDetails
                  value={{ before: event.before, after: event.after }}
                />
              </details>
            ))}
          </section>
        </>
      )}
      <div className="workspace-actions">
        <button
          className="calculator-secondary"
          disabled={!offset}
          onClick={() => {
            setSnapshot(null)
            setOffset(offset - 20)
          }}
        >
          Previous history page
        </button>
        <button
          className="calculator-secondary"
          disabled={
            Math.max(
              resource.data?.experiences.items.length ?? 0,
              resource.data?.history.items.length ?? 0,
            ) < 20
          }
          onClick={() => {
            setSnapshot(null)
            setOffset(offset + 20)
          }}
        >
          Next history page
        </button>
        <button
          className="calculator-secondary"
          onClick={() => {
            setSnapshot(null)
            resource.reload()
          }}
        >
          Reload supplier and saved history
        </button>
      </div>
    </>
  )
}
function SupplierProfileEditor({
  profile,
  onChanged,
}: {
  profile: Awaited<ReturnType<typeof getSupplierProfile>>
  onChanged: () => void
}) {
  const action = useAction()
  const [attempt, setAttempt] = useState<
    | (SupplierFields & {
        request_id: string
        expected_revision: number
        reason: string
      })
    | null
  >(null)
  return (
    <details>
      <summary>Edit private profile or archive it</summary>
      <ErrorNotice error={action.error} />
      <form
        onSubmit={(event) => {
          event.preventDefault()
          const fields = new FormData(event.currentTarget)
          const request = attempt ?? {
            ...profileFields(fields),
            request_id: crypto.randomUUID(),
            expected_revision: profile.revision,
            reason: fieldValue(fields, 'supplier-edit-reason'),
          }
          setAttempt(request)
          void action.run(async () => {
            await updateSupplierProfile(profile.id, request)
            setAttempt(null)
            onChanged()
          })
        }}
      >
        <fieldset
          className="calculator-form"
          disabled={Boolean(attempt) || action.busy}
        >
          <legend className="sr-only">Replace supplier profile</legend>
          <SupplierFieldsForm initial={profile} />
          <TextArea
            name="supplier-edit-reason"
            title="Reason for this profile change"
            required
            maxLength={2000}
          />
        </fieldset>
        <div className="workspace-actions">
          <button className="calculator-secondary" disabled={action.busy}>
            {attempt
              ? 'Retry same profile update'
              : 'Save private profile change'}
          </button>
        </div>
      </form>
      <p>
        Updates preserve history and use the current saved revision. After a
        conflict or uncertain result, reload this supplier and inspect its
        history.
      </p>
    </details>
  )
}
function SupplierExperienceForm({
  profile,
  observations,
  onChanged,
}: {
  profile: Awaited<ReturnType<typeof getSupplierProfile>>
  observations: Awaited<ReturnType<typeof getSupplierExperiences>>['items']
  onChanged: () => void
}) {
  const action = useAction()
  const [attempt, setAttempt] = useState<SupplierExperienceInput | null>(null),
    [corrects, setCorrects] = useState(''),
    [quote, setQuote] = useState(false)
  const [today] = useState(() => new Date().toISOString().slice(0, 10))
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    const request: SupplierExperienceInput = attempt ?? {
      request_id: crypto.randomUUID(),
      expected_supplier_revision: profile.revision,
      label: fieldValue(fields, 'experience-label'),
      observed_on: fieldValue(fields, 'experience-observed'),
      rating: fieldValue(fields, 'experience-rating')
        ? Number(fieldValue(fields, 'experience-rating'))
        : null,
      promised_on: fieldValue(fields, 'experience-promised') || null,
      received_on: fieldValue(fields, 'experience-received') || null,
      notes: fieldValue(fields, 'experience-notes') || null,
      source_quote_id: quote
        ? fieldValue(fields, 'experience-quote') || null
        : null,
      corrects_experience_id: corrects || null,
      correction_reason: corrects
        ? fieldValue(fields, 'experience-correction-reason')
        : null,
    }
    if (!attempt && quote && !request.source_quote_id) {
      void action.run(async () => {
        throw new Error('Choose a source quote or turn off quote linking.')
      })
      return
    }
    if (
      !attempt &&
      request.rating === null &&
      !request.promised_on &&
      !request.received_on &&
      !request.notes
    ) {
      void action.run(async () => {
        throw new Error(
          'Record a rating, delivery observation or notes before saving.',
        )
      })
      return
    }
    setAttempt(request)
    void action.run(async () => {
      await recordSupplierExperience(profile.id, request)
      setAttempt(null)
      onChanged()
    })
  }
  return (
    <section className="workspace-panel">
      <h2>Record what you observed.</h2>
      <ErrorNotice error={action.error} />
      <p>
        New observations and corrections are append-only. Corrections replace an
        observation in current reliability calculations while retaining its
        historical record. Unknown delivery dates remain unknown.
      </p>
      <form onSubmit={save}>
        <fieldset
          className="calculator-form"
          disabled={action.busy || Boolean(attempt) || profile.archived}
        >
          <legend className="sr-only">Supplier experience</legend>
          <div className="calculator-grid">
            <Field
              name="experience-label"
              title="Observation label"
              required
              maxLength={200}
            />
            <Field
              name="experience-observed"
              title="Observed on"
              type="date"
              max={today}
              required
            />
            <label className="calculator-field">
              Reported rating (optional)
              <select name="experience-rating">
                <option value="">Not recorded</option>
                {[1, 2, 3, 4, 5].map((rating) => (
                  <option key={rating} value={rating}>
                    {rating}/5
                  </option>
                ))}
              </select>
            </label>
            <Field
              name="experience-promised"
              title="Promised delivery date (optional)"
              type="date"
            />
            <Field
              name="experience-received"
              title="Received on (optional)"
              type="date"
              max={today}
            />
            <TextArea
              name="experience-notes"
              title="Private observation notes (optional)"
              maxLength={2000}
            />
            <label className="calculator-field">
              Correct an existing observation (latest page/window)
              <select
                value={corrects}
                onChange={(event) => setCorrects(event.target.value)}
              >
                <option value="">New observation</option>
                {observations.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.observed_on} · {item.label}
                  </option>
                ))}
              </select>
            </label>
            {corrects && (
              <TextArea
                name="experience-correction-reason"
                title="Correction reason"
                required
                maxLength={2000}
              />
            )}
          </div>
          <label className="workspace-check">
            <input
              type="checkbox"
              checked={quote}
              onChange={(event) => setQuote(event.target.checked)}
            />
            Link one of my saved supplier quotes as source evidence.
          </label>
          {quote && <QuotePicker name="experience-quote" />}
        </fieldset>
        <div className="workspace-actions">
          <button
            className="button-primary"
            disabled={action.busy || profile.archived}
          >
            {attempt ? 'Retry same observation' : 'Save reported observation'}
          </button>
        </div>
      </form>
      {profile.archived && (
        <p>Unarchive the profile before recording another observation.</p>
      )}
      {attempt && (
        <p>
          The exact observation and retry identifier are retained. After a
          conflict or timeout, reload and inspect saved history before starting
          a different observation.
        </p>
      )}
    </section>
  )
}
