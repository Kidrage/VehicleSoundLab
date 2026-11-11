#ifndef VSL_LOW_BODY_H
#define VSL_LOW_BODY_H
typedef struct {double coefficient[3][2];} LbProfile;
typedef struct {
    const LbProfile *profile;
    double phase,pitch,target_pitch,amount,target_amount,envelope,target_envelope,follow,envelope_follow;
} LbSource;
int lb_profile_load(const char *path,LbProfile *profile);
int lb_init(LbSource *source,const LbProfile *profile,double pitch,double amount);
int lb_set(LbSource *source,double pitch,double amount,double envelope);
/* Mono source object, no LFE assignment. Relative-cycle harmonics1..3 only.
   No PCM, random phase/FM, allocation, or I/O in processing. */
void lb_process(LbSource *source,double *mono,unsigned frames);
#endif
