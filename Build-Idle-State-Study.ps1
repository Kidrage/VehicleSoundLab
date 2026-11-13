$ErrorActionPreference = 'Stop'
$vslIdleStateBuild = Join-Path $PSScriptRoot 'build-idle-state-v1'
cmake -S (Join-Path $PSScriptRoot 'experiments/idle_state_v1') -B $vslIdleStateBuild -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build $vslIdleStateBuild --config Release --parallel 2
if ($LASTEXITCODE) { exit $LASTEXITCODE }
ctest --test-dir $vslIdleStateBuild -C Release --output-on-failure
exit $LASTEXITCODE
