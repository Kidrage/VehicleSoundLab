$ErrorActionPreference = 'Stop'
$vslFastIdleBuild = Join-Path $PSScriptRoot 'build-idle-microtexture-v1'
cmake -S (Join-Path $PSScriptRoot 'experiments/idle_microtexture_v1') -B $vslFastIdleBuild -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build $vslFastIdleBuild --config Release --parallel 2
if ($LASTEXITCODE) { exit $LASTEXITCODE }
ctest --test-dir $vslFastIdleBuild -C Release --output-on-failure
exit $LASTEXITCODE
