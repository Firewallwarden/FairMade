# Synthetic supplier comparisons

All supplier names, places, prices, availability and claims here are fictional
development data. No source or certification is verified. The API stores source
references as plain text and does not fetch external content.

Run migration 0011 using the backend's documented upgrade command. These
PowerShell examples run from the feature worktree root and assume an existing
owned product, `$api = 'http://127.0.0.1:8000/api/v1'` and an authenticated
verified seller's `$authHeaders`. General registration still creates buyers;
these examples do not grant seller access. See the
[account workflow](../seller-workflow.md) and
[full supplier API contract](../../../docs/api-contract.md#private-supplier-sourcing-and-comparisons).

## Record an input and its requirements

Requirements belong to the particular ingredient/material. They do not replace
the finished product's separate Quality Locks.

```powershell
$inputsUrl = "$api/products/$($product.id)/sourcing-inputs"
$inputBody = @{ label = 'Bread flour' } | ConvertTo-Json
$sourcingInput = Invoke-RestMethod -Method Post -Uri $inputsUrl -Headers $authHeaders -ContentType 'application/json' -Body $inputBody
$inputUrl = "$inputsUrl/$($sourcingInput.id)"
$ruleBody = @{
    expected_revision = $sourcingInput.rule_revision
    rules = @(@{ key = 'organic'; label = 'Organic claim'; type = 'boolean'; expected = $true })
} | ConvertTo-Json -Depth 10
$sourcingInput = Invoke-RestMethod -Method Put -Uri "$inputUrl/quality-locks" -Headers $authHeaders -ContentType 'application/json' -Body $ruleBody
```

The example rule checks a supplied claim only. A match is not proof of organic
certification. Without configured requirements, all quotes remain not_evaluated
and are excluded from eligible cost summaries.

## Record two explicitly synthetic quotes

```powershell
$quoteBody = Get-Content -Raw backend/examples/suppliers/flour-quote.json | ConvertFrom-Json
# Refresh only this fictional fixture to exercise a fresh comparison.
$quoteBody.observed_on = [DateTime]::UtcNow.ToString('yyyy-MM-dd')
$quotesUrl = "$inputUrl/supplier-quotes"
$firstQuote = Invoke-RestMethod -Method Post -Uri $quotesUrl -Headers $authHeaders -ContentType 'application/json' -Body ($quoteBody | ConvertTo-Json -Depth 10)

$quoteBody.supplier_name = 'Synthetic lower-price alternative'
$quoteBody.package_price = '8.00'
$quoteBody.claims.organic.value = $false
$secondQuote = Invoke-RestMethod -Method Post -Uri $quotesUrl -Headers $authHeaders -ContentType 'application/json' -Body ($quoteBody | ConvertTo-Json -Depth 10)
Invoke-RestMethod -Uri "$($quotesUrl)?limit=20&offset=0" -Headers $authHeaders
```

Use real observation dates for actual seller-entered evidence. Prices are per
whole package; usable_fraction accounts for the seller's reported loss/waste.
transport_cost is a flat charge for this input's purchase, not per package.
Supply an explicit '0.00' for no transport charge, or null if unknown. Record a
bulk tier as a separate quote with its own package minimum and optional maximum.

## Compare and retain history

```powershell
$reportBody = @{
    quote_ids = @($firstQuote.id, $secondQuote.id)
    expected_rule_revision = $sourcingInput.rule_revision
    required_quantity = @{ value = '9'; unit = 'kg' }
    max_age_days = 30
} | ConvertTo-Json -Depth 10
$reportsUrl = "$inputUrl/supplier-comparisons"
$report = Invoke-RestMethod -Method Post -Uri $reportsUrl -Headers $authHeaders -ContentType 'application/json' -Body $reportBody
$report.result | ConvertTo-Json -Depth 20
Invoke-RestMethod -Uri "$reportsUrl/$($report.id)" -Headers $authHeaders
Invoke-RestMethod -Uri "${reportsUrl}?limit=20&offset=0" -Headers $authHeaders
```

The first quote needs three packages: $36 merchandise + $4 transport = $40 cash
outlay for 12 usable kg, including 3 kg surplus. Its cost per usable kg is
$3.333333. The cheaper quote fails the mandatory claim requirement and is
excluded from both minima. Its computed cost stays visible alongside the failure.

Report rows also exclude unknown claims, no requirements, stale/expired quotes,
unknown/unavailable stock, unknown transport, incompatible dimensions and
insufficient package caps. All inputs remain unverified. Units are g/kg, ml/l,
or item; mass and volume never convert into one another.

Changing requirements needs the latest expected_revision. A stale replacement
or report returns 409 REVISION_CONFLICT; reload the input and review its rules
before retrying. Saved reports preserve their exact rules, quotes and results.
Create a new quote to correct evidence and a new report to reassess it. There are
no quote/report update/delete routes. Reports do not alter recipes, pricing,
Passports or inventory and do not recommend a substitution.
