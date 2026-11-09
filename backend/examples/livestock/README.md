# Synthetic livestock workflow

Run migrations and the API as described in the [backend setup](../../README.md).
Use a verified seller's bearer headers in $sellerHeaders; do not log the token.
Execute from the feature checkout root. All examples are synthetic seller reports.
Fixed example request IDs deliberately demonstrate retries; use new IDs for new
changes and retain a submitted ID/body for retries.

```powershell
$api = 'http://127.0.0.1:8000/api/v1'
$groupBody = Get-Content backend/examples/livestock/group.json -Raw | ConvertFrom-Json
$groupEvent = Invoke-RestMethod "$api/seller/livestock/groups" -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body ($groupBody | ConvertTo-Json -Depth 10)
$group = $groupEvent.after
$animalBody = Get-Content backend/examples/livestock/animal.json -Raw | ConvertFrom-Json
$animalBody.group_id = $group.id
$animalEvent = Invoke-RestMethod "$api/seller/livestock/animals" -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body ($animalBody | ConvertTo-Json -Depth 10)
$animal = $animalEvent.after
# The profile reports 30 observed animals and one registered individual, not 31.
Invoke-RestMethod "$api/seller/livestock/groups/$($group.id)" -Headers $sellerHeaders

$productBody = @{name='Synthetic eggs'; product_type='eggs'; selling_unit='dozen'}
$product = Invoke-RestMethod "$api/products" -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body ($productBody | ConvertTo-Json)
$productionBody = Get-Content backend/examples/livestock/production.json -Raw | ConvertFrom-Json
$productionBody | Add-Member -NotePropertyName livestock_source -NotePropertyValue @{kind='group'; id=$group.id; expected_revision=$group.revision}
$record = Invoke-RestMethod "$api/products/$($product.id)/production-records" -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body ($productionBody | ConvertTo-Json -Depth 10)
# One source per report. Select kind='animal' only for measured individual output.
Invoke-RestMethod "$api/seller/livestock/groups/$($group.id)/production-records" -Headers $sellerHeaders

# Explicitly move this individual out; the observed flock count is unchanged.
$replacement = @{
  request_id=[guid]::NewGuid().ToString(); expected_revision=$animal.revision
  occurred_on=[datetime]::UtcNow.ToString('yyyy-MM-dd'); reason='Synthetic group departure'
  identifier=$animal.identifier; name=$animal.name; breed=$animal.breed; sex=$animal.sex
  born_on=$animal.born_on; acquired_on=$animal.acquired_on
  status='active'; group_id=$null; notes=$animal.notes
}
Invoke-RestMethod "$api/seller/livestock/animals/$($animal.id)" -Method Put -Headers $sellerHeaders -ContentType 'application/json' -Body ($replacement | ConvertTo-Json -Depth 10)
Invoke-RestMethod "$api/seller/livestock/animals/$($animal.id)/history" -Headers $sellerHeaders
# Earlier report source snapshots remain unchanged.
Invoke-RestMethod "$api/products/$($product.id)/production-records/$($record.id)" -Headers $sellerHeaders
```

Reported dates do not establish historical group membership. Output units are
whole dozens in this example; there is no automatic egg conversion. The sample
reports $60 allocated cost and a six-place unit cost of $4.285714 per sellable
dozen. It changes no inventory or prices, certifies no quality, and publishes
nothing. See the [contract and limits](../../../docs/livestock-tracking.md).
