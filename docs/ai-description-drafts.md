# Private AI description drafts and exact seller review

This feature depends on assistant PRs #38, #39 and #40. Its separate PR targets
main and remains draft until prerequisites are integrated, the child is refreshed
and the Review guard passes. Frontend implementation remains separate.

## Generation and review

The owning verified seller can generate copy from the product's name, type,
selling-unit label and existing private description. No pricing analyses,
recipes, supplier records, payment data or account identities are supplied.
The local model is the approved qwen3:8b through the existing loopback gateway.
Generation uses the same single-process inference slot as the assistants.

Generation creates a private draft and preserves the original generated text,
source snapshot/hash, request identity, tone and model provenance. It does not
edit the product. The seller can edit the draft using its current revision.
Approval requires approved=true, expected_revision and the exact preview_hash.
Approval atomically updates the private product description and records approval
time and actor. Approved draft contents remain immutable.

Existing public Passports/listings do not change. Publishing revised copy needs
the normal separate seller-controlled public disclosure and approval workflow.
Existing cost analyses and immutable source snapshots are not rewritten.

The source fingerprint is checked after generation and again before applying a
draft. A changed product requires a new generation instead of overwriting newer
seller work. Exact approval retries return the approved record without reapplying
copy over later manual product edits.

## HTTP proposal

All routes require bearer authentication, current verified seller access and
product ownership. Paths are relative to
/api/v1/products/{product_id}/description-drafts.

| Method/path | Body | Result |
| --- | --- | --- |
| POST empty suffix | {request_id, tone?} | 201 full private draft |
| GET empty suffix | standard limit/offset | 200 page of private drafts |
| GET /{draft_id} | none | 200 full private draft |
| PUT /{draft_id} | {expected_revision, description} | 200 edited draft with new revision/hash |
| POST /{draft_id}/approve | {expected_revision, preview_hash, approved:true} | 200 approved draft |

request_id is a UUID. tone is plain (default) or friendly. Reusing the same
product/request ID and request body returns the existing draft without another
model call; changed request content returns 409 REQUEST_ID_CONFLICT.
Generation POST requires local assistants enabled. Reading, editing and approval
do not require the model to be running.

Draft responses include id, product_id, request_id, revision, state, generated_text,
description, source_snapshot, source_hash, provider, model, tone, created_at,
updated_at, approved_at, preview_hash and notices. Times are UTC. The hash binds
the draft identity, revision, current text and original source fingerprint.
Text is trimmed and bounded to 1-2,000 characters. Extra request fields are
forbidden. Lists use the existing bounded pagination.

Errors use the existing standard format (and redacted 422 validation lists):
401 for missing/expired/revoked sessions, 403 for missing seller access, 404 for
missing/unowned resources, 409 for state/revision/request/source conflicts, 429
for a busy inference slot, 502 for rejected model output and 503 for unavailable
local inference. Source conflicts use DESCRIPTION_SOURCE_CHANGED; other editing/
approval conflicts use REVISION_CONFLICT. All responses are no-store.

## Accuracy, privacy and limitations

AI text is unreviewed copy, not verified product evidence. Model instructions
restrict the source to selected metadata. Mechanical guards reject malformed or
oversized output, unsupported numeric tokens, prices/URLs/HTML and selected
verification/guarantee/health-claim terms. These are not semantic verification.
Real evaluation produced plausible wording beyond the literal source; sellers
must inspect and correct ingredients, methods, quality and marketing claims.

Render the original source and draft as text, show AI provenance/notices, and
allow editing before approval. Do not automatically approve or publish a returned
draft. Unknown factual details must not be presented as verified certifications.
Manual seller edits remain seller-authored assertions, not system verification.

Access/session/source changes during generation prevent saving a result.
Database transactions are released while inference runs; saving and applying
use the existing owned-product write reservation. Failed approvals roll back both
the product change and approval record. Retries do not duplicate model writes.

Migration 0025 adds only the private description_drafts table, constraints and
product/history index. Apply normal Alembic migrations before use; startup never
creates schemas. Downgrades refuse while draft/review records exist and preflight
earlier protected records before dropping the empty table during wider rollback.
No runtime packages, cloud inference or frontend edits are added.

Drafts are durable private business records, distinct from conversation memory.
No automatic deletion/discard endpoint or conversation retention is introduced.
Broader retention/cleanup and hosted operating controls remain future work.

## Synthetic workflow

Use an owned synthetic product, $api as the /api/v1 base and $sellerHeaders as
its authenticated header dictionary. Do not log tokens.

~~~powershell
$draftsUrl = "$api/products/$productId/description-drafts"
$requestBody = @{request_id=[guid]::NewGuid().ToString(); tone='plain'}
$draft = Invoke-RestMethod $draftsUrl -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body ($requestBody | ConvertTo-Json)
$draft.source_snapshot | ConvertTo-Json
$draft.description
# Review every factual claim. Edit if needed, preserving the current revision.
$edit = @{expected_revision=$draft.revision; description='Seller-reviewed description for this product.'}
$draft = Invoke-RestMethod "$draftsUrl/$($draft.id)" -Method Put -Headers $sellerHeaders -ContentType 'application/json' -Body ($edit | ConvertTo-Json)
# Only send approval after reviewing the exact returned text and source.
$approval = @{expected_revision=$draft.revision; preview_hash=$draft.preview_hash; approved=$true}
Invoke-RestMethod "$draftsUrl/$($draft.id)/approve" -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body ($approval | ConvertTo-Json)
~~~

See [local assistant setup](../backend/examples/assistants/README.md) and
[the existing public disclosure contract](api-contract.md).
