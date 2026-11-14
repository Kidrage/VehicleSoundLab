#include "listen.h"
#include <string.h>
int lm_selection_valid(int selection){return selection>=0&&selection<LM_SELECTIONS;}
int lm_listen_init(LmListen *s,int selection) {
    if(!s||!lm_selection_valid(selection))return 0;
    memset(s,0,sizeof *s);s->selection=selection;s->weight[selection]=1;return 1;
}
int lm_listen_set(LmListen *s,int selection) {
    int k;if(!s||!lm_selection_valid(selection))return 0;
    if(s->selection==selection)return 1;
    s->selection=selection;s->remaining=LM_RAMP_FRAMES;
    for(k=0;k<LM_SELECTIONS;++k)s->step[k]=((k==selection?1.:0.)-s->weight[k])/LM_RAMP_FRAMES;
    return 1;
}
int lm_listen_process(LmListen *s,float *pcm,const float *layers,unsigned frames) {
    unsigned n;int k,c;
    if(!s||!lm_selection_valid(s->selection)||(frames&&(!pcm||!layers)))return 0;
    if(!s->remaining&&s->selection==0)return 1; /*Exact full-mix bypass. */
    for(n=0;n<frames;++n) {
        if(s->remaining) {
            if(!--s->remaining)for(k=0;k<LM_SELECTIONS;++k)s->weight[k]=k==s->selection?1:0;
            else for(k=0;k<LM_SELECTIONS;++k)s->weight[k]+=s->step[k];
        }
        for(c=0;c<2;++c) {
            double x=s->weight[0]*pcm[2*n+c];
            for(k=0;k<LM_LAYERS;++k)if(s->weight[k+1]!=0)x+=s->weight[k+1]*layers[n*LM_SAMPLES+2*k+c];
            pcm[2*n+c]=(float)x;
        }
    }
    return 1;
}
