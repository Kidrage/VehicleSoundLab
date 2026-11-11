#include "observation.h"
#include "core/modules.h"
#include <math.h>

static void tick(VslObservedDna *state,float *out) {
    int c;
    for(c=0;c<2;++c) {
        VslEngine *e=&state->channel[c];double a,b;
        vsl_dna_tick(e,&a,&b);
        /* Undo native per-import normalization to retain observed L/R levels.
           The two phase variants then share one fixed audition attenuation. */
        out[c]=(float)(a/e->dna.factory_scale);
        e->dna.pitch_phase=fmod(e->dna.pitch_phase+2*VSL_PI*e->dna.custom_root/e->sample_rate,2*VSL_PI);
    }
}
int vsl_observed_init(VslObservedDna *state,const char *left,const char *right) {
    const char *paths[2]={left,right};int c;unsigned i;float discard[2];
    for(c=0;c<2;++c) {
        VslEngine *e=&state->channel[c];
        vsl_init(e,48000,48271);
        if(!vsl_load_dna(e,paths[c]))return 0;
        e->control.rpm=3000;e->smooth.irregularity=0;e->voice.dna_gain=1;
        vsl_dna_update(e);
    }
    if(state->channel[0].dna.custom_root!=state->channel[1].dna.custom_root)return 0;
    /* Native 8ms coefficient slew settles for 250ms, then common phase zero. */
    for(i=0;i<12000;++i)tick(state,discard);
    for(c=0;c<2;++c)state->channel[c].dna.pitch_phase=0;
    return 1;
}
void vsl_observed_process(VslObservedDna *state,float *stereo,unsigned frames) {
    unsigned i;for(i=0;i<frames;++i)tick(state,stereo+2*i);
}
