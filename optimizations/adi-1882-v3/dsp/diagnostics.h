#ifndef VSL_DIAGNOSTICS_H
#define VSL_DIAGNOSTICS_H
#ifdef VSL_CAPTURE_MODULES
extern unsigned vsl_diag_index;
void vsl_diag_put(unsigned module,const float x[2]);
void vsl_diag_copy(float *out,unsigned frames);
#else
#define vsl_diag_put(module,x) ((void)(module),(void)(x))
#endif
#endif
