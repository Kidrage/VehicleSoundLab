#ifndef VSL_MODAL_TEXTURE_PROFILE_H
#define VSL_MODAL_TEXTURE_PROFILE_H
#define MT_MAX_MODES 64
#define MT_RATE 48000
/* Factor, not a recorded envelope: covariance = factor * transpose(factor).
   Square factors may be singular or zero. Rows follow the OSC profile order. */
typedef struct {
    unsigned rate,count,hop_frames;
    double alpha,factor[MT_MAX_MODES][MT_MAX_MODES];
} MtProfile;
/* Non-RT. Numerical domain: alpha0..0.98, hop1..480000, row std<=0.25.
   These limits are engineering bounds, not source/engine qualifications. */
int mt_profile_valid(const MtProfile *profile);
#endif
