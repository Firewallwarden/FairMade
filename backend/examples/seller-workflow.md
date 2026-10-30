# Local account and seller-application workflow

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

$account = Invoke-RestMethod -Method Post -Uri "$api/auth/register" -ContentType 'application/json' -Body $credentialBody
$login = Invoke-RestMethod -Method Post -Uri "$api/auth/login" -ContentType 'application/json' -Body $credentialBody
$authHeaders = @{ Authorization = "Bearer $($login.access_token)" }
Remove-Variable credentialBody, localCredential

Invoke-RestMethod -Uri "$api/auth/me" -Headers $authHeaders
# The account starts with roles = ["buyer"].
$application = Invoke-RestMethod -Method Post -Uri "$api/seller-applications" -Headers $authHeaders -ContentType 'application/json' -Body '{}'
Invoke-RestMethod -Uri "$api/seller-applications/me" -Headers $authHeaders
# Submitting again returns the same pending application.
Invoke-RestMethod -Method Post -Uri "$api/seller-applications" -Headers $authHeaders -ContentType 'application/json' -Body '{}'

Invoke-RestMethod -Method Post -Uri "$api/auth/logout" -Headers $authHeaders
Remove-Variable login, authHeaders
```

For an existing account, skip registration. Login returns a token and UTC
expiry timestamp. HTTP 401 after logout or expiry requires another login.
No browser storage or automatic token renewal is provided by this backend.

The application remains pending. Verification criteria, decisions, role grants,
and admin access are deferred; the account cannot enable itself as a seller.
Buyers, pending applicants, and admin-only accounts receive 403 SELLER_REQUIRED
from every private product/history endpoint.

Seller-feature integration tests explicitly seed seller grants and continue to
exercise product creation with [product-request.json](product-request.json),
analysis creation with [pricing-request.json](pricing-request.json), and immutable
history reads. There is no API or development command to grant these privileges.
The stateless pricing endpoint remains available for local calculator testing.
