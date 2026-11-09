# Synthetic material inventory workflow

Use an approved seller account, a backend migrated through 0021 and the configured
environment. Run from the feature worktree root. The material, quantities and
reasons below are invented development data, not purchase or availability evidence.
$authHeaders is the seller's bearer-header object from login; never put tokens in
Git, URLs or example files.

```powershell
$api = 'http://127.0.0.1:8000/api/v1'
$material = Invoke-RestMethod "$api/seller/materials" -Method Post -Headers $authHeaders -ContentType 'application/json' -Body (Get-Content -Raw backend/examples/materials/material.json)
$materialUrl = "$api/seller/materials/$($material.id)"
$requestId = [guid]::NewGuid().ToString()
$movementBody = @{
    expected_revision = $material.revision
    request_id = $requestId
    kind = 'receipt'
    quantity = '2.5'
    unit = 'kg'
    occurred_on = [DateTime]::UtcNow.ToString('yyyy-MM-dd')
    reason = 'Synthetic manual test receipt'
} | ConvertTo-Json
$receipt = Invoke-RestMethod "$materialUrl/movements" -Method Post -Headers $authHeaders -ContentType 'application/json' -Body $movementBody
# Matching retry returns the original event without adding stock again.
Invoke-RestMethod "$materialUrl/movements" -Method Post -Headers $authHeaders -ContentType 'application/json' -Body $movementBody
$current = Invoke-RestMethod $materialUrl -Headers $authHeaders
$countBody = @{
    expected_revision = $current.revision
    request_id = [guid]::NewGuid().ToString()
    kind = 'adjustment'
    quantity = '2400'
    unit = 'g'
    occurred_on = [DateTime]::UtcNow.ToString('yyyy-MM-dd')
    reason = 'Synthetic physical count after unrecorded handling loss'
} | ConvertTo-Json
Invoke-RestMethod "$materialUrl/movements" -Method Post -Headers $authHeaders -ContentType 'application/json' -Body $countBody
Invoke-RestMethod "$materialUrl/movements?limit=20&offset=0" -Headers $authHeaders
Invoke-RestMethod $materialUrl -Headers $authHeaders
```

The receipt yields 2500 g; the adjustment sets stock to 2400 g, with delta -100 g.
For explicit usage or waste, quantity is the positive amount removed, not the
new balance. Fetch the latest revision and use a new request ID for every distinct
intentional event. Keep the original ID/body when retrying a transport failure.

No event changes recipe costs, sellable stock, orders or public prices. There is
no valuation, lot or expiry claim. See the [contract and deeper follow-up](../../../docs/manual-material-inventory.md).
