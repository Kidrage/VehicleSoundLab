#include "internal.h"
unsigned es_contour_index(const EsProfile *p,float hz) {
    unsigned i;
    for(i=0;i<ES_CONTOURS;++i)if(p->contours[i].count&&hz>=p->contours[i].low_hz&&hz<p->contours[i].high_hz)return i+1;
    return 0;
}
float es_contour_gain(const EsContour *p,float seconds) {
    unsigned i;
    if(!p->count)return 1;
    if(seconds<=p->seconds[0])return p->gain[0];
    for(i=1;i<p->count;++i)if(seconds<p->seconds[i]) {
        float t=(seconds-p->seconds[i-1])/(p->seconds[i]-p->seconds[i-1]);
        return p->gain[i-1]+t*(p->gain[i]-p->gain[i-1]);
    }
    return p->gain[p->count-1];
}
