import { useState } from 'react'
import { Field } from './FormFields'
export function OptionalPreferences({
  prefix,
  onEdit,
}: {
  prefix: string
  onEdit?: () => void
}) {
  const [rows, setRows] = useState<
    { id: string; type: 'boolean' | 'choice' | 'numeric' }[]
  >([])
  function move(index: number, delta: number) {
    const next = [...rows]
    ;[next[index], next[index + delta]] = [next[index + delta], next[index]]
    setRows(next)
    onEdit?.()
  }
  return (
    <details>
      <summary>
        Optional review preferences (never replace Quality Lock)
      </summary>
      <p>
        Use attribute keys from the saved quote claims. Preferences are ordered
        from most to least important in quality mode. Unknown claims stay
        unknown; no independent quality grade is inferred. Mandatory exclusions
        still apply.
      </p>
      {rows.map((row, index) => (
        <section className="workspace-panel" key={row.id}>
          <h4>Preference {index + 1}</h4>
          <input type="hidden" name={`${prefix}-row`} value={row.id} />
          <div className="calculator-grid">
            <Field
              name={`${prefix}-key-${row.id}`}
              title="Claim attribute key"
              required
              maxLength={64}
              pattern="[a-z][a-z0-9_]{0,63}"
            />
            <Field
              name={`${prefix}-label-${row.id}`}
              title="Preference label"
              required
              maxLength={200}
            />
            <label className="calculator-field">
              Preference type
              <select
                name={`${prefix}-type-${row.id}`}
                value={row.type}
                onChange={(event) => {
                  const type = event.target.value
                  if (
                    type === 'boolean' ||
                    type === 'choice' ||
                    type === 'numeric'
                  )
                    setRows(
                      rows.map((item) =>
                        item.id === row.id ? { ...item, type } : item,
                      ),
                    )
                }}
              >
                <option value="boolean">Yes / no</option>
                <option value="choice">Text choices</option>
                <option value="numeric">Numeric range</option>
              </select>
            </label>
            {row.type === 'boolean' && (
              <label className="calculator-field">
                Preferred reported value
                <select name={`${prefix}-expected-${row.id}`}>
                  <option value="true">Yes / true</option>
                  <option value="false">No / false</option>
                </select>
              </label>
            )}
            {row.type === 'choice' && (
              <Field
                name={`${prefix}-choices-${row.id}`}
                title="Acceptable values, comma separated"
                required
                maxLength={20000}
              />
            )}
            {row.type === 'numeric' && (
              <>
                <Field
                  name={`${prefix}-minimum-${row.id}`}
                  title="Optional minimum"
                  type="number"
                  min="-1000000000"
                  max="1000000000"
                  step="0.000001"
                />
                <Field
                  name={`${prefix}-maximum-${row.id}`}
                  title="Optional maximum"
                  type="number"
                  min="-1000000000"
                  max="1000000000"
                  step="0.000001"
                />
                <Field
                  name={`${prefix}-unit-${row.id}`}
                  title="Reported quantity unit"
                  required
                  maxLength={200}
                />
              </>
            )}
          </div>
          <div className="workspace-actions">
            <button
              type="button"
              className="calculator-secondary"
              disabled={index === 0}
              onClick={() => move(index, -1)}
            >
              Move preference up
            </button>
            <button
              type="button"
              className="calculator-secondary"
              disabled={index === rows.length - 1}
              onClick={() => move(index, 1)}
            >
              Move preference down
            </button>
            <button
              className="calculator-remove"
              type="button"
              onClick={() => {
                setRows(rows.filter((item) => item.id !== row.id))
                onEdit?.()
              }}
            >
              Remove preference {index + 1}
            </button>
          </div>
        </section>
      ))}
      <button
        type="button"
        className="calculator-secondary"
        disabled={rows.length >= 8}
        onClick={() => {
          setRows([...rows, { id: crypto.randomUUID(), type: 'boolean' }])
          onEdit?.()
        }}
      >
        Add optional preference
      </button>
    </details>
  )
}
export function AdditionalQuoteClaims() {
  const [rows, setRows] = useState<
    { id: string; type: 'boolean' | 'choice' | 'numeric' }[]
  >([])
  return (
    <details>
      <summary>
        Additional supplier-reported attributes for optional preferences
      </summary>
      <p>
        Add only claims supported by the quote/source you recorded. These do not
        change mandatory rules or establish verification. Omit an attribute when
        unknown.
      </p>
      {rows.map((row, index) => (
        <section className="workspace-panel" key={row.id}>
          <input type="hidden" name="quote-extra-row" value={row.id} />
          <div className="calculator-grid">
            <Field
              name={`quote-extra-key-${row.id}`}
              title="Additional attribute key"
              required
              maxLength={64}
              pattern="[a-z][a-z0-9_]{0,63}"
            />
            <label className="calculator-field">
              Claim type
              <select
                name={`quote-extra-type-${row.id}`}
                value={row.type}
                onChange={(event) => {
                  const type = event.target.value
                  if (
                    type === 'boolean' ||
                    type === 'choice' ||
                    type === 'numeric'
                  )
                    setRows(
                      rows.map((item) =>
                        item.id === row.id ? { ...item, type } : item,
                      ),
                    )
                }}
              >
                <option value="boolean">Yes / no</option>
                <option value="choice">Text</option>
                <option value="numeric">Numeric</option>
              </select>
            </label>
            {row.type === 'boolean' ? (
              <label className="calculator-field">
                Reported value
                <select name={`quote-extra-value-${row.id}`} required>
                  <option value="">Choose reported value</option>
                  <option value="true">Yes / true</option>
                  <option value="false">No / false</option>
                </select>
              </label>
            ) : (
              <Field
                name={`quote-extra-value-${row.id}`}
                title="Reported value"
                required
                maxLength={200}
                type={row.type === 'numeric' ? 'number' : 'text'}
                step={row.type === 'numeric' ? '0.000001' : undefined}
                min={row.type === 'numeric' ? '-1000000000' : undefined}
                max={row.type === 'numeric' ? '1000000000' : undefined}
              />
            )}
            {row.type === 'numeric' && (
              <Field
                name={`quote-extra-unit-${row.id}`}
                title="Reported unit"
                required
                maxLength={200}
              />
            )}
          </div>
          <button
            type="button"
            className="calculator-remove"
            onClick={() => setRows(rows.filter((item) => item.id !== row.id))}
          >
            Remove additional claim {index + 1}
          </button>
        </section>
      ))}
      <button
        className="calculator-secondary"
        type="button"
        disabled={rows.length >= 8}
        onClick={() =>
          setRows([...rows, { id: crypto.randomUUID(), type: 'boolean' }])
        }
      >
        Add reported attribute
      </button>
    </details>
  )
}
