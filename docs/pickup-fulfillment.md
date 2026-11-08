# Local pickup fulfillment

Backend implemented for local development; frontend contract acceptance and
browser integration remain pending. The user approved pickup-only MVP after
PRs #25-#27 were integrated. Mode is local_pickup, separate from payment state,
stock balances, public approximate locations and refund decisions.

## Current behavior

- Only the order's authenticated buyer and its currently authorized seller can
  read progress, instructions and history. Other accounts receive the same 404
  as a missing order. Seller writes require current verified seller access.
- An order with no reports returns revision 0, state not_started, null instructions
  and no latest event. This is derived on read; migrations do not infer progress
  for existing paid orders or create events automatically.
- Seller progression is preparing → ready_for_pickup → collected. States cannot
  be skipped or reversed; collected is terminal. Instructions may change while
  preparing/ready, with a new immutable revision. Ready/collected require nonempty
  instructions. Instructions can contain a seller-chosen private pickup location;
  they are never copied into catalog, storefront, pricing or order snapshots.
- Writes require a completed backend payment record with capture ID and verification
  timestamp. Client claims and payment-button clicks cannot grant fulfillment access.
  Requested refunds, approved refunds (including failed/retryable execution), refund
  review and completed refunds block further updates. A denied refund permits
  progression again. Refund processing never rewinds historical physical reports.
- One database transaction locks the owned order, checks payment/refund state,
  validates the revision/transition, and appends a report with server time and
  authenticated recorder ID. Existing refund operations share this order write
  serialization. No stock, price, payment or refund mutations occur here.
- Exact retries of the latest content with its current or immediately preceding
  revision return the existing response without another event. Other stale
  revisions conflict. Retry handling cannot bypass payment/refund gates.
- Responses explicitly say seller_reported_unverified. Collected is a seller's
  report, not buyer-confirmed handoff or a dispute-resolution finding. Old events
  remain unchanged when instructions are corrected. There is no delete/edit-history
  API. Already disclosed instructions cannot be recalled from their recipient.

## Endpoints and wire format

| Method and path | Input | Success |
| --- | --- | --- |
| GET /api/v1/orders/{order_id}/fulfillment | None | PickupResponse |
| GET /api/v1/orders/{order_id}/fulfillment/history | limit, offset | Page of PickupEvent |
| GET /api/v1/seller/orders/{order_id}/fulfillment | None | PickupResponse |
| PUT /api/v1/seller/orders/{order_id}/fulfillment | PickupUpdate | PickupResponse |
| GET /api/v1/seller/orders/{order_id}/fulfillment/history | limit, offset | Page of PickupEvent |

PickupUpdate is `{expected_revision, state, pickup_instructions?}`. expected_revision
is a strict integer 0..2,147,483,646; state is preparing/ready_for_pickup/collected;
instructions are trimmed, nonblank, at most 2,000 characters, optional/null only
while preparing. PUT fully specifies the new instructions, so omission clears
them while preparing. Unknown fields are rejected. Validation errors redact
input values. Clients must reload before retrying a conflicting edit.

PickupResponse contains order_id, mode=local_pickup, basis=seller_reported_unverified,
revision, state, pickup_instructions, latest_event or null, updates_allowed and
notices. latest_event/history items contain revision, state, pickup_instructions
and created_at UTC, without actor IDs, account details or provider data.
updates_allowed describes whether the current financial/fulfillment state allows
a seller update; it does not grant the reader permission to write. A buyer always
uses read-only routes. Histories sort by revision descending, with the existing
limit (1..100, default20) and signed-64-bit offset (default0) bounds.

Successful reads/writes and domain/validation errors use Cache-Control: no-store.
No anonymous endpoint exists. Instructions must not be placed in URLs, logs,
analytics or public frontend state. Error responses use the existing detail/code
shape: 401 auth failure, 403 SELLER_REQUIRED, 404 NOT_FOUND; 409 ORDER_NOT_PAID,
REFUND_BLOCKS_FULFILLMENT, REVISION_CONFLICT or INVALID_PICKUP_TRANSITION;
422 standard redacted validation errors.

Migration 0017 adds one event table with unique order/revision and validation
constraints, preserving existing records. Rollback refuses before DDL if pickup
history or earlier protected photo/financial/sourcing/storefront records exist.
Run Alembic upgrades explicitly in the chosen development database.

## Future work and decision triggers

1. **Seller delivery and shipping:** define eligible products, service areas,
   carriers/tracking, dispatch/delivery states, failed delivery and partial fulfillment
   before adding another mode. Keep mode-specific rules in focused modules.
2. **Addresses and disclosure:** choose validation, buyer address consent, private
   seller pickup-address sharing, access controls and retention. An approximate
   public storefront point is never an exact pickup or delivery address by inference.
3. **Authoritative charges:** agree delivery/shipping fees, taxes, discounts and
   payment/refund effects before changing checkout totals. Preserve server-calculated
   money and immutable financial snapshots; do not assume a provider fee schedule.
4. **Scheduling and communication:** pickup windows, time zones, capacity, rescheduling,
   reminders, confirmations and no-shows need product policy and approved channels.
   This slice does not send email, SMS or messages or promise pickup availability.
5. **Handoff evidence:** decide buyer confirmation or pickup-code proof, who can
   correct a mistaken collection report, and an auditable dispute process. A seller
   report alone must not be labeled independently verified.
6. **Returns and refunds:** decide appeals, partial returns, cancellation after
   preparation and explicit inventory/production-cost effects. Fulfillment must not
   silently approve refunds, restore stock or reverse production costs.
7. **Hosted readiness:** review sensitive-location retention/deletion, backups,
   access monitoring, abuse controls, operational recovery, and end-to-end browser
   tests. Use production seller-connected payments only after separately approved
   onboarding/payment work. No paid services or new infrastructure are authorized
   by this backlog.
