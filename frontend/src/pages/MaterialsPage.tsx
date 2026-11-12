import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { Field, TextArea } from '../components/FormFields'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { EvidenceDetails } from '../components/EvidenceDetails'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import { useSession } from '../services/session'
import {
  createMaterial,
  editMaterial,
  getMaterials,
  getMaterial,
  getMaterialMovements,
  createMaterialMovement,
} from '../services/materials'
import { materialUnits, movementKinds } from '../services/material-contract'
import type { MaterialMovementInput } from '../services/material-contract'
import { choice } from '../services/decode'
import { ApiError } from '../services/http'
import { fieldValue } from '../utils/form'

export function MaterialsPage({ id }: { id?: string }) {
  const session = useSession()
  return (
    <WorkspaceLayout
      title="Keep track of what goes into your work."
      intro="A private, manually reported quantity ledger. Material records do not automatically change recipes, prices, public claims or sellable stock."
    >
      {!session ? (
        <SignInPrompt />
      ) : !session.account.roles.includes('seller') ? (
        <p>Seller access is required.</p>
      ) : id ? (
        <MaterialWorkspace id={id} />
      ) : (
        <MaterialList />
      )}
    </WorkspaceLayout>
  )
}
function MaterialList() {
  const [offset, setOffset] = useState(0),
    resource = useResource(
      useCallback((signal) => getMaterials(offset, signal), [offset]),
    ),
    action = useAction()
  return (
    <>
      <a href="#/seller">← Seller workspace</a>
      <section className="workspace-panel">
        <h2>A place for every input.</h2>
        <ErrorNotice error={action.error} />
        <form
          onSubmit={(event) => {
            event.preventDefault()
            const fields = new FormData(event.currentTarget)
            void action.run(async () => {
              const saved = await createMaterial({
                name: fieldValue(fields, 'material-name'),
                notes: fieldValue(fields, 'material-notes') || null,
                unit: choice(
                  fieldValue(fields, 'material-unit'),
                  materialUnits,
                ),
              })
              window.location.hash = `/materials/${saved.id}`
            })
          }}
        >
          <fieldset className="calculator-form" disabled={action.busy}>
            <legend className="sr-only">Create material</legend>
            <div className="calculator-grid">
              <Field
                name="material-name"
                title="Private material name"
                required
                maxLength={200}
              />
              <label className="calculator-field">
                Canonical quantity unit
                <select name="material-unit">
                  <option value="g">g — mass (accepts g/kg movements)</option>
                  <option value="ml">
                    ml — volume (accepts ml/l movements)
                  </option>
                  <option value="item">item — whole counted units</option>
                </select>
              </label>
              <TextArea
                name="material-notes"
                title="Private notes (optional)"
                maxLength={2000}
              />
            </div>
            <p>
              Starts at a recorded count of zero. Add a receipt or a physical
              count to report actual quantities. The canonical unit cannot be
              edited later.
            </p>
            <div className="workspace-actions">
              <button className="button-primary">
                Create private material
              </button>
            </div>
          </fieldset>
        </form>
      </section>
      <ErrorNotice error={resource.error} />
      {resource.loading && <p role="status">Loading material records…</p>}
      {resource.data && (
        <>
          {!resource.data.items.length && <p>No materials on this page.</p>}
          <div className="workspace-grid">
            {resource.data.items.map((item) => (
              <article className="workspace-panel" key={item.id}>
                <h2>{item.name}</h2>
                <p>
                  <strong>
                    {item.on_hand} {item.unit}
                  </strong>{' '}
                  reported on hand
                </p>
                <a href={`#/materials/${item.id}`}>View quantity ledger</a>
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
          Previous materials
        </button>
        <button
          className="calculator-secondary"
          disabled={(resource.data?.items.length ?? 0) < 20}
          onClick={() => setOffset(offset + 20)}
        >
          Next materials
        </button>
        <button className="calculator-secondary" onClick={resource.reload}>
          Reload material list
        </button>
      </div>
    </>
  )
}
function MaterialWorkspace({ id }: { id: string }) {
  const [offset, setOffset] = useState(0),
    resource = useResource(
      useCallback(
        async (signal) => {
          const [material, movements] = await Promise.all([
            getMaterial(id, signal),
            getMaterialMovements(id, offset, signal),
          ])
          return { material, movements }
        },
        [id, offset],
      ),
    )
  return (
    <>
      <a href="#/materials">← Private materials</a>
      <ErrorNotice error={resource.error} />
      {resource.loading && (
        <p role="status">Loading current material and ledger…</p>
      )}
      {resource.data && (
        <>
          <section className="workspace-panel">
            <p className="eyebrow">Seller-reported · Unverified</p>
            <h2>{resource.data.material.name}</h2>
            <p className="listing-price">
              {resource.data.material.on_hand}{' '}
              <span>{resource.data.material.unit} recorded on hand</span>
            </p>
            <p className="private-instructions">
              {resource.data.material.notes}
            </p>
            <MaterialMetadata
              key={resource.data.material.revision}
              material={resource.data.material}
              onChanged={resource.reload}
            />
          </section>
          <MovementForm
            key={resource.data.material.revision}
            material={resource.data.material}
            onChanged={resource.reload}
          />
          <section className="workspace-panel">
            <h2>The quantity history</h2>
            {!resource.data.movements.items.length && (
              <p>No movements on this page.</p>
            )}
            {resource.data.movements.items.map((event) => (
              <details key={event.id}>
                <summary>
                  {event.kind === 'adjustment'
                    ? 'Physical count adjustment'
                    : event.kind}{' '}
                  · {new Date(event.created_at).toLocaleString()}
                </summary>
                <p>
                  Recorded name: {event.material_name}. Before {event.before}{' '}
                  {event.unit}; after {event.after} {event.unit}; change{' '}
                  {event.delta} {event.unit}.
                </p>
                <EvidenceDetails value={event.request} />
              </details>
            ))}
          </section>
        </>
      )}
      <div className="workspace-actions">
        <button
          className="calculator-secondary"
          disabled={!offset}
          onClick={() => setOffset(offset - 20)}
        >
          Earlier ledger page
        </button>
        <button
          className="calculator-secondary"
          disabled={(resource.data?.movements.items.length ?? 0) < 20}
          onClick={() => setOffset(offset + 20)}
        >
          Later ledger page
        </button>
        <button className="calculator-secondary" onClick={resource.reload}>
          Reload current count and ledger
        </button>
      </div>
    </>
  )
}
function MaterialMetadata({
  material,
  onChanged,
}: {
  material: Awaited<ReturnType<typeof getMaterial>>
  onChanged: () => void
}) {
  const action = useAction()
  return (
    <details>
      <summary>Edit material name/notes</summary>
      <ErrorNotice error={action.error} />
      <form
        onSubmit={(event) => {
          event.preventDefault()
          const fields = new FormData(event.currentTarget)
          void action.run(async () => {
            await editMaterial(
              material.id,
              material.revision,
              fieldValue(fields, 'material-edit-name'),
              fieldValue(fields, 'material-edit-notes') || null,
            )
            onChanged()
          })
        }}
      >
        <fieldset className="calculator-form" disabled={action.busy}>
          <legend className="sr-only">Edit material metadata</legend>
          <Field
            name="material-edit-name"
            title="Private material name"
            required
            maxLength={200}
            defaultValue={material.name}
          />
          <TextArea
            name="material-edit-notes"
            title="Private notes"
            maxLength={2000}
            defaultValue={material.notes ?? ''}
          />
          <button className="calculator-secondary">
            Save material metadata
          </button>
        </fieldset>
      </form>
    </details>
  )
}
function MovementForm({
  material,
  onChanged,
}: {
  material: Awaited<ReturnType<typeof getMaterial>>
  onChanged: () => void
}) {
  const action = useAction(),
    [kind, setKind] = useState<(typeof movementKinds)[number]>('receipt'),
    [attempt, setAttempt] = useState<MaterialMovementInput | null>(null),
    [today] = useState(() => new Date().toISOString().slice(0, 10))
  const units =
    material.unit === 'g'
      ? (['g', 'kg'] as const)
      : material.unit === 'ml'
        ? (['ml', 'l'] as const)
        : (['item'] as const)
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    void action.run(async () => {
      const request: MaterialMovementInput = attempt ?? {
        request_id: crypto.randomUUID(),
        expected_revision: material.revision,
        kind,
        quantity: fieldValue(fields, 'movement-quantity'),
        unit: choice(fieldValue(fields, 'movement-unit'), [
          'g',
          'kg',
          'ml',
          'l',
          'item',
        ] as const),
        occurred_on: fieldValue(fields, 'movement-date'),
        reason: fieldValue(fields, 'movement-reason'),
      }
      setAttempt(request)
      try {
        await createMaterialMovement(material.id, request)
        setAttempt(null)
        onChanged()
      } catch (error) {
        if (error instanceof ApiError && error.status === 422) setAttempt(null)
        throw error
      }
    })
  }
  return (
    <section className="workspace-panel">
      <h2>Record a quantity change.</h2>
      <ErrorNotice error={action.error} />
      <form onSubmit={save}>
        <fieldset
          className="calculator-form"
          disabled={action.busy || Boolean(attempt)}
        >
          <legend className="sr-only">Material movement</legend>
          <div className="calculator-grid">
            <label className="calculator-field">
              Movement type
              <select
                value={kind}
                onChange={(event) =>
                  setKind(choice(event.target.value, movementKinds))
                }
              >
                <option value="receipt">Receipt — add received quantity</option>
                <option value="usage">Usage — subtract used quantity</option>
                <option value="waste">Waste — subtract wasted quantity</option>
                <option value="adjustment">
                  Physical count — replace the recorded balance
                </option>
              </select>
            </label>
            <Field
              name="movement-quantity"
              title={
                kind === 'adjustment'
                  ? 'New physical count (not an amount to add)'
                  : 'Positive quantity received, used or wasted'
              }
              type="number"
              min={
                kind === 'adjustment'
                  ? '0'
                  : material.unit === 'item'
                    ? '1'
                    : '0.000001'
              }
              max="1000000000"
              step={material.unit === 'item' ? '1' : '0.000001'}
              required
            />
            <label className="calculator-field">
              Input quantity unit
              <select name="movement-unit">
                {units.map((unit) => (
                  <option key={unit}>{unit}</option>
                ))}
              </select>
            </label>
            <Field
              name="movement-date"
              title="Occurred on"
              type="date"
              max={today}
              required
            />
            <TextArea
              name="movement-reason"
              title="Reason/source for this report"
              required
              maxLength={2000}
            />
          </div>
          {kind === 'adjustment' && (
            <p className="calculator-notice">
              This sets the entire recorded balance to the physical count you
              enter. It does not add that count to the old balance.
            </p>
          )}
        </fieldset>
        <div className="workspace-actions">
          <button className="button-primary" disabled={action.busy}>
            {attempt ? 'Retry same movement' : 'Record material movement'}
          </button>
        </div>
      </form>
      <p>
        Backend conversion and stock checks are authoritative. Negative stock is
        rejected. After an uncertain result, inspect the ledger; retries on this
        page retain the same request identifier.
      </p>
    </section>
  )
}
