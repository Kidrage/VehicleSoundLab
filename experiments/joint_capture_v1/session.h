#ifndef VSL_JOINT_CAPTURE_SESSION_H
#define VSL_JOINT_CAPTURE_SESSION_H
#include "atlas_take/take.h"
/* Non-RT diagnostic: same catalog, original driver and owned take. Two seconds
   startup/settling then three seconds low-to-high acoustic-root bench sweep;
   single-anchor recipes hold. Not a measured source RPM/load trajectory. */
int jc_record(int selection,uint64_t seed,AtTake *take);
/* Canonical hash verification plus six existing dry buses and telemetry.
   Output files must not exist; failures retain partial diagnostic evidence. */
int jc_export(const AtTake *take,const char *prefix,unsigned block,int channels);
#endif
