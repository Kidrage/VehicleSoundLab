#ifndef VSL_SCENARIOS_H
#define VSL_SCENARIOS_H
#include "core/types.h"
typedef enum {
    VSL_SCENARIO_FIXED, VSL_SCENARIO_AUTO, VSL_SCENARIO_LIFT,
    VSL_SCENARIO_SHIFTS, VSL_SCENARIO_NEUTRAL, VSL_SCENARIO_DOWNSHIFT, VSL_SCENARIO_COUNT
} VslScenario;
int vsl_scenario_id(const char *name);
void vsl_scenario_apply(int scenario,double seconds,VslParams *params);
#endif
