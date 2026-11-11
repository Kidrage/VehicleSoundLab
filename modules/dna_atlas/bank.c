#include "bank.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846

static double wrap(double x) { return remainder(x, 2*PI); }
static int valid(const SdProfile *m) {
    unsigned h,c,k,j;
    if (!m || m->rate!=48000 || m->window!=1024 || m->hop!=256 ||
        !m->harmonics || m->harmonics>SD_MAX_HARMONICS || m->components>SD_MAX_COMPONENTS ||
        !isfinite(m->base_hz) || m->base_hz<5 || m->harmonics*m->base_hz*1.1>21600) return 0;
    for (k=0;k<m->components;++k) if (!isfinite(m->rho[k]) || fabs(m->rho[k])>.95) return 0;
    for (h=0;h<m->harmonics;++h) {
        const SdHarmonic *a=&m->harmonic[h];
        if (!isfinite(a->rho) || fabs(a->rho)>.95) return 0;
        for (c=0;c<4;++c) {
            if (!isfinite(a->mean[c]) || fabs(a->mean[c])>4) return 0;
            for (k=0;k<m->components;++k) if (!isfinite(a->basis[k][c]) || fabs(a->basis[k][c])>4) return 0;
            for (j=0;j<4;++j) if (!isfinite(a->root[c][j]) || fabs(a->root[c][j])>4) return 0;
        }
    }
    return 1;
}

static double score(const SaBank *b, unsigned next, unsigned orders, double offset) {
    unsigned h,c;
    double sum=0;
    for (h=0;h<orders;++h) for (c=0;c<2;++c) {
        const double *a=b->profile[next-1]->harmonic[h].mean;
        const double *z=b->profile[next]->harmonic[h].mean;
        double ma=hypot(a[2*c],a[2*c+1]), mb=hypot(z[2*c],z[2*c+1]);
        double phase=atan2(z[2*c+1],z[2*c])+(h+1)*offset;
        sum+=ma*mb*cos(b->phase[next-1][h][c]-phase);
    }
    return sum;
}

int sa_bank_init(SaBank *bank, const SdProfile *const *models, unsigned count, unsigned orders) {
    SaBank result;
    unsigned a,h,c,i,pass;
    if (!bank || !models || !count || count>SA_MAX_ANCHORS || orders>32) return 0;
    for (a=0;a<count;++a) if (!valid(models[a]) || (a &&
        (models[a]->harmonics!=models[0]->harmonics || models[a]->base_hz<=models[a-1]->base_hz))) return 0;
    memset(&result,0,sizeof result);
    result.count=count;result.harmonics=models[0]->harmonics;
    for (i=0;i<=SA_TABLE_SIZE;++i) result.sine[i]=sin(2*PI*i/SA_TABLE_SIZE);
    if (orders>result.harmonics) orders=result.harmonics;
    for (a=0;a<count;++a) {
        double best=0;
        result.profile[a]=models[a];
        if (a && orders) {
            double step=2*PI/4096, value=score(&result,a,orders,0);
            /* Search all origins; exact score ties retain the smaller shift. */
            for (i=0;i<4096;++i) {
                double x=-PI+i*step, v=score(&result,a,orders,x);
                if (v>value+1e-15 || (fabs(v-value)<=1e-15 && fabs(x)<fabs(best))) { best=x;value=v; }
            }
            for (pass=0;pass<3;++pass) {
                double center=best;step/=16;
                for (i=0;i<=32;++i) {
                    double x=center+((int)i-16)*step, v=score(&result,a,orders,x);
                    if (v>value) { best=x;value=v; }
                }
            }
        }
        result.offset[a]=wrap(best);
        for (h=0;h<result.harmonics;++h) for (c=0;c<2;++c) {
            const double *z=models[a]->harmonic[h].mean;
            double norm=hypot(z[2*c],z[2*c+1]);
            double phase=wrap((norm>1e-15?atan2(z[2*c+1],z[2*c]):0)+(h+1)*best);
            result.phase[a][h][c]=phase;
            result.unit[a][h][2*c]=cos(phase);result.unit[a][h][2*c+1]=sin(phase);
        }
        if (a) for (h=0;h<result.harmonics;++h) {
            double *d=result.delta[a-1][h];
            d[0]=wrap(result.phase[a][h][0]-result.phase[a-1][h][0]);
            /* Interpolate L/R relative phase on one shared branch. Independent
               shortest arcs can wind opposite ways and flip stereo at midpoint. */
            d[1]=d[0]+wrap((result.phase[a][h][1]-result.phase[a][h][0])-
                (result.phase[a-1][h][1]-result.phase[a-1][h][0]));
        }
    }
    *bank=result;
    return 1;
}

double sa_bank_sine(const SaBank *b, double radians) {
    double x=radians*(SA_TABLE_SIZE/(2*PI)), fraction;
    unsigned i;
    x-=floor(x/SA_TABLE_SIZE)*SA_TABLE_SIZE;
    /* Tiny negative inputs can round up to4096 during periodic reduction. */
    if (x>=SA_TABLE_SIZE) x=0;
    i=(unsigned)x;fraction=x-i;
    return b->sine[i]+fraction*(b->sine[i+1]-b->sine[i]);
}
