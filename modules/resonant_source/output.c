#include "output.h"
#include <math.h>
int rss_output_frame(const SbLayout *layout,const RssFrame *f,double gain,double width,double *out) {
    double stereo[2];
    if(!layout||(layout->channels!=2&&layout->channels!=12)||!f||!out||
       !isfinite(gain)||gain<0||gain>1||!isfinite(width)||width<0||width>1||
       !isfinite(f->mix[0])||!isfinite(f->mix[1]))return 0;
    stereo[0]=f->mix[0]*gain;stereo[1]=f->mix[1]*gain;
    sb_route(layout,stereo,width,out);return 1;
}
