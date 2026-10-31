# Synthetic finished-product comparisons

All quotes, seller names, places, prices, dates, and quality claims in these files
are **fictional development examples**. They are not live local prices, verified
sources, or pricing recommendations.

- `bread-observation.json`: an illustrative USD 8 quote for 500 g of finished
  sourdough, normalizing to USD 1.600000 per 100 g.
- `egg-observation.json`: an illustrative USD 6 quote for a dozen finished eggs,
  normalizing to USD 0.500000 per egg.

Run migrations first. Calls require a seller account and its owned product;
normal registration remains buyer-only and verification/provisioning is deferred.
Automated tests use synthetic seller grants; these examples do not grant roles.

Using an existing owned sourdough product and a local authenticated context:

```powershell
$observationsUrl = "$api/products/$($product.id)/price-observations"
$body = Get-Content -Raw backend/examples/comparisons/bread-observation.json | ConvertFrom-Json
# For this synthetic test only, use today's UTC date to exercise fresh evidence.
$body.observed_on = [DateTime]::UtcNow.ToString('yyyy-MM-dd')
$observation = Invoke-RestMethod -Method Post -Uri $observationsUrl -Headers $authHeaders -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 10)
Invoke-RestMethod -Uri $observationsUrl -Headers $authHeaders

$comparisonBody = @{
    observation_ids = @($observation.id)
    target_quantity = @{ value = '100'; unit = 'g' }
    max_age_days = 30
} | ConvertTo-Json -Depth 10
$reportsUrl = "$api/products/$($product.id)/price-comparisons"
$report = Invoke-RestMethod -Method Post -Uri $reportsUrl -Headers $authHeaders -ContentType 'application/json' -Body $comparisonBody
$report.result.selected_price_range
$report.result.rows
$report.result.warnings
Invoke-RestMethod -Uri "$reportsUrl/$($report.id)" -Headers $authHeaders
```

For eggs, use an owned egg product, the egg observation file, and target quantity
`{value: "1", unit: "egg"}`. The fixed JSON example date is intentional: without
the synthetic date adjustment, it may be flagged stale.

Use actual observation dates for real seller-entered evidence; never change them
to make a quote appear fresh. Source references are stored as plain text, not
retrieved or verified. Put taxes, delivery costs, discounts, package-size
differences, and uncertainty in the notes. These details remain visible and are
not reconciled by the numerical comparison.

Select only the observation IDs you intend to compare. IDs from another product
or seller return 404. Duplicate IDs and malformed inputs return 422.
Observations and reports are immutable; correcting evidence means adding another
observation and selecting it in a new report. No quote is automatically chosen as
an acceptable alternative, even if it is cheaper or appears within the range.
