#ifndef VSL_SUSTAIN_MODEL_H
#define VSL_SUSTAIN_MODEL_H
#define SU_HARMONICS 320
#define SU_COMPONENTS 16
typedef struct {
    double mean[4],basis[SU_COMPONENTS][4],rho,root[4][4];
} SuHarmonic;
typedef struct {
    unsigned rate,window,hop,harmonics,components;
    double rho[SU_COMPONENTS];SuHarmonic harmonic[SU_HARMONICS];
} SuModel;
/* Static moments only: no PCM or timed coefficient rows. Transactional load. */
int su_model_load(const char *path,SuModel *model);
#endif
