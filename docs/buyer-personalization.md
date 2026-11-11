# Opt-in buyer personalization and remembered preferences

Implemented backend proposal; frontend acceptance/browser integration are pending.
The user selected option 2: activity-based personalization connected to saved
assistant memory. This extends [conversations](assistant-conversations.md) with
buyer-confirmed structured preferences and bounded favorites/purchase signals.

Existing conversations retain dialogue independently of personalization consent.
This extension adds cross-conversation memory: propose preferences from a saved
buyer question, confirm them, then use them in later buyer answers. It does not
silently learn from every sentence or use seller conversations/private business data.

## Profile and consent APIs

All operations require bearer authentication, implicitly target the current
account, and return Cache-Control: no-store including errors. A seller can use
their buyer capabilities. No client-supplied account ID is accepted. Unknown
fields are rejected and validation errors omit private input values.

Paths begin /api/v1/buyer/personalization, without a trailing collection slash:

| Suffix | Method | Result |
| --- | --- | --- |
| Collection | GET | Current ProfileResponse/default disabled state, 200 |
| Collection | PUT | Confirm full preferences/consent at a revision, 200 |
| Collection | DELETE | Erase preferences and disable use at a revision, 200 |
| /suggestions | POST | Up to four current public suggestions, 200 |
| /remember | POST | Reviewable proposal from a saved buyer question, 200 |

Defaults are disabled, revision zero and empty preferences. The project owner's
feature choice does not automatically enroll application users.

~~~json
{
  "expected_revision": 0,
  "enabled": true,
  "confirmed": true,
  "preferences": {
    "budget_per_item": "20.00",
    "product_types": ["sourdough"],
    "location": "Exampletown",
    "excluded_listing_ids": []
  }
}
~~~

All preference fields are optional. budget_per_item is a nonnegative USD decimal
JSON string, at most six fractional places and 1,000,000,000. It applies to one
listed selling unit (which may be a loaf or dozen), not a basket. Unmodeled fees,
taxes and pickup/travel charges are excluded. product_types contains up to three
unique sourdough/eggs/other values; empty means all types. location is an exact
case-insensitive published area label, without geocoding or travel distance.
excluded_listing_ids contains at most twenty unique UUIDs.

Response: revision, enabled, preferences, expires_at (UTC/null), status
(enabled/disabled/expired) and notices. No account ID or raw activity is returned.
Revisions/booleans are strict. Every PUT requires confirmed: true. Disabled PUT
requires empty preferences and erases stored values. A stale update returns 409
REVISION_CONFLICT; reload before confirming.

DELETE body:

~~~json
{"expected_revision": 1}
~~~

The response is the cleared disabled profile and next revision. A minimal
account-linked revision tombstone prevents a stale tab from restoring erased
preferences. Erasure remains possible at the revision maximum; re-enabling does
not. No preference values are kept in that tombstone.

Disable/delete also erases profile-derived evidence, facts and AI paragraphs
from the owner's saved buyer answers that used personalization. Those answers
become unavailable on history reload. Original user messages remain under the
separate conversation policy and can be erased with conversation deletion.
Favorites/orders are not erased by profile deletion. Frontend must clear its
own cached derived answers and reload history; no-store does not erase UI state.

## Retention

Profiles expire thirty days from their last confirmed PUT. Reads, suggestions
and conversations do not extend that period. Expired preferences are immediately
hidden and excluded from activity queries/answers. Re-enabling requires fresh
confirmation; old expired values are not automatically restored.

Operator cleanup physically clears expired preferences and derived answer copies:

~~~powershell
# Use the configured backend environment and intended FAIRMADE_DATABASE_URL.
python -m fairmade.personalization.purge
~~~

Each run handles at most one hundred profiles and retains minimal revision
tombstones. Repeat until none remain or schedule cleanup before hosting. No
scheduler/new service is installed. Until cleanup, expired data can remain on
disk despite being inaccessible through APIs. Backups, SQLite freed pages/WAL
and browser copies require separate retention/secure-erasure controls. No
application-level encryption or legal compliance guarantee is added.

This policy is separate from conversation inactivity expiry and business-record
retention. Durations/caps are implementation limits, not individual user choices.

## Activity and deterministic suggestions

~~~json
{
  "budget_per_item": "18.00",
  "product_types": ["sourdough"],
  "include_unknown_availability": false
}
~~~

Non-null budget/type/location fields override saved preferences for this request
only. A type array [] explicitly clears that request's type filter. Null
budget/location inherits the profile value; clear the saved field via PUT when
needed. Request overrides are not automatically remembered.

Active consent enables these signals:

- Current favorites belonging to the buyer and matching public candidates.
- Up to two hundred order-line signals from the prior ninety days, dated by
  backend-verified completed sandbox capture time. Pending, failed, unverified
  and other-buyer's payments are excluded.
- Only still-public listings. Every order with any refund request is
  conservatively excluded, including denied requests. A purchase is not proof
  of satisfaction, quality or a permanent preference.

Only listing IDs/current public types are projected internally from purchase
history. Provider payloads, transaction IDs, amounts, emails, historical order
text and seller-private records are not read for these signals. Type affinity
uses the current public type of a previously purchased listing, not proof of
its historical variant/contents or a sensitive personal trait.

Hard budget/type/location/exclusion/availability filters apply before ranking.
SQL bounds the complete matching candidate set at one hundred public listings.
Overflow returns 409 PERSONALIZATION_SCOPE_TOO_LARGE rather than ranking a
truncated latest-first subset. Narrow filters. An oversized activity window
also returns that explicit error.

Default suggestions require reported available stock. Unknown stock requires
explicit include_unknown_availability: true. Unavailable products and the
account's own listings are excluded. A disclosed needs_attention quality summary
is excluded. Missing quality evidence is unknown, not certification. The feature
cannot establish allergen, medical, ethical or safety suitability from activity
or infer those requirements. Suggestions are not verified substitutes.

Within eligible candidates, ranking is lexicographic: favorite, previously
purchased listing, then current-type purchase affinity capped at three. Stable
listing IDs break ties. This is not a lowest-price, quality or overall-value
ranking across incompatible quantities. Activity never overrides hard constraints.

Response: items [{listing: current CatalogDetail, reasons: string[]}],
personalized (active-consent flag), profile_revision, effective_preferences and
notices. Reasons include IN_YOUR_FAVORITES, PREVIOUS_VERIFIED_SANDBOX_PURCHASE,
CURRENT_TYPE_AFFINITY_FROM_PURCHASED_LISTINGS and MATCHES_CURRENT_FILTERS.
Active consent does not imply that useful activity exists. Disabled/expired
accounts can receive generic public suggestions from request filters without
reading private activity. Consent/activity and selected listings are rechecked
before return; changes return 409 PERSONALIZATION_CHANGED or visibility errors.
No stock is reserved, no order is created, and checkout rechecks actual eligibility.
Personalization never changes published prices or exposes the buyer's budget to sellers.

## Conversation memory and proposals

Use up to four suggested listing IDs to create a buyer conversation and ask
for an explanation. Existing buyer questions/saved turns now add owner-only
evidence titled Your opted-in shopping preferences and activity matches while
consent is active. Server facts show exact budget/filter outcomes; model context
contains qualitative flags and activity reasons. Seller answers do not read profiles.

Every turn reloads profile/activity and public sources. Mid-inference changes
invalidate the answer. Historical dialogue is not authority for current prices,
availability or deleted preferences. Profile changes can make old answers stale;
disable/delete physically erases profile-derived saved answer copies.

To remember an explicit preference from a saved buyer question:

~~~json
{
  "conversation_id": "49821f31-2410-484c-a5d9-a9397b20436a",
  "turn_id": "f740c47c-a23d-4110-b4e5-5f83a0b971d1"
}
~~~

POST /remember requires an active profile and an owned unexpired buyer
conversation. Seller conversations return 409 BUYER_CONVERSATION_REQUIRED.
Foreign/missing/expired resources return 404. Only that original user question
is sent to the existing local Qwen model, without prior answers, other chats,
seller records or activity payloads.

The model proposes budget/type fields. Budgets require explicit USD/$ amounts
and budget/maximum/limit/spend wording in the source question. Types require
sourdough/bread, egg/eggs or other-products wording. Bare decimal strings are
required; malformed/unsupported output returns 502 ASSISTANT_INVALID_RESPONSE.
Text/numeric presence does not prove correct interpretation of quotations or
negation: review proposals. Locations, exclusions and sensitive traits are not inferred.

Response: profile_revision, merged preferences, source_turn_id, notices. Null
budget/empty extracted types leave existing confirmed settings unchanged.
Nothing is saved or opted in by the proposal. Present it for review, then PUT
the intended full preferences at the returned revision with enabled: true and
confirmed: true. Later logins/conversations can use the confirmed memory.

Deleting the source chat or changing consent/revision during extraction discards
the proposal; expiration/logout is rechecked. Proposals are not separately
persisted. Shared local inference limits apply (429 busy, 502 invalid, 503
unavailable). Profile CRUD/cleanup and suggestions need no running model.

## Migration, frontend and remaining work

Apply Alembic 0028 before use. buyer_profiles has an owner primary key,
revision/consent/expiry checks and an expiry index. No account is automatically
enrolled. Startup does not create schemas. Rollback refuses profile revision
history, including cleared tombstones, and protects older history before SQLite
DDL. Rollback is an explicit operator operation, not a privacy/revision bypass.

Frontend work: opt-in settings, confirmed preference editor, disable/delete,
proposal review from a selected buyer turn, suggestion reasons/units/availability,
buyer conversation creation, safe facts/citation rendering and stale-state
handling. Never present affinity as a fairness, quality or safety score.

No frontend/browser demonstration is included. Single-storefront basket budgets
and saved explanations are now covered by [basket planning](buyer-basket-optimization.md).
Multi-seller optimization, safety evidence verification, cross-category unit equivalence,
behavioral embeddings, sensitive-trait inference, forecasting and hosted
operational controls remain separate work.

Validation: the broad regression run passed 1,311 tests (17 opt-in checks skipped,
two framework warnings). The final amount/date guards were then checked by the
29-test focused personalization run; a separate four-case real Qwen run covered
the remember/confirm/explain flow and existing buyer explanations. Lint, format,
migration parity/preservation, 129 local links, four JSON examples and five
authenticated OpenAPI operations passed. These checks do not prove universal
model understanding or browser integration.

