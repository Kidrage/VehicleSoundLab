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
int sm_render_body_init(SmRender *r,const LbProfile *profile,double amount){return lb_init(&r->body,profile,r->source.pitch,amount);}
int sm_render_body_amount(SmRender *r,double amount){return lb_set(&r->body,r->source.pitch_target,amount,r->body.target_envelope);}
void sm_render_process(SmRender *r,float *raw,float *out,unsigned frames,int stop) {
    unsigned n,c;double block[1024],low[512];
    if(stop)r->stopping=1;
    while(frames){unsigned count=frames>512?512:frames;
        if(r->body.profile){
            const SuHarmonic *h=&r->source.model->harmonic[4];double f=r->source.fraction;
            double re=h->mean[0]+r->source.amount*(r->source.left[4][0]+f*(r->source.right[4][0]-r->source.left[4][0]));
            double im=h->mean[1]+r->source.amount*(r->source.left[4][1]+f*(r->source.right[4][1]-r->source.left[4][1]));
            double envelope=fmax(.5,fmin(1.5,hypot(re,im)/fmax(hypot(h->mean[0],h->mean[1]),1e-12)));
            lb_set(&r->body,r->source.pitch_target,r->body.target_amount,envelope);
            lb_process(&r->body,low,count);
        }else memset(low,0,count*sizeof(double));
        su_process(&r->source,block,count);
        for(n=0;n<count;++n){double envelope;
            r->attenuation+=r->follow*(r->target_attenuation-r->attenuation);
            envelope=r->onset<240?r->onset++/239.:1;
            if(r->stopping){if(r->release<480)++r->release;envelope*=1-r->release/480.;}
            for(c=0;c<2;++c){raw[2*n+c]=(float)block[2*n+c];out[2*n+c]=(float)((low[n]!=0?block[2*n+c]+low[n]:block[2*n+c])*.5*r->attenuation*envelope);}
        }
        raw+=count*2;out+=count*2;frames-=count;
    }
}
