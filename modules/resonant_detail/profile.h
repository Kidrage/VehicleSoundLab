#ifndef VSL_RESONANT_DETAIL_PROFILE_H
#define VSL_RESONANT_DETAIL_PROFILE_H
#define RDT_MAX_BANDS 12
#define RDT_MAX_AR 24
#define RDT_MAX_SOS 4
#define RDT_MAX_ENVELOPE 12
typedef struct {
    unsigned order,sections,envelope_order;
    double low_hz,high_hz,sigma,gain,right_over_left;
    double a[RDT_MAX_AR+1],sos[RDT_MAX_SOS][6];
    /* All cosine coefficients, followed by all sine coefficients. */
    double beta[2*RDT_MAX_ENVELOPE];
} RdtBand;
typedef struct {
    unsigned rate,count,warmup_frames;
    double base_hz;
    RdtBand band[RDT_MAX_BANDS];
} RdtProfile;
/* Non-RT: bounded poles and a conservative continuous-phase power bound.
   Profiles remain immutable and caller-owned throughout voice operation. */
int rdt_profile_valid(const RdtProfile *profile);
#endif
