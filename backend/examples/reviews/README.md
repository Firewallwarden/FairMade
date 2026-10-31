# Synthetic seller pricing review

The UUIDs in request.json are placeholders, not existing records. Replace them
with explicitly selected records from the same owned product. All examples in
this repository are synthetic development inputs, not verified costs or prices.

Run migrations and use an existing seller account. Seller verification and role
provisioning remain deferred; these examples do not grant access. Tests seed
synthetic seller grants.

For the earlier synthetic bread examples, assuming one production unit represents
500 g is a **seller declaration for this example only**. It is not inferred from
"loaf" and is not a recommended size or standard. Review and confirm your actual
unit basis before submitting.

With existing saved record objects in your local integration context:

```powershell
$body = @{
    pricing_analysis_id = $analysis.id
    comparison_report_id = $comparison.id
    quality_evaluation_ids = @($qualityEvaluation.id)
    production_unit_quantity = @{ value = '500'; unit = 'g' }
} | ConvertTo-Json -Depth 10
$reviewsUrl = "$api/products/$($product.id)/pricing-reviews"
$review = Invoke-RestMethod -Method Post -Uri $reviewsUrl -Headers $authHeaders -ContentType 'application/json' -Body $body
$review.result.explanations
$review.result.warnings
$review.result.market_context
Invoke-RestMethod -Uri $reviewsUrl -Headers $authHeaders
Invoke-RestMethod -Uri "$reviewsUrl/$($review.id)" -Headers $authHeaders
```

To review economics without selected quality or comparison records, submit only
pricing_analysis_id. The result explicitly identifies missing evidence. To keep
comparison context on its original quantity basis, omit production_unit_quantity;
no price relation against production-unit prices will be calculated.

The stored pricing analysis is not recalculated. Its costs, fees, scenarios,
assumptions, and warnings remain intact. A new review rechecks selected quote age
at its own UTC date, but does not rewrite the prior comparison report. Historical
review reads do not reassess evidence.

Quality checks remain unverified and are not automatically tied to quote IDs.
A matching claim is not certification; an outdated or failed evaluation does not
establish current compliance. The report gives no instruction to use a cheaper
alternative or change the seller's price.

These payloads include private seller economics and must not be published as a
Fair Price Passport. Buyer-facing disclosure requires a separate approved policy.
