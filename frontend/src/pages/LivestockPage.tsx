import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { Field, TextArea } from '../components/FormFields'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { EvidenceDetails } from '../components/EvidenceDetails'
import { LivestockPicker } from '../components/LivestockSourceFields'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import { useSession } from '../services/session'
import {
  getGroups,
  getAnimals,
  getGroup,
  getAnimal,
  saveLivestock,
  getLivestockHistory,
  getLivestockProduction,
} from '../services/livestock'
import { animalSexes, animalStatuses } from '../services/livestock-contract'
import type {
  Group,
  Animal,
  LivestockKind,
  LivestockChange,
} from '../services/livestock-contract'
import { choice } from '../services/decode'
import { ApiError } from '../services/http'
import { fieldValue } from '../utils/form'

export function LivestockPage({
  kind = 'groups',
  id,
}: {
  kind?: LivestockKind
  id?: string
}) {
  const session = useSession()
  return (
    <WorkspaceLayout
      title="A record for the animals in your care."
      intro="Private, seller-reported identities, observations and production sources. These records do not verify animal health, welfare or product quality."
    >
      {!session ? (
        <SignInPrompt />
      ) : !session.account.roles.includes('seller') ? (
        <p>Seller access is required.</p>
      ) : (
        <>
          <div className="workspace-actions">
            <a href="#/seller">← Seller workspace</a>
            <a className="calculator-secondary" href="#/livestock/groups">
              Groups
            </a>
            <a className="calculator-secondary" href="#/livestock/animals">
              Individual animals
            </a>
          </div>
          {id ? (
            <LivestockDetail kind={kind} id={id} />
          ) : (
            <LivestockList kind={kind} />
          )}
        </>
      )}
    </WorkspaceLayout>
  )
}
function LivestockList({ kind }: { kind: LivestockKind }) {
  const [offset, setOffset] = useState(0)
  const resource = useResource(
    useCallback(
      async (signal) => {
        const data =
          kind === 'groups'
            ? await getGroups(offset, signal)
            : await getAnimals(offset, signal)
        return { ...data, items: data.items as (Group | Animal)[] }
      },
      [kind, offset],
    ),
  )
  return (
    <>
      <section className="workspace-panel">
        <h2>
          {kind === 'groups'
            ? 'Create a private group'
            : 'Register an individual animal'}
        </h2>
        <LivestockForm
          kind={kind}
          onSaved={(id) => {
            window.location.hash = `/livestock/${kind}/${id}`
          }}
        />
      </section>
      <ErrorNotice error={resource.error} />
      {resource.loading && <p role="status">Loading livestock…</p>}
      {resource.data && !resource.data.items.length && (
        <p>No records on this page.</p>
      )}
      <div className="workspace-grid">
        {resource.data?.items.map((row) => (
          <article key={row.id} className="workspace-panel">
            <h2>{'identifier' in row ? row.identifier : row.name}</h2>
            <p>
              {row.species} ·{' '}
              {'archived' in row
                ? row.archived
                  ? 'Archived group'
                  : 'Active group'
                : row.status}
            </p>
            {'reported_headcount' in row && (
              <p>
                Reported count: {row.reported_headcount ?? 'Unknown'} ·
                Registered active animals: {row.registered_active_animals}.
                These counts are separate.
              </p>
            )}
            <a
              className="calculator-secondary"
              href={`#/livestock/${kind}/${row.id}`}
            >
              View private record
            </a>
          </article>
        ))}
      </div>
      <Pager
        offset={offset}
        count={resource.data?.items.length ?? 0}
        change={setOffset}
        label="livestock"
      />
    </>
  )
}
function LivestockDetail({ kind, id }: { kind: LivestockKind; id: string }) {
  const [historyOffset, setHistoryOffset] = useState(0),
    [productionOffset, setProductionOffset] = useState(0)
  const resource = useResource<Group | Animal>(
    useCallback(
      (signal) =>
        kind === 'groups' ? getGroup(id, signal) : getAnimal(id, signal),
      [kind, id],
    ),
  )
  const history = useResource(
    useCallback(
      (signal) => getLivestockHistory(kind, id, historyOffset, signal),
      [kind, id, historyOffset],
    ),
  )
  const production = useResource(
    useCallback(
      (signal) => getLivestockProduction(kind, id, productionOffset, signal),
      [kind, id, productionOffset],
    ),
  )
  const row = resource.data
  const reload = () => {
    resource.reload()
    history.reload()
    production.reload()
  }
  return (
    <>
      <ErrorNotice
        error={resource.error || history.error || production.error}
      />
      {resource.loading && <p role="status">Loading private record…</p>}
      {row && (
        <section className="workspace-panel">
          <p className="eyebrow">
            Seller-reported · unverified · revision {row.revision}
          </p>
          <h2>
            {'identifier' in row ? row.identifier : row.name} · {row.species}
          </h2>
          {'reported_headcount' in row && (
            <>
              <p>
                Manual headcount:{' '}
                <strong>{row.reported_headcount ?? 'Unknown'}</strong>
                {row.headcount_on ? ` observed ${row.headcount_on}` : ''}.
              </p>
              <p>
                Separately registered active animals:{' '}
                <strong>{row.registered_active_animals}</strong>. This is not
                added to the reported headcount.
              </p>
            </>
          )}
          <details>
            <summary>Edit this private record</summary>
            <LivestockForm
              key={row.revision}
              kind={kind}
              current={row}
              onSaved={reload}
            />
          </details>
        </section>
      )}
      <section className="workspace-panel">
        <h2>The change history</h2>
        {history.loading && <p role="status">Loading history…</p>}
        {history.data?.items.map((event) => (
          <details key={event.id}>
            <summary>
              Revision {event.revision} · {event.occurred_on} · {event.reason}
            </summary>
            <EvidenceDetails
              value={{
                before: event.before,
                after: event.after,
                recorded_at: event.created_at,
              }}
            />
          </details>
        ))}
        <Pager
          offset={historyOffset}
          count={history.data?.items.length ?? 0}
          change={setHistoryOffset}
          label="history"
        />
      </section>
      <section className="workspace-panel">
        <h2>Attributed completed production</h2>
        <p>
          Latest effective reports attributed to this source. Historical source
          snapshots remain attached to their original reports.
        </p>
        {production.loading && (
          <p role="status">Loading attributed production…</p>
        )}
        {production.data && !production.data.items.length && (
          <p>No attributed production on this page.</p>
        )}
        {production.data?.items.map((record) => (
          <article key={record.id}>
            <h3>{record.label}</h3>
            <p>
              {record.started_on} – {record.completed_on} ·{' '}
              {record.sellable_units} sellable of {record.total_units} total{' '}
              {record.selling_unit} units.
            </p>
            <a href={`#/seller/${record.product_id}`}>
              Open product production records
            </a>
          </article>
        ))}
        <Pager
          offset={productionOffset}
          count={production.data?.items.length ?? 0}
          change={setProductionOffset}
          label="production"
        />
      </section>
      <button className="calculator-secondary" onClick={reload}>
        Reload livestock record and history
      </button>
    </>
  )
}
function Pager({
  offset,
  count,
  change,
  label,
}: {
  offset: number
  count: number
  change: (value: number) => void
  label: string
}) {
  return (
    <div className="workspace-actions">
      <button
        type="button"
        className="calculator-secondary"
        disabled={!offset}
        onClick={() => change(offset - 20)}
      >
        Previous {label}
      </button>
      <button
        type="button"
        className="calculator-secondary"
        disabled={count < 20}
        onClick={() => change(offset + 20)}
      >
        Next {label}
      </button>
    </div>
  )
}
function LivestockForm({
  kind,
  current,
  onSaved,
}: {
  kind: LivestockKind
  current?: Group | Animal
  onSaved: (id: string) => void
}) {
  const action = useAction(),
    [attempt, setAttempt] = useState<LivestockChange | null>(null)
  const [today] = useState(() => new Date().toISOString().slice(0, 10))
  const [status, setStatus] = useState<Animal['status']>(
    current && 'status' in current ? current.status : 'active',
  )
  const group = current && 'archived' in current ? current : undefined
  const animal = current && 'identifier' in current ? current : undefined
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const f = new FormData(event.currentTarget),
      get = (key: string) => fieldValue(f, 'livestock-' + key)
    void action.run(async () => {
      const payload: LivestockChange = attempt ?? {
        request_id: crypto.randomUUID(),
        occurred_on: get('occurred'),
        reason: get('reason'),
        ...(current
          ? { expected_revision: current.revision }
          : { species: get('species') }),
        ...(kind === 'groups'
          ? {
              name: get('name'),
              breed: get('breed') || null,
              notes: get('notes') || null,
              reported_headcount: get('count') ? Number(get('count')) : null,
              headcount_on: get('count-date') || null,
              archived: f.has('livestock-archived'),
            }
          : {
              identifier: get('identifier'),
              name: get('name') || null,
              breed: get('breed') || null,
              notes: get('notes') || null,
              sex: choice(get('sex'), animalSexes),
              born_on: get('born') || null,
              acquired_on: get('acquired') || null,
              status,
              group_id: status === 'active' ? get('group') || null : null,
            }),
      }
      if (
        'reported_headcount' in payload &&
        (payload.reported_headcount === null) !==
          (payload.headcount_on === null)
      )
        throw new Error(
          'Enter both the reported headcount and its observation date, or leave both blank.',
        )
      setAttempt(payload)
      try {
        const saved = await saveLivestock(kind, payload, current?.id)
        setAttempt(null)
        onSaved(saved.resource_id)
      } catch (error) {
        if (error instanceof ApiError && error.status === 422) setAttempt(null)
        throw error
      }
    })
  }
  return (
    <form onSubmit={submit}>
      <ErrorNotice error={action.error} />
      <fieldset
        className="calculator-form"
        disabled={action.busy || Boolean(attempt)}
      >
        <legend className="sr-only">Livestock record inputs</legend>
        <div className="calculator-grid">
          {!current && (
            <Field
              name="livestock-species"
              title="Species"
              required
              maxLength={200}
            />
          )}
          {kind === 'animals' && (
            <Field
              name="livestock-identifier"
              title="Animal identifier"
              required
              maxLength={200}
              defaultValue={animal?.identifier}
            />
          )}
          <Field
            name="livestock-name"
            title={kind === 'groups' ? 'Group name' : 'Animal name (optional)'}
            required={kind === 'groups'}
            maxLength={200}
            defaultValue={current?.name ?? ''}
          />
          <Field
            name="livestock-breed"
            title="Breed (optional)"
            maxLength={200}
            defaultValue={current?.breed ?? ''}
          />
          {kind === 'groups' ? (
            <>
              <Field
                name="livestock-count"
                title="Observed headcount (optional, not a registered-animal total)"
                type="number"
                min="0"
                max="1000000"
                step="1"
                defaultValue={group?.reported_headcount ?? ''}
              />
              <Field
                name="livestock-count-date"
                title="Headcount observed on (required with count)"
                type="date"
                max={today}
                defaultValue={group?.headcount_on ?? ''}
              />
              <label className="workspace-check">
                <input
                  type="checkbox"
                  name="livestock-archived"
                  defaultChecked={group?.archived}
                />
                Archive group
              </label>
            </>
          ) : (
            <>
              <label className="calculator-field">
                Recorded sex
                <select
                  name="livestock-sex"
                  defaultValue={animal?.sex ?? 'unknown'}
                >
                  {animalSexes.map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </label>
              <Field
                name="livestock-born"
                title="Born on (optional)"
                type="date"
                max={today}
                defaultValue={animal?.born_on ?? ''}
              />
              <Field
                name="livestock-acquired"
                title="Acquired on (optional)"
                type="date"
                max={today}
                defaultValue={animal?.acquired_on ?? ''}
              />
              <label className="calculator-field">
                Current status
                <select
                  value={status}
                  onChange={(e) =>
                    setStatus(choice(e.target.value, animalStatuses))
                  }
                >
                  {animalStatuses.map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </label>
            </>
          )}
          <Field
            name="livestock-occurred"
            title="This change occurred on"
            type="date"
            required
            max={today}
          />
          <TextArea
            name="livestock-reason"
            title="Reason/source for this change"
            required
            maxLength={2000}
          />
          <TextArea
            name="livestock-notes"
            title="Private notes (optional)"
            maxLength={2000}
            defaultValue={current?.notes ?? ''}
          />
        </div>
        {kind === 'animals' &&
          (status === 'active' ? (
            <LivestockPicker
              mode="group"
              initialGroup={animal?.group_id ?? ''}
            />
          ) : (
            <p>
              Departed and deceased animals are removed from their current
              group.
            </p>
          ))}
      </fieldset>
      <div className="workspace-actions">
        <button className="button-primary" disabled={action.busy}>
          {attempt
            ? 'Retry same livestock change'
            : current
              ? 'Save livestock change'
              : 'Create private livestock record'}
        </button>
      </div>
      {attempt && (
        <p>
          The exact change and request identifier are retained for retry. After
          a timeout or conflict, reload the saved record and history before
          starting another change.
        </p>
      )}
      <p>
        Species is fixed after creation. The backend checks ownership, group
        compatibility and dates. Saved changes are retained in history.
      </p>
    </form>
  )
}
