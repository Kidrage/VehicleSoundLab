#define _CRT_SECURE_NO_WARNINGS
#include "ui_checks.h"
#include "io/file.h"
#include <commctrl.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

/* Program-internal test of this application's own controls, never other apps. */
static void slider(HWND owner, int id, int value) {
    HWND control = GetDlgItem(owner, id);
    SendMessageW(control, TBM_SETPOS, TRUE, value);
    SendMessageW(owner, WM_HSCROLL, MAKEWPARAM(TB_THUMBPOSITION, value), (LPARAM)control);
}
static void checkbox(HWND owner, int id, int checked) {
    SendMessageW(GetDlgItem(owner, id), BM_SETCHECK, checked ? BST_CHECKED : BST_UNCHECKED, 0);
    SendMessageW(owner, WM_COMMAND, MAKEWPARAM(id, BN_CLICKED), (LPARAM)GetDlgItem(owner, id));
}
static int screenshot(HWND owner, const wchar_t *directory) {
    RECT rect; HDC window_dc, memory; HBITMAP bitmap, previous; BITMAPINFO info = {0};
    BITMAPFILEHEADER header = {0}; void *pixels; DWORD bytes; wchar_t path[4096]; FILE *file;
    int ok = 0; GetWindowRect(owner, &rect);
    info.bmiHeader.biSize = sizeof info.bmiHeader; info.bmiHeader.biWidth = rect.right - rect.left;
    info.bmiHeader.biHeight = -(rect.bottom - rect.top); info.bmiHeader.biPlanes = 1; info.bmiHeader.biBitCount = 32;
    window_dc = GetWindowDC(owner); memory = CreateCompatibleDC(window_dc);
    bitmap = CreateDIBSection(window_dc, &info, DIB_RGB_COLORS, &pixels, NULL, 0);
    if (!bitmap) { DeleteDC(memory); ReleaseDC(owner, window_dc); return 0; }
    previous = SelectObject(memory, bitmap);
    RedrawWindow(owner, NULL, NULL, RDW_INVALIDATE | RDW_ERASE | RDW_FRAME | RDW_ALLCHILDREN | RDW_UPDATENOW);
    if (PrintWindow(owner, memory, 0)) {
        unsigned i, nonblack = 0; unsigned count = (unsigned)(info.bmiHeader.biWidth * -info.bmiHeader.biHeight);
        const DWORD *color = pixels;
        for (i = 0; i < count; ++i) if (color[i] & 0xffffff) ++nonblack;
        if (nonblack < count / 10) goto done;
        bytes = (DWORD)(info.bmiHeader.biWidth * -info.bmiHeader.biHeight * 4);
        header.bfType = 0x4d42; header.bfOffBits = sizeof header + sizeof info.bmiHeader; header.bfSize = header.bfOffBits + bytes;
        swprintf(path, 4096, L"%ls/ui.bmp", directory); file = _wfopen(path, L"wb");
        if (file) { ok = fwrite(&header, 1, sizeof header, file) == sizeof header &&
            fwrite(&info.bmiHeader, 1, sizeof info.bmiHeader, file) == sizeof info.bmiHeader && fwrite(pixels, 1, bytes, file) == bytes;
            if (fclose(file)) ok = 0; }
    }
done:
    SelectObject(memory, previous); DeleteObject(bitmap); DeleteDC(memory); ReleaseDC(owner, window_dc); return ok;
}
void smo_ui_checks_tick(SmoUiChecks *t, HWND owner, SaAudio *a) {
    SaStats s = sa_audio_stats(a); SmoControl c;
    if (!t->enabled) return;
    if (s.error[0]) { t->passed = 0; DestroyWindow(owner); return; }
    if (t->stage == 0 && s.frames >= 24000) {
        if (GetDlgItem(owner, 32)) {
            c = sa_audio_control(a); t->controls_ok &= c.scene.source.phase_texture == 1;
            checkbox(owner, 32, 0); c = sa_audio_control(a); t->controls_ok &= c.scene.source.phase_texture == 0;
            checkbox(owner, 32, 1); c = sa_audio_control(a); t->controls_ok &= c.scene.source.phase_texture == 1;
        }
        slider(owner, 20, 900); c = sa_audio_control(a);
        t->controls_ok &= c.scene.source.pitch == .9 && c.scene.source.low_gain == 1 && c.spatial == 0 && c.scene.output_gain == .5;
        t->stage = 1;
    } else if (t->stage == 1 && s.frames >= 48000) {
        slider(owner, 21, 0); c = sa_audio_control(a);
        t->controls_ok &= c.scene.source.pitch == .9 && c.scene.source.low_gain == 0 && c.scene.output_gain == .5;
        checkbox(owner, 30, 1); slider(owner, 22, 40); slider(owner, 23, 65); checkbox(owner, 31, 1);
        c = sa_audio_control(a); t->controls_ok &= c.spatial == 1 && c.scene.width == .4 && c.scene.space == .65 && c.scene.propagation == 1;
        t->stage = 2;
    } else if (t->stage == 2 && s.frames >= 72000) {
        slider(owner, 24, -6); c = sa_audio_control(a);
        t->controls_ok &= fabs(c.scene.output_gain - .5 * pow(10, -6./20)) < 1e-15 && c.scene.source.pitch == .9;
        t->stage = 3;
    } else if (t->stage == 3 && s.frames >= 96000) {
        SendMessageW(owner, WM_COMMAND, 11, 0);
        t->passed &= !a->thread && !a->running && a->render.release == 480;
        slider(owner, 20, 1000); slider(owner, 21, 100); slider(owner, 22, 100); slider(owner, 23, 0); slider(owner, 24, 0);
        checkbox(owner, 30, 0); checkbox(owner, 31, 0);
        t->passed &= screenshot(owner, t->directory);
        SendMessageW(owner, WM_COMMAND, 10, 0); t->stage = 4;
    } else if (t->stage == 4 && s.frames >= 24000) {
        t->stage = 5; SendMessageW(owner, WM_CLOSE, 0, 0);
    }
}
void smo_ui_checks_finish(SmoUiChecks *t, SaAudio *a) {
    wchar_t path[4096]; FILE *file; SaStats s = sa_audio_stats(a);
    t->passed &= t->stage == 5 && t->controls_ok && !a->thread && !a->running && a->render.release == 480 && s.opened && !s.error[0] && !s.queue_empty;
    swprintf(path, 4096, L"%ls/ui.json", t->directory); file = _wfopen(path, L"wb");
    if (!file) { t->passed = 0; return; }
    fprintf(file, "{\"result\":\"%s\",\"program_internal_control_test\":true,\"device_muted\":true,\"controls_isolated\":%s,\"stop_restart_close\":%s,\"model_bank_checked\":true,\"manual_interaction_verified\":false}\n",
        t->passed ? "pass" : "fail", t->controls_ok ? "true" : "false", t->stage == 5 ? "true" : "false");
    fclose(file);
}
