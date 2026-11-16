param(
    [Parameter(Mandatory = $true)][string]$Job,
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$Workspace = 'E:/VehicleSoundLab',
    [switch]$InspectOnly
)
$ErrorActionPreference = 'Stop'
$vslPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (!(Test-Path -LiteralPath $vslPython)) { $vslPython = (Get-Command python -ErrorAction Stop).Source }
$vslArguments = @((Join-Path $PSScriptRoot 'tools/design_sound_clip.py'), $Job, '--out', $Out, '--workspace', $Workspace)
if ($InspectOnly) { $vslArguments += '--inspect' }
& $vslPython @vslArguments
exit $LASTEXITCODE
