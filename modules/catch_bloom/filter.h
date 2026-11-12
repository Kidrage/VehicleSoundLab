#ifndef VSL_CATCH_BLOOM_FILTER_H
#define VSL_CATCH_BLOOM_FILTER_H
typedef struct {double b0,b2,a1,a2,z1[2],z2[2];} CbFilter;
int cb_filter_init(CbFilter *filter,double hz,double q);
/* Fixed stable poles; unit bandpass gain at centre, no time-varying tuning. */
void cb_filter_tick(CbFilter *filter,const double stereo[2],double out[2]);
#endif
