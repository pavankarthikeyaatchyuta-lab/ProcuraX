param([string]$Destination)
$ErrorActionPreference = 'Stop'
if (-not $Destination) { throw 'Supply -Destination on an encrypted drive.' }
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$resolved = [IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Force -Path $resolved | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$dumpName = "database-$stamp.dump"
$documentName = "documents-$stamp.tar.gz"
$backupContainer = 'vyaya-backup-' + $stamp
$running = @(docker compose ps --services --status running)
$writers = @('web','api','worker','scheduler') | Where-Object { $running -contains $_ }
try {
    if ($writers.Count -gt 0) { docker compose stop @writers; if ($LASTEXITCODE -ne 0) { throw 'Could not quiesce writers' } }
    docker compose exec -T db pg_dump -U procure -d procurement -Fc -f "/tmp/$dumpName"
    if ($LASTEXITCODE -ne 0) { throw 'Database backup failed' }
    docker compose cp "db:/tmp/$dumpName" (Join-Path $resolved $dumpName)
    if ($LASTEXITCODE -ne 0) { throw 'Backup copy failed' }
    docker compose run --no-deps --name $backupContainer api tar -czf /tmp/documents.tar.gz -C /app/data documents
    if ($LASTEXITCODE -ne 0) { throw 'Document backup failed' }
    docker cp "${backupContainer}:/tmp/documents.tar.gz" (Join-Path $resolved $documentName)
    if ($LASTEXITCODE -ne 0) { throw 'Document backup copy failed' }
} finally {
    docker rm $backupContainer 2>$null | Out-Null
    if ($writers.Count -gt 0) { docker compose up -d @writers }
}
Write-Host 'Backup saved. Preserve TOKEN_ENCRYPTION_KEY separately in an encrypted password manager.'
