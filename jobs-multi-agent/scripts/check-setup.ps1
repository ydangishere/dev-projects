[CmdletBinding()]
param(
  [string]$DriveBridgeRoot = 'G:\My Drive\ChatGPT-Jobs-Bridge',
  [string]$CvRoot = 'E:\cvok\updated'
)
$ErrorActionPreference = 'Stop'
Write-Host "Drive root: $DriveBridgeRoot"
foreach ($folder in @('inbox-jd','outbox-cv','reports')) {
  $ok = Test-Path -LiteralPath (Join-Path $DriveBridgeRoot $folder) -PathType Container
  Write-Host "${folder}: $ok"
}
Write-Host "CV source: $(Test-Path -LiteralPath $CvRoot -PathType Container)"
$cmd = Get-Command codex -ErrorAction SilentlyContinue
if (-not $cmd) { Write-Warning 'codex CLI is not installed or is not in PATH'; exit 1 }
& codex --version
