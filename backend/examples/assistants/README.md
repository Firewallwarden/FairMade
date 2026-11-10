# Synthetic local assistant workflow

Use the [backend setup](../../README.md) and create synthetic seller product,
analysis, approved Passport and listing records with the
[marketplace workflow](../marketplace/README.md). These requests do not invent
real costs or market evidence. Use your existing API, product, listing and
authentication variables; never log a bearer token.
The examples use $api as the /api/v1 base URL, $productId as the owned product
UUID, $listingId as the active listing UUID, and $sellerHeaders/$buyerHeaders
as authenticated request headers. After the marketplace example, $product.id,
$listing.id and $authHeaders supply the seller-side values. Stop before its
deactivation step.

## Start local inference

Ollama must be running locally. Download the approved model once:

~~~powershell
ollama pull qwen3:8b
~~~

Enable assistants in the terminal that starts the API:

~~~powershell
$env:FAIRMADE_ASSISTANTS_ENABLED = 'true'
# Run the backend startup command from backend/README.md in this terminal.
~~~

No paid account/API key is used. The API never downloads models on requests.
Unavailable inference returns 503 rather than a fabricated answer.

## Seller question and exact price scenario

~~~powershell
$sellerBody = Get-Content backend/examples/assistants/seller-question.json -Raw | ConvertFrom-Json
$sellerBody.product_id = $productId
# null analysis_id selects the latest saved analysis, identified in evidence.
$sellerResult = Invoke-RestMethod "$api/assistants/seller" -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body ($sellerBody | ConvertTo-Json -Depth 10)
$sellerResult.facts | ConvertTo-Json -Depth 10
$sellerResult.paragraphs | ConvertTo-Json -Depth 10
$sellerResult.notices
~~~

Use a specific saved analysis UUID for reproducible scenarios. Optional
supplier_report_id selects an owned sourcing-input comparison; current
requirements and quote freshness are checked without rewriting the report.
Use explicit numeric prices such as $8, not “increase it a little.”

## Buyer explanation or comparison

~~~powershell
$buyerBody = Get-Content backend/examples/assistants/buyer-question.json -Raw | ConvertFrom-Json
$buyerBody.listing_ids = @($listingId)
# Select up to four distinct currently visible listings to compare disclosures.
$buyerResult = Invoke-RestMethod "$api/assistants/buyer" -Method Post -Headers $buyerHeaders -ContentType 'application/json' -Body ($buyerBody | ConvertTo-Json -Depth 10)
$buyerResult.facts | ConvertTo-Json -Depth 10
$buyerResult.paragraphs | ConvertTo-Json -Depth 10
$buyerResult.evidence | ConvertTo-Json -Depth 20
~~~

Every account can use the buyer assistant. Buyer context never reads private
analyses or private account identities. Missing disclosures do not establish that a cost
was excluded from the price. Facts and AI paragraphs must remain visibly distinct.

## Evaluation before recording

Normal tests use an injected fake model or HTTP mocks; no provider is called.
Run the separate real Qwen evaluation from this checkout using the configured
project interpreter in place of the illustrative python command:

~~~powershell
$env:FAIRMADE_RUN_LOCAL_AI_EVAL = 'true'
python -m pytest -q -s --tb=short -c backend/pyproject.toml backend/tests/assistants/test_local_evaluation.py
Remove-Item Env:FAIRMADE_RUN_LOCAL_AI_EVAL
~~~

Evaluation uses temporary migrated databases and synthetic accounts/data, prints
synthetic paragraphs and warm response times, and does not touch your working
database. Review prose as well as assertions. Passing this small bank is not a
guarantee against hallucinations or prompt injection.

For recording, warm the model, rehearse both roles and the actual browser,
display calculated facts and uncertainty notices, and test with the recorder
running. See the [contract and limits](../../../docs/local-assistants.md).
