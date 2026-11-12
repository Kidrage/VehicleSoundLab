# Bind the recording to all current DSP/control sources, independently of the
# legacy take version. configure_file updates only if the content changes.
file(GLOB_RECURSE at_render_files CONFIGURE_DEPENDS
  "${VSL_ROOT}/src/core/*.c" "${VSL_ROOT}/src/core/*.h"
  "${VSL_ROOT}/src/drive/*.c" "${VSL_ROOT}/src/drive/*.h"
  "${VSL_ROOT}/src/profiles/*.c" "${VSL_ROOT}/src/profiles/*.h"
  "${VSL_ROOT}/src/spatial/*.c" "${VSL_ROOT}/src/spatial/*.h"
  "${VSL_ROOT}/modules/sound_dna/*.c" "${VSL_ROOT}/modules/sound_dna/*.h"
  "${VSL_ROOT}/modules/sound_residual/*.c" "${VSL_ROOT}/modules/sound_residual/*.h"
  "${VSL_ROOT}/modules/residual_atlas/*.c" "${VSL_ROOT}/modules/residual_atlas/*.h"
  "${VSL_ROOT}/modules/dna_atlas/*.c" "${VSL_ROOT}/modules/dna_atlas/*.h"
  "${VSL_ROOT}/modules/dna_scene/*.c" "${VSL_ROOT}/modules/dna_scene/*.h"
  "${VSL_ROOT}/modules/phase_texture/*.c" "${VSL_ROOT}/modules/phase_texture/*.h"
  "${VSL_ROOT}/modules/harmonic_body/*.c" "${VSL_ROOT}/modules/harmonic_body/*.h"
  "${VSL_ROOT}/modules/drive_aux/*.c" "${VSL_ROOT}/modules/drive_aux/*.h"
  "${VSL_ROOT}/modules/rt_numeric/*.c" "${VSL_ROOT}/modules/rt_numeric/*.h"
  "${VSL_ROOT}/modules/stereo_bed/*.c" "${VSL_ROOT}/modules/stereo_bed/*.h"
  "${VSL_ROOT}/modules/start_texture/*.c" "${VSL_ROOT}/modules/start_texture/*.h"
  "${VSL_ROOT}/modules/catch_bloom/*.c" "${VSL_ROOT}/modules/catch_bloom/*.h"
  "${VSL_ROOT}/modules/atlas_drive/*.c" "${VSL_ROOT}/modules/atlas_drive/*.h"
  "${VSL_ROOT}/modules/atlas_monitor/*.c" "${VSL_ROOT}/modules/atlas_monitor/*.h"
  "${VSL_ROOT}/modules/atlas_take/*.c" "${VSL_ROOT}/modules/atlas_take/*.h")
list(SORT at_render_files)
set(at_render_identity "atlas-take-player-v5:${CMAKE_C_COMPILER_ID}:${CMAKE_C_COMPILER_VERSION}:${CMAKE_SYSTEM_PROCESSOR}")
foreach(source IN LISTS at_render_files)
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${source}")
  file(SHA256 "${source}" digest)
  file(RELATIVE_PATH relative "${VSL_ROOT}" "${source}")
  string(APPEND at_render_identity "${relative}:${digest}\n")
endforeach()
if(CMAKE_CONFIGURATION_TYPES)
  set(at_configurations ${CMAKE_CONFIGURATION_TYPES})
else()
  set(at_configurations "${CMAKE_BUILD_TYPE}")
  if(NOT at_configurations)
    set(at_configurations Default)
  endif()
endif()
foreach(configuration IN LISTS at_configurations)
  string(TOUPPER "${configuration}" upper)
  string(SHA256 AT_RENDER_HASH "${at_render_identity}:${configuration}:${CMAKE_C_FLAGS}:${CMAKE_C_FLAGS_${upper}}")
  configure_file(atlas_take_build.h.in "${CMAKE_CURRENT_BINARY_DIR}/${configuration}/atlas_take_build.h" @ONLY)
endforeach()
add_library(atlas_take STATIC parameters.c assets.c take.c player.c)
target_include_directories(atlas_take PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/.." PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/$<IF:$<BOOL:$<CONFIG>>,$<CONFIG>,Default>")
target_link_libraries(atlas_take PUBLIC atlas_monitor)
target_compile_features(atlas_take PUBLIC c_std_11)
if(MSVC)
  target_compile_options(atlas_take PRIVATE /W4 /we4013 /utf-8)
else()
  target_compile_options(atlas_take PRIVATE -Wall -Wextra -Wpedantic)
endif()
