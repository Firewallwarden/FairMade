import { useCallback } from 'react'
import { useSession } from '../services/session'
import { getBuyerProfile, saveBuyerPreferences } from '../services/preferences'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import { ErrorNotice } from './Feedback'

export function HideFromSuggestions({ listingId }: { listingId: string }) {
  const session = useSession()
  return session ? (
    <ExclusionControl key={session.account.id} listingId={listingId} />
  ) : null
}
function ExclusionControl({ listingId }: { listingId: string }) {
  const resource = useResource(
    useCallback((signal) => getBuyerProfile(signal), []),
  )
  const action = useAction()
  const profile = resource.data
  if (!profile?.enabled) return null
  const excluded = profile.preferences.excluded_listing_ids.includes(listingId)
  return (
    <div>
      <ErrorNotice error={action.error} />
      {excluded ? (
        <p>
          Hidden from your personalized suggestions.{' '}
          <a href="#/preferences">Manage preferences</a>
        </p>
      ) : (
        <button
          className="calculator-secondary"
          disabled={
            action.busy || profile.preferences.excluded_listing_ids.length >= 20
          }
          onClick={() =>
            action.run(async () => {
              await saveBuyerPreferences(profile.revision, {
                ...profile.preferences,
                excluded_listing_ids: [
                  ...profile.preferences.excluded_listing_ids,
                  listingId,
                ],
              })
              resource.reload()
            })
          }
        >
          Hide this product from my suggestions
        </button>
      )}
      {profile.preferences.excluded_listing_ids.length >= 20 && !excluded && (
        <p>
          Twenty exclusions are saved. Manage your preferences to remove one
          first.
        </p>
      )}
    </div>
  )
}
