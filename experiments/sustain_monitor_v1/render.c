#include "render.h"
#include <math.h>
#include <string.h>
static int valid(int pitch,int detail,int db){return pitch>=900&&pitch<=1100&&detail>=0&&detail<=1000&&db>=-18&&db<=0;}
int sm_render_init(SmRender *r,const SuModel *m,int pitch,int detail,int db) {
    if(!r||!valid(pitch,detail,db))return 0;
    memset(r,0,sizeof *r);
    if(!su_init(&r->source,m,SM_SEED,pitch/1000.,detail/1000.,1))return 0;
    r->attenuation=r->target_attenuation=pow(10,db/20.);r->follow=1-exp(-1/(.018*m->rate));return 1;
}
int sm_render_set(SmRender *r,int pitch,int detail,int db) {
    if(!r||!valid(pitch,detail,db)||!su_set(&r->source,pitch/1000.,detail/1000.,1))return 0;
    r->target_attenuation=pow(10,db/20.);return 1;
}
void sm_render_process(SmRender *r,float *raw,float *out,unsigned frames,int stop) {
    unsigned n,c;double block[1024];
    if(stop)r->stopping=1;
    while(frames){unsigned count=frames>512?512:frames;
        su_process(&r->source,block,count);
        for(n=0;n<count;++n){double envelope;
            r->attenuation+=r->follow*(r->target_attenuation-r->attenuation);
            envelope=r->onset<240?r->onset++/239.:1;
            if(r->stopping){if(r->release<480)++r->release;envelope*=1-r->release/480.;}
            for(c=0;c<2;++c){raw[2*n+c]=(float)block[2*n+c];out[2*n+c]=(float)(block[2*n+c]*.5*r->attenuation*envelope);}
        }
        raw+=count*2;out+=count*2;frames-=count;
    }
}
