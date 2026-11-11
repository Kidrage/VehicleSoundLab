#ifndef VSL_WAV_H
#define VSL_WAV_H
#include <stdio.h>
#include <stddef.h>
typedef struct { FILE *file; unsigned sample_rate, frames,channels,floating; } VslWavWriter;
int vsl_wav_begin(VslWavWriter *w,const char *path,unsigned sample_rate);
int vsl_wav_begin_layout(VslWavWriter *w,const char *path,unsigned sample_rate,unsigned channels);
int vsl_wav_begin_float(VslWavWriter *w,const char *path,unsigned sample_rate,unsigned channels);
int vsl_wav_write(VslWavWriter *w,const float *stereo,unsigned frames);
int vsl_wav_end(VslWavWriter *w);
/* Non realtime import. PCM 16/24/32 and IEEE float 32; mono/stereo only. */
float *vsl_wav_read(const char *path,unsigned *frames,unsigned *sample_rate);
#endif
