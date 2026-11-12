import { useCallback, useState } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { PreferenceEditor } from '../components/PreferenceEditor'
import { EvidenceDetails } from '../components/EvidenceDetails'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import { useSession } from '../services/session'
import {
  getBuyerProfile,
  disableBuyerPreferences,
  deleteBuyerPreferences,
  getPersonalizedSuggestions,
} from '../services/preferences'
import { usd } from '../utils/presentation'

export function PreferencesPage() {
  const session = useSession()
  return (
    <WorkspaceLayout
      title="A market that listens to your choices."
      intro="Personalization is optional, private and yours to control."
    >
      {!session ? <SignInPrompt /> : <PreferenceWorkspace />}
    </WorkspaceLayout>
  )
}
function PreferenceWorkspace() {
  const resource = useResource(
    useCallback((signal) => getBuyerProfile(signal), []),
  )
  const action = useAction()
  const [suggestions, setSuggestions] = useState<Awaited<
    ReturnType<typeof getPersonalizedSuggestions>
  > | null>(null)
  function changed() {
    setSuggestions(null)
    resource.reload()
  }
  return (
    <>
      <ErrorNotice error={resource.error || action.error} />
      {resource.loading && (
        <p role="status">Loading your current consent and preferences…</p>
      )}
      {resource.data && (
        <>
          <section className="workspace-panel">
            <p className="workspace-status">{resource.data.status}</p>
            <h2>Your choices, clearly stated.</h2>
            {resource.data.expires_at && (
              <p>
                Preference expiry:{' '}
                {new Date(resource.data.expires_at).toLocaleString()}.
              </p>
            )}
            <ul>
              {resource.data.notices.map((notice, index) => (
                <li key={index}>{notice}</li>
              ))}
            </ul>
            <PreferenceEditor
              key={resource.data.revision}
              revision={resource.data.revision}
              initial={resource.data.preferences}
              onSaved={changed}
            />
            <p>
              You can hide a product from suggestions on its product page once
              personalization is enabled.
            </p>
          </section>
          {resource.data.enabled && (
            <section className="workspace-panel">
              <h2>A few goods you might like.</h2>
              <p>
                Uses the saved choices above. Suggestions do not reserve stock
                or make a purchase.
              </p>
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  const unknown = new FormData(event.currentTarget).has(
                    'suggest-unknown',
                  )
                  void action.run(async () => {
                    setSuggestions(null)
                    setSuggestions(await getPersonalizedSuggestions(unknown))
                  })
                }}
              >
                <label className="workspace-check">
                  <input
                    type="checkbox"
                    name="suggest-unknown"
                    disabled={action.busy}
                  />
                  Also include listings with unknown availability.
                </label>
                <div className="workspace-actions">
                  <button className="button-primary" disabled={action.busy}>
                    Find matches with my saved choices
                  </button>
                </div>
              </form>
              {suggestions && (
                <>
                  <p>
                    {suggestions.personalized
                      ? 'Personalized using your active choice'
                      : 'Personalization was not active when this report was built'}
                    .
                  </p>
                  <details>
                    <summary>Effective preferences for these results</summary>
                    <EvidenceDetails value={suggestions.preferences} />
                  </details>
                  {!suggestions.items.length && (
                    <p>
                      No matching products. Broaden your saved choices or
                      explore the market.
                    </p>
                  )}
                  <div className="workspace-grid">
                    {suggestions.items.map((item) => (
                      <article
                        className="workspace-panel"
                        key={item.listing.id}
                      >
                        <h3>{item.listing.payload.product.title}</h3>
                        <p>
                          {usd(item.listing.payload.price.amount)} /{' '}
                          {item.listing.payload.product.selling_unit}
                        </p>
                        <ul>
                          {item.reasons.map((reason, index) => (
                            <li key={index}>{reason.replaceAll('_', ' ')}</li>
                          ))}
                        </ul>
                        <a href={`#/market/${item.listing.id}`}>
                          View product & Passport
                        </a>
                      </article>
                    ))}
                  </div>
                  <ul>
                    {suggestions.notices.map((notice, index) => (
                      <li key={index}>{notice}</li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          )}
          <section className="workspace-panel">
            <h2>Change your mind at any time.</h2>
            <p>
              Disabling or deleting clears these preferences and removes saved
              personalized answers as the backend specifies. Favorites, orders
              and other conversation records keep their own histories. A minimal
              revision record prevents stale tabs restoring a deleted profile.
            </p>
            <div className="workspace-actions">
              <button
                className="calculator-secondary"
                disabled={action.busy || !resource.data.enabled}
                onClick={() => {
                  const revision = resource.data?.revision
                  if (revision !== undefined)
                    void action.run(async () => {
                      await disableBuyerPreferences(revision)
                      changed()
                    })
                }}
              >
                Disable personalization & clear preferences
              </button>
            </div>
            <details>
              <summary>Delete saved preference memory</summary>
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  const revision = resource.data?.revision
                  if (
                    revision !== undefined &&
                    new FormData(event.currentTarget).has('delete-preferences')
                  )
                    void action.run(async () => {
                      await deleteBuyerPreferences(revision)
                      changed()
                    })
                }}
              >
                <label className="workspace-check">
                  <input
                    type="checkbox"
                    name="delete-preferences"
                    required
                    disabled={action.busy}
                  />
                  Delete this preference memory and disable personalization.
                </label>
                <button className="calculator-secondary" disabled={action.busy}>
                  Delete preference memory
                </button>
              </form>
            </details>
          </section>
        </>
      )}
      <button
        className="calculator-secondary"
        disabled={action.busy}
        onClick={changed}
      >
        Reload consent and saved preferences
      </button>
    </>
  )
}
