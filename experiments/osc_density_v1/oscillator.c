#include "oscillator.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846
int do_render(const DoModel *m,double *mono) {
    double window[1024];unsigned g,j,n;
    if(!m||!m->grains||!mono||m->window>1024||m->hop*4!=m->window)return 0;
    memset(mono,0,m->frames*sizeof *mono);
    /* Four periodic Hann windows have constant squared sum=1.5. */
    for(n=0;n<m->window;++n)window[n]=(.5-.5*cos(2*PI*n/m->window))/1.5;
    for(g=0;g<m->count;++g) {
        const DoGrain *grain=&m->grains[g];
        for(j=0;j<grain->count;++j) {
            const DoTone *t=&grain->tones[j];
            double angle=2*PI*t->bin/m->window,c=1,s=0,dc=cos(angle),ds=sin(angle);
            double scale=(t->bin==0||t->bin==m->window/2?1.:2.)/m->window;
            for(n=0;n<m->window;++n) {
                int index=grain->start+(int)n;double next=c*dc-s*ds;
                if(index>=0&&(unsigned)index<m->frames)
                    mono[index]+=(t->real*c-t->imag*s)*scale*window[n];
                s=s*dc+c*ds;c=next;
            }
        }
    }
    for(n=0;n<m->frames;++n)if(!isfinite(mono[n]))return 0;
    return 1;
}
