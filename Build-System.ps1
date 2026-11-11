$ErrorActionPreference = 'Stop'
$vslBuild = Join-Path $PSScriptRoot 'handoff-build'
cmake -S (Join-Path $PSScriptRoot 'handoff') -B $vslBuild -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build $vslBuild --config Release --parallel
if ($LASTEXITCODE) { exit $LASTEXITCODE }
ctest --test-dir $vslBuild -C Release --output-on-failure
exit $LASTEXITCODE
