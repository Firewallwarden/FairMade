# Synthetic Quality Lock examples

All names, requirements, durations, product specifications, welfare claims, and
alternative claims here are **fictional development inputs**. They are not
recommended quality/safety standards or verified product information. The backend
does not supply default rules; each seller chooses their own mandatory requirements.

- `sourdough-locks.json` demonstrates boolean, choice, and numeric rules.
- `sourdough-candidate.json` matches all three with unverified claims.
- `egg-locks.json` demonstrates a seller-defined welfare lock and size choices.
- `egg-candidate.json` fails the welfare lock and must return a failed overall check.

Run migrations before starting the local API. These calls require an account
already holding seller access and a product it owns. Role grants and seller
verification are deferred; normal registration remains buyer-only. Automated tests
seed synthetic seller grants to cover this flow. These examples do not grant access.

With `$api`, `$authHeaders`, and an existing owned `$product.id` available
from your local integration context, run from the feature worktree root:

```powershell
$locksUrl = "$api/products/$($product.id)/quality-locks"
$current = Invoke-RestMethod -Uri $locksUrl -Headers $authHeaders
$lockBody = Get-Content -Raw backend/examples/quality/sourdough-locks.json | ConvertFrom-Json
$lockBody.expected_revision = $current.revision
$installed = Invoke-RestMethod -Method Put -Uri $locksUrl -Headers $authHeaders -ContentType 'application/json' -Body ($lockBody | ConvertTo-Json -Depth 10)

$checksUrl = "$api/products/$($product.id)/quality-evaluations"
$candidateBody = Get-Content -Raw backend/examples/quality/sourdough-candidate.json | ConvertFrom-Json
$candidateBody.expected_revision = $installed.revision
$saved = Invoke-RestMethod -Method Post -Uri $checksUrl -Headers $authHeaders -ContentType 'application/json' -Body ($candidateBody | ConvertTo-Json -Depth 10)
$saved.status
$saved.basis
$saved.checks
Invoke-RestMethod -Uri $checksUrl -Headers $authHeaders
Invoke-RestMethod -Uri "$checksUrl/$($saved.id)" -Headers $authHeaders
```

For eggs, use the egg files and a separate owned egg product. Always use the
revision you reviewed; do not automatically resubmit stale changes after a 409.
Reload and review the current rules before retrying.

Every evaluation is immutable. Editing or clearing the current rules never
changes previous checks. Repeating a successful evaluation POST creates another
record. A pass means only that all supplied claims match the configured rules,
with exact units and no source verification. Unknown/failed/not-evaluated results
cannot establish compliance. No status is a recommendation to use an alternative.
