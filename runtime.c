#if defined(_WIN32)
/* Windows: use Win32 API directly — no CRT headers needed, no name conflicts */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdarg.h>
#include <stdint.h>

/* Memory: use CRT's malloc/free/realloc (available via default msvcrt link) */

/* Declare CRT vsprintf — available via default msvcrt link */
int __cdecl vsprintf(char *, const char *, va_list);

int printf(const char *fmt, ...) {
    char buf[4096]; int n;
    va_list ap; va_start(ap, fmt);
    n = vsprintf(buf, fmt, ap); va_end(ap);
    HANDLE h = GetStdHandle(-11);
    DWORD wn; WriteFile(h, buf, n, &wn, 0);
    return n;
}

int fopen(const char *path, const char *mode) {
    HANDLE h; DWORD access, disp;
    if (*mode == 'w') { access = 0x40000000; disp = 2; }
    else if (*mode == 'a') { access = 0xC0000000; disp = 4; }
    else { access = 0x80000000; disp = 3; }
    h = CreateFileA(path, access, 0, 0, disp, 0x80, 0);
    if (h == INVALID_HANDLE_VALUE) return 0;
    if (*mode == 'a') SetFilePointer(h, 0, 0, 2);
    return (intptr_t)h;
}
int fclose(int s) { return CloseHandle((HANDLE)(intptr_t)s) ? 0 : -1; }
int fread(void *b, int sz, int c, int s) { DWORD n; ReadFile((HANDLE)(intptr_t)s, b, sz*c, &n, 0); return n; }
int fwrite(const void *b, int sz, int c, int s) { DWORD n; WriteFile((HANDLE)(intptr_t)s, b, sz*c, &n, 0); return n; }
int fputs(const char *str, int s) { int n = lstrlenA(str); fwrite(str, 1, n, s); return n; }
int fputc(int c, int s) { char ch = c; fwrite(&ch, 1, 1, s); return c; }
int fseek(int s, long o, int w) { return SetFilePointer((HANDLE)(intptr_t)s, o, 0, w) == -1 ? -1 : 0; }
long ftell(int s) { return SetFilePointer((HANDLE)(intptr_t)s, 0, 0, 1); }
int fflush(int s) { if (s) FlushFileBuffers((HANDLE)(intptr_t)s); return 0; }
void exit(int c) { ExitProcess(c); }
int system(const char *c) { return (int)WinExec(c, 1); }

unsigned int strlen(const char *s) { return lstrlenA(s); }
int strcmp(const char *a, const char *b) { return lstrcmpA(a, b); }
char *strcpy(char *d, const char *s) { return lstrcpyA(d, s); }
char *strcat(char *d, const char *s) { return lstrcatA(d, s); }
void *memset(void *p, int c, unsigned int n) { FillMemory(p, n, c); return p; }

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

/* ============== Out-of-bounds handler =========== */
void out_of_bounds(void) {
    printf("Index Out Of Bounds\n");
    exit(1);
}
#if defined(LINUX_WRAP)
void _out_of_bounds(void) { out_of_bounds(); }
#endif

/* ==================== Dict runtime functions (all platforms) ==================== */
/* Forward declarations to avoid -Wimplicit-function-declaration on Windows */
void *malloc(size_t);
void free(void *);
void *memset(void *, int, size_t);
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

void *dict_new(void) {
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

int dict_has(void *d, const char *key) {
    int cap = *(int*)((char*)d + 4);
    char **keys = *(char***)((char*)d + 8);
    return _df(keys, cap, key) >= 0 ? 1 : 0;
}

intptr_t dict_get(void *d, const char *key) {
    int cap = *(int*)((char*)d + 4);
    char **keys = *(char***)((char*)d + 8);
    intptr_t *values = *(intptr_t**)((char*)d + 16);
    int idx = _df(keys, cap, key);
    return idx >= 0 ? values[idx] : 0;
}

void dict_set(void *d, const char *key, intptr_t value) {
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

void dict_remove(void *d, const char *key) {
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
void *dict_keys(void *d) {
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

void *dict_values(void *d) {
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

void *dict_items(void *d) {
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
void *_dict_new(void) { return dict_new(); }
int _dict_has(void *d, const char *k) { return dict_has(d, k); }
intptr_t _dict_get(void *d, const char *k) { return dict_get(d, k); }
void _dict_set(void *d, const char *k, intptr_t v) { dict_set(d, k, v); }
void _dict_remove(void *d, const char *k) { dict_remove(d, k); }
void *_dict_keys(void *d) { return dict_keys(d); }
void *_dict_values(void *d) { return dict_values(d); }
void *_dict_items(void *d) { return dict_items(d); }
#endif
