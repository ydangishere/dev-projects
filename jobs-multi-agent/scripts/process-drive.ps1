#Requires -Version 5.1
# Agent 2 cloud/local bridge: consume verified job manifests from Google Drive.
[CmdletBinding()]
param(
  [string]$DriveBridgeRoot = 'G:\My Drive\ChatGPT-Jobs-Bridge',
  [string]$CvRoot = 'E:\cvok\updated',
  [string]$LocalBridgeRoot = 'E:\cvok\jobs-bridge'
)
$ErrorActionPreference='Stop'
$inbox=Join-Path $DriveBridgeRoot 'inbox-jd'
$outbox=Join-Path $DriveBridgeRoot 'outbox-cv'
$reports=Join-Path $DriveBridgeRoot 'reports'
foreach ($p in @($inbox,$outbox,$reports,$CvRoot)) {
  if (-not (Test-Path -LiteralPath $p -PathType Container)) {throw "Missing directory: $p"}
}
$doneDir=Join-Path $LocalBridgeRoot 'drive-processed'
New-Item -ItemType Directory -Force -Path $doneDir | Out-Null
$files=@(Get-ChildItem -LiteralPath $inbox -Filter 'jobs-*.json' -File | Sort-Object Name)
if ($files.Count -eq 0) {Write-Host 'No new JD manifests in inbox-jd';exit 0}
foreach ($file in $files) {
  $hash=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
  $marker=Join-Path $doneDir "$hash.done"
  if (Test-Path -LiteralPath $marker) {continue}
  try {
    $manifest=Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
    $jobs=@($manifest.jobs | Where-Object { $null -ne $_ })
    $stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
    $results=@()
    if ($jobs.Count -gt 0) {
      $localReport=Join-Path $LocalBridgeRoot 'outbox\report.json'
      if (Test-Path -LiteralPath $localReport) {Remove-Item -LiteralPath $localReport -Force}
      & (Join-Path $PSScriptRoot 'run-jobs.ps1') -JobFile $file.FullName -CvRoot $CvRoot -BridgeRoot $LocalBridgeRoot
      if (-not (Test-Path -LiteralPath $localReport)) {throw 'Codex did not produce report.json'}
      $results=@(Get-Content -LiteralPath $localReport -Raw -Encoding UTF8 | ConvertFrom-Json)
    }
    $rows=@()
    $idx=0
    foreach ($r in $results) {
      $idx++
      $zip=''
      if ($r.status -eq 'created_review_required' -and $r.cv_local_path -and (Test-Path -LiteralPath $r.cv_local_path -PathType Container)) {
        $slug=([string]$r.company -replace '[^\p{L}\p{Nd}_-]','-').Trim('-')
        $zip="CV-$slug-$stamp-$idx.zip"
        Compress-Archive -LiteralPath ([string]$r.cv_local_path) -DestinationPath (Join-Path $outbox $zip) -Force
      }
      $rows+= [pscustomobject]@{
        company=$r.company
        position=$r.position
        jd_url=$r.jd_url
        cv_local_path=$r.cv_local_path
        cv_drive_zip_filename=$zip
        status=$r.status
        notes=$r.notes
      }
    }
    $summary=[pscustomobject]@{
      manifest_name=$file.Name
      generated_at=(Get-Date).ToString('o')
      job_count=$jobs.Count
      jobs=@($rows)
      excluded=@($manifest.excluded | Where-Object { $null -ne $_ })
    }
    $reportFile=Join-Path $reports "report-$stamp.json"
    $summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportFile -Encoding UTF8
    "Processed $(Get-Date -Format o)" | Set-Content -LiteralPath $marker -Encoding UTF8
    Write-Host "Done: $($file.Name) -> $reportFile"
  } catch {
    Write-Warning "Manifest $($file.Name) failed: $_. It will be retried."
  }
}
