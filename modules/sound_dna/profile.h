#ifndef VSL_SOUND_DNA_PROFILE_H
#define VSL_SOUND_DNA_PROFILE_H
#define SD_MAX_HARMONICS 320
#define SD_MAX_COMPONENTS 16
typedef struct {double mean[4],basis[SD_MAX_COMPONENTS][4],rho,root[4][4];} SdHarmonic;
typedef struct {
    unsigned rate,window,hop,harmonics,components;
    double base_hz;
    double rho[SD_MAX_COMPONENTS];SdHarmonic harmonic[SD_MAX_HARMONICS];
} SdProfile;
/* Transactional, non-real-time load. SOUND_DNA1 stores an independent base Hz.
   Legacy SUSTAIN_OSC1 imports with rate/window Hz. Rendering fixes mean phase. */
int sd_profile_load(const char *utf8_path,SdProfile *profile);
#endif
