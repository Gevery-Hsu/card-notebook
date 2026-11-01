$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$env:PYTHONUTF8 = '1'
& '.\.venv\Scripts\python.exe' 'scripts/launcher.py' 'stop'
if ($LASTEXITCODE -ne 0) { throw 'Stop failed. Please read the message above.' }
