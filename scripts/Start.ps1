param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:PYTHONUTF8 = '1'
if (-not (Test-Path '.venv\Scripts\python.exe')) { throw 'Run the installation launcher first.' }
$launchArgs = @('scripts/launcher.py', 'start')
if ($NoBrowser) { $launchArgs += '--no-browser' }
& '.\.venv\Scripts\python.exe' @launchArgs
if ($LASTEXITCODE -ne 0) { throw 'Startup failed. Please read the message above.' }
