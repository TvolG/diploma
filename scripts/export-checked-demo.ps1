# Export an already updated and runtime-tested COPY of a file database.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$OneCExe,
    [Parameter(Mandatory=$true)][string]$DatabasePath,
    [Parameter(Mandatory=$true)][string]$OutputDt,
    [string]$User = 'Администратор',
    [switch]$RuntimeChecksPassed
)
$ErrorActionPreference = 'Stop'
if (-not $RuntimeChecksPassed) { throw 'Run the runtime checklist in docs/checks.md first.' }
if (-not (Test-Path -LiteralPath $OneCExe -PathType Leaf)) { throw '1cv8.exe not found.' }
if (-not (Test-Path -LiteralPath (Join-Path $DatabasePath '1Cv8.1CD') -PathType Leaf)) { throw 'File database not found.' }
if (Test-Path -LiteralPath $OutputDt) { throw 'Output already exists. Choose a new filename.' }
$exportPath = [IO.Path]::GetFullPath($OutputDt)
$parentPath = Split-Path -Parent $exportPath
New-Item -ItemType Directory -Force -Path $parentPath | Out-Null
$logPath = $exportPath + '.log'
# No password argument: use the normal local authentication dialog when needed.
& $OneCExe DESIGNER /F $DatabasePath /N $User /DumpIB $exportPath /Out $logPath
$exitStatus = $LASTEXITCODE
if ($exitStatus -ne 0 -or -not (Test-Path -LiteralPath $exportPath)) {
    throw "Export failed (exit $exitStatus). Read $logPath"
}
if ((Get-Item -LiteralPath $exportPath).Length -eq 0) { throw 'Empty DT file.' }
Get-FileHash -LiteralPath $exportPath -Algorithm SHA256
Write-Output "Exported: $exportPath. Restore into a new database and verify before publishing."
