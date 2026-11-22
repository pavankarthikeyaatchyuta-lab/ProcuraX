$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root '.env'
if (Test-Path -LiteralPath $envFile) { Write-Host '.env exists; leaving credentials unchanged.'; exit 0 }
function New-Secret([int]$Length) { $bytes = New-Object byte[] $Length; $rng = [Security.Cryptography.RandomNumberGenerator]::Create(); try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }; return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_') }
$key = (New-Secret 32) + '='
$dbPassword = New-Secret 24
$demoPassword = New-Secret 18
@"
DB_PASSWORD=$dbPassword
TOKEN_ENCRYPTION_KEY=$key
DEMO_PASSWORD=$demoPassword
ZOHO_CLIENT_ID=
ZOHO_CLIENT_SECRET=
GOOGLE_DOCUMENT_AI_PROCESSOR=
CLAMAV_HOST=127.0.0.1
"@ | Set-Content -LiteralPath $envFile -Encoding utf8
New-Item -ItemType Directory -Force -Path (Join-Path $root 'secrets') | Out-Null
Write-Host 'Created local credentials. Keep .env private.'
Write-Host 'Demo login: owner@vyaya.local'
Write-Host "Demo password: $demoPassword"
