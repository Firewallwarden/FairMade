import { useState } from 'react'
import { Field } from '../../components/FormFields'
import {
  compositionKinds,
  compositionUnits,
} from '../../services/composition-contract'
export function CompositionFields({ onEdit }: { onEdit: () => void }) {
  const [include, setInclude] = useState(false)
  const [rows, setRows] = useState(() => [crypto.randomUUID()])
  return (
    <details>
      <summary>
        Declare finished-product ingredients or materials (optional)
      </summary>
      <p>
        Author this disclosure separately. Private recipe inputs are not copied
        or inferred. Describe only the finished product and its packaging; do
        not treat production feed, waste or processing inputs as finished
        contents.
      </p>
      <label className="workspace-check">
        <input
          name="include_composition"
          type="checkbox"
          checked={include}
          onChange={(event) => setInclude(event.target.checked)}
        />
        Include this separate composition declaration in the public preview.
      </label>
      {include && (
        <>
          <label className="calculator-field">
            Completeness
            <select name="composition-completeness">
              <option value="partial">Partial declaration</option>
              <option value="seller_declared_complete">
                I declare this list complete (unverified)
              </option>
            </select>
          </label>
          {rows.map((key, index) => (
            <section className="workspace-panel" key={key}>
              <h4>Component {index + 1}</h4>
              <input name="composition-row" type="hidden" value={key} />
              <div className="calculator-grid">
                <Field
                  name={`composition-label-${key}`}
                  title="Public ingredient/material label"
                  required
                  maxLength={200}
                />
                <label className="calculator-field">
                  Component type
                  <select name={`composition-kind-${key}`}>
                    {compositionKinds.map((kind) => (
                      <option key={kind}>{kind}</option>
                    ))}
                  </select>
                </label>
                <Field
                  name={`composition-role-${key}`}
                  title="Reported role (optional)"
                  maxLength={200}
                />
                <Field
                  name={`composition-spec-${key}`}
                  title="Reported specification (optional, unverified)"
                  maxLength={200}
                />
                <Field
                  name={`composition-quantity-${key}`}
                  title="Declared amount (optional)"
                  type="number"
                  min="0.000001"
                  max="1000000000"
                  step="0.000001"
                />
                <label className="calculator-field">
                  Amount unit
                  <select name={`composition-unit-${key}`}>
                    <option value="">No quantity declaration</option>
                    {compositionUnits.map((unit) => (
                      <option key={unit}>{unit}</option>
                    ))}
                  </select>
                </label>
              </div>
              <button
                type="button"
                className="calculator-remove"
                disabled={rows.length <= 1}
                onClick={() => {
                  setRows(rows.filter((row) => row !== key))
                  onEdit()
                }}
              >
                Remove component {index + 1}
              </button>
            </section>
          ))}
          <button
            className="calculator-secondary"
            type="button"
            disabled={rows.length >= 20}
            onClick={() => {
              setRows([...rows, crypto.randomUUID()])
              onEdit()
            }}
          >
            Add component
          </button>
          <p>
            Completeness and specifications are seller statements, not
            verification. Omitted ingredients do not establish allergen absence,
            safety, nutritional value or suitability.
          </p>
        </>
      )}
    </details>
  )
}
