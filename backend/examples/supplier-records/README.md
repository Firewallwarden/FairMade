# Synthetic private supplier records

Use the [backend setup](../../README.md) and migrations. Run from a feature
checkout root with a verified seller's bearer headers in $sellerHeaders; do not
print the token. These are synthetic private business records, not community
ratings. Keep a submitted request ID/body for retries and use new IDs for new work.

```powershell
$api = 'http://127.0.0.1:8000/api/v1/seller/suppliers'
$profileBody = Get-Content backend/examples/supplier-records/profile.json -Raw
$registered = Invoke-RestMethod $api -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body $profileBody
$supplier = $registered.after
$experienceBody = Get-Content backend/examples/supplier-records/experience.json -Raw | ConvertFrom-Json
$experienceBody.expected_supplier_revision = $supplier.revision
$saved = Invoke-RestMethod "$api/$($supplier.id)/experiences" -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body ($experienceBody | ConvertTo-Json -Depth 10)
# Optional source_quote_id must identify an existing quote belonging to this seller.
Invoke-RestMethod "$api/$($supplier.id)/reliability" -Headers $sellerHeaders
Invoke-RestMethod "$api/$($supplier.id)/experiences?observed_from=2025-05-01&observed_until=2025-05-31" -Headers $sellerHeaders

# Correct the opinion; retain the original report and its supplier/quote snapshots.
$correction = Get-Content backend/examples/supplier-records/experience.json -Raw | ConvertFrom-Json
$correction.request_id = [guid]::NewGuid().ToString()
$correction.expected_supplier_revision = $saved.supplier_revision
$correction.rating = 3
$correction | Add-Member -NotePropertyName corrects_experience_id -NotePropertyValue $saved.id
$correction | Add-Member -NotePropertyName correction_reason -NotePropertyValue 'Synthetic opinion correction'
Invoke-RestMethod "$api/$($supplier.id)/experiences" -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body ($correction | ConvertTo-Json -Depth 10)
Invoke-RestMethod "$api/$($supplier.id)/experiences?include_corrected=true" -Headers $sellerHeaders
```

The first report gives a four-star opinion and one reported timely delivery.
Correcting the score changes the current average to three stars without adding
another shipment to the denominator. Missing delivery dates remain unknown;
none of these scores approves a Quality Lock or verifies supplier availability.
Quotes, comparisons, recipes, stock, prices and payments remain unchanged. Read
the [full private contract](../../../docs/private-supplier-reliability.md) before
integration. A frontend should render supplier text as untrusted plain text and
keep this history confined to its owning account.
