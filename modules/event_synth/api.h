#ifndef VSL_EVENT_SYNTH_API_H
#define VSL_EVENT_SYNTH_API_H
#include <stdint.h>
#define ES_RATE 48000
#define ES_VOICES 4
#define ES_MODES 12
#define ES_BANDS 4
#define ES_CONTOURS 4
#define ES_KNOTS 8
#define ES_LOG_CAPACITY 128
enum {ES_ENGAGE,ES_CRANK,ES_CATCH,ES_AFTERFIRE,ES_SHIFT,ES_DISENGAGE,ES_STOP,ES_TYPES};
enum {ES_STARTED=1,ES_ENDED,ES_REJECTED,ES_REPLACED};
enum {ES_NATURAL=0,ES_RELEASED,ES_STOLEN,ES_CAPACITY,ES_DUPLICATE,ES_CANCELLED,ES_UNAVAILABLE};
typedef struct {
    double hz,amplitude,phase,decay_seconds,end_hz;
    double attack_seconds; /* 0: original path; seconds, independent of request decay. */
} EsMode;
typedef struct {double hz,q,amplitude,attack_seconds,decay_seconds;} EsBand;
typedef struct {
    unsigned count; /* 0: original envelopes; otherwise 2..8 continuous gain knots. */
    double low_hz,high_hz,seconds[ES_KNOTS],gain[ES_KNOTS];
} EsContour;
typedef struct {
    unsigned mode_count,band_count,gated;
    double duration_seconds,attack_seconds,release_seconds,sweep_seconds,level;
    EsMode modes[ES_MODES];EsBand bands[ES_BANDS];
    double noise_lowpass_hz; /* 0: original path; otherwise source noise colour, no room. */
    EsContour contours[ES_CONTOURS]; /* Nominal-frequency groups; time follows request decay. */
} EsProfile;
typedef struct {
    uint64_t id,requested_frame;
    unsigned type,priority;
    uint32_t seed;
    double strength,pitch,decay,texture;
} EsRequest;
typedef struct {
    uint64_t id,frame,requested_frame;
    unsigned type,slot,action,reason;
} EsNotice;
typedef struct {
    double phase,frequency,amplitude,decay,sweep_step,end_hz;
} EsOscillator;
typedef struct {double b0,b2,a1,a2,z1,z2,amplitude,decay,attack;} EsNoiseBand;
typedef struct {double b0,b1,b2,a1,a2,z1,z2;} EsColorSection;
typedef struct {
    EsProfile profile;
    EsRequest request,pending;
    EsOscillator modes[ES_MODES];EsNoiseBand bands[ES_BANDS];
    EsColorSection noise_color[2];
    unsigned mode_contour[ES_MODES],band_contour[ES_BANDS]; /* 0 none, otherwise index+1. */
    uint32_t rng;
    uint64_t age,duration,release_at,release_frames;
    unsigned active,has_pending,end_reason;
} EsVoice;
typedef struct {
    EsProfile profiles[ES_TYPES];
    EsVoice voices[ES_VOICES];
    uint64_t frame;
    EsNotice log[ES_LOG_CAPACITY];
    unsigned log_read,log_count,log_lost,started,rejected,replaced,peak_active;
} EsPool;
typedef struct {double sample[ES_VOICES];uint64_t id[ES_VOICES];unsigned type[ES_VOICES];} EsFrame;
/* All state is caller-owned. No allocation, files, PCM, room or routing. */
int es_profile_valid(const EsProfile *profile);
int es_pool_init(EsPool *pool,const EsProfile profiles[ES_TYPES]);
int es_pool_start(EsPool *pool,const EsRequest *request); /* 0 rejected; 1 started; 2 deferred within one slot */
void es_pool_release(EsPool *pool,int type,double seconds); /* type -1: all */
int es_pool_tick(EsPool *pool,EsFrame *frame);
unsigned es_pool_notices(EsPool *pool,EsNotice *out,unsigned capacity);
unsigned es_pool_active(const EsPool *pool);
#endif
