<#
.SYNOPSIS
Install four validated candidates after checking a frozen snapshot and making a backup.
.DESCRIPTION
The Python generator never touches live saves. This optional Windows helper performs
that separate step. It verifies SHA-256 preconditions, refuses a running DD2 process,
and restores changed files from its fresh backup if installation fails.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$SaveDirectory,
    [Parameter(Mandatory)][string]$CandidateDirectory,
    [Parameter(Mandatory)][string]$BackupDirectory
)
$ErrorActionPreference = 'Stop'
$before = Get-Content (Join-Path $CandidateDirectory 'snapshot-manifest.json') -Raw | ConvertFrom-Json
$after = Get-Content (Join-Path $CandidateDirectory 'validation.json') -Raw | ConvertFrom-Json
$allowed = @('data005Slot.bin', 'data006Slot.bin', 'data009Slot.bin', 'data00-1.bin')
if (@($after).Count -ne 4 -or @($after.file | Sort-Object -Unique).Count -ne 4) {
    throw 'Expected exactly four unique candidate files.'
}
foreach ($record in $after) {
    if ($record.file -notin $allowed) { throw 'Unexpected candidate filename.' }
}
foreach ($record in $before) {
    if ($record.file -notmatch '^data(00-1|\d{3}(Slot)?)\.bin$') {
        throw 'Unexpected snapshot filename.'
    }
}
$required = @('data000.bin', 'data001Slot.bin', 'data004Slot.bin') + $allowed
foreach ($name in $required) {
    if ($name -notin $before.file) { throw 'Snapshot manifest is incomplete.' }
}
$currentNames = @(Get-ChildItem $SaveDirectory -File -Filter '*.bin' | Select-Object -ExpandProperty Name | Sort-Object)
$expectedNames = @($before.file | Sort-Object)
if (@(Compare-Object $currentNames $expectedNames).Count -ne 0) {
    throw 'Live snapshot file set has changed.'
}
if (Test-Path $BackupDirectory) { throw 'Backup directory already exists.' }
if (Get-Process -Name DD2 -ErrorAction SilentlyContinue) { throw 'Exit DD2 before installing.' }

function Test-FileHash([string]$Path, [string]$Expected) {
    if ((Get-FileHash $Path -Algorithm SHA256).Hash -ne $Expected) {
        throw "SHA-256 mismatch: $Path"
    }
}
# Refuse to overwrite progress made after the frozen snapshot was collected.
foreach ($record in $before) {
    Test-FileHash (Join-Path $SaveDirectory $record.file) $record.sha256
}
foreach ($record in $after) {
    Test-FileHash (Join-Path $CandidateDirectory $record.file) $record.sha256
}
if (-not $PSCmdlet.ShouldProcess($SaveDirectory, 'Back up and install slot-2 transfer')) { return }
New-Item -ItemType Directory -Path $BackupDirectory | Out-Null
foreach ($record in $before) {
    Copy-Item (Join-Path $SaveDirectory $record.file) (Join-Path $BackupDirectory $record.file)
    Test-FileHash (Join-Path $BackupDirectory $record.file) $record.sha256
}
# Recheck immediately before changing files; partial installation rolls back below.
if (Get-Process -Name DD2 -ErrorAction SilentlyContinue) { throw 'DD2 started during preparation.' }
foreach ($record in $before) {
    Test-FileHash (Join-Path $SaveDirectory $record.file) $record.sha256
}
try {
    foreach ($record in $after) {
        Copy-Item (Join-Path $CandidateDirectory $record.file) (Join-Path $SaveDirectory $record.file) -Force
        Test-FileHash (Join-Path $SaveDirectory $record.file) $record.sha256
    }
    # Only the four allowlisted files may change, including when slot 3 exists.
    foreach ($record in $before) {
        if ($record.file -notin $allowed) {
            Test-FileHash (Join-Path $SaveDirectory $record.file) $record.sha256
        }
    }
} catch {
    $failure = $_
    foreach ($record in $after) {
        Copy-Item (Join-Path $BackupDirectory $record.file) (Join-Path $SaveDirectory $record.file) -Force
        $original = $before | Where-Object { $_.file -eq $record.file }
        Test-FileHash (Join-Path $SaveDirectory $record.file) $original.sha256
    }
    throw $failure
}
Write-Output 'Installed and verified. Keep the backup; verify loading and online behavior in-game.'
