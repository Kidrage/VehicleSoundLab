/* Included after magnitude() in dna_atlas/voice.c. Coefficients are evaluated
   at 375 Hz by default; all original stochastic innovations and the audio phase advance
   every sample. Adjacent 2048-point stereo tables crossfade over SA_TABLE_HOP samples. */
#ifdef VSL_ADSP_21569
#include <filter.h>
#endif
void sa_table_init(SaTable *t){
    unsigned i;memset(t,0,sizeof *t);
    for(i=0;i<SA_TABLE_POINTS/2;++i){
        float a=2*PI*i/SA_TABLE_POINTS;t->roots[i].re=cosf(a);t->roots[i].im=sinf(a);
    }
}
static void table_inverse(SaTable *t,SaTableComplex *output){
#ifdef VSL_ADSP_21569
    complex_float *result=ifft2048((complex_float *)(void *)t->work,(complex_float *)(void *)t->temporary);
    memcpy(output,result,sizeof t->work);
#else
    unsigned i,j,size;
    for(i=1,j=0;i<SA_TABLE_POINTS;++i){
        unsigned bit=SA_TABLE_POINTS>>1;
        for(;j&bit;bit>>=1)j^=bit;j^=bit;
        if(i<j){SaTableComplex z=t->work[i];t->work[i]=t->work[j];t->work[j]=z;}
    }
    for(size=2;size<=SA_TABLE_POINTS;size<<=1){unsigned half=size>>1,start;
        for(start=0;start<SA_TABLE_POINTS;start+=size)for(i=0;i<half;++i){
            SaTableComplex w=t->roots[i*(SA_TABLE_POINTS/size)],a=t->work[start+i],b=t->work[start+i+half],z;
            z.re=b.re*w.re-b.im*w.im;z.im=b.re*w.im+b.im*w.re;
            t->work[start+i].re=a.re+z.re;t->work[start+i].im=a.im+z.im;
            t->work[start+i+half].re=a.re-z.re;t->work[start+i+half].im=a.im-z.im;
        }
    }
    for(i=0;i<SA_TABLE_POINTS;++i){output[i].re=t->work[i].re/SA_TABLE_POINTS;output[i].im=t->work[i].im/SA_TABLE_POINTS;}
#endif
}
static float table_cubic(float a,float b,float c,float d,float u){
    return b+.5f*u*(c-a+u*(2*a-5*b+4*c-d+u*(3*(b-c)+d-a)));
}
static void table_read(const SaTableComplex *p,unsigned i,float u,float out[2]){
    const SaTableComplex *a=p+((i-1)&(SA_TABLE_POINTS-1)),*b=p+i;
    const SaTableComplex *c=p+((i+1)&(SA_TABLE_POINTS-1)),*d=p+((i+2)&(SA_TABLE_POINTS-1));
    out[0]=table_cubic(a->re,b->re,c->re,d->re,u);out[1]=table_cubic(a->im,b->im,c->im,d->im,u);
}
static void table_build(const SaVoice *v,unsigned lo,unsigned hi,float blend,const HbBand *band,
                        const float *shape,float amount,unsigned target){
    SaTable *t=v->table;const SaBank *b=v->bank;unsigned h,c,kind;
    float (*coefficients)[4]=t->coefficients,*weights=t->weights;
    memset(coefficients,0,sizeof t->coefficients);memset(weights,0,sizeof t->weights);
    for(h=0;h<b->harmonics;++h){
        float hz=(h+1)*v->root_hz,aa=1;
        if(hz>=21600)break;
        if(hz>19200){float x=(hz-19200)/2400;aa=1-x*x*(3-2*x);}
        weights[h]=band?hb_band_weight_inline(band,hz):0;
        for(c=0;c<2;++c){
            float mag=magnitude(b,v->sample_cache,v->texture,lo,h,c,v->detail,v->texture[lo].fraction);
            const float *unit=b->unit[lo][h];float re=unit[2*c],im=unit[2*c+1];
            if(lo!=hi){
                float phase=b->phase[lo][h][c]+blend*b->delta[lo][h][c];
                mag+=blend*(magnitude(b,v->sample_cache,v->texture,hi,h,c,v->detail,v->texture[hi].fraction)-mag);
                if(blend==1){re=b->unit[hi][h][2*c];im=b->unit[hi][h][2*c+1];}
                else if(blend!=0){re=sa_bank_sine(b,phase+PI/2);im=sa_bank_sine(b,phase);}
            }
            mag*=aa;if(shape&&amount>0)mag*=1+amount*(shape[h]-1);
            coefficients[h][2*c]=mag*re;coefficients[h][2*c+1]=mag*im;
        }
    }
    for(kind=0;kind<(band?2u:1u);++kind){
        memset(t->work,0,sizeof t->work);
        for(h=0;h<b->harmonics;++h){
            const float *z=coefficients[h];float scale=(SA_TABLE_POINTS*.5f)*(kind?weights[h]:1);
            unsigned p=h+1,n=SA_TABLE_POINTS-p;
            t->work[p].re=scale*(z[0]-z[3]);t->work[p].im=scale*(z[1]+z[2]);
            t->work[n].re=scale*(z[0]+z[3]);t->work[n].im=scale*(-z[1]+z[2]);
        }
        table_inverse(t,kind?t->body[target]:t->main[target]);
    }
}
static void table_sample(const SaVoice *v,unsigned lo,unsigned hi,float blend,float out[2],float body[2],
                         const HbBand *band,const float *shape,float amount){
    SaTable *t=v->table;unsigned current=(unsigned)(v->frame/SA_TABLE_HOP)&1,previous=current^1,c;
    float position=v->phase*(SA_TABLE_POINTS/(2*PI));unsigned index=((unsigned)position)&(SA_TABLE_POINTS-1);
    float fraction=position-(unsigned)position,a[2],b[2],u=(float)(v->frame&(SA_TABLE_HOP-1))/SA_TABLE_HOP;
    if(t->has_body!=(body!=NULL))t->ready=0;
    if(!t->ready||!(v->frame&(SA_TABLE_HOP-1))){
        table_build(v,lo,hi,blend,band,shape,amount,current);
        if(!t->ready){
            memcpy(t->main[previous],t->main[current],sizeof t->main[current]);
            if(body)memcpy(t->body[previous],t->body[current],sizeof t->body[current]);
            t->ready=1;
        }
    }
    table_read(t->main[previous],index,fraction,a);table_read(t->main[current],index,fraction,b);
    for(c=0;c<2;++c)out[c]=a[c]+u*(b[c]-a[c]);
    if(body){table_read(t->body[previous],index,fraction,a);table_read(t->body[current],index,fraction,b);
        for(c=0;c<2;++c)body[c]=a[c]+u*(b[c]-a[c]);}
    t->has_body=body!=NULL;
}
