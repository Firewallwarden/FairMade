import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { Field } from './FormFields'
import { ErrorNotice } from './Feedback'
import { useAction } from '../hooks/useAction'
import { useResource } from '../hooks/useResource'
import { getCatalogListing } from '../services/commerce'
import { saveBuyerPreferences } from '../services/preferences'
import type { BuyerPreferences } from '../services/preferences-contract'
import { fieldValue } from '../utils/form'
import { choice } from '../services/decode'

export function PreferenceEditor({
  revision,
  initial,
  onSaved,
}: {
  revision: number
  initial: BuyerPreferences
  onSaved: () => void
}) {
  const action = useAction()
  const [confirmed, setConfirmed] = useState(false)
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!confirmed) return
    const fields = new FormData(event.currentTarget)
    void action.run(async () => {
      await saveBuyerPreferences(revision, {
        budget_per_item: fieldValue(fields, 'preference-budget') || null,
        location: fieldValue(fields, 'preference-location') || null,
        product_types: fields
          .getAll('preference-type')
          .map((value) =>
            choice(value, ['sourdough', 'eggs', 'other'] as const),
          ),
        excluded_listing_ids: fields.getAll('preference-exclusion').map(String),
      })
      onSaved()
    })
  }
  return (
    <form onSubmit={save}>
      <ErrorNotice error={action.error} />
      <fieldset className="calculator-form" disabled={action.busy}>
        <legend className="sr-only">Review buyer preferences</legend>
        <div onChange={() => setConfirmed(false)}>
          <div className="calculator-grid">
            <Field
              name="preference-budget"
              title="Budget per listed selling unit (USD, optional)"
              type="number"
              min="0"
              max="1000000000"
              step="0.01"
              defaultValue={initial.budget_per_item ?? ''}
            />
            <Field
              name="preference-location"
              title="Exact seller location label (optional)"
              maxLength={200}
              defaultValue={initial.location ?? ''}
              placeholder="e.g. Exampletown (demo)"
            />
          </div>
          <h3>Your product interests</h3>
          <p>No types selected means all product types.</p>
          {(['sourdough', 'eggs', 'other'] as const).map((type) => (
            <label className="workspace-check" key={type}>
              <input
                type="checkbox"
                name="preference-type"
                value={type}
                defaultChecked={initial.product_types.includes(type)}
              />
              {type === 'sourdough'
                ? 'Sourdough bread'
                : type === 'eggs'
                  ? 'Eggs'
                  : 'Other local goods'}
            </label>
          ))}
          {initial.excluded_listing_ids.length > 0 && (
            <>
              <h3>Products hidden from suggestions</h3>
              <p>Uncheck a product to remove that exclusion when you save.</p>
              {initial.excluded_listing_ids.map((id) => (
                <ExcludedListing key={id} id={id} />
              ))}
            </>
          )}
        </div>
        <p>
          Enabling personalization uses these saved preferences, favorites and
          recent verified sandbox purchases. This does not establish quality,
          fairness or equivalence. Your saved choice expires on the backend’s
          schedule.
        </p>
        <label className="workspace-check">
          <input
            name="confirm-preferences"
            type="checkbox"
            required
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
          />
          I choose to enable personalization and save exactly these reviewed
          preferences.
        </label>
        <div className="workspace-actions">
          <button className="button-primary" disabled={!confirmed}>
            Save reviewed preferences
          </button>
        </div>
      </fieldset>
    </form>
  )
}
function ExcludedListing({ id }: { id: string }) {
  const resource = useResource(
    useCallback((signal) => getCatalogListing(id, signal), [id]),
  )
  return (
    <label className="workspace-check">
      <input
        type="checkbox"
        name="preference-exclusion"
        value={id}
        defaultChecked
      />
      {resource.data?.payload.product.title ??
        'Previously excluded product (public details unavailable)'}
    </label>
  )
}
