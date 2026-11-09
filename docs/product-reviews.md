# Buyer product reviews: local MVP

The user chose immediate publication for eligible buyer reviews, with production
moderation policy to be revisited. This backend feature is distinct from private
seller pricing reviews. Frontend contract acceptance and browser checks are pending.

## Eligibility and publication

A general FairMade account may review an exact listing on its own order after
backend-verified completed sandbox capture. The backend checks order/line ownership,
capture ID and verification timestamp; it never accepts client payment claims.
Seller accounts retain buying/reviewing capabilities for other sellers' products.
Seller-reported pickup completion is not required, so a seller cannot gate feedback
by withholding collection status. A review is permitted even if the product is
currently hidden, but anonymous product pages always respect catalog visibility.

At most one review exists per buyer/product, across repeat orders. First publication
freezes private source order/line/listing IDs and historical capture evidence.
Those fields cannot be changed by author edits. Refund requests or later refunds
do not erase a purchase's history or automatically suppress feedback. The badge
explicitly means sandbox_capture_verified_at_submission, not live-market verified
identity, current settlement status, product quality or a fairness verdict.

POST requires explicit publish=true (strict boolean), rating (strict integer1..5)
and trimmed text (1..2000 characters, no null characters). It publishes immediately without seller
approval. Exact same-source/content retry returns the existing record; changed
content or another purchase of the same product returns REVIEW_EXISTS, directing
the buyer to their existing review. Order write serialization and a database
unique buyer/product constraint prevent duplicate races.

Authors can edit or withdraw only their own review, using optimistic revisions.
PUT includes publish=true and expected_revision; it immediately publishes the new
content, including explicit republication after withdrawal. Exact latest-content
retries using the current or immediately preceding revision are idempotent.
Other stale edits return REVISION_CONFLICT. Withdrawal increments revision once
and is retry-safe under the same revision rules. Edits replace current text/rating;
immutable content-edit history and moderator audit are future work. Original
purchase evidence remains immutable. Withdrawn content remains privately readable
by its author and is excluded from public pages/counts/averages.

Sellers have no review approval, selective hiding, edit or withdrawal endpoint.
Their ordinary catalog controls still hide the entire product and associated
review page while a listing/Passport is hidden or seller access is lost. This is
not deletion: re-publication restores all still-published reviews, including low
ratings. Public results are never filtered by seller preference.

## Routes and DTOs

| Method/path | Input | Result |
| --- | --- | --- |
| POST /api/v1/orders/{order_id}/listings/{listing_id}/review | rating, text, publish=true | 201 OwnReview, or 200 exact retry |
| GET /api/v1/account/product-reviews | limit, offset | Page of own reviews |
| GET /api/v1/account/product-reviews/{review_id} | None | OwnReview |
| PUT /api/v1/account/product-reviews/{review_id} | content plus expected_revision | OwnReview |
| POST /api/v1/account/product-reviews/{review_id}/withdraw | expected_revision | 204 |
| GET /api/v1/marketplace/listings/{listing_id}/reviews | limit, offset | Page of PublicReview |
| GET /api/v1/marketplace/listings/{listing_id}/reviews/summary | None | RatingSummary |

Private operations require CurrentAccount, never seller-only permission. Foreign
and missing sources/reviews return identical 404 NOT_FOUND. No session gives 401.
Unverified payment returns 409 PURCHASE_NOT_VERIFIED; duplicate/conflicting create
returns 409 REVIEW_EXISTS; stale edits/withdrawal return 409 REVISION_CONFLICT.
Validation is redacted 422; responses use Cache-Control: no-store.

OwnReview fields: id, order_id, listing_id, revision, state (published/withdrawn),
rating, text, created_at and updated_at UTC. No buyer account ID, internal product
ID, raw order line ID, private seller economics or provider data is returned.
PublicReview fields: id, rating, text, created_at, updated_at, generic
reviewer_label="Verified sandbox buyer", purchase_basis="sandbox_capture_verified_at_submission",
and claims_basis="buyer_reported_unverified". No author identity/alias, email,
order IDs, capture IDs, payment timestamps or refund information is exposed.
Purchase evidence is historical at original submission; later edits do not claim
a newly verified payment. Backend schemas do not turn user review text into facts.

Pages use existing limit1..100/default20 and signed-64-bit offset/default0 bounds.
Sort by created_at descending then UUID descending; editing does not move a review
to the top. Public queries recheck current listing/Passport visibility inside the
data query. Hidden/missing product pages and summaries return 404, preventing a
review endpoint from bypassing catalog withdrawal. RatingSummary returns
review_count, average_rating (string with two decimal places, null if no reviews)
and evidence notices. Sum/count are integers and averaging uses isolated decimal
precision with half-up rounding. These are buyer opinion statistics, never a
quality-weighted value score or an objective fairness rating.

Migration 0018 adds the private review records and indexes without creating
reviews, rewriting public listings or backfilling evidence. Downgrade checks reviews
and earlier protected history before any DDL. Publication does not alter paid order
snapshots, monetary totals, stock or refunds. No paid services are introduced.

## Beyond local MVP

- Decide platform moderation, reporting/takedown/appeal policy, moderator permissions,
  and auditable decisions before production. Sellers must not gain selective
  suppression as a shortcut for platform moderation.
- Add appropriate spam, coordinated-review and account-abuse controls, rate limits
  and monitoring; sandbox purchase verification alone does not establish real buyer
  authenticity. Decide how fraud/reversed verification evidence affects reviews.
- Review sensitive content, personal-data disclosure, retention/deletion, revision
  history and moderation audit. User-authored text can itself contain identifying
  information; a generic system label cannot guarantee anonymity.
- Coordinate frontend consent/preview and safe text rendering, author management,
  evidence labels, accessibility and end-to-end checks. Treat text as untrusted
  plain content, never executable HTML. Do not put bearer tokens or private source
  data in public state, URLs, logs or analytics.
- Decide seller replies, helpfulness voting, review media, aggregate scaling and
  richer product comparisons separately. Ratings must not silently become Quality
  Lock certification or an AI-derived fairness verdict.
