#ifndef VSL_CRANK_ROTATION_H
#define VSL_CRANK_ROTATION_H
#include <stdint.h>
#include "resonant_detail/excitation.h"
#define CK_MODES 96
#define CK_BANDS 8
#define CK_TABLE 8192
#define CK_HOP 32
typedef struct {double hz,width_hz,amplitude[3][2],phase[2];unsigned band;} CkMode;
typedef struct {
    unsigned count,bands;double flutter_hz,coherence;
    double cosine[CK_BANDS][2],sine[CK_BANDS][2];CkMode mode[CK_MODES];
} CkProfile;
typedef struct {
    CkProfile profile;RdtExcitation rng;
    double table[CK_TABLE+1],phase[CK_MODES],offset[CK_MODES][2];
    double unit[CK_MODES][2][2],variance[CK_MODES][CK_HOP],weight[CK_HOP];
    double left[CK_MODES][2],right[CK_MODES][2],alpha[CK_MODES],innovation[CK_MODES];
    double clock,initial_phase[CK_MODES],roughness;unsigned position;
    uint64_t frame;int previous_gate;
} CkVoice;
/* Non-RT: validates/copies parameters and prepares LUT/stationary states. */
int ck_init(CkVoice *voice,const CkProfile *profile,uint64_t seed);
/* Continuous OSC phases, fresh complex modulation, coarse spectral states.
   Acoustic flutter is NOT inferred shaft/gear/cylinder RPM. No PCM/score. */
int ck_tick(CkVoice *voice,double progress,int gate,double pitch,double motion,double out[2],double *air_amplitude);
#endif
