#define _CRT_SECURE_NO_WARNINGS
#include "trajectory.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

int sp_trajectory_load(SpTrajectory *path,const char *filename) {
    FILE *file; char line[160],extra; unsigned long long frame; double hz;
    size_t count=0; int ok=1;
    if(!path||!filename)return 0;
    memset(path,0,sizeof *path);
    file=fopen(filename,"rb");if(!file)return 0;
    while(fgets(line,sizeof line,file)) {
        if(!strchr(line,'\n')&&!feof(file)){ok=0;break;}
        if(count==SP_MAX_POINTS||sscanf(line,"%llu %lf %c",&frame,&hz,&extra)!=2||
           frame>SP_MAX_FRAMES||!isfinite(hz)||hz<0||hz>1000||
           (!count&&frame!=0)||(count&&frame<=path->point[count-1].frame)){ok=0;break;}
        path->point[count++]=(SpPoint){(unsigned)frame,hz};
    }
    if(ferror(file)||count<2)ok=0;
    if(fclose(file))ok=0;
    if(!ok){memset(path,0,sizeof *path);return 0;}
    path->count=count;return 1;
}
int sp_trajectory_value(SpTrajectory *path,unsigned frame,double *hz) {
    const SpPoint *a,*b; double x;
    if(!path||!hz||path->count<2||frame>path->point[path->count-1].frame||
       frame<path->point[path->cursor].frame)return 0;
    while(path->cursor+2<path->count&&frame>=path->point[path->cursor+1].frame)++path->cursor;
    a=&path->point[path->cursor];b=a+1;
    x=(double)(frame-a->frame)/(b->frame-a->frame);
    *hz=a->root_hz+x*(b->root_hz-a->root_hz);return 1;
}
