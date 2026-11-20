#ifndef VSL_CATCH_BLOOM_FILTER_H
#define VSL_CATCH_BLOOM_FILTER_H
typedef struct {float b0,b2,a1,a2,z1[2],z2[2];} CbFilter;
int cb_filter_init(CbFilter *filter,float hz,float q);
/* Fixed stable poles; unit bandpass gain at centre, no time-varying tuning. */
void cb_filter_tick(CbFilter *filter,const float stereo[2],float out[2]);
#endif
