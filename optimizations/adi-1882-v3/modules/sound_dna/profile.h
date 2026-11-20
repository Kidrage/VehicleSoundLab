#ifndef VSL_SOUND_DNA_PROFILE_H
#define VSL_SOUND_DNA_PROFILE_H
#define SD_MAX_HARMONICS 320
#define SD_MAX_COMPONENTS 16
typedef struct {float mean[4],basis[SD_MAX_COMPONENTS][4],rho,root[4][4];} SdHarmonic;
typedef struct {
    unsigned rate,window,hop,harmonics,components;
    float base_hz;
    float rho[SD_MAX_COMPONENTS];SdHarmonic harmonic[SD_MAX_HARMONICS];
} SdProfile;
/* Transactional, non-real-time load. SOUND_DNA1 stores an independent base Hz.
   Legacy SUSTAIN_OSC1 imports with rate/window Hz. Rendering fixes mean phase. */
int sd_profile_load(const char *utf8_path,SdProfile *profile);
/* Explicit opt-in for dna_atlas/SaVoice's actual-root carrier taper only.
   Non-RT, transactional; base5..1000Hz, all coefficients/orders retained and
   validated. Legacy SdVoice/SdOscillator still reject unsafe profiles.
   This loader alone does not make an arbitrary renderer bandlimited. */
int sd_profile_load_bandlimited(const char *utf8_path,SdProfile *profile);
#endif
