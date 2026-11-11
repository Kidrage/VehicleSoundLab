#ifndef VSL_ENGINE_H
#define VSL_ENGINE_H
#include "types.h"
const VslProfile *vsl_profile(int id);
VslParams vsl_default_params(int profile);
void vsl_init(VslEngine *engine, double sample_rate, uint32_t seed);
void vsl_set_params(VslEngine *engine, const VslParams *params);
void vsl_process(VslEngine *engine, float *stereo, unsigned frames);
/* Layout: 2 or 12 channels; object stems are pre-spatial and pre-master. */
int vsl_process_layout(VslEngine *engine,float *output,unsigned frames,int channels,float *stems);
/* Strict OSC disables stochastic source layers, pad and source IR. Optional
   listener propagation and spatial monitoring remain separately selectable. */
int vsl_load_dna(VslEngine *engine, const char *path);
int vsl_set_ir(VslEngine *engine, const float *mono, unsigned frames, unsigned sample_rate);
void vsl_drive(double seconds, VslParams *params);
#endif
