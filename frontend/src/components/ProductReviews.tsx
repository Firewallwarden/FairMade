import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import {
  getPublicReviews,
  getReviewSummary,
  createReview,
  updateReview,
  withdrawReview,
} from '../services/order-care'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import { ErrorNotice } from './Feedback'
import { fieldValue } from '../utils/form'
import type { decodeOwnReview } from '../services/order-care-contract'

export function PublicProductReviews({ listingId }: { listingId: string }) {
  const [offset, setOffset] = useState(0)
  const resource = useResource(
    useCallback(
      async (signal) => {
        const [summary, reviews] = await Promise.all([
          getReviewSummary(listingId, signal),
          getPublicReviews(listingId, offset, signal),
        ])
        return { summary, reviews }
      },
      [listingId, offset],
    ),
  )
  return (
    <section className="workspace-panel">
      <h2>A word from buyers.</h2>
      <p>
        Buyer opinions are unverified claims. The purchase label describes
        historical sandbox capture evidence at submission, not a quality
        certification.
      </p>
      <ErrorNotice error={resource.error} />
      {resource.loading && (
        <p role="status">Loading published buyer feedback…</p>
      )}
      {resource.data && (
        <>
          <p>
            {resource.data.summary.review_count} review(s) ·{' '}
            {resource.data.summary.average_rating === null
              ? 'No average rating yet'
              : `${resource.data.summary.average_rating}/5 average rating`}
            .
          </p>
          {!resource.data.reviews.items.length && (
            <p>No public reviews on this page.</p>
          )}
          {resource.data.reviews.items.map((review) => (
            <article key={review.id} className="message-bubble">
              <p>
                <strong>{review.rating}/5</strong> · {review.reviewer_label} ·{' '}
                {new Date(review.created_at).toLocaleDateString()}
              </p>
              <p>{review.text}</p>
              <small>
                {review.purchase_basis.replaceAll('_', ' ')} ·{' '}
                {review.claims_basis.replaceAll('_', ' ')}
              </small>
            </article>
          ))}
          <ul>
            {resource.data.summary.notices.map((notice, index) => (
              <li key={index}>{notice}</li>
            ))}
          </ul>
          <div className="workspace-actions">
            <button
              className="calculator-secondary"
              disabled={!offset}
              onClick={() => setOffset(offset - 20)}
            >
              Previous reviews
            </button>
            <button
              className="calculator-secondary"
              disabled={resource.data.reviews.items.length < 20}
              onClick={() => setOffset(offset + 20)}
            >
              Next reviews
            </button>
          </div>
        </>
      )}
      <button className="calculator-secondary" onClick={resource.reload}>
        Refresh reviews
      </button>
    </section>
  )
}

function ReviewFields({
  initial,
}: {
  initial?: ReturnType<typeof decodeOwnReview>
}) {
  return (
    <>
      <label className="calculator-field">
        Your rating
        <select
          name="review-rating"
          defaultValue={initial?.rating ?? ''}
          required
        >
          <option value="">Choose a rating</option>
          {[1, 2, 3, 4, 5].map((rating) => (
            <option key={rating} value={rating}>
              {rating}/5
            </option>
          ))}
        </select>
      </label>
      <label className="calculator-field">
        Your review
        <textarea
          name="review-text"
          required
          maxLength={2000}
          rows={4}
          defaultValue={initial?.text ?? ''}
        />
      </label>
      <p>
        Your text will be public under a generic buyer label. Keep private
        information out of it.
      </p>
      <label className="workspace-check">
        <input name="review-publish" type="checkbox" required />I approve
        publishing this review and rating.
      </label>
    </>
  )
}

export function WriteProductReview({
  orderId,
  listingId,
  title,
}: {
  orderId: string
  listingId: string
  title: string
}) {
  const action = useAction()
  const [saved, setSaved] = useState(false)
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    if (!fields.has('review-publish')) return
    void action.run(async () => {
      await createReview(orderId, listingId, {
        rating: Number(fieldValue(fields, 'review-rating')),
        text: fieldValue(fields, 'review-text'),
        publish: true,
      })
      setSaved(true)
    }, 'Your review was published. It is a buyer opinion, not independently verified product evidence.')
  }
  return (
    <details className="workspace-panel">
      <summary>Review your sandbox purchase: {title}</summary>
      <ErrorNotice error={action.error} />
      {saved ? (
        <p role="status">{action.notice}</p>
      ) : (
        <form onSubmit={submit}>
          <fieldset className="calculator-form" disabled={action.busy}>
            <legend className="sr-only">Publish product review</legend>
            <ReviewFields />
            <div className="workspace-actions">
              <button type="submit" className="button-primary">
                Publish approved review
              </button>
            </div>
          </fieldset>
        </form>
      )}
      <a href="#/reviews">Manage your existing reviews</a>
    </details>
  )
}

export function OwnReviewEditor({
  review,
  onChanged,
}: {
  review: ReturnType<typeof decodeOwnReview>
  onChanged: () => void
}) {
  const action = useAction()
  return (
    <article className="workspace-panel">
      <p className="eyebrow">Your review · {review.state}</p>
      <p>
        Listing {review.listing_id.slice(0, 8)} · {review.rating}/5
      </p>
      <ErrorNotice error={action.error} />
      <form
        onSubmit={(event) => {
          event.preventDefault()
          const fields = new FormData(event.currentTarget)
          if (!fields.has('review-publish')) return
          void action.run(async () => {
            await updateReview(review.id, review.revision, {
              rating: Number(fieldValue(fields, 'review-rating')),
              text: fieldValue(fields, 'review-text'),
              publish: true,
            })
            onChanged()
          })
        }}
      >
        <fieldset disabled={action.busy} className="calculator-form">
          <legend className="sr-only">Edit and publish your review</legend>
          <ReviewFields initial={review} />
          <div className="workspace-actions">
            <button type="submit" className="calculator-secondary">
              {review.state === 'withdrawn'
                ? 'Approve & republish review'
                : 'Save approved public changes'}
            </button>
          </div>
        </fieldset>
      </form>
      {review.state === 'published' && (
        <button
          className="calculator-secondary"
          disabled={action.busy}
          onClick={() =>
            action.run(async () => {
              await withdrawReview(review.id, review.revision)
              onChanged()
            })
          }
        >
          Withdraw this public review
        </button>
      )}
      <p>
        Editing republishes immediately with your consent. Withdrawal removes it
        from public results while retaining your private record.
      </p>
    </article>
  )
}
