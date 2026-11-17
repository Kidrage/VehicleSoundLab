$ErrorActionPreference = 'Stop'
$vslSourceBuild = Join-Path $PSScriptRoot 'build-vehicle-source-v14'
cmake -S (Join-Path $PSScriptRoot 'experiments/vehicle_source_v1') -B $vslSourceBuild -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build $vslSourceBuild --config Release --parallel 2 --target vsl_source_bridge vehicle_source_checks vehicle_source_probe vehicle_input_checks vehicle_event_checks event_policy_checks vehicle_dna_checks vehicle_state_dna_checks vehicle_character_checks
if ($LASTEXITCODE) { exit $LASTEXITCODE }
ctest --test-dir $vslSourceBuild -C Release -R '^(independent_source_stems_and_spatial_bypass|vehicle_external_input_authority|vehicle_event_native_clock_and_stems|vehicle_event_policy_recipe|authored_dna_owned_assets|state_dna_common_clock_and_owned_assets|unified_dna_roles_and_lifecycle)$' --output-on-failure
exit $LASTEXITCODE
