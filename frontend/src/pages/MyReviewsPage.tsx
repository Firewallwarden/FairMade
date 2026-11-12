import { useCallback, useState } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { OwnReviewEditor } from '../components/ProductReviews'
import { useSession } from '../services/session'
import { useResource } from '../hooks/useResource'
import { getOwnReviews } from '../services/order-care'

export function MyReviewsPage() {
  const session = useSession()
  return (
    <WorkspaceLayout
      title="Your words, your choice."
      intro="Edit or withdraw your own public product feedback."
    >
      {!session ? <SignInPrompt /> : <Reviews />}
    </WorkspaceLayout>
  )
}
function Reviews() {
  const [offset, setOffset] = useState(0)
  const resource = useResource(
    useCallback((signal) => getOwnReviews(offset, signal), [offset]),
  )
  return (
    <>
      <ErrorNotice error={resource.error} />
      {resource.loading && <p role="status">Loading your reviews…</p>}
      {resource.data && (
        <>
          {!resource.data.items.length && (
            <p>
              No reviews on this page. Review an eligible purchase from its
              order page.
            </p>
          )}
          {resource.data.items.map((review) => (
            <OwnReviewEditor
              key={`${review.id}-${review.revision}`}
              review={review}
              onChanged={resource.reload}
            />
          ))}
          <div className="workspace-actions">
            <button
              className="calculator-secondary"
              disabled={!offset}
              onClick={() => setOffset(offset - 20)}
            >
              Previous
            </button>
            <button
              className="calculator-secondary"
              disabled={resource.data.items.length < 20}
              onClick={() => setOffset(offset + 20)}
            >
              Next
            </button>
          </div>
        </>
      )}
      <button className="calculator-secondary" onClick={resource.reload}>
        Refresh your reviews
      </button>
    </>
  )
}
