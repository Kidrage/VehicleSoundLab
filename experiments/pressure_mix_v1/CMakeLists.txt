cmake_minimum_required(VERSION 3.21)
project(VslPressureMix LANGUAGES C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
get_filename_component(VSL_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
set(FROZEN "${VSL_ROOT}/baselines/v0.17.0/src")

# Generate an offline observer from pinned functions; native files stay intact.
function(replace_once input marker replacement output)
  string(FIND "${input}" "${marker}" index)
  if(index EQUAL -1)
    message(FATAL_ERROR "Missing frozen hook: ${marker}")
  endif()
  string(REPLACE "${marker}" "" remainder "${input}")
  string(FIND "${remainder}" "${marker}" duplicate)
  # A separate length check rejects multiple replacements, including overlaps.
  string(LENGTH "${input}" before)
  string(LENGTH "${remainder}" after)
  string(LENGTH "${marker}" length)
  math(EXPR removed "${before}-${after}")
  if(NOT removed EQUAL length)
    message(FATAL_ERROR "Non-unique frozen hook: ${marker}")
  endif()
  string(REPLACE "${marker}" "${replacement}" result "${input}")
  set(${output} "${result}" PARENT_SCOPE)
endfunction()

file(READ "${FROZEN}/core/character.c" SOURCE)
string(FIND "${SOURCE}" "static double random_bipolar(" A)
string(FIND "${SOURCE}" "void vsl_character_init(" B)
math(EXPR LENGTH "${B}-${A}")
string(SUBSTRING "${SOURCE}" ${A} ${LENGTH} RANDOM)
string(FIND "${SOURCE}" "void vsl_character_tick(" A)
string(SUBSTRING "${SOURCE}" ${A} -1 SOURCE)
replace_once("${SOURCE}" "void vsl_character_tick(VslEngine *e,VslObjectFrame *o)"
  "void vsl_cf_character_tick(VslEngine *e,VslPressureObserver *observer,VslObjectFrame *o)" SOURCE)
replace_once("${SOURCE}" "vsl_character_pressure_strike(&s->pressure,engine->bank[c],pressure_gain,shape,elapsed);"
  "vsl_cf_strike(observer,e,&s->pressure,engine->bank[c],pressure_gain,shape,elapsed);" SOURCE)
replace_once("${SOURCE}" "vsl_character_pressure_init(&s->pressure,e->sample_rate);"
  "++observer->resets;vsl_character_pressure_init(&s->pressure,e->sample_rate);" SOURCE)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/observed_character.c"
  "#include \"observer.h\"\n#include \"core/modules.h\"\n#include \"profiles/firing.h\"\n#include \"drive/fueling.h\"\n#include <math.h>\n${RANDOM}${SOURCE}")

file(READ "${FROZEN}/core/engine.c" SOURCE)
string(FIND "${SOURCE}" "int vsl_process_layout(" A)
string(FIND "${SOURCE}" "void vsl_process(" B)
math(EXPR LENGTH "${B}-${A}")
string(SUBSTRING "${SOURCE}" ${A} ${LENGTH} SOURCE)
replace_once("${SOURCE}" "int vsl_process_layout(VslEngine *e," "int vsl_cf_process(VslEngine *e,VslPressureObserver *observer," SOURCE)
replace_once("${SOURCE}" "vsl_character_tick(e,o);" "vsl_cf_character_tick(e,observer,o);vsl_cf_output(observer,e,o);" SOURCE)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/observed_engine.c"
  "#include \"observer.h\"\n#include \"core/modules.h\"\n#include \"drive/drive.h\"\n#include \"spatial/scene.h\"\n#include <math.h>\n#include <string.h>\n${SOURCE}")

file(READ "${FROZEN}/session/take.c" SOURCE)
string(FIND "${SOURCE}" "unsigned vsl_take_process(" A)
string(SUBSTRING "${SOURCE}" ${A} -1 SOURCE)
replace_once("${SOURCE}" "unsigned vsl_take_process(VslTakePlayer *player,VslEngine *e,"
  "unsigned vsl_cf_take(VslTakePlayer *player,VslEngine *e,VslPressureObserver *observer," SOURCE)
replace_once("${SOURCE}" "vsl_process_layout(e,out+done*channels,n,channels,stems?stems+done*VSL_OBJECTS:NULL);"
  "vsl_cf_process(e,observer,out+done*channels,n,channels,stems?stems+done*VSL_OBJECTS:NULL);" SOURCE)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/observed_take.c" "#include \"observer.h\"\n#include <math.h>\n${SOURCE}")

add_executable(pressure_mix_probe probe.c observer.c
  "${CMAKE_CURRENT_BINARY_DIR}/observed_character.c"
  "${CMAKE_CURRENT_BINARY_DIR}/observed_engine.c"
  "${CMAKE_CURRENT_BINARY_DIR}/observed_take.c")
target_include_directories(pressure_mix_probe PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}" "${FROZEN}")
target_link_libraries(pressure_mix_probe PRIVATE "${VSL_ROOT}/baselines/v0.17.0/bin/vsl_core.lib")
if(MSVC)
  target_compile_options(pressure_mix_probe PRIVATE /W4 /we4013 /utf-8)
endif()
