# Synthetic manual seller review

Use the feature backend migrated through 0019 and the same explicit database URL
for the API and operator command. Register a dedicated reviewer account and a
separate buyer applicant normally; do not put credentials in Git or command history.
The first administrator is provisioned by the local database operator only:

```powershell
python -m fairmade.admin_bootstrap --account-id $initialAdminAccountId --reason 'Synthetic local reviewer setup'
```

Older sessions for that account are revoked; log in again to obtain `$adminHeaders`.
`$applicantHeaders` belongs to the separate buyer. These are bearer-header objects,
never URL tokens. Do not run bootstrap against a shared/production DB as a test.

```powershell
$base = 'http://127.0.0.1:8000'
$application = Invoke-RestMethod "$base/api/v1/seller-applications" -Method Post -Headers $applicantHeaders -ContentType 'application/json' -Body '{}'
$queue = Invoke-RestMethod "$base/api/v1/admin/seller-applications?state=pending&limit=20&offset=0" -Headers $adminHeaders
$record = Invoke-RestMethod "$base/api/v1/admin/seller-applications/$($application.id)" -Headers $adminHeaders
# Perform the manual review first. Reason is shared with the applicant.
$body = @{
    expected_revision = $record.revision
    outcome = 'approved'
    reason = 'Synthetic local manual review completed.'
} | ConvertTo-Json
Invoke-RestMethod "$base/api/v1/admin/seller-applications/$($application.id)/decision" -Method Post -Headers $adminHeaders -ContentType 'application/json' -Body $body
Invoke-RestMethod "$base/api/v1/seller-applications/me" -Headers $applicantHeaders
Invoke-RestMethod "$base/api/v1/auth/me" -Headers $applicantHeaders
```

Use denied instead of approved for a denial; it grants no seller access. Exact
decision retry preserves the recorded outcome; a conflicting decision is rejected.
An admin cannot decide the application on the same account. There is no automatic
reapplication, decision overwrite, generic role-grant or further-admin command.
Approval preserves buyer capabilities and does not publish products or certify
identity/quality. See [the contract and future plans](../../../docs/manual-seller-review.md).
