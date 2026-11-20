#ifndef VSL_STARTUP_RIDGE_H
#define VSL_STARTUP_RIDGE_H
#include <stdint.h>
#define SC_RIDGES 48
typedef struct {unsigned start_frame,frames;float hz,slew,amplitude[2],phase[2];} ScRidge;
typedef struct {
    ScRidge data[SC_RIDGES];float phase[SC_RIDGES][2],previous_hz[SC_RIDGES],pitch[SC_RIDGES],gain[SC_RIDGES];
    unsigned active[SC_RIDGES],count,reference_frames;int previous_gate;
} ScRidgeVoice;
int sc_ridge_init(ScRidgeVoice *voice,const ScRidge *ridges,unsigned count,unsigned reference_frames,float variation,float pitch,uint64_t seed);
void sc_ridge_tick(ScRidgeVoice *voice,float progress,int gate,float stereo[2]);
/* Optional continuously varying common pitch, relative to configured pitch.
   The host owns the action clock; pitch never rescales that clock. */
int sc_ridge_tick_pitch(ScRidgeVoice *voice,float progress,int gate,float pitch,float stereo[2]);
#endif
