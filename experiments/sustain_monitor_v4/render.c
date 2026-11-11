#include "render.h"
#include <math.h>
#include <string.h>
static int valid(int pitch,int detail,int db,int amount,int mode){return pitch>=900&&pitch<=1100&&detail>=0&&detail<=1000&&db>=-18&&db<=0&&amount>=0&&amount<=1000&&mode>=0&&mode<=2;}
int sm_render_init(SmRender *r,const SdProfile *m,const LrProfile *low,int pitch,int detail,int db,int amount,int mode) {
    if(!r||!valid(pitch,detail,db,amount,mode))return 0;
    memset(r,0,sizeof *r);
    if(!sd_voice_init(&r->source,m,SM_SEED,pitch/1000.,detail/1000.,1))return 0;
    if(!lr_voice_init(&r->rumble,low,SM_SEED+173,pitch/1000.,amount/1000.))return 0;
    r->attenuation=r->target_attenuation=pow(10,db/20.);r->follow=1-exp(-1/(.018*m->rate));
    r->dna_mix=r->dna_target=mode==2?0:1;r->low_mix=r->low_target=mode==1?0:1;r->mode=mode;return 1;
}
int sm_render_set(SmRender *r,int pitch,int detail,int db,int amount,int mode) {
    if(!r||!valid(pitch,detail,db,amount,mode)||!sd_voice_set(&r->source,pitch/1000.,detail/1000.,1))return 0;
    if(!lr_voice_set(&r->rumble,pitch/1000.,amount/1000.))return 0;
    r->target_attenuation=pow(10,db/20.);r->dna_target=mode==2?0:1;r->low_target=mode==1?0:1;r->mode=mode;return 1;
}
void sm_render_process(SmRender *r,float *raw,float *low_raw,float *out,unsigned frames,int stop) {
    unsigned n,c;double block[1024],low[512];
    if(stop)r->stopping=1;
    while(frames){unsigned count=frames>512?512:frames;
        sd_voice_process(&r->source,block,count);
        lr_voice_process(&r->rumble,low,count);
        for(n=0;n<count;++n){double envelope;
            r->attenuation+=r->follow*(r->target_attenuation-r->attenuation);
            r->dna_mix+=r->follow*(r->dna_target-r->dna_mix);r->low_mix+=r->follow*(r->low_target-r->low_mix);
            envelope=r->onset<240?r->onset++/239.:1;
            if(r->stopping){if(r->release<480)++r->release;envelope*=1-r->release/480.;}
            if(low_raw)low_raw[n]=(float)low[n];
            for(c=0;c<2;++c){raw[2*n+c]=(float)block[2*n+c];out[2*n+c]=(float)((block[2*n+c]*r->dna_mix+low[n]*r->low_mix)*.5*r->attenuation*envelope);}
        }
        raw+=count*2;if(low_raw)low_raw+=count;out+=count*2;frames-=count;
    }
}
