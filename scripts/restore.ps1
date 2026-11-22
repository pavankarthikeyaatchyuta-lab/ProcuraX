param([Parameter(Mandatory)][string]$DatabaseDump,[Parameter(Mandatory)][string]$DocumentArchive,[switch]$ConfirmReplace)
$ErrorActionPreference = 'Stop'
if (-not $ConfirmReplace) { throw 'Restore replaces current records. Use a separate Compose project for rehearsal, or pass -ConfirmReplace intentionally.' }
$dump = (Resolve-Path -LiteralPath $DatabaseDump).Path
$archive = (Resolve-Path -LiteralPath $DocumentArchive).Path
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
docker compose stop api worker scheduler web
docker compose cp $dump 'db:/tmp/restore.dump'
docker compose exec -T db pg_restore -U procure -d procurement --clean --if-exists --exit-on-error /tmp/restore.dump
if ($LASTEXITCODE -ne 0) { throw 'Restore failed; services remain stopped' }
docker compose run --rm -v "${archive}:/tmp/documents.tar.gz:ro" api tar -xzf /tmp/documents.tar.gz -C /app/data
if ($LASTEXITCODE -ne 0) { throw 'Document restore failed; inspect before restarting' }
docker compose up -d api worker scheduler web
