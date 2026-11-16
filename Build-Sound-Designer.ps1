$ErrorActionPreference = 'Stop'
$vslBuild = Join-Path $PSScriptRoot 'build-sound-dna-export-v1'
cmake -S (Join-Path $PSScriptRoot 'experiments/sound_dna_export_v1') -B $vslBuild -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build $vslBuild --config Release --parallel 2
exit $LASTEXITCODE
