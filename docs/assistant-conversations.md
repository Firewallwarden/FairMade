# Saved seller and buyer conversations

Implemented backend proposal; frontend acceptance and browser integration are
pending. [Implementation PR #42](https://github.com/Firewallwarden/FairMade/pull/42)
is a main-targeted draft depending on #38, #39, #40 and #41; it is not integrated
into main. After the [continuity audit](assistant-continuity-audit.md), the user
chose saved database conversations (option 2), ownership, deletion and a defined
retention policy.

The [local assistant](local-assistants.md) provider remains opt-in Ollama/Qwen3
8B. Exact financial outcomes remain server-calculated; chat cannot change
products, Quality Locks or payments. The existing /assistants/seller and
/assistants/buyer question endpoints remain independent and stateless.

## HTTP contract

Paths start with /api/v1/assistants/conversations, without a trailing slash on
the collection. All operations require bearer authentication and return
Cache-Control: no-store, including errors. UUIDs are strings, money uses decimal
strings and timestamps are UTC. Unknown body fields are rejected.

| Suffix | Method | Behavior |
| --- | --- | --- |
| Collection | POST | Create owner-bound metadata (201); no inference |
| Collection | GET | List owner's unexpired metadata (200) |
| /{id} | GET | Read metadata with current role/source checks (200) |
| /{id} | DELETE | Erase conversation and all turns, idempotently (204) |
| /{id}/turns | POST | Generate and atomically save a completed turn (200) |
| /{id}/turns | GET | Read chronological history with source checks (200) |

Both lists accept limit 1..20 (default 20), offset 0..1000 (default 0), and return
{items, limit, offset}. Conversations sort by updated_at descending then id
descending; turns sort by revision ascending. Offset pages can shift while new
turns arrive; writes must use the current revision.

Creation example with illustrative synthetic IDs:

~~~json
{
  "request_id": "b7d04c11-b389-498b-982c-3db2949fa687",
  "scope": {
    "role": "seller",
    "product_id": "59a9818e-37a5-47c0-9302-b1b54ab67514"
  }
}
~~~

Seller scope requires a current seller grant and owned product_id. Optional
analysis_id, supplier_report_id and history_period follow the existing question
contract. Omitted analysis_id selects the latest analysis on each turn; an
explicit ID fixes that source. Buyer scope is {role: "buyer", listing_ids:
[one to four unique active UUIDs]}. A seller may create a separate buyer
conversation, which uses public evidence only.

Buyer creation example with illustrative synthetic IDs:

~~~json
{
  "request_id": "9e2f26df-d49c-4ba0-97a0-acf229a771f1",
  "scope": {
    "role": "buyer",
    "listing_ids": ["851062e4-c8de-4403-a04e-b02620a8b8ca"]
  }
}
~~~

Scope is immutable. Create a new conversation to change assistant role, product,
listings or explicitly selected sources. Clients cannot submit prior transcripts,
assistant output, evidence, tools, provider URLs or turn roles.

Metadata fields are id, role, scope, revision (initially zero), created_at,
updated_at, expires_at. No account ID or session token is returned. Collection
lists expose only the owner's scope/metadata even after source access is lost;
they never expose dialogue or old evidence. Detail/history/turn requests check
current role, ownership and public source visibility.

Turn example with a synthetic retry key:

~~~json
{
  "request_id": "cf14e1c2-5864-42e7-9bc8-0d5661a60103",
  "expected_revision": 0,
  "question": "What happens if I charge $8 per loaf?"
}
~~~

Turn responses contain id, conversation_id, request_id, revision, question, answer,
answer_status, context_turns, created_at. Answer is the existing AssistantResponse
with deterministic facts, cited qualitative paragraphs, evidence and notices.
The next question uses expected_revision: 1 and a new request_id.

"Why does that price lose money?" may retain the immediately previous validated
scenario prices. The backend recalculates them from current selected economics
and adds a notice. Explicit new prices replace previous prices. If several
previous prices were selected, their bounded set is retained rather than silently
choosing one. Explicit numeric questions are more precise than "a little more."
If the product type or saved analysis selling unit changed, implicit price reuse
returns 409 CONVERSATION_PRICE_BASIS_CHANGED; state a new price explicitly in its
new basis. A new numeric question cannot silently fall back to an old price when
the model extracts no price.

A reference such as "Why is that missing?" can retain the previous resolved
history period when no new period is selected. Resolved UTC dates are saved,
so midnight does not silently change an earlier period. New explicit period
phrases select the normal documented period unless scope fixed history_period.

## Continuity and current evidence

At most six recent completed pairs within 12,000 UTF-8 content bytes enter the
explanation prompt. Oldest pairs are omitted at the byte limit. context_turns
reports the actual number included; older turns remain pageable but are outside
model context. A conversation accepts at most forty completed turns.

Prior questions supply intent, never authoritative facts. Numeric text is
redacted from explanation history. Prior assistant prose is replayed only when
its full evidence fingerprint, including price scenarios, matches current evidence.
Old evidence payloads and numerical facts are never replayed. Current evidence/citation keys
govern every answer; retained price inputs are recalculated by the calculator.

Current access, seller grants, approved public disclosures, Quality Locks and
business evidence are loaded before inference, checked afterward, and checked
again inside the final write transaction. No write lock is held during inference.

History and completed retries follow these rules:

- Inaccessible sources, such as withdrawn listings, produce the existing 404/403
  source/access error. The owner can still delete the conversation.
- Accessible but changed evidence causes old turns to return answer: null and
  answer_status: "evidence_changed". The owner's original question, timestamp and
  revision remain visible, but the old answer and disclosures are withheld.
- Matching evidence returns the saved answer and answer_status: "available".
  generated_at stays the original answer time.

Owner-submitted question text remains private history. Do not submit credentials
or unrelated personal data. Chat text is not a verified source or certification.
Schema, digit and citation checks do not prove semantic correctness; factual
review remains necessary.

## Retries, transactions and limits

Creation request_id is unique per account. An identical retry returns the same
conversation (201); changed scope under that key returns 409 REQUEST_ID_CONFLICT.
Deletion or physical expiry cleanup removes the record and its retry key.

Turn request_id is unique per conversation. An identical completed retry returns
the same turn without inference, subject to current-evidence rules. A changed
question or expected_revision under the same key returns 409 REQUEST_ID_CONFLICT.
Failed generation consumes no key, saves no turn, advances no revision and does
not extend retention. The turn endpoint still requires an enabled configured
gateway; history, creation and deletion need no inference.

expected_revision is a strict integer 0..40; booleans are rejected. Concurrent
turns cannot both advance the same revision. Stale requests return 409
REVISION_CONFLICT; reload before retrying the intended question. Busy inference
returns 429 ASSISTANT_BUSY. Deletion or expiry during inference prevents saving,
without resurrecting data. It does not cancel an already running local inference.
Turn, revision and retention timestamps commit atomically.

There are at most twenty unexpired conversations per account, forty turns per
conversation, 2,000 characters per question, 24,000 encoded evidence bytes and
65,536 saved answer bytes. Cap errors are 409 CONVERSATION_LIMIT,
CONVERSATION_FULL or ASSISTANT_SCOPE_TOO_LARGE. Existing assistant 401/403/404/422,
502/503 errors apply. Error shape is {detail: {code, message}} except redacted
validation detail arrays; raw submitted bodies and prompts are not echoed.

## Retention and deletion

Durable database storage is the confirmed user choice. These are documented
implementation limits, rather than additional user-selected policy:

- Expiry is thirty days after creation or the last successfully committed new
  turn. Reads, exact retries and failures do not extend it. Expired chats cannot
  resume; a new conversation is required.
- Owner DELETE removes conversation and cascaded turns in the live DB, including
  after role/source loss. Repeating DELETE is 204, as is deleting an absent or
  other-account ID; it never deletes another account's record.
- Creation cleans that owner's expired rows. The operator command below cleans
  expired rows across accounts. No timer/scheduling infrastructure is installed.

~~~powershell
# Run in the configured backend environment against the intended database.
# FAIRMADE_DATABASE_URL uses the normal backend setting.
python -m fairmade.conversations.purge
~~~

Access expiry is enforced even if cleanup has not run. Physical retention can
exceed thirty days until cleanup runs. The command prints only a count, without
chat contents or account identities. Hosted use needs scheduled cleanup and a
backup retention policy.

SQLite stores the chat content and selected evidence. No application-level
encryption, legal retention policy, secure erasure of SQLite free pages/WAL files
or removal from backups is added. Keep database files private and use synthetic
demo data. Review these controls before hosting. Logout revokes access, without
deleting chats; a later valid login for the same account can resume an unexpired
conversation.

## Migration and frontend handoff

Synthetic seller request flow, using the existing example variables: $api is
the /api/v1 base, $productId is an owned synthetic product, and $sellerHeaders
contains the authenticated bearer header. Do not print credentials or headers.

~~~powershell
$createBody = @{
    request_id = [guid]::NewGuid().ToString()
    scope = @{ role = 'seller'; product_id = $productId }
} | ConvertTo-Json -Depth 10
$conversation = Invoke-RestMethod "$api/assistants/conversations" -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body $createBody
$turnUrl = "$api/assistants/conversations/$($conversation.id)/turns"
$firstBody = @{
    request_id = [guid]::NewGuid().ToString()
    expected_revision = $conversation.revision
    question = 'What happens if I charge $8 per loaf?'
} | ConvertTo-Json
$first = Invoke-RestMethod $turnUrl -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body $firstBody
$followUpBody = @{
    request_id = [guid]::NewGuid().ToString()
    expected_revision = $first.revision
    question = 'Why does that price lose money?'
} | ConvertTo-Json
$second = Invoke-RestMethod $turnUrl -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body $followUpBody
$second.answer.facts | ConvertTo-Json -Depth 10
$second.answer.paragraphs | ConvertTo-Json -Depth 10
$history = Invoke-RestMethod $turnUrl -Headers $sellerHeaders
# Explicitly erase this synthetic conversation when finished:
Invoke-RestMethod "$api/assistants/conversations/$($conversation.id)" -Method Delete -Headers $sellerHeaders
~~~

Apply Alembic 0026 before use. It adds assistant_conversations and assistant_turns,
owner/source metadata, unique retry/revision constraints, checks, list/expiry
indexes and cascading deletion. Startup never creates schemas. Downgrade refuses
retained conversation history; explicitly erase/purge it before rolling back.
Wider SQLite downgrades preflight existing protected history before dropping
empty conversation tables.

The frontend developer should:

1. Create a conversation with explicit role/scope and retain its ID.
2. Send a new retry key with the current revision; reuse the key for network
   retries. Render all question/model text safely as text.
3. Restore paged history after reload. Render deterministic facts, citations,
   notices and evidence distinctly. Explain null/stale answers and offer refresh.
4. Offer deletion and new conversations for scope changes. Handle 401/login,
   revision conflicts, busy inference, expiry, caps and withdrawn evidence.
5. Demonstrate seller price/follow-up and buyer disclosure/follow-up flows, then
   check browser/recorder latency before recording the demo.

Browser work is not implemented here. Receipt extraction and
[opt-in buyer personalization](buyer-personalization.md) now have separate backend
implementations. Buyer profile memory can propose preferences from saved buyer
questions, then use confirmed settings across conversations. Forecasting and
basket optimization remain follow-ups.
This feature does not activate autonomous development or change provider approval.
