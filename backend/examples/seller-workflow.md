# Local seller workflow

All product and pricing examples are synthetic development data, not market
evidence. Run the migrations and server as described in the backend README first.
These PowerShell commands run from the feature worktree root.

Read development credentials interactively so no password is placed in source
control. Use disposable local credentials.

```powershell
$api = 'http://127.0.0.1:8000/api/v1'
$localCredential = Get-Credential -Message 'Local FairMade email and password (12-128 characters)'
$credentialBody = @{
    email = $localCredential.UserName
    password = $localCredential.GetNetworkCredential().Password
} | ConvertTo-Json

$seller = Invoke-RestMethod -Method Post -Uri "$api/auth/register" -ContentType 'application/json' -Body $credentialBody
$login = Invoke-RestMethod -Method Post -Uri "$api/auth/login" -ContentType 'application/json' -Body $credentialBody
$authHeaders = @{ Authorization = "Bearer $($login.access_token)" }
Remove-Variable credentialBody, localCredential

$product = Invoke-RestMethod -Method Post -Uri "$api/products" -Headers $authHeaders -ContentType 'application/json' -Body (Get-Content -Raw backend/examples/product-request.json)
$historyUrl = "$api/products/$($product.id)/analyses"
$saved = Invoke-RestMethod -Method Post -Uri $historyUrl -Headers $authHeaders -ContentType 'application/json' -Body (Get-Content -Raw backend/examples/pricing-request.json)
$saved.result.costs
Invoke-RestMethod -Uri $historyUrl -Headers $authHeaders
Invoke-RestMethod -Uri "$historyUrl/$($saved.id)" -Headers $authHeaders

Invoke-RestMethod -Method Post -Uri "$api/auth/logout" -Headers $authHeaders
Remove-Variable login, authHeaders
```

For an existing account, skip registration. Login returns a token and UTC
expiry timestamp. HTTP 401 after logout or expiry requires another login.
No browser storage or automatic token renewal is provided by this backend.
