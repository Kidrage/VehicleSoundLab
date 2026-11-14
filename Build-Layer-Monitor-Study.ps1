$ErrorActionPreference = 'Stop'
$vslLayerBuild = Join-Path $PSScriptRoot 'build-layer-monitor-v1'
cmake -S (Join-Path $PSScriptRoot 'experiments/layer_monitor_v1') -B $vslLayerBuild -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build $vslLayerBuild --config Release --parallel 2
if ($LASTEXITCODE) { exit $LASTEXITCODE }
ctest --test-dir $vslLayerBuild -C Release --output-on-failure
exit $LASTEXITCODE
