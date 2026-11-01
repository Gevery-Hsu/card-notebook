$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$oldTemp = $env:TEMP
$oldTmp = $env:TMP
try {
    $env:PYTHONUTF8 = '1'
    $env:TEMP = Join-Path $projectRoot '.runtime\tmp'
    $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python virtual environment.' }
    }
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    Write-Host 'Installation complete. Open the start launcher.'
} finally { $env:TEMP = $oldTemp; $env:TMP = $oldTmp }
