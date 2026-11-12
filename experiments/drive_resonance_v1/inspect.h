#ifndef VSL_DRIVE_RESONANCE_INSPECT_H
#define VSL_DRIVE_RESONANCE_INSPECT_H
#include "atlas_take/take.h"
/* Offline only: inspect adopted-input replay, without touching the device thread. */
int drp_inspect(const AtTake *take,const char *directory);
#endif
