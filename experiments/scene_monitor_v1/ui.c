#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <commctrl.h>
#include <commdlg.h>
#include <shellapi.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "audio.h"
#include "models.h"
#include "ui_checks.h"
static SmoModels models;
static SaAudio audio;
static SmoUiChecks checks;
static HWND sliders[5], labels[5], status, voices;
static HFONT font, heading;
static int last_voice;
static int phase_study;
static const wchar_t *dna_paths[] = {L"voices/dna_bank_v1/V10 Exterior.model", L"voices/dna_bank_v1/Warm Additive.model", L"voices/dna_bank_v1/Hollow Spectrum.model"};
static const wchar_t *low_path = L"voices/coherent_low_v1/measured_phase.model";

static HWND control(HWND owner, const wchar_t *kind, const wchar_t *text, DWORD style, int id, int x, int y, int width, int height) {
    HWND item = CreateWindowW(kind, text, WS_CHILD | WS_VISIBLE | style, x, y, width, height, owner, (HMENU)(INT_PTR)id, NULL, NULL);
    SendMessageW(item, WM_SETFONT, (WPARAM)font, TRUE); return item;
}
static void controls(HWND owner) {
    SmoControl c = sa_audio_control(&audio); wchar_t text[100]; int values[5], i;
    for (i = 0; i < 5; ++i) values[i] = (int)SendMessageW(sliders[i], TBM_GETPOS, 0, 0);
    c.scene.source.pitch = values[0] / 1000.; c.scene.source.low_gain = models.has_low ? values[1] / 100. : 0;
    c.scene.width = values[2] / 100.; c.scene.space = values[3] / 100.; c.scene.output_gain = .5 * pow(10, values[4] / 20.);
    c.spatial = SendMessageW(GetDlgItem(owner, 30), BM_GETCHECK, 0, 0) == BST_CHECKED;
    c.scene.propagation = SendMessageW(GetDlgItem(owner, 31), BM_GETCHECK, 0, 0) == BST_CHECKED;
    c.scene.source.phase_texture = phase_study && SendMessageW(GetDlgItem(owner, 32), BM_GETCHECK, 0, 0) == BST_CHECKED ? 1 : 0;
    sa_audio_controls(&audio, &c);
    swprintf(text, 100, L"相对音高    ×%.2f", c.scene.source.pitch); SetWindowTextW(labels[0], text);
    if (models.has_low) swprintf(text, 100, L"低频轰鸣    %d%%", values[1]); else wcscpy_s(text, 100, L"低频轰鸣    当前音色未配低频模型");
    SetWindowTextW(labels[1], text);
    swprintf(text, 100, L"空间宽度    %d%%", values[2]); SetWindowTextW(labels[2], text);
    swprintf(text, 100, L"房间量    %d%%", values[3]); SetWindowTextW(labels[3], text);
    swprintf(text, 100, L"输出衰减    %d dB", values[4]); SetWindowTextW(labels[4], text);
    EnableWindow(sliders[1], models.has_low); EnableWindow(sliders[2], c.spatial); EnableWindow(sliders[3], c.spatial);
    EnableWindow(GetDlgItem(owner, 31), c.spatial);
    if (status && !InterlockedCompareExchange(&audio.running, 0, 0))
        SetWindowTextW(status, c.spatial ? L"已停止 · 空间监听" : L"已停止 · 直送监听");
}
static int load_model(HWND owner, const wchar_t *dna, const wchar_t *low) {
    SmoModels *candidate = malloc(sizeof *candidate); int ok = 0;
    if (candidate && smo_models_read(candidate, dna, low)) {
        sa_audio_stop(&audio); models = *candidate;
        audio.config = smo_recipe_config(&models.dna, models.has_low ? &models.low : NULL);
        SendMessageW(sliders[1], TBM_SETPOS, TRUE, models.has_low ? 100 : 0); controls(owner); ok = 1;
    }
    free(candidate); return ok;
}
static int bank_checks(HWND owner) {
    SmoModels *saved = malloc(sizeof *saved); int ok = saved != NULL, i;
    if (!saved) return 0;
    for (i = 1; i >= 0; --i) {
        SendMessageW(voices, CB_SETCURSEL, i ? 2 : 1, 0);
        SendMessageW(owner, WM_COMMAND, MAKEWPARAM(40, CBN_SELCHANGE), (LPARAM)voices);
        ok &= !models.has_low && !IsWindowEnabled(sliders[1]);
    }
    *saved = models; ok &= !smo_models_read(&models, L"missing.model", NULL) && !memcmp(saved, &models, sizeof models);
    SendMessageW(voices, CB_SETCURSEL, 0, 0);
    SendMessageW(owner, WM_COMMAND, MAKEWPARAM(40, CBN_SELCHANGE), (LPARAM)voices);
    ok &= models.has_low && IsWindowEnabled(sliders[1]); free(saved); return ok;
}
static LRESULT CALLBACK procedure(HWND owner, UINT message, WPARAM w, LPARAM l) {
    switch (message) {
    case WM_CREATE: {
        const int minimum[] = {900, 0, 0, 0, -18}, maximum[] = {1100, 100, 100, 100, 0}, initial[] = {1000, 100, 100, 0, 0};
        int i;
        font = CreateFontW(-17, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"Microsoft YaHei UI");
        heading = CreateFontW(-24, 0, 0, 0, FW_SEMIBOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"Microsoft YaHei UI");
        SendMessageW(control(owner, L"STATIC", L"持续声源", 0, 0, 24, 18, 470, 32), WM_SETFONT, (WPARAM)heading, TRUE);
        control(owner, L"STATIC", L"DNA + 低频轰鸣", 0, 0, 24, 55, 470, 26);
        if (phase_study) {
            HWND phase = control(owner, L"BUTTON", L"共同微扰 · 轻量", BS_AUTOCHECKBOX | WS_TABSTOP, 32, 275, 52, 230, 28);
            SendMessageW(phase, BM_SETCHECK, BST_CHECKED, 0);
        }
        voices = control(owner, WC_COMBOBOXW, L"", CBS_DROPDOWNLIST | WS_TABSTOP, 40, 24, 88, 342, 200);
        SendMessageW(voices, CB_ADDSTRING, 0, (LPARAM)L"V10 · 车外"); SendMessageW(voices, CB_ADDSTRING, 0, (LPARAM)L"Warm · 合成测试");
        SendMessageW(voices, CB_ADDSTRING, 0, (LPARAM)L"Hollow · 合成测试"); SendMessageW(voices, CB_SETCURSEL, 0, 0);
        control(owner, L"BUTTON", L"载入 DNA", BS_PUSHBUTTON | WS_TABSTOP, 41, 382, 85, 120, 34);
        for (i = 0; i < 5; ++i) {
            int y = 137 + i * 65;
            labels[i] = control(owner, L"STATIC", L"", 0, 0, 24, y, 478, 26);
            sliders[i] = control(owner, TRACKBAR_CLASSW, L"", TBS_HORZ | TBS_NOTICKS | WS_TABSTOP, 20 + i, 24, y + 27, 478, 30);
            SendMessageW(sliders[i], TBM_SETRANGEMIN, FALSE, minimum[i]); SendMessageW(sliders[i], TBM_SETRANGEMAX, TRUE, maximum[i]);
            SendMessageW(sliders[i], TBM_SETPOS, TRUE, initial[i]);
        }
        control(owner, L"BUTTON", L"空间监听", BS_AUTOCHECKBOX | WS_TABSTOP, 30, 24, 478, 200, 28);
        control(owner, L"BUTTON", L"几何传播", BS_AUTOCHECKBOX | WS_TABSTOP, 31, 262, 478, 220, 28);
        control(owner, L"BUTTON", L"播放／重新开始", BS_PUSHBUTTON | WS_TABSTOP, 10, 24, 526, 204, 40);
        control(owner, L"BUTTON", L"停止", BS_PUSHBUTTON | WS_TABSTOP, 11, 246, 526, 112, 40);
        status = control(owner, L"STATIC", L"已停止 · 直送监听", 0, 0, 24, 584, 478, 28);
        control(owner, L"STATIC", L"固定声学情境 · 启用空间监听后可调宽度与房间", 0, 0, 24, 620, 500, 26);
        controls(owner); SetTimer(owner, 1, 25, NULL);
        return 0;
    }
    case WM_HSCROLL: controls(owner); return 0;
    case WM_COMMAND:
        if (LOWORD(w) == 30 || LOWORD(w) == 31 || LOWORD(w) == 32) { controls(owner); return 0; }
        if (LOWORD(w) == 40 && HIWORD(w) == CBN_SELCHANGE) {
            int selection = (int)SendMessageW(voices, CB_GETCURSEL, 0, 0);
            if (selection >= 0 && selection < 3) {
                if (!load_model(owner, dna_paths[selection], selection == 0 ? low_path : NULL)) {
                    SendMessageW(voices, CB_SETCURSEL, last_voice, 0);
                    if (checks.enabled) checks.passed = 0; else MessageBoxW(owner, L"模型无法载入，保留原音色。", L"Vehicle Sound Lab", MB_OK);
                } else last_voice = selection;
            }
            return 0;
        }
        if (LOWORD(w) == 41) {
            wchar_t path[2048] = {0}; OPENFILENAMEW file = {0};
            file.lStructSize = sizeof file; file.hwndOwner = owner; file.lpstrFilter = L"Sound DNA model\0*.model\0\0";
            file.lpstrFile = path; file.nMaxFile = 2048; file.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR;
            if (GetOpenFileNameW(&file)) {
                if (load_model(owner, path, NULL)) {
                    if (SendMessageW(voices, CB_GETCOUNT, 0, 0) > 3) SendMessageW(voices, CB_DELETESTRING, 3, 0);
                    SendMessageW(voices, CB_ADDSTRING, 0, (LPARAM)L"自定义 DNA"); SendMessageW(voices, CB_SETCURSEL, 3, 0); last_voice = 3;
                } else MessageBoxW(owner, L"模型无法载入，保留原音色。", L"Vehicle Sound Lab", MB_OK);
            }
            return 0;
        }
        if (LOWORD(w) == 10) {
            if (!sa_audio_start(&audio)) { if (checks.enabled) { checks.passed = 0; DestroyWindow(owner); }
                else MessageBoxW(owner, L"无法开始监听。", L"Vehicle Sound Lab", MB_OK); }
            return 0;
        }
        if (LOWORD(w) == 11) { sa_audio_stop(&audio); return 0; }
        break;
    case WM_TIMER: {
        SaStats s = sa_audio_stats(&audio); SmoControl c = sa_audio_control(&audio); wchar_t text[160];
        if (s.error[0]) swprintf(text, 160, L"%ls", s.error);
        else if (InterlockedCompareExchange(&audio.running, 0, 0)) swprintf(text, 160, L"%ls   %.1f s    峰值 %.1f dBFS", c.spatial ? L"空间监听" : L"直送监听", s.frames / 48000., 20 * log10(fmax(1e-9, s.peak)));
        else swprintf(text, 160, L"已停止 · %ls", c.spatial ? L"空间监听" : L"直送监听");
        SetWindowTextW(status, text); if (checks.enabled) smo_ui_checks_tick(&checks, owner, &audio); return 0;
    }
    case WM_CTLCOLORSTATIC: SetBkMode((HDC)w, TRANSPARENT); return (LRESULT)GetSysColorBrush(COLOR_WINDOW);
    case WM_CLOSE: DestroyWindow(owner); return 0;
    case WM_DESTROY:
        KillTimer(owner, 1); sa_audio_stop(&audio); if (checks.enabled) smo_ui_checks_finish(&checks, &audio);
        if (font) DeleteObject(font); if (heading) DeleteObject(heading); PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(owner, message, w, l);
}

static int project_directory(void) {
    wchar_t path[4096]; int i;
    if (GetFileAttributesW(dna_paths[0]) != INVALID_FILE_ATTRIBUTES) return 1;
    if (!GetModuleFileNameW(NULL, path, 4096)) return 0;
    for (i = 0; i < 6; ++i) {
        wchar_t *slash = wcsrchr(path, L'\\'); if (!slash) return 0; *slash = 0;
        if (SetCurrentDirectoryW(path) && GetFileAttributesW(dna_paths[0]) != INVALID_FILE_ATTRIBUTES) return 1;
    }
    return 0;
}
int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command, int show) {
    int argc, muted = 0, i; wchar_t **args = CommandLineToArgvW(GetCommandLineW(), &argc);
    WNDCLASSW klass = {0}; INITCOMMONCONTROLSEX common = {sizeof common, ICC_BAR_CLASSES}; HWND window; MSG message = {0};
    DsSceneConfig config; SmoControl initial = smo_recipe_control(); (void)previous; (void)command;
    if (!args) return 2;
    for (i = 1; i < argc; ++i) {
        if (!wcscmp(args[i], L"--muted")) muted = 1;
        else if (!wcscmp(args[i], L"--phase-texture")) phase_study = 1;
        else if (!wcscmp(args[i], L"--ui-checks") && i + 1 < argc) {
            checks.enabled = 1; muted = 1; checks.passed = checks.controls_ok = 1;
            if (!GetFullPathNameW(args[++i], 2048, checks.directory, NULL)) { LocalFree(args); return 2; }
        } else { LocalFree(args); return 2; }
    }
    LocalFree(args);
    if (!project_directory() || !smo_models_read(&models, dna_paths[0], low_path)) return 2;
    config = smo_recipe_config(&models.dna, &models.low); sa_audio_init(&audio, &config, &initial, muted);
    InitCommonControlsEx(&common); klass.lpfnWndProc = procedure; klass.hInstance = instance;
    klass.lpszClassName = L"VslSceneMonitorV1"; klass.hCursor = LoadCursorW(NULL, IDC_ARROW); klass.hbrBackground = GetSysColorBrush(COLOR_WINDOW);
    if (!RegisterClassW(&klass)) { sa_audio_destroy(&audio); return 2; }
    window = CreateWindowW(klass.lpszClassName, phase_study ? L"Vehicle Sound Lab · Shared Phase" : L"Vehicle Sound Lab · DNA + Low + Space", WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT, 560, 710, NULL, NULL, instance, NULL);
    if (!window) { sa_audio_destroy(&audio); return 2; }
    if (checks.enabled) {
        checks.passed &= bank_checks(window); PostMessageW(window, WM_COMMAND, 10, 0);
    }
    ShowWindow(window, checks.enabled ? SW_SHOWNOACTIVATE : show); UpdateWindow(window);
    while (GetMessageW(&message, NULL, 0, 0) > 0) {
        if (!IsDialogMessageW(window, &message)) { TranslateMessage(&message); DispatchMessageW(&message); }
    }
    sa_audio_destroy(&audio); return checks.enabled && !checks.passed ? 3 : 0;
}
