$ErrorActionPreference = 'Stop'
$vslIdleBuild = Join-Path $PSScriptRoot 'build-modal-idle-v1'
cmake -S (Join-Path $PSScriptRoot 'experiments/modal_idle_v1') -B $vslIdleBuild -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build $vslIdleBuild --config Release --parallel 2
if ($LASTEXITCODE) { exit $LASTEXITCODE }
ctest --test-dir $vslIdleBuild -C Release --output-on-failure
exit $LASTEXITCODE
