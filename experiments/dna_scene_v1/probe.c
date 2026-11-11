#define _CRT_SECURE_NO_WARNINGS
#include "dna_scene/scene.h"
#include "core/engine.h"
#include "spatial/scene.h"
#include "io/wav.h"
#include "io/file.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif

#define BLOCK 512
#define FILES (6 + VSL_OBJECTS)
static SdProfile dna, low;
static DsScene scene;
static VslEngine spatial;
static float rendered[BLOCK * 12], dry[BLOCK * 2], dna_raw[BLOCK * 2], low_raw[BLOCK * 2];
static float dna_layer[BLOCK * 2], low_layer[BLOCK * 2], stems[BLOCK * VSL_OBJECTS], mono[BLOCK];

static int number(const char *value, double *result) {
    char *end;
    *result = strtod(value, &end);
    return end != value && !*end && isfinite(*result);
}

static int run(int argc, char **argv) {
    DsSceneConfig config = {{0}, DS_OBSERVE_LEFT, DS_ROUTE_PAIR, 2};
    DsSceneControl control = {{1, 1, 1, 1, 1}, .5, 1, 0, 0, 0};
    DsCapture capture = {dna_raw, low_raw, dna_layer, low_layer, dry, stems};
    VslWavWriter writers[FILES] = {{0}};
    const char *suffix[6] = {"render", "dry", "dna_raw", "low_raw", "dna", "low"};
    float *buffers[6] = {rendered, dry, dna_raw, low_raw, dna_layer, low_layer};
    double seconds = 8, peak = 0, cpu = 0;
    unsigned frames, at = 0;
    int i, ok = 0;
    if (argc < 4) {
        fputs("usage: dna_scene_probe DNA.model LOW.model|- OUTPUT_PREFIX [--seconds 8 --channels 2|12 --pitch 1 --dna 1 --low 1 --low-scale 1 --detail 1 --low-detail 1 --gain .5 --width 1 --space 0 --perspective 0 --propagation 0|1 --route pair|left|right --projection left|right|mid]\n", stderr);
        return 1;
    }
    config.source.low_scale = 1;
    config.source.dna_seed = config.source.low_seed = 48271;
    for (i = 4; i < argc; i += 2) {
        double value;
        const char *option = argv[i], *arg;
        if (i + 1 == argc) return 1;
        arg = argv[i+1];
        if (!strcmp(option, "--route")) {
            if (!strcmp(arg, "pair")) config.route = DS_ROUTE_PAIR;
            else if (!strcmp(arg, "left")) config.route = DS_ROUTE_LEFT;
            else if (!strcmp(arg, "right")) config.route = DS_ROUTE_RIGHT;
            else return 1;
            continue;
        }
        if (!strcmp(option, "--projection")) {
            if (!strcmp(arg, "left")) config.projection = DS_OBSERVE_LEFT;
            else if (!strcmp(arg, "right")) config.projection = DS_OBSERVE_RIGHT;
            else if (!strcmp(arg, "mid")) config.projection = DS_OBSERVE_MID;
            else return 1;
            continue;
        }
        if (!number(arg, &value)) return 1;
        if (!strcmp(option, "--seconds")) seconds = value;
        else if (!strcmp(option, "--channels")) {
            if (value != 2 && value != 12) return 1;
            config.channels = (int)value;
        } else if (!strcmp(option, "--pitch")) control.source.pitch = value;
        else if (!strcmp(option, "--dna")) control.source.dna_gain = value;
        else if (!strcmp(option, "--low")) control.source.low_gain = value;
        else if (!strcmp(option, "--low-scale")) config.source.low_scale = value;
        else if (!strcmp(option, "--detail")) control.source.dna_detail = value;
        else if (!strcmp(option, "--low-detail")) control.source.low_detail = value;
        else if (!strcmp(option, "--gain")) control.output_gain = value;
        else if (!strcmp(option, "--width")) control.width = value;
        else if (!strcmp(option, "--space")) control.space = value;
        else if (!strcmp(option, "--perspective")) control.perspective = value;
        else if (!strcmp(option, "--propagation")) {
            if (value != 0 && value != 1) return 1;
            control.propagation = (int)value;
        } else return 1;
    }
    if (seconds <= 0 || seconds > 60 || !sd_profile_load(argv[1], &dna)) return 2;
    config.source.dna = &dna;
    if (strcmp(argv[2], "-")) {
        if (!sd_profile_load(argv[2], &low)) return 2;
        config.source.low = &low;
    }
    if (!ds_scene_init(&scene, &spatial, &config, &control)) return 2;
    for (i = 0; i < FILES; ++i) {
        char path[4096];
        const char *name = i < 6 ? suffix[i] : vsl_object_info(i-6)->name;
        int length = snprintf(path, sizeof path, "%s_%s.wav", argv[3], name);
        FILE *existing;
        if (length < 0 || length >= (int)sizeof path) goto done;
        existing = vsl_fopen(path, "rb");
        if (existing) { fclose(existing); fprintf(stderr, "refusing existing output: %s\n", path); goto done; }
        if (!vsl_wav_begin_float(&writers[i], path, 48000, i == 0 ? (unsigned)config.channels : i < 6 ? 2u : 1u)) goto done;
    }
    frames = (unsigned)(seconds * 48000 + .5);
    while (at < frames) {
        unsigned n = frames - at, j, c;
        clock_t start;
        if (n > BLOCK) n = BLOCK;
        start = clock();
        if (!ds_scene_process(&scene, rendered, n, &capture)) goto done;
        cpu += (double)(clock() - start) / CLOCKS_PER_SEC;
        for (j = 0; j < n * (unsigned)config.channels; ++j) {
            if (!isfinite(rendered[j])) goto done;
            peak = fmax(peak, fabs(rendered[j]));
        }
        for (i = 0; i < 6; ++i) if (!vsl_wav_write(&writers[i], buffers[i], n)) goto done;
        for (c = 0; c < VSL_OBJECTS; ++c) {
            for (j = 0; j < n; ++j) mono[j] = stems[j * VSL_OBJECTS + c];
            if (!vsl_wav_write(&writers[c+6], mono, n)) goto done;
        }
        at += n;
    }
    printf("{\"frames\":%u,\"channels\":%d,\"source_frame\":%llu,\"legacy_frame\":%llu,\"peak\":%.12g,\"process_clock_seconds\":%.6g}\n",
        frames, config.channels, (unsigned long long)scene.source.frame, (unsigned long long)spatial.frame, peak, cpu);
    ok = 1;
done:
    for (i = 0; i < FILES; ++i) if (writers[i].file && !vsl_wav_end(&writers[i])) ok = 0;
    return ok ? 0 : 3;
}

#ifdef _WIN32
int wmain(int argc, wchar_t **wide) {
    char **args = calloc((size_t)argc, sizeof *args);
    int i, result = 2;
    if (!args) return 2;
    for (i = 0; i < argc; ++i) {
        int length = WideCharToMultiByte(CP_UTF8, 0, wide[i], -1, NULL, 0, NULL, NULL);
        if (!length || !(args[i] = malloc((size_t)length)) ||
            !WideCharToMultiByte(CP_UTF8, 0, wide[i], -1, args[i], length, NULL, NULL)) goto done;
    }
    result = run(argc, args);
done:
    for (i = 0; i < argc; ++i) free(args[i]);
    free(args);
    return result;
}
#else
int main(int argc, char **argv) { return run(argc, argv); }
#endif
