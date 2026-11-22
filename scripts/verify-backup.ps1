param([string]$Destination)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
if (-not $Destination) { $Destination = Join-Path $root 'data/backup-rehearsal' }
& (Join-Path $PSScriptRoot 'backup.ps1') -Destination $Destination
$dump = Get-ChildItem -LiteralPath $Destination -Filter 'database-*.dump' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$archive = Get-ChildItem -LiteralPath $Destination -Filter 'documents-*.tar.gz' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$testDatabase = 'restore_check_' + (Get-Date -Format 'yyyyMMddHHmmss')
docker compose cp $dump.FullName 'db:/tmp/rehearsal.dump'
docker compose exec -T db createdb -U procure $testDatabase
if ($LASTEXITCODE -ne 0) { throw 'Could not create isolated restore database' }
try {
    docker compose exec -T db pg_restore -U procure -d $testDatabase --exit-on-error /tmp/rehearsal.dump
    if ($LASTEXITCODE -ne 0) { throw 'Isolated restore failed' }
    $query = 'SELECT (SELECT count(*) FROM businesses), (SELECT count(*) FROM products), (SELECT count(*) FROM documents), (SELECT count(*) FROM baskets), (SELECT count(*) FROM audit_events);'
    $original = docker compose exec -T db psql -U procure -d procurement -Atc $query
    $restored = docker compose exec -T db psql -U procure -d $testDatabase -Atc $query
    if ($original -ne $restored) { throw "Restored record counts differ: $original / $restored" }
    docker compose cp $archive.FullName 'api:/tmp/rehearsal.tar.gz'
    docker compose exec -T api mkdir -p /tmp/rehearsal
    docker compose exec -T api tar -xzf /tmp/rehearsal.tar.gz -C /tmp/rehearsal
    if ($LASTEXITCODE -ne 0) { throw 'Document archive extraction failed' }
    $checkCode = @'
from pathlib import Path
from hashlib import sha256
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Document
with SessionLocal() as db:
    docs=db.scalars(select(Document)).all()
    checked=0
    for d in docs:
        source=Path(d.path)
        if not source.is_file(): continue
        restored=Path('/tmp/rehearsal/documents') / source.relative_to('/app/data/documents')
        assert sha256(restored.read_bytes()).hexdigest()==d.sha256, 'Restored document hash mismatch'
        checked+=1
    print(f'Restored document SHA-256 verified: {checked}')
'@
    docker compose exec -T api python -c $checkCode
    if ($LASTEXITCODE -ne 0) { throw 'Document verification failed' }
    Write-Host "Isolated PostgreSQL restore verified. Counts (businesses|products|documents|baskets|audit): $restored"
} finally {
    docker compose exec -T db dropdb -U procure $testDatabase
}
