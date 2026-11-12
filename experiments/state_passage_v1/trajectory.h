#ifndef VSL_STATE_PASSAGE_TRAJECTORY_H
#define VSL_STATE_PASSAGE_TRAJECTORY_H
#include <stddef.h>

#define SP_MAX_POINTS 20000
#define SP_MAX_FRAMES (48000u*180u)
typedef struct { unsigned frame; double root_hz; } SpPoint;
typedef struct { SpPoint point[SP_MAX_POINTS]; size_t count, cursor; } SpTrajectory;

/* Diagnostic host only: observed acoustic Hz, never RPM/pedal/load.
   Text rows: frame root_hz; first frame0, increasing, last<=180s at48kHz.
   Load before rendering; caller submits increasing frames, no extrapolation. */
int sp_trajectory_load(SpTrajectory *path,const char *filename);
int sp_trajectory_value(SpTrajectory *path,unsigned frame,double *root_hz);
#endif
