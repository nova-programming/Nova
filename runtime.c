#if defined(_WIN32)
/* Windows: use Win32 API directly — no CRT headers needed, no name conflicts.
 * All runtime functions use Win32 API so CRT linkage is optional. */

/* SysV ABI attribute — Nova x86_64 codegen uses System V AMD64 calling convention
 * (args: rdi, rsi, rdx, rcx, r8, r9) while Windows uses Microsoft x64 ABI
 * (args: rcx, rdx, r8, r9). This attribute makes the compiler generate SysV-convention
 * entry/exit so the assembly's call sites work on both Linux and Windows. */
#if defined(__x86_64__)
#define SYSCALL __attribute__((sysv_abi))
#else
#define SYSCALL
#endif

/* On x86 (32-bit), MinGW adds _ prefix to C symbols automatically, matching the
 * assembly's references to _printf, _malloc, etc.
 * On x64, MinGW does NOT add _ prefix. The x86_64 codegen still emits _printf
 * (for Linux/macOS compatibility), so on x64 we must define with explicit _ prefix.
 * Using STR_PFX, on x64 we define _strlen/_malloc etc. which don't conflict with
 * system headers that declare strlen/malloc (without underscore). */
#if defined(_WIN64)
#define STR_PFX(name) _##name
#else
#define STR_PFX(name) name
#endif

/* On x64 Windows, stdlib.h (indirectly included by windows.h) declares _exit with
 * __cdecl, which conflicts with our SYSCALL (sysv_abi) _exit definition.
 * We suppress _exit declarations before including windows.h, then undefine. */
#if defined(_WIN64)
#define _exit(...) /* suppress stdlib.h _exit declaration */
#endif

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdarg.h>

#if defined(_WIN64)
#undef _exit
#endif

/* All runtime functions are SYSCALL to match the Nova codegen calling convention.
 * Inside the function body, Win32 API calls use the default Windows convention —
 * the compiler handles the ABI translation at call sites automatically. */

/* Minimal printf: handles %s, %d, %% for Nova codegen.
 * Uses SysV ABI variadic args directly (read from registers) to avoid MinGW
 * va_start/va_arg incompatibility with __attribute__((sysv_abi)). */
SYSCALL int STR_PFX(printf)(const char *fmt, const void *arg_s) {
    HANDLE h = GetStdHandle(-11);
    DWORD wn;
    int written = 0;
    while (*fmt) {
        if (*fmt == '%') {
            fmt++;
            switch (*fmt) {
                case 's': {
                    const char *s = (const char*)arg_s;
                    if (s) { int n = lstrlenA(s); WriteFile(h, s, n, &wn, 0); written += n; }
                    break;
                }
                case 'd': {
                    char buf[32];
                    int val = (int)(long long)arg_s;
                    int neg = 0, pos = 30, dlen;
                    buf[31] = 0;
                    if (val < 0) { neg = 1; val = -val; }
                    do { buf[pos--] = '0' + (val % 10); val /= 10; } while (val);
                    if (neg) buf[pos--] = '-';
                    pos++;
                    dlen = 31 - pos;
                    WriteFile(h, buf + pos, dlen, &wn, 0);
                    written += dlen;
                    break;
                }
                case '%': {
                    WriteFile(h, "%", 1, &wn, 0); written++;
                    break;
                }
                default: break;
            }
        } else {
            WriteFile(h, fmt, 1, &wn, 0);
            written++;
        }
        fmt++;
    }
    return written;
}

SYSCALL int STR_PFX(fopen)(const char *path, const char *mode) {
    HANDLE h; DWORD access, disp;
    if (*mode == 'w') { access = 0x40000000; disp = 2; }
    else if (*mode == 'a') { access = 0xC0000000; disp = 4; }
    else { access = 0x80000000; disp = 3; }
    h = CreateFileA(path, access, 0, 0, disp, 0x80, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;
    if (*mode == 'a') SetFilePointer(h, 0, 0, 2);
    return (int)(intptr_t)h;
}
SYSCALL int STR_PFX(fclose)(int s) { return CloseHandle((HANDLE)(intptr_t)s) ? 0 : -1; }
SYSCALL int STR_PFX(fread)(void *b, int sz, int c, int s) { DWORD n; ReadFile((HANDLE)(intptr_t)s, b, sz*c, &n, 0); return n; }
SYSCALL int STR_PFX(fwrite)(const void *b, int sz, int c, int s) { DWORD n; WriteFile((HANDLE)(intptr_t)s, b, sz*c, &n, 0); return n; }
SYSCALL int STR_PFX(fputs)(const char *str, int s) { int n = lstrlenA(str); STR_PFX(fwrite)(str, 1, n, s); return n; }
SYSCALL int STR_PFX(fputc)(int c, int s) { char ch = c; STR_PFX(fwrite)(&ch, 1, 1, s); return c; }
SYSCALL int STR_PFX(fseek)(int s, long o, int w) { return SetFilePointer((HANDLE)(intptr_t)s, o, 0, w) == -1 ? -1 : 0; }
SYSCALL long STR_PFX(ftell)(int s) { return SetFilePointer((HANDLE)(intptr_t)s, 0, 0, 1); }
SYSCALL int STR_PFX(fflush)(int s) { if (s) FlushFileBuffers((HANDLE)(intptr_t)s); return 0; }
SYSCALL void STR_PFX(exit)(int c) { ExitProcess(c); }
SYSCALL int STR_PFX(system)(const char *c) { return (int)WinExec(c, 1); }

/* String/memory functions — manual implementations to avoid ABI transition bugs */
SYSCALL unsigned int STR_PFX(strlen)(const char *s) {
    unsigned int n = 0;
    while (s[n]) n++;
    return n;
}
SYSCALL int STR_PFX(strcmp)(const char *a, const char *b) { return lstrcmpA(a, b); }
SYSCALL char *STR_PFX(strcpy)(char *d, const char *s) { return lstrcpyA(d, s); }
SYSCALL char *STR_PFX(strcat)(char *d, const char *s) { return lstrcatA(d, s); }
SYSCALL void *STR_PFX(memset)(void *p, int c, unsigned int n) {
    unsigned char *b = (unsigned char*)p;
    while (n--) *b++ = (unsigned char)c;
    return p;
}
SYSCALL void *STR_PFX(memcpy)(void *d, const void *s, unsigned int n) {
    unsigned char *bd = (unsigned char*)d;
    const unsigned char *bs = (const unsigned char*)s;
    while (n--) *bd++ = *bs++;
    return d;
}

/* Memory functions via Win32 Heap API (no CRT dependency).
 * Note: HeapReAlloc does not zero memory like realloc; fine for Nova's usage. */
static HANDLE _nova_heap = 0;
SYSCALL void *STR_PFX(malloc)(unsigned int s) {
    if (!_nova_heap) _nova_heap = GetProcessHeap();
    return HeapAlloc(_nova_heap, 0, s);
}
SYSCALL void STR_PFX(free)(void *p) {
    if (p) { if (!_nova_heap) _nova_heap = GetProcessHeap(); HeapFree(_nova_heap, 0, p); }
}
SYSCALL void *STR_PFX(realloc)(void *p, unsigned int s) {
    if (!_nova_heap) _nova_heap = GetProcessHeap();
    return HeapReAlloc(_nova_heap, 0, p, s);
}

/* strstr — we may not need it but define for completeness */
SYSCALL char *STR_PFX(strstr)(const char *h, const char *n) {
    if (!*n) return (char*)h;
    while (*h) {
        const char *a = h, *b = n;
        while (*a && *b && *a == *b) { a++; b++; }
        if (!*b) return (char*)h;
        h++;
    }
    return 0;
}

/* Custom sprintf that handles %d and basic floats, respecting SysV ABI registers */
SYSCALL int STR_PFX(sprintf)(char *b, const char *fmt, long long arg_d) {
    char *out = b;
    while (*fmt) {
        if (*fmt == '%') {
            fmt++;
            if (*fmt == 'd') {
                char buf[32];
                long long val = arg_d;
                int neg = 0, pos = 30;
                buf[31] = 0;
                if (val < 0) { neg = 1; val = -val; }
                do { buf[pos--] = '0' + (val % 10); val /= 10; } while (val);
                if (neg) buf[pos--] = '-';
                pos++;
                while (buf[pos]) *out++ = buf[pos++];
            } else if (*fmt == 'f') {
                /* floats are passed in xmm0 */
                double arg_f = 0.0;
                asm("movsd %%xmm0, %0" : "=m"(arg_f) : : "memory");
                
                long long val = (long long)arg_f;
                int neg = 0;
                if (arg_f < 0.0) { neg = 1; val = -val; arg_f = -arg_f; }
                if (neg) *out++ = '-';
                
                char buf[32];
                int pos = 30;
                buf[31] = 0;
                do { buf[pos--] = '0' + (val % 10); val /= 10; } while (val);
                pos++;
                while (buf[pos]) *out++ = buf[pos++];
                
                *out++ = '.';
                double frac = arg_f - (double)(long long)arg_f;
                for (int i = 0; i < 6; i++) {
                    frac *= 10.0;
                    int digit = (int)frac;
                    *out++ = '0' + digit;
                    frac -= digit;
                }
            } else {
                *out++ = *fmt;
            }
        } else {
            *out++ = *fmt;
        }
        fmt++;
    }
    *out = 0;
    return out - b;
}
/* Out-of-bounds handler */
SYSCALL void STR_PFX(out_of_bounds)(void) {
    STR_PFX(printf)("Index Out Of Bounds\n", 0);
    STR_PFX(exit)(1);
}

/* ============== Nova sys_* runtime ============== */
/* Removed: sys_open, sys_write, etc. are now implemented natively in Nova os_* modules. */

/* ============== Entry point bridge for Windows x64 ============== */
/* MinGW x64 CRT expects main() (no _ prefix). Nova codegen emits _main (with _ prefix
 * for Linux compatibility). This bridge lets CRT startup find the entry point. */
#if defined(_WIN64)
int main(void) {
    extern int _main(void);
    return _main();
}
#endif

#elif defined(LINUX_WRAP) || defined(MACOS)
/* Linux: libc exports without underscore (printf, not _printf).
 * Our assembly calls _printf, _malloc, etc. — these wrappers bridge the gap.
 * macOS: libc exports with underscore, so no wrappers needed — but we still
 * need the standard headers for our own runtime functions (dict, etc.). */
#if defined(LINUX_WRAP)
#define _GNU_SOURCE
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdint.h>

#if defined(LINUX_WRAP)
int _printf(const char *fmt, ...) {
    va_list ap; va_start(ap, fmt);
    int n = vprintf(fmt, ap); va_end(ap);
    fflush(stdout);
    return n;
}
void *_malloc(size_t s) { return malloc(s); }
void _free(void *p) { free(p); }
void *_realloc(void *p, size_t s) { return realloc(p, s); }
size_t _strlen(const char *s) { return strlen(s); }
int _strcmp(const char *a, const char *b) { return strcmp(a, b); }
char *_strcpy(char *d, const char *s) { return strcpy(d, s); }
char *_strcat(char *d, const char *s) { return strcat(d, s); }
void *_memset(void *p, int c, size_t n) { return memset(p, c, n); }
char *_strstr(const char *h, const char *n) { return strstr(h, n); }
int _fopen(const char *p, const char *m) {
    FILE *f = fopen(p, m);
    return f ? (intptr_t)f : 0;
}
int _fclose(int s) { return fclose((FILE*)(intptr_t)s); }
int _fwrite(const void *b, int sz, int c, int s) { return fwrite(b, sz, c, (FILE*)(intptr_t)s); }
int _fread(void *b, int sz, int c, int s) { return fread(b, sz, c, (FILE*)(intptr_t)s); }
int _fputs(const char *str, int s) { return fputs(str, (FILE*)(intptr_t)s); }
int _fputc(int c, int s) { return fputc(c, (FILE*)(intptr_t)s); }
int _fseek(int s, long o, int w) { return fseek((FILE*)(intptr_t)s, o, w); }
long _ftell(int s) { return ftell((FILE*)(intptr_t)s); }
int _fflush(int s) { return fflush((FILE*)(intptr_t)s); }
void _exit(int c) { exit(c); }
int _system(const char *c) { return system(c); }
int _sprintf(char *b, const char *fmt, ...) {
    va_list ap; va_start(ap, fmt);
    int n = vsprintf(b, fmt, ap); va_end(ap);
    return n;
}

#endif /* defined(LINUX_WRAP) */
#endif /* defined(_WIN32) / defined(LINUX_WRAP) || defined(MACOS) */

/* ==================== Dict runtime functions (all platforms) ==================== */
/* Forward declarations for dict functions (Linux/macOS need these since malloc/free/memset
 * aren't defined yet. On Windows they're already defined above.) */
#if !defined(_WIN32)
SYSCALL void *malloc(size_t);
SYSCALL void free(void *);
SYSCALL void *memset(void *, int, size_t);
#endif
/* strcmp, strlen, strcpy are defined above on Windows, in <string.h> on macOS/Linux */
/* Dict layout (24 bytes): [count:4][pad/capacity:4][keys_ptr:8][values_ptr:8] */

/* FNV-1a hash */
static unsigned long _dh(const char *s) {
    unsigned long h = 2166136261UL;
    while (*s) { h ^= (unsigned char)(*s++); h *= 16777619UL; }
    return h;
}

/* Find key slot; returns index or -1 */
static int _df(char **keys, int cap, const char *key) {
    if (!keys || cap < 1) return -1;
    unsigned long h = _dh(key);
    int idx = (int)(h % (unsigned long)cap);
    for (int i = 0; i < cap; i++) {
        int j = (idx + i) % cap;
        if (!keys[j]) return -1;
        if (strcmp(keys[j], key) == 0) return j;
    }
    return -1;
}

/* Grow: double capacity, rehash */
static void _dg(void *d) {
    int cap = *(int*)((char*)d + 4);
    char **ok = *(char***)((char*)d + 8);
    intptr_t *ov = *(intptr_t**)((char*)d + 16);
    int nc = cap * 2;
    char **nk = (char**)malloc((size_t)nc * sizeof(char*));
    intptr_t *nv = (intptr_t*)malloc((size_t)nc * sizeof(intptr_t));
    if (!nk || !nv) { free(nk); free(nv); return; }
    memset(nk, 0, (size_t)nc * sizeof(char*));
    memset(nv, 0, (size_t)nc * sizeof(intptr_t));
    for (int i = 0; i < cap; i++) {
        if (ok[i]) {
            unsigned long h = _dh(ok[i]);
            int idx = (int)(h % (unsigned long)nc);
            while (nk[idx]) idx = (idx + 1) % nc;
            nk[idx] = ok[i];
            nv[idx] = ov[i];
        }
    }
    free(ok); free(ov);
    *(char***)((char*)d + 8) = nk;
    *(intptr_t**)((char*)d + 16) = nv;
    *(int*)((char*)d + 4) = nc;
}

SYSCALL void *dict_new(void) {
    void *d = malloc(24);
    if (!d) return 0;
    int cap = 8;
    *(int*)d = 0;
    *(int*)((char*)d + 4) = cap;
    char **keys = (char**)malloc((size_t)cap * sizeof(char*));
    intptr_t *values = (intptr_t*)malloc((size_t)cap * sizeof(intptr_t));
    if (!keys || !values) { free(keys); free(values); free(d); return 0; }
    memset(keys, 0, (size_t)cap * sizeof(char*));
    memset(values, 0, (size_t)cap * sizeof(intptr_t));
    *(char***)((char*)d + 8) = keys;
    *(intptr_t**)((char*)d + 16) = values;
    return d;
}

SYSCALL int dict_has(void *d, const char *key) {
    int cap = *(int*)((char*)d + 4);
    char **keys = *(char***)((char*)d + 8);
    return _df(keys, cap, key) >= 0 ? 1 : 0;
}

SYSCALL intptr_t dict_get(void *d, const char *key) {
    int cap = *(int*)((char*)d + 4);
    char **keys = *(char***)((char*)d + 8);
    intptr_t *values = *(intptr_t**)((char*)d + 16);
    int idx = _df(keys, cap, key);
    return idx >= 0 ? values[idx] : 0;
}

SYSCALL void dict_set(void *d, const char *key, intptr_t value) {
    int count = *(int*)d;
    int cap = *(int*)((char*)d + 4);
    char **keys = *(char***)((char*)d + 8);
    intptr_t *values = *(intptr_t**)((char*)d + 16);
    int idx = _df(keys, cap, key);
    if (idx >= 0) { values[idx] = value; return; }
    /* Grow if load > 70% */
    if (count * 10 >= cap * 7) {
        _dg(d);
        cap = *(int*)((char*)d + 4);
        keys = *(char***)((char*)d + 8);
        values = *(intptr_t**)((char*)d + 16);
    }
    unsigned long h = _dh(key);
    idx = (int)(h % (unsigned long)cap);
    while (keys[idx]) idx = (idx + 1) % cap;
    size_t len = strlen(key) + 1;
    keys[idx] = (char*)malloc(len);
    if (keys[idx]) { strcpy(keys[idx], key); }
    values[idx] = value;
    *(int*)d = count + 1;
}

SYSCALL void dict_remove(void *d, const char *key) {
    int cap = *(int*)((char*)d + 4);
    char **keys = *(char***)((char*)d + 8);
    intptr_t *values = *(intptr_t**)((char*)d + 16);
    int idx = _df(keys, cap, key);
    if (idx < 0) return;
    free(keys[idx]); keys[idx] = 0; values[idx] = 0;
    *(int*)d = *(int*)d - 1;
}

/* Count actual entries in dict (handles tombstones from dict_remove on full table) */
static int _dc(void *d) {
    int count = *(int*)d;
    return count < 0 ? 0 : count;
}

/* Return Nova list of key strings (deep-copied).
 * Nova list header: [count:4][capacity:4][data_ptr:4] (12 bytes total)
 * Data is a separate malloc'd buffer at [data_ptr]. */
SYSCALL void *dict_keys(void *d) {
    int cap = *(int*)((char*)d + 4);
    char **keys = *(char***)((char*)d + 8);
    int n = _dc(d);
    void *list = malloc(12);
    if (!list) return 0;
    void *data = malloc((size_t)n * 4);
    if (!data) { free(list); return 0; }
    *(int*)list = n;
    *(int*)((char*)list + 4) = n;
    *(int*)((char*)list + 8) = (int)(intptr_t)data;
    int out = 0;
    for (int i = 0; i < cap; i++) {
        if (keys[i]) {
            /* Deep-copy key string so it survives dict_remove */
            size_t sl = strlen(keys[i]) + 1;
            char *copy = (char*)malloc(sl);
            if (copy) { strcpy(copy, keys[i]); }
            *(int*)((char*)data + out * 4) = (int)(intptr_t)(copy ? copy : keys[i]);
            out++;
        }
    }
    return list;
}

SYSCALL void *dict_values(void *d) {
    int cap = *(int*)((char*)d + 4);
    char **keys = *(char***)((char*)d + 8);
    intptr_t *values = *(intptr_t**)((char*)d + 16);
    int n = _dc(d);
    void *list = malloc(12);
    if (!list) return 0;
    void *data = malloc((size_t)n * 4);
    if (!data) { free(list); return 0; }
    *(int*)list = n;
    *(int*)((char*)list + 4) = n;
    *(int*)((char*)list + 8) = (int)(intptr_t)data;
    int out = 0;
    for (int i = 0; i < cap; i++) {
        if (keys[i]) {
            *(int*)((char*)data + out * 4) = (int)values[i];
            out++;
        }
    }
    return list;
}

SYSCALL void *dict_items(void *d) {
    int cap = *(int*)((char*)d + 4);
    char **keys = *(char***)((char*)d + 8);
    intptr_t *values = *(intptr_t**)((char*)d + 16);
    int n = _dc(d);
    void *list = malloc(12);
    if (!list) return 0;
    void *data = malloc((size_t)n * 2 * 4);
    if (!data) { free(list); return 0; }
    *(int*)list = n * 2;
    *(int*)((char*)list + 4) = n * 2;
    *(int*)((char*)list + 8) = (int)(intptr_t)data;
    int out = 0;
    for (int i = 0; i < cap; i++) {
        if (keys[i]) {
            /* Deep-copy key string */
            size_t sl = strlen(keys[i]) + 1;
            char *copy = (char*)malloc(sl);
            if (copy) { strcpy(copy, keys[i]); }
            *(int*)((char*)data + out * 4) = (int)(intptr_t)(copy ? copy : keys[i]);
            out++;
            *(int*)((char*)data + out * 4) = (int)values[i];
            out++;
        }
    }
    return list;
}

#if defined(LINUX_WRAP)
/* Linux ELF: no underscore prefix. Assembly calls _dict_new but C function is dict_new. */
SYSCALL void *_dict_new(void) { return dict_new(); }
SYSCALL int _dict_has(void *d, const char *k) { return dict_has(d, k); }
SYSCALL intptr_t _dict_get(void *d, const char *k) { return dict_get(d, k); }
SYSCALL void _dict_set(void *d, const char *k, intptr_t v) { dict_set(d, k, v); }
SYSCALL void _dict_remove(void *d, const char *k) { dict_remove(d, k); }
SYSCALL void *_dict_keys(void *d) { return dict_keys(d); }
SYSCALL void *_dict_values(void *d) { return dict_values(d); }
SYSCALL void *_dict_items(void *d) { return dict_items(d); }
#elif defined(_WIN64)
/* Windows x64: MinGW doesn't add _ prefix. Same wrapper approach as Linux. */
SYSCALL void *_dict_new(void) { return dict_new(); }
SYSCALL int _dict_has(void *d, const char *k) { return dict_has(d, k); }
SYSCALL intptr_t _dict_get(void *d, const char *k) { return dict_get(d, k); }
SYSCALL void _dict_set(void *d, const char *k, intptr_t v) { dict_set(d, k, v); }
SYSCALL void _dict_remove(void *d, const char *k) { dict_remove(d, k); }
SYSCALL void *_dict_keys(void *d) { return dict_keys(d); }
SYSCALL void *_dict_values(void *d) { return dict_values(d); }
SYSCALL void *_dict_items(void *d) { return dict_items(d); }
#endif
