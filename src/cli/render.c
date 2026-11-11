#define _CRT_SECURE_NO_WARNINGS
#include "io/render_session.h"
#include "io/scene_metadata.h"
#include "drive/scenarios.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#ifdef _WIN32
#include <windows.h>
#endif
static int unit_argument(const char *s,double *out) {
    char *end;double x=strtod(s,&end);
    if(end==s||*end||!isfinite(x)||x<0||x>1)return 0;
    *out=x;return 1;
}
static int render_main(int argc,char**argv) {
    VslParams p=vsl_default_params(0); double seconds=12; int drive=1,i;
    const char *dna=NULL,*ir=NULL,*trace=NULL,*stems=NULL,*scene=NULL;int channels=2;
    if(argc<2) {
        puts("vsl_render output.wav [--profile 0..4] [--pure] [--rpm N] [--load -1..1]\n"
             "  [--throttle 0..1] [--brake 0..1] [--width 0..1] [--space 0..1] [--cabin]\n"
             "  [--detail 0..1] [--mechanical 0..1] [--mechanical-model 0|1]\n"
             "  [--combustion-variation 0|1] [--irregularity 0..1] [--fuel-cut 0|1] [--pumping 0..1]\n"
             "  [--propagation 0|1] (source distance, stereo ear delay and simple head shadow)\n"
             "  [--pressure-texture 0..1] [--structure-transfer 0..1] (experimental; default off)\n"
             "  [--firing-source 0|1|2] [--pulse-amount 0..1] (OSC / fixed / variable; default OSC)\n"
             "  [--scenario fixed|auto|lift|shifts|neutral|downshift] [--seconds N] [--channels 2|12]\n"
             "  [--trace file.csv] [--stems prefix] [--scene scene.json] [--dna file.dna] [--ir file.wav]");return 1;
    }
    for(i=2;i<argc;++i) {
        if(!strcmp(argv[i],"--pure"))p.pure_osc=1;
        else if(!strcmp(argv[i],"--profile") && i+1<argc)p.profile=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--scenario") && i+1<argc) { drive=vsl_scenario_id(argv[++i]);if(drive<0) { fputs("Scenario: fixed, auto, lift, shifts, neutral or downshift\n",stderr);return 1; } }
        else if(!strcmp(argv[i],"--rpm") && i+1<argc) { p.rpm=atof(argv[++i]); drive=0; }
        else if(!strcmp(argv[i],"--load") && i+1<argc)p.load=atof(argv[++i]);
        else if(!strcmp(argv[i],"--throttle") && i+1<argc) { p.throttle=atof(argv[++i]);p.drive_mode=VSL_PEDALS;drive=0; }
        else if(!strcmp(argv[i],"--brake") && i+1<argc)p.brake=atof(argv[++i]);
        else if(!strcmp(argv[i],"--width") && i+1<argc)p.width=atof(argv[++i]);
        else if(!strcmp(argv[i],"--space") && i+1<argc)p.space=atof(argv[++i]);
        else if(!strcmp(argv[i],"--detail") && i+1<argc)p.detail=atof(argv[++i]);
        else if(!strcmp(argv[i],"--mechanical") && i+1<argc)p.mechanical=atof(argv[++i]);
        else if(!strcmp(argv[i],"--mechanical-model") && i+1<argc)p.mechanical_model=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--combustion-variation") && i+1<argc)p.combustion_variation=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--propagation") && i+1<argc)p.propagation=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--pressure-texture") && i+1<argc) { if(!unit_argument(argv[++i],&p.pressure_texture))return 1; }
        else if(!strcmp(argv[i],"--structure-transfer") && i+1<argc) { if(!unit_argument(argv[++i],&p.structure_transfer))return 1; }
        else if(!strcmp(argv[i],"--firing-source") && i+1<argc) {
            const char *s=argv[++i];
            if(strlen(s)!=1||s[0]<'0'||s[0]>'2')return 1;
            p.firing_source=s[0]-'0';
        }
        else if(!strcmp(argv[i],"--pulse-amount") && i+1<argc) { if(!unit_argument(argv[++i],&p.pulse_amount))return 1; }
        else if(!strcmp(argv[i],"--irregularity") && i+1<argc)p.irregularity=atof(argv[++i]);
        else if(!strcmp(argv[i],"--fuel-cut") && i+1<argc)p.fuel_cut=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--pumping") && i+1<argc)p.pumping=atof(argv[++i]);
        else if(!strcmp(argv[i],"--cabin"))p.perspective=1;
        else if(!strcmp(argv[i],"--channels") && i+1<argc)channels=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--trace") && i+1<argc)trace=argv[++i];
        else if(!strcmp(argv[i],"--stems") && i+1<argc)stems=argv[++i];
        else if(!strcmp(argv[i],"--scene") && i+1<argc)scene=argv[++i];
        else if(!strcmp(argv[i],"--seconds") && i+1<argc)seconds=atof(argv[++i]);
        else if(!strcmp(argv[i],"--dna") && i+1<argc)dna=argv[++i];
        else if(!strcmp(argv[i],"--ir") && i+1<argc)ir=argv[++i];
        else { fprintf(stderr,"Unknown/incomplete option: %s\n",argv[i]); return 1; }
    }
    if(p.profile<0 || p.profile>=VSL_PROFILE_COUNT || seconds<=0 || seconds>3600 || p.rpm<0 || p.rpm>10000 || p.load< -1 || p.load>1 || p.fuel_cut<0 || p.fuel_cut>1 || p.pumping<0 || p.pumping>1 || p.mechanical_model<0 || p.mechanical_model>1 || p.mechanical<0 || p.mechanical>1 || p.combustion_variation<0 || p.combustion_variation>1 || p.irregularity<0 || p.irregularity>1)return 1;
    if(p.propagation<0 || p.propagation>1)return 1;
    if(!vsl_render_session(argv[1],&p,seconds,drive,dna,ir,channels,trace,stems)) { fputs("Render failed\n",stderr); return 2; }
    if(scene) {
        vsl_scenario_apply(drive,0,&p);
        if(!vsl_write_scene_metadata(scene,&p,channels,stems)) { fputs("Scene metadata failed\n",stderr);return 2; }
    }
    printf("Rendered %s | DSP %s | seed 48271 | 48000 Hz | profile %d | pure %d\n",argv[1],VSL_VERSION,p.profile,p.pure_osc); return 0;
}
#ifdef _WIN32
int wmain(int argc,wchar_t**wide) {
    int i,result; char **args=(char**)calloc((size_t)argc,sizeof(char*));
    if(!args)return 2;
    for(i=0;i<argc;++i) {
        int size=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);
        args[i]=(char*)malloc(size);
        if(!args[i]) { while(i)free(args[--i]); free(args); return 2; }
        WideCharToMultiByte(CP_UTF8,0,wide[i],-1,args[i],size,NULL,NULL);
    }
    result=render_main(argc,args); for(i=0;i<argc;++i)free(args[i]); free(args); return result;
}
#else
int main(int argc,char**argv) { return render_main(argc,argv); }
#endif

