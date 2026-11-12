import { useCallback, useState } from 'react'
import { useResource } from '../hooks/useResource'
import { ErrorNotice } from './Feedback'
import { getAnimals, getGroups } from '../services/livestock'
import type { Animal, Group } from '../services/livestock-contract'

/** Optional selectors share revision snapshots; the server validates current ownership and eligibility. */
export function LivestockPicker({
  mode = 'source',
  initialGroup = '',
}: {
  mode?: 'source' | 'group'
  initialGroup?: string
}) {
  const [kind, setKind] = useState<'group' | 'animal'>('group')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState(initialGroup)
  const [retained, setRetained] = useState<Group | Animal | null>(null)
  const resource = useResource(
    useCallback(
      async (signal) => {
        const data =
          kind === 'group'
            ? await getGroups(offset, signal, true)
            : await getAnimals(offset, signal, true)
        return { ...data, items: data.items as (Group | Animal)[] }
      },
      [kind, offset],
    ),
  )
  const rows = resource.data?.items ?? []
  const options =
    retained && !rows.some((row) => row.id === retained.id)
      ? [retained, ...rows]
      : rows
  const current = options.find((row) => row.id === selected)
  return (
    <div className="workspace-panel">
      <h3>
        {mode === 'source'
          ? 'Attribute this production (optional)'
          : 'Current group (optional)'}
      </h3>
      <p>
        Select an active, privately recorded source. This does not change animal
        counts, health claims or stock.
      </p>
      <ErrorNotice error={resource.error} />
      {mode === 'source' && (
        <label className="calculator-field">
          Source type
          <select
            value={kind}
            onChange={(e) => {
              setKind(e.target.value as 'group' | 'animal')
              setSelected('')
              setRetained(null)
              setOffset(0)
            }}
          >
            <option value="group">Group</option>
            <option value="animal">Individual animal</option>
          </select>
        </label>
      )}
      <label className="calculator-field">
        {kind === 'group' ? 'Livestock group' : 'Individual animal'}
        <select
          name={mode === 'source' ? 'livestock-source' : 'livestock-group'}
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value)
            setRetained(
              options.find((row) => row.id === e.target.value) ?? null,
            )
          }}
        >
          <option value="">No selection</option>
          {initialGroup && !options.some((row) => row.id === initialGroup) && (
            <option value={initialGroup}>
              Current recorded group — keep unchanged
            </option>
          )}
          {options.map((row) => (
            <option key={row.id} value={row.id}>
              {'identifier' in row ? row.identifier : row.name} · {row.species}{' '}
              · revision {row.revision}
            </option>
          ))}
        </select>
      </label>
      {mode === 'source' && (
        <>
          <input type="hidden" name="livestock-kind" value={kind} />
          <input
            type="hidden"
            name="livestock-revision"
            value={current?.revision ?? ''}
          />
        </>
      )}
      {resource.loading && <p role="status">Loading sources…</p>}
      <div className="workspace-actions">
        <button
          type="button"
          className="calculator-secondary"
          disabled={!offset}
          onClick={() => setOffset(offset - 20)}
        >
          Previous sources
        </button>
        <button
          type="button"
          className="calculator-secondary"
          disabled={rows.length < 20}
          onClick={() => setOffset(offset + 20)}
        >
          Next sources
        </button>
        <button
          type="button"
          className="calculator-secondary"
          onClick={resource.reload}
        >
          Reload sources
        </button>
      </div>
    </div>
  )
}
