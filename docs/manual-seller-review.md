# Manual seller application review: local MVP

The user approved manual administrator review with approve/deny outcomes, a
recorded reason and an audit trail. This is an access decision, not identity,
business, food-safety or product-quality certification. Document verification,
external checks and production onboarding standards remain undecided future work.
Backend implementation is proposed for frontend integration; no UI is included.

## Roles and workflow

1. General accounts still register as buyer. POST /api/v1/seller-applications with
   an empty JSON object records intent only; it cannot grant any role. Applications
   begin pending at revision1. GET its /me subpath returns only the caller's record.
2. A separately provisioned administrator can browse the pending queue, inspect
   an application, and submit one final approved/denied outcome with the expected
   revision and a nonempty reason. The administrator performs manual evaluation
   outside this API; the app does not invent verification evidence or criteria.
3. Approval atomically records the decision and grants seller while retaining
   buyer. Denial records the outcome without granting access. An administrator
   cannot decide the application on their own account. Existing seller access on
   a pending application is reported as a conflict, not backfilled as a new grant.
4. Application status, revision, immutable decision and role grant commit in one
   serialized transaction. Competing decisions cannot both win. Matching retries
   return the original outcome without another record or re-granting a subsequently
   removed role. Conflicting/revised decisions are rejected, including denial after
   approval. Reapplication/appeal/revocation needs a separate future policy.
5. Applicants see the final outcome, shared reason, timestamp and
   manual_administrator_review basis. They never see reviewer account IDs or the
   administrator queue. Reason is deliberately applicant-visible, not an internal
   investigation note. Do not put confidential third-party information in it.

No account, role, decision, storefront or public listing is automatically created
by migration. Existing role grants remain as they were; no historical approval
evidence is fabricated. Admin alone still does not confer seller access. Public
Passports/listings/quality claims retain their existing consent and evidence labels.

## First administrator: local operator command

There is no HTTP bootstrap, signup role field, development bypass or generic role
grant endpoint. A trusted operator with access to the configured local database
can provision the **first** administrator on an existing registered account:

```powershell
# Run from the feature backend, using its configured environment/interpreter.
# Use exactly the same explicit database URL as the local API server.
# $initialAdminAccountId is the UUID of a dedicated registered reviewer account.
python -m fairmade.admin_bootstrap --account-id $initialAdminAccountId --reason 'Synthetic local reviewer setup'
```

This is an intentional privileged database operation; never run it automatically
at startup. Migrate through 0019 first. The command adds only admin, preserves
buyer, records the operator-provisioned target/reason/time in a singleton audit
record, and revokes that account's older sessions. Sign in again afterward.
It does not take passwords/tokens, create accounts, approve sellers or grant seller.
Arguments/reasons must contain no secrets or private documents.

Once any administrator exists or bootstrap was recorded, it cannot provision a
different administrator. Exact target retries are a no-op while the original grant
still exists; they do not rewrite the reason or revoke newly issued sessions.
It cannot silently restore a revoked grant. Parallel initial attempts produce
one grant/audit. Record/role/session changes roll back together on failure.
Expected errors do not print submitted reasons or SQL/credential details.

Use a dedicated reviewer account separate from seller applicants. The self-review
guard is account-based; it is not proof of separate real-world identities.
Additional administrators and privileged recovery are deliberately not available
through this first-admin command. Hosted deployment needs a separately reviewed
provisioning/recovery and administrator-security design.

## HTTP contract

| Method/path | Input | Success |
| --- | --- | --- |
| GET /api/v1/admin/seller-applications | state, limit, offset | Page of AdminApplication |
| GET /api/v1/admin/seller-applications/{application_id} | None | AdminApplication |
| POST /api/v1/admin/seller-applications/{application_id}/decision | DecisionRequest | AdminApplication |

All require a current server-stored admin grant. Buyer/seller-only accounts get
403 ADMIN_REQUIRED, missing/revoked sessions401, missing applications404. State
filter is pending (default), approved, denied or all. Queue order is oldest
submission then UUID ascending; existing bounded limit/offset pagination applies.
The query joins applicant email and decision data without per-row account lookups.

DecisionRequest is `{expected_revision, outcome, reason}`: revision uses existing
strict positive publication revision bounds; outcome approved/denied; reason is
trimmed, 1..2000 characters, without NUL. Extra fields such as role, status or actor
are rejected; validation errors omit raw input. Decisions recheck administrator
access under the write lock. No email, role or actor ID is taken from the body.

SellerApplication responses add revision and nullable decision. Status may now be
pending/approved/denied. The original id/submitted_at are preserved. Decision fields
are outcome, reason, created_at UTC and basis=manual_administrator_review. Admin
responses additionally expose applicant_account_id, applicant_email and nullable
decided_by_account_id for operational review/audit; they expose no passwords,
sessions, private economics or payment data. Applicant responses omit those admin
fields. Successful private reads/writes and domain/validation errors use no-store.

Application submission remains retry-safe. A denied application's repeated POST
returns the same denied record; it does not reopen it. An approved seller receives
the existing ALREADY_SELLER conflict when submitting. GET /me remains available to
read their decision. Existing sessions obtain additive seller access on subsequent
requests because authorization reads server roles; admin bootstrap specifically
revokes older sessions due to its higher privilege.

Application review errors use existing detail/code shape: 403 SELF_REVIEW_FORBIDDEN,
409 REVISION_CONFLICT, DECISION_ALREADY_RECORDED, SELLER_ALREADY_GRANTED or
APPLICATION_NOT_PENDING. There is no decision edit/delete or role-revocation API.

## Migration and future work

Migration 0019 preserves pending application IDs/account links/timestamps, widens
status values, adds revision1, and creates decision/bootstrap audit tables. It does
not grant roles. SQLite recreates only the small application table before adding
incoming decision references. Downgrade preflights audits, non-pending/revised
applications and earlier protected records before DDL. Empty/pending-only schemas
can roundtrip; recorded decisions/bootstrap cannot be discarded through downgrade.

Before production, decide and implement verification criteria/evidence, document
consent/access/retention, reviewer responsibilities, separation of duties, step-up
authentication/MFA, additional-admin management and recovery, audit monitoring,
revocation/suspension/reverification, denial appeals/reapplication and operational
recovery. Keep administrative access approval distinct from certifications. External
providers, infrastructure, notifications and a frontend admin dashboard need their
own approved scope; this slice sends no messages or collects documents.
