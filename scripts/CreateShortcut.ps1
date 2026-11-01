param([string]$DestinationDirectory = [Environment]::GetFolderPath('Desktop'))
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$desktopPath = $DestinationDirectory
$shortcutName = ([char]0x79c1).ToString() + [char]0x4eba + [char]0x5361 + [char]0x7247 + [char]0x672c
$shortcutPath = Join-Path $desktopPath ($shortcutName + '.lnk')
if (Test-Path -LiteralPath $shortcutPath) {
    $shortcutPath = Join-Path $desktopPath ($shortcutName + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.lnk')
}
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = 'powershell.exe'
$shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $PSScriptRoot 'Start.ps1') + '"'
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = 'Private card notebook'
$shortcut.Save()
Write-Host ('Shortcut created: ' + $shortcutPath)
