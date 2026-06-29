/* SysV ABI attribute — Nova x86_64 codegen uses System V AMD64 calling convention
 * (args: rdi, rsi, rdx, rcx, r8, r9) while Windows uses Microsoft x64 ABI
 * (args: rcx, rdx, r8, r9). This attribute makes the compiler generate SysV-convention
 * entry/exit so the assembly's call sites work on both Linux and Windows.
 * Must be defined on all platforms since dict functions use it. */
#if defined(__x86_64__)
#define SYSCALL __attribute__((sysv_abi))
#else
#define SYSCALL
#endif

#if defined(_WIN32)
/* Windows: use Win32 API directly — no CRT headers needed, no name conflicts.
 * All runtime functions use Win32 API so CRT linkage is optional. */

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

SYSCALL long long STR_PFX(fopen)(const char *path, const char *mode) {
    HANDLE h; DWORD access, disp;
    if (*mode == 'w') { access = 0x40000000; disp = 2; }
    else if (*mode == 'a') { access = 0xC0000000; disp = 4; }
    else { access = 0x80000000; disp = 3; }
    h = CreateFileA(path, access, 0, 0, disp, 0x80, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;
    if (*mode == 'a') SetFilePointer(h, 0, 0, 2);
    return (long long)(intptr_t)h;
}
SYSCALL int STR_PFX(fclose)(long long s) { return CloseHandle((HANDLE)(intptr_t)s) ? 0 : -1; }
SYSCALL int STR_PFX(fread)(void *b, int sz, int c, long long s) { DWORD n; ReadFile((HANDLE)(intptr_t)s, b, sz*c, &n, 0); return n; }
SYSCALL int STR_PFX(fwrite)(const void *b, int sz, int c, long long s) { DWORD n; WriteFile((HANDLE)(intptr_t)s, b, sz*c, &n, 0); return n; }
SYSCALL int STR_PFX(fputs)(const char *str, long long s) { int n = lstrlenA(str); STR_PFX(fwrite)(str, 1, n, s); return n; }
SYSCALL int STR_PFX(fputc)(int c, long long s) { char ch = c; STR_PFX(fwrite)(&ch, 1, 1, s); return c; }
SYSCALL int STR_PFX(fseek)(long long s, long o, int w) { return SetFilePointer((HANDLE)(intptr_t)s, o, 0, w) == -1 ? -1 : 0; }
SYSCALL long STR_PFX(ftell)(long long s) { return SetFilePointer((HANDLE)(intptr_t)s, 0, 0, 1); }
SYSCALL int STR_PFX(fflush)(long long s) { if (s) FlushFileBuffers((HANDLE)(intptr_t)s); return 0; }
SYSCALL void STR_PFX(exit)(int c) { ExitProcess(c); }
SYSCALL int STR_PFX(system)(const char *c) { return system(c); }

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

/* ============== Nova sys_* runtime (_c suffix to match Nova codegen naming) ============== */
SYSCALL long long _sys_open_c(const char *path, const char *mode) { return STR_PFX(fopen)(path, mode); }
SYSCALL void _sys_close_c(long long s) { STR_PFX(fclose)(s); }
SYSCALL char *_sys_read_c(long long s) {
    long len;
    char *buf;
    STR_PFX(fseek)(s, 0, 2);
    len = STR_PFX(ftell)(s);
    STR_PFX(fseek)(s, 0, 0);
    buf = (char *)STR_PFX(malloc)(len + 1);
    STR_PFX(fread)(buf, 1, len, s);
    buf[len] = '\0';
    return buf;
}
SYSCALL void _sys_write_c(long long s, const char *str) { STR_PFX(fputs)(str, s); }
SYSCALL int _sys_write_raw_c(int s, void *arr) {
    int *iarr = (int*)arr;
    int len = iarr[0];
    char *data = (char*)arr + 16;
    return STR_PFX(fwrite)(data, 1, len, s);
}
SYSCALL void *_sys_alloc_c(int sz) { return STR_PFX(malloc)(sz); }
SYSCALL void _sys_free_c(void *p) { STR_PFX(free)(p); }
SYSCALL void _sys_exit_c(int c) { STR_PFX(exit)(c); }
SYSCALL int _system_c(const char *c) { return STR_PFX(system)(c); }
SYSCALL int _sys_flush_c(int s) { return STR_PFX(fflush)(s); }
SYSCALL const char *_sys_platform_c(void) { return "windows"; }
SYSCALL int _sys_get_tick_count_c(void) { return (int)GetTickCount(); }

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
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#if defined(LINUX_WRAP)
SYSCALL int _printf(const char *fmt, ...) {
    va_list ap; va_start(ap, fmt);
    int n = vprintf(fmt, ap); va_end(ap);
    fflush(stdout);
    return n;
}
SYSCALL void *_malloc(size_t s) { return malloc(s); }
SYSCALL void _free(void *p) { free(p); }
SYSCALL void *_realloc(void *p, size_t s) { return realloc(p, s); }
SYSCALL size_t _strlen(const char *s) { return strlen(s); }
SYSCALL int _strcmp(const char *a, const char *b) { return strcmp(a, b); }
SYSCALL char *_strcpy(char *d, const char *s) { return strcpy(d, s); }
SYSCALL char *_strcat(char *d, const char *s) { return strcat(d, s); }
SYSCALL void *_memset(void *p, int c, size_t n) { return memset(p, c, n); }
SYSCALL char *_strstr(const char *h, const char *n) { return strstr(h, n); }
SYSCALL int _fopen(const char *p, const char *m) {
    FILE *f = fopen(p, m);
    return f ? (intptr_t)f : 0;
}
SYSCALL int _fclose(int s) { return fclose((FILE*)(intptr_t)s); }
SYSCALL int _fwrite(const void *b, int sz, int c, int s) { return fwrite(b, sz, c, (FILE*)(intptr_t)s); }
SYSCALL int _fread(void *b, int sz, int c, int s) { return fread(b, sz, c, (FILE*)(intptr_t)s); }
SYSCALL int _fputs(const char *str, int s) { return fputs(str, (FILE*)(intptr_t)s); }
SYSCALL int _fputc(int c, int s) { return fputc(c, (FILE*)(intptr_t)s); }
SYSCALL int _fseek(int s, long o, int w) { return fseek((FILE*)(intptr_t)s, o, w); }
SYSCALL long _ftell(int s) { return ftell((FILE*)(intptr_t)s); }
SYSCALL int _fflush(int s) { return fflush((FILE*)(intptr_t)s); }
SYSCALL void _exit(int c) { exit(c); }
SYSCALL int _system_c(const char *c) { return system(c); }
SYSCALL int _sprintf(char *b, const char *fmt, ...) {
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
/* Apple defines memset as a fortified macro (__builtin___memset_chk with extra
 * args) in <string.h> — a forward declaration with SYSCALL attribute would expand
 * through the macro and cause parameter mismatch. Rely on the system header. */
#if !defined(__APPLE__)
SYSCALL void *memset(void *, int, size_t);
#endif
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
    unsigned long mask = (unsigned long)(cap - 1);
    int idx = (int)(h & mask);
    for (int i = 0; i < cap; i++) {
        int j = (idx + i) & (int)mask;
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
            unsigned long nmask = (unsigned long)(nc - 1);
            int idx = (int)(h & nmask);
            while (nk[idx]) idx = (idx + 1) & (int)nmask;
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
    unsigned long mask = (unsigned long)(cap - 1);
    idx = (int)(h & mask);
    while (keys[idx]) idx = (idx + 1) & (int)mask;
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

SYSCALL void dict_free(void *d) {
    if (!d) return;
    int cap = *(int*)((char*)d + 4);
    char **keys = *(char***)((char*)d + 8);
    intptr_t *values = *(intptr_t**)((char*)d + 16);
    for (int i = 0; i < cap; i++) {
        if (keys[i]) free(keys[i]);
    }
    free(keys);
    free(values);
    free(d);
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
    void *list = malloc(16);
    if (!list) return 0;
    void *data = malloc((size_t)n * sizeof(intptr_t));
    if (!data) { free(list); return 0; }
    *(int*)list = n;
    *(int*)((char*)list + 4) = n;
    *(intptr_t*)((char*)list + 8) = (intptr_t)data;
    int out = 0;
    for (int i = 0; i < cap; i++) {
        if (keys[i]) {
            /* Deep-copy key string so it survives dict_remove */
            size_t sl = strlen(keys[i]) + 1;
            char *copy = (char*)malloc(sl);
            if (copy) { strcpy(copy, keys[i]); }
            *(intptr_t*)((char*)data + out * sizeof(intptr_t)) = (intptr_t)(copy ? copy : keys[i]);
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
    void *list = malloc(16);
    if (!list) return 0;
    void *data = malloc((size_t)n * sizeof(intptr_t));
    if (!data) { free(list); return 0; }
    *(int*)list = n;
    *(int*)((char*)list + 4) = n;
    *(intptr_t*)((char*)list + 8) = (intptr_t)data;
    int out = 0;
    for (int i = 0; i < cap; i++) {
        if (keys[i]) {
            *(intptr_t*)((char*)data + out * sizeof(intptr_t)) = (intptr_t)values[i];
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
    void *list = malloc(16);
    if (!list) return 0;
    void *data = malloc((size_t)n * 2 * sizeof(intptr_t));
    if (!data) { free(list); return 0; }
    *(int*)list = n * 2;
    *(int*)((char*)list + 4) = n * 2;
    *(intptr_t*)((char*)list + 8) = (intptr_t)data;
    int out = 0;
    for (int i = 0; i < cap; i++) {
        if (keys[i]) {
            /* Deep-copy key string */
            size_t sl = strlen(keys[i]) + 1;
            char *copy = (char*)malloc(sl);
            if (copy) { strcpy(copy, keys[i]); }
            *(intptr_t*)((char*)data + out * sizeof(intptr_t)) = (intptr_t)(copy ? copy : keys[i]);
            out++;
            *(intptr_t*)((char*)data + out * sizeof(intptr_t)) = (intptr_t)values[i];
            out++;
        }
    }
    return list;
}

/* ===== Dict wrappers (shared, identical on all platforms) ===== */
SYSCALL void *_dict_new(void) { return dict_new(); }
SYSCALL int _dict_has(void *d, const char *k) { return dict_has(d, k); }
SYSCALL intptr_t _dict_get(void *d, const char *k) { return dict_get(d, k); }
SYSCALL void _dict_set(void *d, const char *k, intptr_t v) { dict_set(d, k, v); }
SYSCALL void _dict_remove(void *d, const char *k) { dict_remove(d, k); }
SYSCALL void *_dict_keys(void *d) { return dict_keys(d); }
SYSCALL void *_dict_values(void *d) { return dict_values(d); }
SYSCALL void *_dict_items(void *d) { return dict_items(d); }

/* ===== Platform-specific helpers ===== */
#if defined(LINUX_WRAP)
SYSCALL const char *_sys_platform_c(void) { return "linux"; }
SYSCALL void *_sys_get_args_c(void) {
    extern int __nova_argc;
    extern char **__nova_argv;
    int n = __nova_argc;
    void *list = malloc(16);
    if (!list) return 0;
    void *data = malloc((size_t)n * sizeof(intptr_t));
    if (!data) { free(list); return 0; }
    *(int*)list = n;
    *(int*)((char*)list + 4) = n;
    *(intptr_t*)((char*)list + 8) = (intptr_t)data;
    for (int i = 0; i < n; i++) {
        size_t sl = strlen(__nova_argv[i]) + 1;
        char *copy = (char*)malloc(sl);
        if (copy) strcpy(copy, __nova_argv[i]);
        *(intptr_t*)((char*)data + i * sizeof(intptr_t)) = (intptr_t)(copy ? copy : __nova_argv[i]);
    }
    return list;
}
#elif defined(_WIN64)
SYSCALL void *_sys_get_args_c(void) {
    extern int __argc;
    extern char **__argv;
    int n = __argc;
    void *list = malloc(16);
    if (!list) return 0;
    void *data = malloc((size_t)n * sizeof(intptr_t));
    if (!data) { free(list); return 0; }
    *(int*)list = n;
    *(int*)((char*)list + 4) = n;
    *(intptr_t*)((char*)list + 8) = (intptr_t)data;
    for (int i = 0; i < n; i++) {
        size_t sl = strlen(__argv[i]) + 1;
        char *copy = (char*)malloc(sl);
        if (copy) strcpy(copy, __argv[i]);
        *(intptr_t*)((char*)data + i * sizeof(intptr_t)) = (intptr_t)(copy ? copy : __argv[i]);
    }
    return list;
}
#elif defined(MACOS)
#include <crt_externs.h>
SYSCALL const char *_sys_platform_c(void) { return "macos"; }
SYSCALL void *_sys_get_args_c(void) {
    int n = *_NSGetArgc();
    char **argv = *_NSGetArgv();
    void *list = malloc(16);
    if (!list) return 0;
    void *data = malloc((size_t)n * sizeof(intptr_t));
    if (!data) { free(list); return 0; }
    *(int*)list = n;
    *(int*)((char*)list + 4) = n;
    *(intptr_t*)((char*)list + 8) = (intptr_t)data;
    for (int i = 0; i < n; i++) {
        size_t sl = strlen(argv[i]) + 1;
        char *copy = (char*)malloc(sl);
        if (copy) strcpy(copy, argv[i]);
        *(intptr_t*)((char*)data + i * sizeof(intptr_t)) = (intptr_t)(copy ? copy : argv[i]);
    }
    return list;
}
#endif

/* ==================== File read + get_args for Linux/macOS (no Win32 API) ==================== */
#if defined(LINUX_WRAP) || defined(MACOS)
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>

SYSCALL char *_nova_read_file(int fd) {
    off_t len = lseek(fd, 0, SEEK_END);
    lseek(fd, 0, SEEK_SET);
    char *buf = malloc((size_t)len + 1);
    if (!buf) return 0;
    ssize_t n = read(fd, buf, (size_t)len);
    if (n < 0) { free(buf); return 0; }
    buf[n] = '\0';
    return buf;
}

SYSCALL int _sys_get_tick_count_c(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

/* ===== Unix syscall helpers (_c suffix for Nova codegen naming compatibility) ===== */
SYSCALL long long _sys_open_c(const char *path, const char *mode) {
    int flags;
    if (*mode == 'w' || *mode == 'a') {
        flags = O_WRONLY | O_CREAT;
        if (*mode == 'a') flags |= O_APPEND;
        else flags |= O_TRUNC;
        return open(path, flags, 0666);
    }
    return open(path, O_RDONLY);
}

SYSCALL void _sys_close_c(long long fd) {
    close(fd);
}

SYSCALL char *_sys_read_c(long long fd) {
    off_t len = lseek(fd, 0, SEEK_END);
    lseek(fd, 0, SEEK_SET);
    char *buf = (char*)malloc((size_t)len + 1);
    if (!buf) return 0;
    ssize_t n = read(fd, buf, (size_t)len);
    if (n < 0) { free(buf); return 0; }
    buf[n] = '\0';
    return buf;
}

SYSCALL void _sys_write_c(long long fd, const char *str) {
    int len = strlen(str);
    write(fd, str, (size_t)len);
}

SYSCALL void _sys_write_raw_c(int fd, void *list) {
    int len = *(int*)list;
    char *data = (char*)list + 16;
    write(fd, data, (size_t)len);
}

SYSCALL void *_sys_alloc_c(int sz) {
    return malloc((size_t)sz);
}

SYSCALL void _sys_free_c(void *p) {
    free(p);
}

SYSCALL void _sys_flush_c(int fd) {
    fsync(fd);
}

SYSCALL void _sys_exit_c(int code) {
    _exit(code);
}
#endif

/* ==================== String helper functions ==================== */
SYSCALL int _char_code(const char *s, int i) {
    if (!s) return 0;
    return (unsigned char)s[i];
}

SYSCALL char *_str_sub(const char *s, int start, int end) {
    if (!s) return 0;
    int actual_len = 0;
    while (s[actual_len] != '\0') actual_len++;
    if (start < 0) start = 0;
    if (end > actual_len) end = actual_len;
    int len = end - start;
    if (len < 0) len = 0;
#if defined(_WIN32)
    char *res = (char*)STR_PFX(malloc)(len + 1);
#else
    char *res = (char*)malloc(len + 1);
#endif
    if (!res) return 0;
    for (int i = 0; i < len; i++) {
        res[i] = s[start + i];
    }
    res[len] = '\0';
    return res;
}

/* ==================== List slice function ==================== */
/* List struct: [0..3]=len(int), [4..7]=cap_bytes(int), [8..15]=data(void*)
 * Capacity at offset 4 is in BYTES to match the codegen's append handler. */
SYSCALL void *_slice_list(void *list, int start, int end) {
    if (!list) return 0;
    int len = *(int*)list;
    if (end > len) end = len;
    if (start < 0) start = 0;
    if (start > len) start = len;
    int new_len = end - start;
    if (new_len < 0) new_len = 0;
    int cap_bytes = (new_len ? new_len : 1) * (int)sizeof(intptr_t);
#if defined(_WIN32)
    void *result = STR_PFX(malloc)(16);
#else
    void *result = malloc(16);
#endif
    if (!result) return 0;
#if defined(_WIN32)
    void *new_data = STR_PFX(malloc)((size_t)cap_bytes);
#else
    void *new_data = malloc((size_t)cap_bytes);
#endif
    if (!new_data) {
#if defined(_WIN32)
        STR_PFX(free)(result);
#else
        free(result);
#endif
        return 0;
    }
    *(int*)result = new_len;
    *(int*)((char*)result + 4) = cap_bytes;
    *(intptr_t*)((char*)result + 8) = (intptr_t)new_data;
    intptr_t *src = (intptr_t*)(*(intptr_t*)((char*)list + 8));
    intptr_t *dst = (intptr_t*)new_data;
    for (int i = 0; i < new_len; i++) {
        dst[i] = src[start + i];
    }
    return result;
}

/* ==================== Built-in math and file functions ==================== */
SYSCALL int _abs(int n) {
    return n < 0 ? -n : n;
}

SYSCALL int _min(int a, int b) {
    return a < b ? a : b;
}

SYSCALL int _max(int a, int b) {
    return a > b ? a : b;
}

SYSCALL int _file_exists(const char *path) {
#if defined(_WIN32)
    DWORD attrs = GetFileAttributesA(path);
    return (attrs != INVALID_FILE_ATTRIBUTES) ? 1 : 0;
#else
    FILE *f = fopen(path, "r");
    if (f) { fclose(f); return 1; }
    return 0;
#endif
}

SYSCALL int _file_size(const char *path) {
#if defined(_WIN32)
    HANDLE h = CreateFileA(path, 0x80000000, 0, 0, 3, 0x80, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;
    DWORD sz = GetFileSize(h, NULL);
    CloseHandle(h);
    return (int)sz;
#else
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fclose(f);
    return (int)sz;
#endif
}

SYSCALL const char *_file_type(const char *path) {
#if defined(_WIN32)
    DWORD attrs = GetFileAttributesA(path);
    if (attrs == INVALID_FILE_ATTRIBUTES) return "";
    if (attrs & FILE_ATTRIBUTE_DIRECTORY) return "dir";
    return "file";
#else
    struct stat st;
    if (stat(path, &st) != 0) return "";
    if (S_ISDIR(st.st_mode)) return "dir";
    return "file";
#endif
}

SYSCALL char *_now(void) {
#if defined(_WIN32)
    SYSTEMTIME st;
    GetLocalTime(&st);
#else
    time_t t = time(NULL);
    struct tm *lt = localtime(&t);
#endif
    char *buf;
#if defined(_WIN32)
    buf = (char*)STR_PFX(malloc)(32);
#else
    buf = (char*)malloc(32);
#endif
    if (!buf) return 0;
#if defined(_WIN32)
    int pos = 0, v;
    v = st.wYear;   buf[pos++] = '0' + v / 1000; buf[pos++] = '0' + (v / 100) % 10; buf[pos++] = '0' + (v / 10) % 10; buf[pos++] = '0' + v % 10;
    buf[pos++] = '-';
    v = st.wMonth;  buf[pos++] = '0' + v / 10; buf[pos++] = '0' + v % 10;
    buf[pos++] = '-';
    v = st.wDay;    buf[pos++] = '0' + v / 10; buf[pos++] = '0' + v % 10;
    buf[pos++] = ' ';
    v = st.wHour;   buf[pos++] = '0' + v / 10; buf[pos++] = '0' + v % 10;
    buf[pos++] = ':';
    v = st.wMinute; buf[pos++] = '0' + v / 10; buf[pos++] = '0' + v % 10;
    buf[pos++] = ':';
    v = st.wSecond; buf[pos++] = '0' + v / 10; buf[pos++] = '0' + v % 10;
    buf[pos] = '\0';
#else
    strftime(buf, 32, "%Y-%m-%d %H:%M:%S", lt);
#endif
    return buf;
}

/* _call(name, args, num_args) — dynamic dispatch stub; native codegen never emits this */
SYSCALL long long _call(const char *name, long long *args, long long num_args) {
    (void)name; (void)args; (void)num_args;
    return 0;
}
