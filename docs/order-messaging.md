# Private order messaging

Backend implementation and additive frontend contract proposal. The user chose
option 1: buyer–seller messages tied to an existing order. Option 2,
pre-purchase product/storefront inquiries, is explicitly a later improvement;
there is no pre-purchase contact endpoint in this feature.

Apply migration 0029 after 0028. This work follows the existing migration chain
through the personalization branch to avoid competing schema heads. Basket and
forecasting work are not prerequisites. No frontend changes, model calls, paid
service, email provider or background infrastructure are introduced.

## Participant scope and lifecycle

GET and POST /api/v1/orders/{order_id}/messages require the existing bearer
token. Only that order's buyer and seller can access the history. The seller
must still have the verified seller role; revoked seller access returns 403.
Buyer access is determined by the order's buyer identity, even when the buyer
also has a seller role. Unrelated accounts, including administrators, receive
the same 404 as an unknown order. There is no support/admin bypass.

An existing unpaid, expired, cancelled, paid or refunded order can retain a
conversation. Payment completion is not a prerequisite for discussing an
existing order; this does not grant a way to contact a storefront without an
order. Withdrawing the current product listing does not remove historical
order communication. Order participant identities are authoritative server
data, never client-provided recipients or sender roles.

Messages are independent of payment, refund, fulfillment, production, stock
and publication transitions. Writing “refund this order” performs no refund;
updating pickup instructions still uses the fulfillment API. A message response
does not confirm payment, delivery, pickup or a seller's claim.

All responses and errors use Cache-Control: no-store. Fixed 24-hour bearer
expiry and logout remain unchanged. Access/session state is rechecked after a
write-lock wait and before returning fetched history.

## Sending and retry contract

POST /api/v1/orders/{order_id}/messages accepts only request_id and text:

~~~json
{
  "request_id": "90000000-0000-4000-8000-000000000001",
  "text": "When can I collect this order?"
}
~~~

Use an actual owned order UUID in the URL and a fresh request UUID per intended
message. A successful new append returns 201. An identical retry with the same
request_id, order and authenticated sender returns the same response with 200.
The same request UUID is independent for the other participant or another
order. Reusing one's key for different normalized text returns 409
REQUEST_ID_CONFLICT; it never overwrites the old message.

Illustrative response shape, with synthetic IDs/timestamp:

~~~json
{
  "id": "91000000-0000-4000-8000-000000000001",
  "sequence": 1,
  "sender": "buyer",
  "is_mine": true,
  "text": "When can I collect this order?",
  "created_at": "2026-11-10T18:00:00Z"
}
~~~

sender is buyer or seller, based on the order relationship at send time.
is_mine is calculated separately for the authenticated reader. The other
participant sees the same message ID/sequence/text/time and is_mine false.
Responses omit sender account UUIDs, email addresses, login tokens, request
keys, payment references and recipient contact details. User-authored text
itself is shared as written; it is not redacted or independently verified.

Text must be a strict JSON string, nonblank after outer-whitespace trimming,
at most 2,000 Unicode characters, with a 4,000-character raw-input cap before
normalization to bound padding and Windows line endings. CRLF and bare CR become LF before validation
and retry comparison. Newlines, tabs and valid Unicode are allowed. Unsupported
control characters (including NUL/escape) and unpaired surrogate characters
are rejected. Numbers, booleans, null, attachments, arbitrary recipients,
spoofed identities, timestamps, order/payment state and all extra fields fail
with 422. Validation errors omit submitted private values.

Text is stored and returned literally as JSON, including HTML-looking strings
and links. The backend does not render HTML, fetch links, interpret commands or
send the text to an AI provider. The frontend must render it as text using
normal framework escaping, with suitable line wrapping; never insert it as
raw HTML. Human order messages are not included in seller or buyer assistant
evidence and do not populate personalization or conversation memory.

## Cursor history

GET /api/v1/orders/{order_id}/messages accepts:

- after_sequence: nonnegative integer 0..1,000, default 0.
- limit: 1..100, default 20.

The response is MessagePage:

- order_id and my_role, derived from the authorized order.
- items: MessageResponse objects in ascending sequence order.
- after_sequence: the requested cursor.
- next_after_sequence: the last returned sequence, or the unchanged cursor
  when no messages were returned.
- limit and has_more.
- notices describing privacy, plain-text/no-action semantics and retention.

Use next_after_sequence for subsequent pages or incremental polling. Appends
do not shift earlier messages, so an ascending sequence cursor does not skip
or duplicate items because of new arrivals. Fetching an empty order returns
an empty list without creating a conversation row. There is one implicit
history per order, not a client-selectable thread or recipient list.

History survives application restarts. No edit, delete, read-receipt,
notification, attachment or WebSocket endpoint is added. These are current
implementation boundaries, not individually confirmed user decisions.

## Limits, concurrency and failures

An order holds at most 1,000 messages shared between both participants.
Overflow returns 409 ORDER_MESSAGE_LIMIT. Existing history remains readable
and an identical send retry still works when full.

Each account can append at most ten messages in the previous sixty seconds,
across all orders and both buyer/seller roles. Overflow returns 429
MESSAGE_RATE_LIMIT and Retry-After: 60. Identical retries do not consume
additional capacity or receive a new sequence and remain available at the
rate limit. These bounds are local implementation limits, not a claim of
hosted abuse prevention or a user-selected product quota.

A short SQLite write transaction serializes append, retry, rate and sequence
checks. Unique database constraints protect per-order sequences and
(order, sender, request_id) keys. A no-op order-row lock changes no business
state or stock hold. Failed commits roll back both the message and its
sequence allocation. History uses an indexed order/sequence cursor; sending
rate queries use a sender/time index. SQLite serializes writers globally;
revisit account-wide limit synchronization if changing database concurrency.

Other errors retain established shapes: 401 for invalid/expired/revoked
sessions, 403 for an order seller without current seller access, 404 for
nonparticipants/missing orders, and 422 for invalid payloads or pagination.
There is no external delivery acknowledgement: 201 confirms a durable backend
append, not that the recipient read the message.

## Storage, retention and migration

OrderMessage stores its ID, order, sequence, sender account/role, request UUID,
canonical text and server UTC timestamp. The internal identity columns are
used for authorization/retries/rate controls, not exposed through message DTOs.

History is append-only and retained with the order, with no automatic expiry
or participant deletion in this implementation. This is business communication
rather than AI chat: the AI conversation's thirty-day inactivity expiry and
buyer-profile erasure do not delete human messages. Retention, participant
erasure/export, reporting/blocking/moderation and operational backup policies
need a separate product decision before broader use. No silently chosen
purge schedule or secure-erasure guarantee is implied.

Migration 0029 adds only order_messages, constraints and indexes. Existing
accounts/orders/payments and stock are preserved, with no message backfill.
Downgrade refuses when any message history exists. A wider downgrade preflights
older protected history before nontransactional SQLite DDL, so a refused parent
downgrade does not drop this new empty table. An empty migration can be rolled
back to 0028 and reapplied without changing existing orders.

## Frontend handoff and later improvement

The frontend developer owns the order conversation view, correct buyer/seller
direction, pending-send state, safe literal text display, bounded incremental
polling and auth/rate/error handling. Preserve the request UUID across uncertain
network retries. Present 409 key conflicts and full history explicitly;
respect Retry-After and stop polling on lost authorization. Do not show “read”
or “delivered” based on successful append alone.

Current code does not change the frontend or demonstrate the browser flow.
Shared contract acceptance remains pending.

Option 2 remains a later improvement: pre-purchase inquiries tied to a product
or storefront, with explicit eligibility, recipient consent, identity/privacy,
reporting/blocking, retention and abuse rules. Other possible extensions are
inbox/unread indicators, attachments, read receipts and notifications. These
entries do not authorize a contact service, external provider, paid feature
or expanded messaging scope automatically.

## Validation

The affected messaging/orders/payments/refunds/fulfillment regression passed
192 tests with two existing framework warnings. The final raw-input cap and
valid-Unicode/newline boundary checks passed separately (two tests). Coverage
includes participant/privacy boundaries, seller-role/session revocation,
restart restoration, cursor stability, idempotency, concurrent retries/appends,
account-wide sending limits, full history, commit rollback, assistant evidence
isolation, migration parity/preservation and refused lossy/wider downgrades.
Ruff lint/format passed for 375 Python files, 119 local documentation links
resolved, two JSON examples validated against actual schemas and two OpenAPI
operations required authentication. These are affected-backend checks, not
a full-suite rerun, browser demonstration or hosted abuse assessment.
