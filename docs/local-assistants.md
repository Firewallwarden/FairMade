# Local seller and buyer assistant foundation

The user approved Ollama with Qwen3 8B locally, without paid inference or a
cloud fallback. This implements the read-only backend foundation for both
assistants. Frontend acceptance and browser integration remain pending.
Implementation: [PR #38](https://github.com/Firewallwarden/FairMade/pull/38).
Validation: 1,173 backend tests passed, plus eight opt-in real local-model
evaluations run separately. Lint, formatting, examples and contract checks passed.

## Scope

Seller questions select one owned product, an optional saved analysis and an
optional supplier comparison report. Without an analysis ID, the latest saved
analysis is selected and identified in the returned evidence. Missing history
stays unknown. The assistant explains costs, modeled ranges, quality requirements
and selected supplier evidence. It can extract up to five explicit proposed USD
selling prices and pass them to the existing deterministic calculator. Extracted
values must occur numerically in the question and satisfy existing finite,
nonnegative amount bounds. Use digits, for example: “What if I charge $8 per loaf?”

Buyer questions select one to four unique, currently visible listing IDs. Only
the existing public listing/Passport allowlists are read. Cost disclosures stay
seller-controlled; omitted costs are unknown, not zero and not necessarily
excluded from the seller's price. Public unit-price differences are calculated
only when product type, currency and reference unit match and both prices have
calculated status. Differences use rounded six-place displays. They do not
establish quality equivalence, overall value, affordability or objective fairness.

No prices, products, stock, orders, Quality Locks, supplier reports or
publications are changed. There are no arbitrary tools, SQL, URL fetching,
browser search, model-selected resource IDs, client-supplied evidence or
privileged system messages.

## HTTP contract

Both endpoints require a current bearer session; any account can use the buyer
endpoint, including sellers. Seller questions additionally require current
verified seller access and product ownership.

| Method/path | Request | Success |
| --- | --- | --- |
| POST /api/v1/assistants/seller | SellerQuestion below | 200 AssistantResponse |
| POST /api/v1/assistants/buyer | BuyerQuestion below | 200 AssistantResponse |

SellerQuestion:

~~~json
{
  "question": "What happens if I charge $8 per loaf?",
  "product_id": "11111111-1111-4111-8111-111111111111",
  "analysis_id": "22222222-2222-4222-8222-222222222222",
  "supplier_report_id": null
}
~~~

BuyerQuestion:

~~~json
{
  "question": "Explain the disclosed costs and the missing evidence.",
  "listing_ids": ["33333333-3333-4333-8333-333333333333"]
}
~~~

IDs are illustrative. Question text is trimmed, nonempty and bounded to 2,000
characters. Extra fields are forbidden. Optional seller IDs default to null.
The report must belong to a sourcing input of the selected owned product.

AssistantResponse contains:

| Field | Meaning |
| --- | --- |
| assistant_version | fairmade-assistant-v1 |
| role | seller or buyer |
| provider / model | ollama_local / qwen3:8b |
| generated_at | UTC generation timestamp |
| facts | Server-rendered exact statements, each with text and evidence_keys |
| paragraphs | Qualitative AI explanation, each with text and evidence_keys |
| evidence | Allowlisted records with key, title, basis and data |
| notices | Unverified-input, AI-review, quality and read-only limitations |

Render facts and paragraphs separately. Facts carry exact numerical results
and scenario outcomes; paragraphs are generated explanations, not replacement
financial records. Render all text safely as text, never raw HTML. Citations
resolve to evidence keys, not model-generated URLs. Display the notices and
retain uncertainty when a disclosure is absent.

All responses and authorization failures use Cache-Control: no-store. Errors
use the standard detail object except the usual redacted 422 validation list.
Raw questions, draft inputs and provider errors are not echoed in failures.

| Status/code | Behavior |
| --- | --- |
| 401 UNAUTHORIZED | Missing, expired or revoked session |
| 403 SELLER_REQUIRED | Seller access missing or revoked |
| 404 NOT_FOUND | Missing/unowned private evidence or invisible listing |
| 409 UNSUPPORTED_EVIDENCE_VERSION | Unsupported saved evidence version |
| 409 ASSISTANT_SCOPE_TOO_LARGE | Evidence exceeds the 24,000-byte JSON budget |
| 409 ASSISTANT_EVIDENCE_CHANGED | Evidence changed during inference; ask again |
| 429 ASSISTANT_BUSY | Another generation occupies the local process slot |
| 502 ASSISTANT_INVALID_RESPONSE | Invalid/truncated output, numeric prose or invalid citations |
| 503 ASSISTANT_UNAVAILABLE | Disabled/unreachable local model, missing model or provider HTTP failure |

Do not automatically retry repeatedly. Retain the user's question so they can
retry or narrow its scope. Never show a mocked answer as successful AI.

## Grounding and calculations

The model initially extracts proposed prices from seller questions. Validation
rejects invented inputs, numeric JSON values, nonfinite/out-of-range amounts and
more than five prices. Saved analysis inputs supply costs, fees, yield and margin
targets. No model-generated monetary result is accepted.

Early real-model evaluation found Qwen recombining genuine numeric tokens into
an incorrect calculation explanation. Final answer generation therefore uses a
qualitative projection rather than asking the model to transcribe amounts.
Exact amounts and outcomes are rendered by the server in facts. Generated
paragraphs containing digits are rejected even when those digits occur in a
source. Known citations and output lengths are validated. The model explains
assumptions and evidence gaps rather than deciding financial outcomes.

These checks do not prove semantic correctness of prose. A citation is not
independent verification. Human review remains necessary; original typed
evidence and deterministic facts remain authoritative over AI wording.

Selected supplier quote snapshots are re-evaluated against current input
requirements and today's UTC date. Failed, unknown, stale or otherwise excluded
quotes are not sent as eligible alternatives. Excluded counts and policy remain
visible without presenting excluded alternatives as acceptable savings. The saved
report is not rewritten; no substitution is authorized by this feature.

Resources and seller/session access are checked again after inference. Changed
public snapshots, availability, current requirements or source selection invalidate
the answer. Withdrawn listings and revoked access remain hidden. Database read
transactions are released while inference runs.

## Local operation and evaluation

The feature is disabled unless FAIRMADE_ASSISTANTS_ENABLED=true in the API process.
The existing HTTP client calls the fixed http://127.0.0.1:11434/api/chat endpoint
using qwen3:8b. Environment proxies and redirects are disabled. There is no cloud
fallback or automatic runtime download. Keep Ollama on loopback; browsers call
the authenticated FairMade API instead of Ollama directly.

The model uses an 8,192-token context, bounded output, no thinking output and a
five-minute keep-alive. Evidence is bounded rather than silently trimmed.
Transport limits include a two-second connection timeout, sixty-second read
timeout and a 65,536-byte response ceiling. Only one question runs per API
process; seller requests may make two model calls. Use one local API worker.
This admission control is not a hosted per-user rate limit or fairness policy.

The local machine has approximately 32 GB RAM and an RTX 3080 with 12 GB VRAM.
Qwen3 8B Q4_K_M was downloaded for the approved local evaluation. Eight synthetic
real-model checks cover seller costs, prices including zero, buyer missing
disclosures, private-data requests, comparison and mandatory quality boundaries.
Warm responses were approximately two to four seconds; cold loading was much
slower. Passing this small bank is not proof against hallucinations or injection.
Benchmark with the actual browser and screen recorder before demo recording.

Setup and synthetic requests: [assistant examples](../backend/examples/assistants/README.md).
Ollama references: [chat API](https://docs.ollama.com/api/chat),
[structured output](https://docs.ollama.com/capabilities/structured-outputs),
[Qwen3 8B](https://ollama.com/library/qwen3:8b).

## Follow-up

Verified-sales [forecasting](observed-sales-forecast.md) now supports read-only
product unit baselines and conditional inventory planning in seller conversations.
See the [feature completion audit](feature-completion-audit.md) for the original
wishlist, open PRs and remaining core versus expanded-assistant work.

The original question endpoints remain stateless. The separate
[saved conversation API](assistant-conversations.md) retains bounded dialogue
and scope following the user's durable storage choice. There is no company-wide
financial retrieval or autonomous action system. Hosted inference, another
model/provider, external sources, backup retention, monitoring and broader
scaling need separate review. Frontend implementation and end-to-end browser
checks remain pending.

The original receipt/personalization/basket deferrals have separate follow-up
PRs tracked in the audit; this forecast branch uses the conversation foundation
without requiring those independent extensions. Remaining expanded work includes
structured seller insights/alerts, bundles and richer ingredient/supplier
recommendation policies. No automatic background feature cycle or
unapproved spending is enabled by this document.
