/* Fresh native-schema inputs for native-versus-frozen character validation.
   Does not import, translate or rewrite historical takes. */
#include "core/engine.h"
#include "session/take.h"
#include "io/take_file.h"
#include "io/drive_trace.h"
#include "io/file.h"
#include "drive/scenarios.h"
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
#include <inttypes.h>
static int number(const char *s,double lo,double hi,double *v) {
    char *end;*v=strtod(s,&end);return end!=s&&!*end&&isfinite(*v)&&*v>=lo&&*v<=hi;
}
int main(int argc,char **argv) {
    VslTake t={0};VslEngine *e=NULL;VslParams p=vsl_default_params(VSL_V10);float audio[1024];
    double seconds;int scenario,ok=0;uint64_t frames;FILE *trace=NULL;char trace_path[4096];
    if((argc<8||argc>12)||snprintf(trace_path,sizeof trace_path,"%s.csv",argv[1])>=(int)sizeof trace_path) { puts("vsl_character_probe output.vsltake scenario seconds rpm load pressure structure [response_shape [event_color [firing_source [pulse_amount]]]] (ASCII diagnostic paths)");return 1; }
    scenario=vsl_scenario_id(argv[2]);
    if(scenario<0||!number(argv[3],.1,60,&seconds)||!number(argv[4],0,10000,&p.rpm)||
       !number(argv[5],-1,1,&p.load)||!number(argv[6],0,1,&p.pressure_texture)||!number(argv[7],0,1,&p.structure_transfer))return 1;
    if(argc>=9&&!number(argv[8],0,1,&p.response_shape))return 1;
    if(argc>=10&&!number(argv[9],0,1,&p.event_color))return 1;
    if(argc>=11) { double mode;if(!number(argv[10],0,2,&mode)||floor(mode)!=mode)return 1;p.firing_source=(int)mode; }
    if(argc==12&&!number(argv[11],0,1,&p.pulse_amount))return 1;
    e=malloc(sizeof *e);if(!e||!vsl_take_allocate(&t,20000))goto done;
    vsl_init(e,48000,48271);vsl_set_params(e,&p);frames=(uint64_t)(seconds*48000+.5);
    if(!vsl_take_begin(&t,e))goto done;
    trace=vsl_fopen(trace_path,"w");if(!trace)goto done;vsl_trace_header(trace);
    while(e->frame<frames) {
        unsigned n=(unsigned)(frames-e->frame);if(n>512)n=512;
        vsl_scenario_apply(scenario,e->frame/48000.,&p);vsl_set_params(e,&p);
        if(!vsl_take_record(&t,e->frame,&e->target))goto done;
        while(n) {
            unsigned chunk=e->control_period-(unsigned)(e->frame%e->control_period);if(chunk>n)chunk=n;
            vsl_process(e,audio,chunk);vsl_take_commit(&t,audio,chunk);n-=chunk;
            if(e->frame%e->control_period==0)vsl_trace_frame(trace,e,e->frame/48000.);
        }
    }
    vsl_take_finish(&t);if(!vsl_take_save(argv[1],&t))goto done;
    printf("Native %s | frames %" PRIu64 " | events %u | hash %016" PRIx64 "\n",VSL_VERSION,t.frames,t.count,t.audio_hash);ok=1;
done:if(trace) { if(ferror(trace))ok=0;if(fclose(trace))ok=0; }vsl_take_free(&t);free(e);return ok?0:2;
}
