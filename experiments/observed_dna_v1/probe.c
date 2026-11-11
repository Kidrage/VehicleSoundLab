#include "observation.h"
#include "io/wav.h"
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv) {
    VslObservedDna *state=NULL;VslWavWriter wav={0};float block[257*2];
    unsigned frame=0,block_frames=257;int ok=0;
    if(argc!=4&&argc!=5)return 1;
    if(argc==5) {
        char *end;long n=strtol(argv[4],&end,10);
        if(end==argv[4]||*end||n<1||n>257)return 1;
        block_frames=(unsigned)n;
    }
    state=malloc(sizeof *state);
    if(!state||!vsl_observed_init(state,argv[1],argv[2])||!vsl_wav_begin_float(&wav,argv[3],48000,2))goto done;
    ok=1;
    while(frame<144000) {
        unsigned n=144000-frame;if(n>block_frames)n=block_frames;
        vsl_observed_process(state,block,n);
        if(!vsl_wav_write(&wav,block,n)) { ok=0;break; }
        frame+=n;
    }
    printf("observed_dna_v1 | native %s | static root %.12gHz | frames %u | %s\n",VSL_VERSION,state->channel[0].dna.custom_root,frame,ok?"pass":"FAIL");
done:
    if(wav.file)ok=vsl_wav_end(&wav)&&ok;
    free(state);return ok?0:2;
}
