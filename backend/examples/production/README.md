# Synthetic completed production workflow

[bread.json](bread.json) and [eggs.json](eggs.json) contain invented dates, output
and costs, not local prices or verified expenses. Use an approved seller account
and backend migrated through 0022, from the feature worktree root with its environment.

$productId is an owned product whose selling unit is loaf (bread) or dozen (eggs).
$authHeaders is the seller's bearer-header object. Keep tokens out of files, Git
and URLs. Counts use that exact unit, never implicit conversions.

```powershell
$api = 'http://127.0.0.1:8000/api/v1'
$recordsUrl = "$api/products/$productId/production-records"
$body = Get-Content -Raw backend/examples/production/bread.json | ConvertFrom-Json
$body.request_id = [guid]::NewGuid().ToString()
$requestJson = $body | ConvertTo-Json -Depth 10
$record = Invoke-RestMethod $recordsUrl -Method Post -Headers $authHeaders -ContentType 'application/json' -Body $requestJson
# Keep the same body/key when retrying a transport failure.
Invoke-RestMethod $recordsUrl -Method Post -Headers $authHeaders -ContentType 'application/json' -Body $requestJson
$body.request_id = [guid]::NewGuid().ToString()
$body.sellable_units = 8
$body | Add-Member -NotePropertyName corrects_record_id -NotePropertyValue $record.id
$body | Add-Member -NotePropertyName correction_reason -NotePropertyValue 'Synthetic correction after output recount'
Invoke-RestMethod $recordsUrl -Method Post -Headers $authHeaders -ContentType 'application/json' -Body ($body | ConvertTo-Json -Depth 10)
Invoke-RestMethod $recordsUrl -Headers $authHeaders
Invoke-RestMethod "$($recordsUrl)?include_corrected=true&limit=20&offset=0" -Headers $authHeaders
Invoke-RestMethod "$recordsUrl/$($record.id)" -Headers $authHeaders
```

The initial bread report costs 45.30 total and 4.53 per sellable loaf; the corrected
eight-loaf yield costs 5.662500 per loaf, preserving the earlier report. Zero sellable
output is valid with costs and null unit cost.

This records completion, not a plan or stock movement. See the
[contract and optional future workflow](../../../docs/completed-production-records.md).
