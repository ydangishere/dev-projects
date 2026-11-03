[CmdletBinding()]
param([string]$DriveBridgeRoot = 'G:\My Drive\ChatGPT-Jobs-Bridge')
$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'process-drive.ps1'
if (-not (Test-Path -LiteralPath (Join-Path $DriveBridgeRoot 'inbox-jd') -PathType Container)) {
  throw "Drive inbox not found: $DriveBridgeRoot"
}
$triggers = @('04:20','04:50','05:20','05:50') | ForEach-Object {
  New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $_
}
$args = '-NoProfile -ExecutionPolicy Bypass -File "' + $runner + '" -DriveBridgeRoot "' + $DriveBridgeRoot + '"'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $args
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'Jobs-Codex-CV-Tailor' -Action $action -Trigger $triggers -Settings $settings -Force | Out-Null
Write-Host 'Created Windows Task Scheduler task: Jobs-Codex-CV-Tailor'
