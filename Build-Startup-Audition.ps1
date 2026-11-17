$ErrorActionPreference = 'Stop'
$vslAuditionBuild = Join-Path $PSScriptRoot 'build-startup-character-v5'
cmake -S (Join-Path $PSScriptRoot 'experiments/startup_character_v1') -B $vslAuditionBuild -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build $vslAuditionBuild --config Release --parallel 4 --target startup_character_bridge crank_rotation_checks
if ($LASTEXITCODE) { exit $LASTEXITCODE }
ctest --test-dir $vslAuditionBuild -C Release -R '^continuous_crank_rotation_contract$' --output-on-failure
exit $LASTEXITCODE
