# Operations

## Health and jobs

`GET /api/v1/health` checks the database and Redis and reports provider/scanner configuration, without secrets. `docker compose ps` checks container health. Use Activity for failed processing jobs and safe errors. Upload failures preserve existing data. Restore failed services before explicitly retrying. Zoho draft retries reconcile uncertain attempts; they do not blindly resend requests.

The single scheduler checks hourly Zoho sync eligibility and document retention every minute. Run exactly one scheduler. RQ persists queued jobs in Redis; configure host monitoring for worker exit, Redis availability, scanner health, job failures and stale sync. Unexpected worker termination can leave a job marked running; inspect the external outcome before an operator resets or recreates a job. Never reset an uncertain order attempt to pending merely to retry.

## Backups and restore

Use an encrypted destination. The backup script stops running web/API/worker/scheduler services for a consistent database/document snapshot, then restarts the services that were running:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup.ps1 -Destination D:\EncryptedBackups\Vyaya
```

`backup.ps1` exports a PostgreSQL custom-format dump and a private-document archive. Keep `TOKEN_ENCRYPTION_KEY` separately in encrypted storage. Verify SHA-256 hashes after copying backups off the host. Retain daily encrypted backups for 30 days by default; operators are responsible for expiring copies on removable/offline media.

Restore only during a controlled maintenance window. The script stops writer services, restores database records and extracts originals, then restarts services. For a clean rehearsal, use a separate workspace/Compose project with fresh volumes and the same encryption key; do not point it at the live Zoho organization or start its scheduler. Set its client credentials blank to prevent provider calls.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore.ps1 -DatabaseDump D:\EncryptedBackups\Vyaya\database-TIMESTAMP.dump -DocumentArchive D:\EncryptedBackups\Vyaya\documents-TIMESTAMP.tar.gz -ConfirmReplace
```

Verify sign-in, tenant/product counts, a downloaded original's SHA-256, purchase evidence and an approved basket after every restore rehearsal. A database-only restore does not restore documents. An archive-only restore does not restore approval state or credentials.

## Privacy and retention

Business settings determine original-document retention. The scheduler removes expired originals and records a retention event; normalized financial/decision evidence remains until explicit business deletion. Business exports contain records and document metadata, not credentials or binary originals; use backup tooling for originals.

Owner deletion requires typing the business name and no active processing job. It removes active business records and originals. Backups are independent copies; they expire according to the 30-day operational policy. When restoring an old backup, reapply deletions and retention before allowing users or integrations access. Document subprocessors and purposes before real-business onboarding. The EU OCR consent is separate from other permissions. Shared model training, cross-shop sharing and bank access are disabled.

## Incident response

1. Stop web/API/worker/scheduler if tenant isolation, credentials or write behavior is suspect; preserve encrypted database and logs.
2. Revoke compromised Zoho refresh tokens/service-account keys and app sessions. Disable the affected provider until the cause is known.
3. Check append-only application audit events, job state and unique PO references. Reconcile actual Zoho orders before any retry.
4. Restore verified backups into an isolated environment if data integrity is affected. Run integrity/security tests and document affected businesses/records.
5. Assess notification obligations with the business owner and qualified advisers based on the incident and applicable rules. Resume only after the cause is fixed and recovery verified.

For password/MFA recovery, use the CLI from the trusted host; never expose it as a public endpoint. Encryption-key rotation requires decrypting and re-encrypting saved MFA/OAuth secrets with both keys available; changing the environment variable alone is not rotation. Reconnect integrations and re-enroll MFA if the old key is lost.

## Limits

Local HTTP is intended for localhost. Require HTTPS and `COOKIE_SECURE=true` if serving over a network. The app provides session/role/tenant controls; the local database/files and Docker administrator remain trusted. Audit events cannot be edited through application endpoints; a host/database administrator can still alter storage. Backups and host encryption are operational requirements.
