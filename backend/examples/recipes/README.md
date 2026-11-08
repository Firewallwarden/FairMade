# Synthetic manual recipe workflow

All amounts, quantities and dates in [sourdough.json](sourdough.json) and
[eggs.json](eggs.json) are invented test data, not market or purchase evidence.
Use the backend migrated through 0020, the configured environment and an approved
seller account. Run the commands from the feature worktree root.

$productId is an owned product UUID; $authHeaders contains the seller's bearer
header from login. Neither tokens nor credentials belong in Git or URLs.
For the egg example, use an egg product whose selling unit is dozen: yield 24
means 24 dozens, while ingredient units describe consumed feed separately.

```powershell
$api = 'http://127.0.0.1:8000/api/v1'
$recipeUrl = "$api/products/$productId/recipe"
$body = Get-Content -Raw backend/examples/recipes/sourdough.json
$recipe = Invoke-RestMethod $recipeUrl -Method Post -Headers $authHeaders -ContentType 'application/json' -Body $body
$requestId = [guid]::NewGuid().ToString()
$costingBody = @{
    expected_revision = $recipe.revision
    request_id = $requestId
} | ConvertTo-Json
$costing = Invoke-RestMethod "$recipeUrl/costings" -Method Post -Headers $authHeaders -ContentType 'application/json' -Body $costingBody
Invoke-RestMethod "$api/products/$productId/analyses/$($costing.pricing_analysis_id)" -Headers $authHeaders
# Reuse this body after a transport failure; do not generate a new request ID.
Invoke-RestMethod "$recipeUrl/costings" -Method Post -Headers $authHeaders -ContentType 'application/json' -Body $costingBody
Invoke-RestMethod "$recipeUrl/costings?limit=20&offset=0" -Headers $authHeaders
$updated = $body | ConvertFrom-Json
$updated | Add-Member -NotePropertyName expected_revision -NotePropertyValue $recipe.revision
$updated.name = 'Synthetic revised bread recipe'
Invoke-RestMethod $recipeUrl -Method Put -Headers $authHeaders -ContentType 'application/json' -Body ($updated | ConvertTo-Json -Depth 10)
```

A PUT replaces the whole current recipe; stale revisions return 409. Saved costing
and analysis snapshots retain earlier costs/instructions. Pricing review, selected
sales cost basis and Passport approval remain explicit separate actions.

Costing does not buy packages, consume stock, record production, select supplier
quotes or change public prices. See the [full contract and production follow-up](../../../docs/manual-recipe-costing.md).
