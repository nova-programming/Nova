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
#include <process.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>

#if defined(_WIN64)
#undef _exit
#endif

/* All runtime functions are SYSCALL to match the Nova codegen calling convention.
 * Inside the function body, Win32 API calls use the default Windows convention —
 * the compiler handles the ABI translation at call sites automatically. */

/* Minimal printf: handles %s, %d, %f, %% for Nova codegen.
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
                    long long val = (long long)arg_s;
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
                case 'f': {
                    /* Nova floats are IEEE single precision held in the low 32 bits of the value */
                    union { uint32_t u; float f; } cv;
                    cv.u = (uint32_t)(uintptr_t)arg_s;
                    double val = (double)cv.f;
                    char buf[512];
                    int len = snprintf(buf, sizeof(buf), "%.6f", val);
                    if (len < 0) len = 0;
                    if (len >= (int)sizeof(buf)) len = (int)sizeof(buf) - 1;
                    WriteFile(h, buf, len, &wn, 0);
                    written += len;
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
    return HeapAlloc(_nova_heap, HEAP_ZERO_MEMORY, s);
}
SYSCALL void STR_PFX(free)(void *p) {
    if (p) { if (!_nova_heap) _nova_heap = GetProcessHeap(); HeapFree(_nova_heap, 0, p); }
}
SYSCALL void *STR_PFX(realloc)(void *p, unsigned int s) {
    if (!_nova_heap) _nova_heap = GetProcessHeap();
    return HeapReAlloc(_nova_heap, 0, p, s);
}

/* Arena/Bump Allocator for compiler pipeline — fast linear allocation with bulk free */
#define ARENA_DEFAULT_SIZE (1024 * 1024)

typedef struct {
    char *base;
    char *ptr;
    char *end;
} NovaArena;

static NovaArena _compile_arena = {0};

SYSCALL void arena_init(void) {
    if (!_compile_arena.base) {
        _compile_arena.base = (char*)STR_PFX(malloc)(ARENA_DEFAULT_SIZE);
        _compile_arena.ptr = _compile_arena.base;
        _compile_arena.end = _compile_arena.base + ARENA_DEFAULT_SIZE;
    }
}

SYSCALL void *arena_alloc(size_t size) {
    if (!_compile_arena.base) arena_init();
    
    size = (size + 7) & ~7;  // 8-byte align
    
    if (_compile_arena.ptr + size > _compile_arena.end) {
        size_t new_size = ARENA_DEFAULT_SIZE * 2;
        char *new_base = (char*)STR_PFX(malloc)(new_size);
        if (!new_base) return 0;
        STR_PFX(memcpy)(new_base, _compile_arena.base, _compile_arena.ptr - _compile_arena.base);
        STR_PFX(free)(_compile_arena.base);
        _compile_arena.base = new_base;
        _compile_arena.ptr = new_base + (_compile_arena.ptr - _compile_arena.base);
        _compile_arena.end = new_base + new_size;
    }
    
    void *result = _compile_arena.ptr;
    _compile_arena.ptr += size;
    return result;
}

SYSCALL void arena_reset(void) {
    if (_compile_arena.base) {
        _compile_arena.ptr = _compile_arena.base;
    }
}

SYSCALL void arena_free(void) {
    if (_compile_arena.base) {
        STR_PFX(free)(_compile_arena.base);
        _compile_arena.base = 0;
        _compile_arena.ptr = 0;
        _compile_arena.end = 0;
    }
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
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wbuiltin-declaration-mismatch"
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
#pragma GCC diagnostic pop

/* Out-of-bounds globals (set by codegen before each bounds check) */
long long _oob_file_ptr;
long long _oob_line;

/* Out-of-bounds handler */
SYSCALL void STR_PFX(out_of_bounds)(void) {
    if (_oob_file_ptr) {
        STR_PFX(printf)("error: Index Out Of Bounds at ", 0);
        STR_PFX(printf)("%s", (void*)(intptr_t)_oob_file_ptr);
        STR_PFX(printf)(" line %d\n", (void*)(intptr_t)_oob_line);
    } else {
        STR_PFX(printf)("error: Index Out Of Bounds\n", 0);
    }
    STR_PFX(exit)(1);
}

/* ============== Nova sys_* runtime (_c suffix to match Nova codegen naming) ============== */
SYSCALL long long _sys_open_c(const char *path, const char *mode) { return STR_PFX(fopen)(path, mode); }
SYSCALL void _sys_close_c(long long s) { STR_PFX(fclose)(s); }
SYSCALL int _sys_mkdir_c(const char *path) {
    if (!path) return 0;
    return CreateDirectoryA(path, NULL) ? 1 : 0;
}
SYSCALL int _sys_delete_c(const char *path) {
    if (!path) return 0;
    return DeleteFileA(path) ? 1 : 0;
}
SYSCALL int _sys_copy_c(const char *source, const char *destination) {
    if (!source || !destination || STR_PFX(strcmp)(source, destination) == 0) return 0;
    return CopyFileA(source, destination, TRUE) ? 1 : 0;
}
SYSCALL int _sys_move_c(const char *source, const char *destination) {
    if (!source || !destination) return 0;
    return MoveFileExA(source, destination, MOVEFILE_REPLACE_EXISTING) ? 1 : 0;
}
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
SYSCALL void _sys_write_c(long long s, const char *str) {
    /* Map Nova fd 0/1/2 to actual Win32 handles.  Nova uses raw HANDLEs as
     * file descriptors (from CreateFileA), but standard streams 0/1/2 must
     * be mapped via GetStdHandle since (HANDLE)1/2 are invalid handles. */
    HANDLE h;
    if (s == 0) h = GetStdHandle(STD_INPUT_HANDLE);
    else if (s == 1) h = GetStdHandle(STD_OUTPUT_HANDLE);
    else if (s == 2) h = GetStdHandle(STD_ERROR_HANDLE);
    else h = (HANDLE)(intptr_t)s;
    STR_PFX(fputs)(str, (long long)(intptr_t)h);
}
SYSCALL int _sys_write_raw_c(int s, void *arr) {
    int *iarr = (int*)arr;
    int len = iarr[0];
    char *data = (char*)arr + 16;
    return STR_PFX(fwrite)(data, 1, len, s);
}
SYSCALL void *_sys_alloc_c(int sz) { return STR_PFX(malloc)(sz); }
SYSCALL void _sys_free_c(void *p) { STR_PFX(free)(p); }
SYSCALL void _sys_exit_c(int c) { STR_PFX(exit)(c); }
SYSCALL int _system_c(const char *c) {
    if (!c) return -1;
    if (strchr(c, '"')) {
        size_t len = strlen(c);
        char *wrapped = (char*)malloc(len + 3);
        if (wrapped) {
            wrapped[0] = '"';
            memcpy(wrapped + 1, c, len);
            wrapped[len + 1] = '"';
            wrapped[len + 2] = '\0';
            int ret = STR_PFX(system)(wrapped);
            free(wrapped);
            return ret;
        }
    }
    return STR_PFX(system)(c);
}
SYSCALL int _sys_flush_c(int s) { return STR_PFX(fflush)(s); }
SYSCALL const char *_sys_platform_c(void) { return "windows"; }
SYSCALL int _sys_get_tick_count_c(void) { return (int)GetTickCount(); }
SYSCALL const char *_sys_env_get_c(const char *name) {
    const char *value = getenv(name);
    return value ? value : "";
}
SYSCALL int _sys_env_set_c(const char *name, const char *value) {
    return _putenv_s(name, value) == 0 ? 1 : 0;
}
SYSCALL int _sys_process_run_c(void *args) {
    int count;
    intptr_t *values;
    char **argv;
    int i;
    if (!args) return -1;
    count = *(int*)args;
    values = (intptr_t*)(*(intptr_t*)((char*)args + 8));
    if (count <= 0) return -1;
    argv = (char**)malloc((size_t)(count + 1) * sizeof(char*));
    if (!argv) return -1;
    for (i = 0; i < count; i++) {
        argv[i] = (char*)values[i];
        if (!argv[i]) { free(argv); return -1; }
    }
    argv[count] = NULL;
    i = _spawnvp(_P_WAIT, argv[0], (const char *const *)argv);
    free(argv);
    return i < 0 ? -1 : i;
}

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
#include <signal.h>
#include <execinfo.h>
#include <dlfcn.h>
/* MinGW's dlfcn.h lacks Dl_info/dladdr (real POSIX provides them). */
#if defined(__MINGW32__) || defined(__MINGW64__)
typedef struct { const char *dli_fname; void *dli_fbase; const char *dli_sname; void *dli_saddr; } Dl_info;
int dladdr(const void *, Dl_info *);
#endif

/* Custom printf: processes fmt manually and writes to fd 1 via write().
 * Avoids va_list/AAPCS64 register save area issues on ARM64 that can occur
 * with fprintf(stdout, ...) when called from hand-written assembly. */
#if defined(LINUX_WRAP) || defined(MACOS)
SYSCALL int _printf(const char *fmt, int64_t arg) {
    int written = 0;
    while (*fmt) {
        if (*fmt == '%') {
            fmt++;
            switch (*fmt) {
                case 's': {
                    const char *s = (const char*)arg;
                    if (s) { int n = strlen(s); write(1, s, n); written += n; }
                    break;
                }
                case 'd': {
                    char buf[32];
                    int val = (int)arg, neg = 0, pos = 30, dlen;
                    buf[31] = 0;
                    if (val < 0) { neg = 1; val = -val; }
                    do { buf[pos--] = '0' + (val % 10); val /= 10; } while (val);
                    if (neg) buf[pos--] = '-';
                    pos++; dlen = 31 - pos;
                    write(1, buf + pos, dlen);
                    written += dlen;
                    break;
                }
                case '%':
                    write(1, "%", 1);
                    written++;
                    break;
                default: break;
            }
        } else {
            write(1, fmt, 1);
            written++;
        }
        fmt++;
    }
    return written;
}
/* Fixed-arg signature — same reasoning as _printf above.
 * LINUX ONLY: on Linux, libc exports `sprintf` (no underscore) so the
 * codegen's `bl _sprintf` needs this bridge. On macOS, libc exports
 * `_sprintf` directly AND this wrapper would recurse infinitely: the
 * `sprintf()` call inside compiles to `bl _sprintf`, which the Mach-O
 * alias maps back to this very function. */
#if defined(LINUX_WRAP)
SYSCALL int _sprintf(char *b, const char *fmt, int64_t arg) {
    return sprintf(b, fmt, arg);
}
#endif
/* _system_c: called from Nova stdlib's system_exec(). Safe to alias on macOS
 * because it calls system() -> Mach-O _system (not aliased), no recursion. */
SYSCALL int _system_c(const char *c) { return system(c); }
#endif

/* Linux-only libc wrappers: on Linux, libc exports `printf` (no underscore),
 * but our codegen emits `_printf`, `_malloc`, etc. These wrappers bridge
 * the naming gap. On macOS, libc exports `_printf`, `_malloc`, etc. directly
 * (Mach-O adds the underscore), so no wrappers needed — the codegen's
 * `bl _malloc` resolves to system `malloc` automatically.
 * IMPORTANT: Do NOT define wrappers for functions like malloc/free/strlen
 * on macOS — calling malloc() inside _malloc() would compile to `bl _malloc`
 * which aliases back to _malloc, causing infinite recursion. */
#if defined(LINUX_WRAP)
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

/* Arena/Bump Allocator for Linux */
#define ARENA_DEFAULT_SIZE (1024 * 1024)
typedef struct {
    char *base;
    char *ptr;
    char *end;
} NovaArena;
static NovaArena _compile_arena = {0};

SYSCALL void arena_init(void) {
    if (!_compile_arena.base) {
        _compile_arena.base = (char*)malloc(ARENA_DEFAULT_SIZE);
        _compile_arena.ptr = _compile_arena.base;
        _compile_arena.end = _compile_arena.base + ARENA_DEFAULT_SIZE;
    }
}

SYSCALL void *arena_alloc(size_t size) {
    if (!_compile_arena.base) arena_init();
    
    size = (size + 7) & ~7;
    
    if (_compile_arena.ptr + size > _compile_arena.end) {
        size_t new_size = ARENA_DEFAULT_SIZE * 2;
        char *new_base = (char*)malloc(new_size);
        if (!new_base) return 0;
        memcpy(new_base, _compile_arena.base, _compile_arena.ptr - _compile_arena.base);
        free(_compile_arena.base);
        _compile_arena.base = new_base;
        _compile_arena.ptr = new_base + (_compile_arena.ptr - _compile_arena.base);
        _compile_arena.end = new_base + new_size;
    }
    
    void *result = _compile_arena.ptr;
    _compile_arena.ptr += size;
    return result;
}

SYSCALL void arena_reset(void) {
    if (_compile_arena.base) {
        _compile_arena.ptr = _compile_arena.base;
    }
}

SYSCALL void arena_free(void) {
    if (_compile_arena.base) {
        free(_compile_arena.base);
        _compile_arena.base = 0;
        _compile_arena.ptr = 0;
        _compile_arena.end = 0;
    }
}

#endif /* defined(LINUX_WRAP) */

/* macOS: shadow libc realloc to log every list-growth call for the
 * self-hosting crash diagnosis. dlsym(RTLD_NEXT) returns the real libSystem
 * realloc — a plain `realloc` call here would auto-underscore to `_realloc`
 * and recurse infinitely. The `.set _realloc, __realloc` alias below bridges
 * the Mach-O underscore gap for the codegen's `bl _realloc`. */
#if defined(MACOS)
#include <dlfcn.h>
static void *_last_realloc_from = 0;
static void *_diag_real_realloc(void *p, size_t s) {
    static void *(*fn)(void *, size_t) = 0;
    if (!fn) fn = (void *(*)(void *, size_t))dlsym(RTLD_NEXT, "realloc");
    return fn(p, s);
}
SYSCALL void *_realloc(void *p, size_t s) {
    void *r = _diag_real_realloc(p, s);
    _last_realloc_from = __builtin_return_address(0);
    return r;
}

/* Arena/Bump Allocator for macOS */
#define ARENA_DEFAULT_SIZE (1024 * 1024)
typedef struct {
    char *base;
    char *ptr;
    char *end;
} NovaArena;
static NovaArena _compile_arena = {0};

SYSCALL void arena_init(void) {
    if (!_compile_arena.base) {
        _compile_arena.base = (char*)malloc(ARENA_DEFAULT_SIZE);
        _compile_arena.ptr = _compile_arena.base;
        _compile_arena.end = _compile_arena.base + ARENA_DEFAULT_SIZE;
    }
}

SYSCALL void *arena_alloc(size_t size) {
    if (!_compile_arena.base) arena_init();
    
    size = (size + 7) & ~7;
    
    if (_compile_arena.ptr + size > _compile_arena.end) {
        size_t new_size = ARENA_DEFAULT_SIZE * 2;
        char *new_base = (char*)malloc(new_size);
        if (!new_base) return 0;
        memcpy(new_base, _compile_arena.base, _compile_arena.ptr - _compile_arena.base);
        free(_compile_arena.base);
        _compile_arena.base = new_base;
        _compile_arena.ptr = new_base + (_compile_arena.ptr - _compile_arena.base);
        _compile_arena.end = new_base + new_size;
    }
    
    void *result = _compile_arena.ptr;
    _compile_arena.ptr += size;
    return result;
}

SYSCALL void arena_reset(void) {
    if (_compile_arena.base) {
        _compile_arena.ptr = _compile_arena.base;
    }
}

SYSCALL void arena_free(void) {
    if (_compile_arena.base) {
        free(_compile_arena.base);
        _compile_arena.base = 0;
        _compile_arena.ptr = 0;
        _compile_arena.end = 0;
    }
}

#endif /* defined(MACOS) */

/* SIGSEGV/SIGBUS handler for debug — prints fault address, registers, backtrace */
/* Write to BOTH fd 1 and fd 2 — the failing fd must not hide the dump. */
static void _w2(const char *s, int n) { (void)!write(1, s, n); (void)!write(2, s, n); }
/* Nested-fault guard: if a dump read touches unmapped memory, the second
 * fault re-enters the handler — exit cleanly instead of hanging, keeping all
 * lines already printed. */
static volatile int _in_handler = 0;
#if defined(_WIN32)
static void _sigsegv(int sig) {
    if (_in_handler) { _exit(139); }
    _in_handler = 1;
    void *buf[64];
    int n = backtrace(buf, 64);
    write(2, sig == 11 ? "SIGNAL:SIGSEGV\n" : "SIGNAL:SIGBUS\n", 16);
    backtrace_symbols_fd(buf, n, 2);
    _exit(139);
}
__attribute__((constructor))
static void _init_sig(void) {
    signal(SIGSEGV, _sigsegv);
    signal(SIGBUS, _sigsegv);
}
#else
static void _sigsegv(int sig, siginfo_t *info, void *uctx) {
    void *buf[64];
    if (_in_handler) { _w2("NESTED-FAULT-EXIT\n", 17); _exit(139); }
    _in_handler = 1;
    /* Raw-write the marker FIRST — a corrupted heap can crash fopen/fprintf
     * inside the handler, so everything critical goes to stderr via write(). */
    _w2(sig == 11 ? "SIGNAL:SIGSEGV\n" : "SIGNAL:SIGBUS\n", 16);
    int n = backtrace(buf, 64);
    char line[512];
    int len;
    FILE *df = NULL;
    /* Darwin arm64: mcontext64 = __es (16: far 0, esr 8, exception 12)
     * + thread state64 at +0x10 (x0..x28, fp 232, lr 240, sp 248, pc 256,
     * cpsr 264, pad 268). uc_mcontext pointer read at uctx+0x30. */
    if (uctx) {
        void *mctx = *(void **)((char *)uctx + 0x30);
        unsigned char *mb = (unsigned char *)mctx;
        char hdr[64];
        int hl = snprintf(hdr, sizeof(hdr), "UCTX=%p UC_MCONTEXT=%p\n", uctx, mctx);
        _w2(hdr, hl);
        if (df) fputs(hdr, df);
        if (mb) {
            unsigned long long far = *(unsigned long long *)(mb + 0);
            unsigned int esr = *(unsigned int *)(mb + 8);
            unsigned char *ts = mb + 16;
            unsigned long long x0 = *(unsigned long long *)(ts + 0);
            unsigned long long x29 = *(unsigned long long *)(ts + 232);
            unsigned long long x30 = *(unsigned long long *)(ts + 240);
            unsigned long long x31 = *(unsigned long long *)(ts + 248);
            unsigned long long pc = *(unsigned long long *)(ts + 256);
            unsigned int cpsr = *(unsigned int *)(ts + 264);
            len = snprintf(line, sizeof(line),
                "SIG: far=%llx esr=%x x0=%llx fp=%llx lr=%llx sp=%llx pc=%llx cpsr=%x\n",
                far, esr, x0, x29, x30, x31, pc, cpsr);
            _w2(line, len);
            if (df) fputs(line, df);
            /* Resolve the faulting instruction and its caller via dladdr —
             * identifies the exact function + offset without needing the
             * PIE slide (dladdr returns running addresses). */
            {
                Dl_info di;
                if (dladdr((void *)pc, &di) && di.dli_sname) {
                    len = snprintf(line, sizeof(line), "PC_SYM: %s+%lld\n",
                        di.dli_sname, (long long)((unsigned long long)pc -
                        (unsigned long long)di.dli_saddr));
                    _w2(line, len);
                }
                if (dladdr((void *)x30, &di) && di.dli_sname) {
                    len = snprintf(line, sizeof(line), "LR_SYM: %s+%lld\n",
                        di.dli_sname, (long long)((unsigned long long)x30 -
                        (unsigned long long)di.dli_saddr));
                    _w2(line, len);
                }
#if defined(MACOS)
                if (_last_realloc_from && dladdr(_last_realloc_from, &di) && di.dli_sname) {
                    len = snprintf(line, sizeof(line), "FROM_SYM: %s+%lld\n",
                        di.dli_sname, (long long)((unsigned long long)_last_realloc_from -
                        (unsigned long long)di.dli_saddr));
                    _w2(line, len);
                }
#endif
            /* Walk the frame chain upward from the faulted fp and resolve each
             * caller's saved lr via dladdr — reveals the recursion cycle on a
             * stack overflow. Garbage fp chain → nested fault → clean exit. */
            {
                unsigned long long cur_fp = x29;
                int depth = 0;
                while (cur_fp >= 0x100000000LL && cur_fp < 0x2000000000LL && depth < 64) {
                    unsigned long long *frm = (unsigned long long *)cur_fp;
                    unsigned long long rlr = frm[1];
                    unsigned long long nfp = frm[0];
                    Dl_info di2;
                    if (dladdr((void *)rlr, &di2) && di2.dli_sname)
                        len = snprintf(line, sizeof(line), "FRAME %d: %s+%lld\n",
                            depth, di2.dli_sname,
                            (long long)(rlr - (unsigned long long)di2.dli_saddr));
                    else
                        len = snprintf(line, sizeof(line), "FRAME %d: %llx\n", depth, rlr);
                    _w2(line, len);
                    if (nfp <= cur_fp || nfp >= 0x2000000000LL) break;
                    cur_fp = nfp;
                    depth++;
                }
            }
            }
            /* _parse frame locals: [fp-8] tokens, [fp-16] filename,
             * [fp-24] ps, [fp-32] stmts, [fp-40] flag, [fp-48] tok. */
            if (x29 > 0x100000000LL && x29 < 0x2000000000LL) {
                unsigned long long *f = (unsigned long long *)x29;
                len = snprintf(line, sizeof(line),
                    "PARSE: tokens=%llx filename=%llx ps=%llx stmts=%llx flag=%llx tok=%llx saved_fp=%llx saved_lr=%llx\n",
                    f[-1], f[-2], f[-3], f[-4], f[-5], f[-6], f[0], f[1]);
                _w2(line, len);
                if (df) fputs(line, df);
                unsigned long long ps = f[-3];
                if (ps > 0x100000000LL && ps < 0x2000000000LL) {
                    unsigned long long *p = (unsigned long long *)ps;
                    len = snprintf(line, sizeof(line),
                        "PS: tokens=%llx pos=%lld filename=%llx comp_counter=%lld\n",
                        p[0], (long long)p[1], p[2], (long long)p[3]);
                    _w2(line, len);
                    if (df) fputs(line, df);
                    unsigned long long tk = p[0];
                    if (tk > 0x100000000LL && tk < 0x2000000000LL) {
                        unsigned int cnt = *(unsigned int *)(tk + 0);
                        unsigned int cap = *(unsigned int *)(tk + 4);
                        unsigned long long data = *(unsigned long long *)(tk + 8);
                        long long pos = (long long)p[1];
                        unsigned long long el = 0;
                        if (pos >= 0 && pos < (long long)cnt && cnt < 100000000 &&
                            data > 0x100000000LL && data < 0x2000000000LL)
                            el = ((unsigned long long *)data)[pos];
                        len = snprintf(line, sizeof(line),
                            "TOKENS: count=%u cap=%u data=%llx pos=%lld elem=%llx\n",
                            cnt, cap, data, pos, el);
                        _w2(line, len);
                        if (df) fputs(line, df);
                        if (el > 0x100000000LL && el < 0x2000000000LL) {
                            len = snprintf(line, sizeof(line),
                                "ELEM: kind=%llx v2=%llx v3=%llx v4=%llx\n",
                                ((unsigned long long *)el)[0], ((unsigned long long *)el)[1],
                                ((unsigned long long *)el)[2], ((unsigned long long *)el)[3]);
                            _w2(line, len);
                            if (df) fputs(line, df);
                        }
                        /* Heap hexdump around the tokens header: covers the
                         * header chunk, data buffer, ps/stmts overlap. */
                        if (df) {
                            unsigned char *tkh = (unsigned char *)tk - 0x40;
                            fprintf(df, "HEAP@tk-0x40 (%p):\n", tkh);
                            for (int i = 0; i < 0x200; i += 16) {
                                char hl4[64];
                                int l4 = snprintf(hl4, sizeof(hl4), "%03x:", i);
                                for (int j = 0; j < 16; j++)
                                    l4 += snprintf(hl4 + l4, sizeof(hl4) - l4, " %02x", tkh[i + j]);
                                fprintf(df, "%s\n", hl4);
                            }
                        }
                    }
                }
            }
            /* REGS to stderr via raw write (heap-safe). */
            len = snprintf(line, sizeof(line),
                "REGS: x1=%llx x2=%llx x3=%llx x4=%llx x5=%llx x6=%llx x7=%llx x8=%llx x9=%llx\n",
                ((unsigned long long *)ts)[1], ((unsigned long long *)ts)[2],
                ((unsigned long long *)ts)[3], ((unsigned long long *)ts)[4],
                ((unsigned long long *)ts)[5], ((unsigned long long *)ts)[6],
                ((unsigned long long *)ts)[7], ((unsigned long long *)ts)[8],
                ((unsigned long long *)ts)[9]);
            _w2(line, len);
            len = snprintf(line, sizeof(line),
                "REGS: x10=%llx x11=%llx x12=%llx x13=%llx x14=%llx x15=%llx x16=%llx x17=%llx x18=%llx\n",
                ((unsigned long long *)ts)[10], ((unsigned long long *)ts)[11],
                ((unsigned long long *)ts)[12], ((unsigned long long *)ts)[13],
                ((unsigned long long *)ts)[14], ((unsigned long long *)ts)[15],
                ((unsigned long long *)ts)[16], ((unsigned long long *)ts)[17],
                ((unsigned long long *)ts)[18]);
            _w2(line, len);
            len = snprintf(line, sizeof(line),
                "REGS: x19=%llx x20=%llx x21=%llx x22=%llx x23=%llx x24=%llx x25=%llx x26=%llx x27=%llx x28=%llx\n",
                ((unsigned long long *)ts)[19], ((unsigned long long *)ts)[20],
                ((unsigned long long *)ts)[21], ((unsigned long long *)ts)[22],
                ((unsigned long long *)ts)[23], ((unsigned long long *)ts)[24],
                ((unsigned long long *)ts)[25], ((unsigned long long *)ts)[26],
                ((unsigned long long *)ts)[27], ((unsigned long long *)ts)[28]);
            _w2(line, len);
            /* Hexdumps: file only (best-effort; fopen/malloc may crash on a
             * corrupted heap — critical lines are already on stderr). */
            df = fopen("nova_diag.txt", "a");
            if (df) {
                if (x31 > 0x100000000LL && x31 < 0x2000000000LL) {
                    unsigned char *spb = (unsigned char *)x31;
                    fprintf(df, "STACK@sp=%llx fp=%llx:\n", x31, x29);
                    for (int i = -0x60; i < 0x160; i += 16) {
                        char hl2[64];
                        int l2 = snprintf(hl2, sizeof(hl2), "%s%03x:", i < 0 ? "-" : "+", i < 0 ? -i : i);
                        for (int j = 0; j < 16; j++)
                            l2 += snprintf(hl2 + l2, sizeof(hl2) - l2, " %02x", spb[i + j]);
                        fprintf(df, "%s\n", hl2);
                    }
                }
                if (x29 > 0x100000000LL && x29 < 0x2000000000LL) {
                    unsigned char *fpb = (unsigned char *)x29;
                    fprintf(df, "STACK@fp=%llx (caller frame):\n", x29);
                    for (int i = 0; i < 0x200; i += 16) {
                        char hl3[64];
                        int l3 = snprintf(hl3, sizeof(hl3), "+%03x:", i);
                        for (int j = 0; j < 16; j++)
                            l3 += snprintf(hl3 + l3, sizeof(hl3) - l3, " %02x", fpb[i + j]);
                        fprintf(df, "%s\n", hl3);
                    }
                }
            }
        }
    }
    len = snprintf(line, sizeof(line),
                   "FAULT: addr=%p bt_pc=%p\n", info->si_addr, buf[2]);
    _w2(line, len);
    if (df) { fputs(line, df); fclose(df); }
    backtrace_symbols_fd(buf, n, 1);
    backtrace_symbols_fd(buf, n, 2);
    _exit(139);
}
/* Alt stack: if the faulting sp is garbage/guard-page, the kernel can't set
 * up a signal frame on it — the handler silently never runs. SA_ONSTACK +
 * sigaltstack lets the handler run regardless of the corrupted sp. */
static char _alt_stack[65536];
__attribute__((constructor))
static void _init_sig(void) {
    struct sigaction sa;
    stack_t ss;
    memset(&sa, 0, sizeof(sa));
    sa.sa_sigaction = _sigsegv;
    sa.sa_flags = SA_SIGINFO | SA_ONSTACK;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGSEGV, &sa, NULL);
    sigaction(SIGBUS, &sa, NULL);
    memset(&ss, 0, sizeof(ss));
    ss.ss_sp = _alt_stack;
    ss.ss_size = sizeof(_alt_stack);
    sigaltstack(&ss, NULL);
}
#endif /* defined(_WIN32) */

/* Out-of-bounds globals and handler (also in Windows section above) */
long long _oob_file_ptr;
long long _oob_line;
SYSCALL void _out_of_bounds(void) {
    if (_oob_file_ptr) {
        _printf("error: Index Out Of Bounds at ", 0);
        _printf("%s", _oob_file_ptr);
        _printf(" line %d\n", _oob_line);
    } else {
        _printf("error: Index Out Of Bounds\n", 0);
    }
    exit(1);
}

#endif /* defined(_WIN32) / defined(LINUX_WRAP) / MACOS */

/* ==================== Assembly alias for Mach-O (macOS ARM64) ==================== */
/* On ARM64 Mach-O, Clang prepends an underscore to all C symbols.
 * So C function `_abs` exports as Mach-O `__abs`, while assembly
 * references `_abs` (single underscore). These aliases bridge the gap. */
#if defined(MACOS) && defined(__aarch64__)
__asm__(".globl _abs\n.set _abs, __abs");
__asm__(".globl _call\n.set _call, __call");
__asm__(".globl _char_code\n.set _char_code, __char_code");
__asm__(".globl _dict_new\n.set _dict_new, __dict_new");
__asm__(".globl _dict_has\n.set _dict_has, __dict_has");
__asm__(".globl _dict_get\n.set _dict_get, __dict_get");
__asm__(".globl _dict_set\n.set _dict_set, __dict_set");
__asm__(".globl _dict_remove\n.set _dict_remove, __dict_remove");
__asm__(".globl _dict_keys\n.set _dict_keys, __dict_keys");
__asm__(".globl _dict_values\n.set _dict_values, __dict_values");
__asm__(".globl _dict_items\n.set _dict_items, __dict_items");
__asm__(".globl _file_exists\n.set _file_exists, __file_exists");
__asm__(".globl _file_size\n.set _file_size, __file_size");
__asm__(".globl _file_type\n.set _file_type, __file_type");
__asm__(".globl _max\n.set _max, __max");
__asm__(".globl _min\n.set _min, __min");
__asm__(".globl _now\n.set _now, __now");
__asm__(".globl _realloc\n.set _realloc, __realloc");
__asm__(".globl _slice_list\n.set _slice_list, __slice_list");
__asm__(".globl _str_sub\n.set _str_sub, __str_sub");
__asm__(".globl _sys_alloc_c\n.set _sys_alloc_c, __sys_alloc_c");
__asm__(".globl _sys_close_c\n.set _sys_close_c, __sys_close_c");
__asm__(".globl _sys_exit_c\n.set _sys_exit_c, __sys_exit_c");
__asm__(".globl _sys_flush_c\n.set _sys_flush_c, __sys_flush_c");
__asm__(".globl _sys_free_c\n.set _sys_free_c, __sys_free_c");
__asm__(".globl _sys_get_args_c\n.set _sys_get_args_c, __sys_get_args_c");
__asm__(".globl _sys_get_tick_count_c\n.set _sys_get_tick_count_c, __sys_get_tick_count_c");
__asm__(".globl _sys_open_c\n.set _sys_open_c, __sys_open_c");
__asm__(".globl _sys_platform_c\n.set _sys_platform_c, __sys_platform_c");
__asm__(".globl _sys_read_c\n.set _sys_read_c, __sys_read_c");
__asm__(".globl _sys_write_c\n.set _sys_write_c, __sys_write_c");
__asm__(".globl _sys_awrite_c\n.set _sys_awrite_c, __sys_awrite_c");
__asm__(".globl _sys_write_raw_c\n.set _sys_write_raw_c, __sys_write_raw_c");
__asm__(".globl _list_insert\n.set _list_insert, __list_insert");
__asm__(".globl _list_clear\n.set _list_clear, __list_clear");
__asm__(".globl _random\n.set _random, __random");
__asm__(".globl _random_range\n.set _random_range, __random_range");
__asm__(".globl _chacha20_init\n.set _chacha20_init, __chacha20_init");
__asm__(".globl _api_open_internal\n.set _api_open_internal, __api_open_internal");
/* Non-variadic printf/sprintf — must be aliased or assembly calls resolve
 * to the system's variadic printf (which reads garbage from the register
 * save area on ARM64 AAPCS64). Only these two are aliased; other libc
 * wrappers (malloc, strlen, fwrite, etc.) are NOT defined on macOS since
 * system libc exports them at the same Mach-O symbol name directly.
 * Defining _malloc on macOS would cause infinite recursion: _malloc calls
 * malloc() → `bl _malloc` → back to _malloc. */
__asm__(".globl _printf\n.set _printf, __printf");
/* _sprintf deliberately NOT aliased: macOS libc exports `_sprintf` (=sprintf)
 * directly, so the codegen's `bl _sprintf` resolves to the system function.
 * Aliasing it to __sprintf made the wrapper's internal `sprintf()` call
 * recurse into itself until stack exhaustion. */
__asm__(".globl _system_c\n.set _system_c, __system_c");
__asm__(".globl _oob_file_ptr\n.set _oob_file_ptr, __oob_file_ptr");
__asm__(".globl _oob_line\n.set _oob_line, __oob_line");
__asm__(".globl _out_of_bounds\n.set _out_of_bounds, __out_of_bounds");
__asm__(".globl _nova_arc_alloc\n.set _nova_arc_alloc, __nova_arc_alloc");
__asm__(".globl _nova_inc_ref\n.set _nova_inc_ref, __nova_inc_ref");
__asm__(".globl _nova_dec_ref\n.set _nova_dec_ref, __nova_dec_ref");
__asm__(".globl _slice_cmp\n.set _slice_cmp, __slice_cmp");
__asm__(".globl _slice_eq\n.set _slice_eq, __slice_eq");
__asm__(".globl _slice_find\n.set _slice_find, __slice_find");
__asm__(".globl _slice_to_str\n.set _slice_to_str, __slice_to_str");
__asm__(".globl _slice_from_str\n.set _slice_from_str, __slice_from_str");
__asm__(".globl _slice_from_list_data\n.set _slice_from_list_data, __slice_from_list_data");
__asm__(".globl _slice_byte_at\n.set _slice_byte_at, __slice_byte_at");
__asm__(".globl _ffi_open\n.set _ffi_open, __ffi_open");
__asm__(".globl _ffi_sym\n.set _ffi_sym, __ffi_sym");
__asm__(".globl _ffi_close\n.set _ffi_close, __ffi_close");
__asm__(".globl _ffi_call0\n.set _ffi_call0, __ffi_call0");
__asm__(".globl _ffi_call1\n.set _ffi_call1, __ffi_call1");
__asm__(".globl _ffi_call2\n.set _ffi_call2, __ffi_call2");
__asm__(".globl _ffi_call3\n.set _ffi_call3, __ffi_call3");
__asm__(".globl _ffi_call4\n.set _ffi_call4, __ffi_call4");
__asm__(".globl _ffi_call5\n.set _ffi_call5, __ffi_call5");
__asm__(".globl _ffi_call6\n.set _ffi_call6, __ffi_call6");
__asm__(".globl _gui_poll_char\n.set _gui_poll_char, __gui_poll_char");
__asm__(".globl _gui_char_to_str\n.set _gui_char_to_str, __gui_char_to_str");
#endif

/* ==================== Dict & ARC runtime functions (all platforms) ==================== */
/* Forward declarations for dict & ARC functions (Linux/macOS need these since malloc/free/memset
 * aren't defined yet. On Windows they're already defined above.) */
#if !defined(_WIN32)
SYSCALL void *malloc(size_t);
SYSCALL void free(void *);
#if !defined(__APPLE__)
SYSCALL void *memset(void *, int, size_t);
#endif
#endif

/* ==================== Automatic Reference Counting (ARC) Engine ==================== */
#define NOVA_ARC_MAGIC 0x4E4F5641 /* "NOVA" */

/* Stable value-kind IDs used by the future shared VM/native value ABI.
 * Existing ARC tags are kept numerically compatible: lists, dictionaries,
 * and strings already use these IDs in allocations emitted by codegen. */
typedef enum {
    NOVA_VALUE_NONE   = 0,
    NOVA_VALUE_LIST   = 1,
    NOVA_VALUE_DICT   = 2,
    NOVA_VALUE_STRING = 3,
    NOVA_VALUE_BOOL   = 4,
    NOVA_VALUE_INT    = 5,
    NOVA_VALUE_FLOAT  = 6
} NovaValueKind;

typedef struct {
    uint32_t magic;      /* Magic identifier 0x4E4F5641 */
    int32_t  ref_count;  /* Active reference count */
    uint32_t type_tag;   /* NovaValueKind for heap-backed values */
    uint32_t pad;        /* 16-byte alignment pad */
} NovaARCHeader;

SYSCALL void *_nova_arc_alloc(unsigned int size, uint32_t type_tag);
SYSCALL void *_nova_value_retain(void *ptr);
SYSCALL void _nova_dec_ref(void *ptr);

/* Internal ABI probe. It is intentionally limited to heap-backed values:
 * immediate integers and booleans do not carry a pointer header yet. */
SYSCALL int _nova_value_kind(void *ptr) {
    NovaARCHeader *hdr;
    if (!ptr) return NOVA_VALUE_NONE;
    /* Immediate Nova scalars are passed through pointer-shaped ABI slots. */
    if ((uintptr_t)ptr < 4096u) return NOVA_VALUE_NONE;
    hdr = ((NovaARCHeader*)ptr) - 1;
    if (hdr->magic != NOVA_ARC_MAGIC) return NOVA_VALUE_NONE;
    return (int)hdr->type_tag;
}

static void *_nova_box_alloc(uint32_t kind, size_t size) {
    return _nova_arc_alloc((unsigned int)size, kind);
}

SYSCALL void *_value_box_none(void) {
    return _nova_box_alloc(NOVA_VALUE_NONE, sizeof(intptr_t));
}

SYSCALL void *_value_box_string(const char *value) {
    size_t length;
    char *boxed;
    if (!value) value = "";
    length = strlen(value) + 1;
    boxed = (char*)_nova_box_alloc(NOVA_VALUE_STRING, length);
    if (boxed) strcpy(boxed, value);
    return boxed;
}

SYSCALL void *_value_box_list(void *value) {
    if (_nova_value_kind(value) != NOVA_VALUE_LIST) return 0;
    return _nova_value_retain(value);
}

SYSCALL void *_value_box_dict(void *value) {
    if (_nova_value_kind(value) != NOVA_VALUE_DICT) return 0;
    return _nova_value_retain(value);
}

SYSCALL void *_value_box_bool(int value) {
    intptr_t *boxed = (intptr_t*)_nova_box_alloc(NOVA_VALUE_BOOL, sizeof(intptr_t));
    if (boxed) *boxed = value ? 1 : 0;
    return boxed;
}

SYSCALL void *_value_box_int(long long value) {
    intptr_t *boxed = (intptr_t*)_nova_box_alloc(NOVA_VALUE_INT, sizeof(intptr_t));
    if (boxed) *boxed = (intptr_t)value;
    return boxed;
}

SYSCALL void *_value_box_float(double value) {
    double *boxed = (double*)_nova_box_alloc(NOVA_VALUE_FLOAT, sizeof(double));
    if (boxed) *boxed = value;
    return boxed;
}

SYSCALL int _value_unbox_bool(void *ptr) {
    if (_nova_value_kind(ptr) != NOVA_VALUE_BOOL) return 0;
    return *(intptr_t*)ptr ? 1 : 0;
}

SYSCALL long long _value_unbox_int(void *ptr) {
    if (_nova_value_kind(ptr) != NOVA_VALUE_INT) return 0;
    return (long long)*(intptr_t*)ptr;
}

SYSCALL double _value_unbox_float(void *ptr) {
    if (_nova_value_kind(ptr) != NOVA_VALUE_FLOAT) return 0.0;
    return *(double*)ptr;
}

SYSCALL const char *_value_unbox_string(void *ptr) {
    if (_nova_value_kind(ptr) != NOVA_VALUE_STRING) return "";
    return (const char*)ptr;
}


SYSCALL void *_nova_arc_alloc(unsigned int size, uint32_t type_tag) {
    unsigned int total_size = size + (unsigned int)sizeof(NovaARCHeader);
#if defined(_WIN32)
    NovaARCHeader *hdr = (NovaARCHeader*)STR_PFX(malloc)(total_size);
#else
    NovaARCHeader *hdr = (NovaARCHeader*)malloc(total_size);
#endif
    if (!hdr) return 0;
    hdr->magic = NOVA_ARC_MAGIC;
    hdr->ref_count = 1;
    hdr->type_tag = type_tag;
    hdr->pad = 0;
    return (void*)(hdr + 1);
}

SYSCALL void _nova_inc_ref(void *ptr) {
    if (!ptr) return;
    NovaARCHeader *hdr = ((NovaARCHeader*)ptr) - 1;
    if (hdr->magic == NOVA_ARC_MAGIC) {
        hdr->ref_count++;
    }
}

SYSCALL void dict_free(void *d);

SYSCALL void _nova_dec_ref(void *ptr) {
    if (!ptr) return;
    NovaARCHeader *hdr = ((NovaARCHeader*)ptr) - 1;
    if (hdr->magic == NOVA_ARC_MAGIC) {
        hdr->ref_count--;
        if (hdr->ref_count <= 0) {
            if (hdr->type_tag == 1) { /* LIST */
                void *data = *(void**)((char*)ptr + 8);
                if (data) {
#if defined(_WIN32)
                    STR_PFX(free)(data);
#else
                    free(data);
#endif
                }
            } else if (hdr->type_tag == 2) { /* DICT */
                dict_free(ptr);
                return;
            }
#if defined(_WIN32)
            STR_PFX(free)(hdr);
#else
            free(hdr);
#endif
        }
    }
}

/* strcmp, strlen, strcpy are defined above on Windows, in <string.h> on macOS/Linux */
/* Dict layout (open addressing, single flat entry array):
 * struct NovaDict {
 *   int count;       // offset 0
 *   int capacity;    // offset 4 (always power of 2)
 *   Entry *entries;  // offset 8 (separately allocated, flat array)
 * }
 * Entry: { uint64_t hash; char *key; intptr_t value; } (24 bytes)
 * Empty: key == NULL, Tombstone: key == (char*)1
 */

typedef struct {
    uint64_t hash;
    char *key;
    intptr_t value;
} DictEntry;

#if defined(_WIN32)
#define DICT_MALLOC(s) STR_PFX(malloc)(s)
#define DICT_FREE(p) STR_PFX(free)(p)
#else
#define DICT_MALLOC(s) malloc(s)
#define DICT_FREE(p) free(p)
#endif

static uint64_t _dh64(const char *s) {
    uint64_t h = 14695981039346656037ULL;
    while (*s) {
        h ^= (unsigned char)(*s++);
        h *= 1099511628211ULL;
    }
    return h;
}

#define TOMBSTONE_KEY ((char*)1)
#define IS_EMPTY(e)   ((e)->key == NULL)
#define IS_TOMBSTONE(e) ((e)->key == TOMBSTONE_KEY)
#define IS_OCCUPIED(e) (!IS_EMPTY(e) && !IS_TOMBSTONE(e))

static DictEntry *_dict_entries(void *d) {
    return *(DictEntry**)((char*)d + 8);
}

static int _df_idx(void *d, const char *key, uint64_t hash) {
    int cap = *(int*)((char*)d + 4);
    if (cap < 1) return -1;
    DictEntry *entries = _dict_entries(d);
    if (!entries) return -1;
    uint64_t mask = (uint64_t)(cap - 1);
    int idx = (int)(hash & mask);
    for (int i = 0; i < cap; i++) {
        int probe = (idx + i) & (int)mask;
        DictEntry *e = &entries[probe];
        if (IS_EMPTY(e)) return -1;
        if (IS_TOMBSTONE(e)) continue;
        if (e->hash == hash && strcmp(e->key, key) == 0) return probe;
    }
    return -1;
}

static int _df_find_or_insert(void *d, const char *key, uint64_t hash) {
    int cap = *(int*)((char*)d + 4);
    DictEntry *entries = _dict_entries(d);
    if (!entries) return -1;
    uint64_t mask = (uint64_t)(cap - 1);
    int idx = (int)(hash & mask);
    int first_tombstone = -1;
    for (int i = 0; i < cap; i++) {
        int probe = (idx + i) & (int)mask;
        DictEntry *e = &entries[probe];
        if (IS_EMPTY(e)) {
            if (first_tombstone >= 0) return first_tombstone;
            return probe;
        }
        if (IS_TOMBSTONE(e)) {
            if (first_tombstone < 0) first_tombstone = probe;
            continue;
        }
        if (e->hash == hash && strcmp(e->key, key) == 0) return probe;
    }
    if (first_tombstone >= 0) return first_tombstone;
    return -1;
}

static void _dg(void *d) {
    int old_cap = *(int*)((char*)d + 4);
    DictEntry *old_entries = _dict_entries(d);
    int new_cap = old_cap * 2;
    size_t entry_size = (size_t)new_cap * sizeof(DictEntry);
    DictEntry *new_entries = (DictEntry*)DICT_MALLOC(entry_size);
    if (!new_entries) return;
    memset(new_entries, 0, entry_size);
    if (old_entries) {
        for (int i = 0; i < old_cap; i++) {
            DictEntry *e = &old_entries[i];
            if (IS_OCCUPIED(e)) {
                uint64_t mask = (uint64_t)(new_cap - 1);
                int idx = (int)(e->hash & mask);
                for (int j = 0; j < new_cap; j++) {
                    int probe = (idx + j) & (int)mask;
                    if (IS_EMPTY(&new_entries[probe])) {
                        new_entries[probe] = *e;
                        break;
                    }
                }
            }
        }
        DICT_FREE(old_entries);
    }
    *(DictEntry**)((char*)d + 8) = new_entries;
    *(int*)((char*)d + 4) = new_cap;
}

SYSCALL void *dict_new(void) {
    int cap = 8;
    void *d = _nova_arc_alloc(16, 2);
    if (!d) return 0;
    DictEntry *entries = (DictEntry*)DICT_MALLOC((size_t)cap * sizeof(DictEntry));
    if (!entries) { _nova_dec_ref(d); return 0; }
    memset(entries, 0, (size_t)cap * sizeof(DictEntry));
    *(int*)d = 0;
    *(int*)((char*)d + 4) = cap;
    *(DictEntry**)((char*)d + 8) = entries;
    return d;
}

SYSCALL int dict_has(void *d, const char *key) {
    if (!d || !key) return 0;
    uint64_t hash = _dh64(key);
    return _df_idx(d, key, hash) >= 0 ? 1 : 0;
}

SYSCALL intptr_t dict_get(void *d, const char *key) {
    if (!d || !key) return 0;
    uint64_t hash = _dh64(key);
    int idx = _df_idx(d, key, hash);
    if (idx < 0) return 0;
    DictEntry *entries = _dict_entries(d);
    return entries[idx].value;
}

SYSCALL void dict_set(void *d, const char *key, intptr_t value) {
    if (!d || !key) return;
    int count = *(int*)d;
    int cap = *(int*)((char*)d + 4);
    uint64_t hash = _dh64(key);
    int idx = _df_find_or_insert(d, key, hash);
    if (idx < 0) {
        _dg(d);
        cap = *(int*)((char*)d + 4);
        idx = _df_find_or_insert(d, key, hash);
        if (idx < 0) return;
    }
    DictEntry *entries = _dict_entries(d);
    DictEntry *e = &entries[idx];
    if (IS_OCCUPIED(e)) {
        e->value = value;
        return;
    }
    size_t len = strlen(key) + 1;
    char *key_copy = (char*)DICT_MALLOC(len);
    if (!key_copy) return;
    strcpy(key_copy, key);
    e->hash = hash;
    e->key = key_copy;
    e->value = value;
    *(int*)d = count + 1;
    if (*(int*)d * 10 >= cap * 7) {
        _dg(d);
    }
}

SYSCALL void dict_remove(void *d, const char *key) {
    if (!d || !key) return;
    uint64_t hash = _dh64(key);
    int idx = _df_idx(d, key, hash);
    if (idx < 0) return;
    DictEntry *entries = _dict_entries(d);
    DictEntry *e = &entries[idx];
    DICT_FREE(e->key);
    e->key = TOMBSTONE_KEY;
    e->value = 0;
    e->hash = 0;
    *(int*)d = *(int*)d - 1;
}

SYSCALL void dict_free(void *d) {
    if (!d) return;
    int cap = *(int*)((char*)d + 4);
    DictEntry *entries = _dict_entries(d);
    if (entries) {
        for (int i = 0; i < cap; i++) {
            if (IS_OCCUPIED(&entries[i])) {
                DICT_FREE(entries[i].key);
            }
        }
        DICT_FREE(entries);
    }
    NovaARCHeader *hdr = ((NovaARCHeader*)d) - 1;
    if (hdr->magic == NOVA_ARC_MAGIC) {
#if defined(_WIN32)
        STR_PFX(free)(hdr);
#else
        free(hdr);
#endif
    } else {
#if defined(_WIN32)
        STR_PFX(free)(d);
#else
        free(d);
#endif
    }
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
    DictEntry *entries = _dict_entries(d);
    int n = _dc(d);
    void *list = malloc(16);
    if (!list) return 0;
    void *data = malloc((size_t)(n ? n : 1) * sizeof(intptr_t));
    if (!data) { free(list); return 0; }
    *(int*)list = n;
    *(int*)((char*)list + 4) = n;
    *(intptr_t*)((char*)list + 8) = (intptr_t)data;
    int out = 0;
    for (int i = 0; i < cap; i++) {
        if (IS_OCCUPIED(&entries[i])) {
            size_t sl = strlen(entries[i].key) + 1;
            char *copy = (char*)malloc(sl);
            if (copy) { strcpy(copy, entries[i].key); }
            *(intptr_t*)((char*)data + out * sizeof(intptr_t)) = (intptr_t)(copy ? copy : entries[i].key);
            out++;
        }
    }
    return list;
}

SYSCALL void *dict_values(void *d) {
    int cap = *(int*)((char*)d + 4);
    DictEntry *entries = _dict_entries(d);
    int n = _dc(d);
    void *list = malloc(16);
    if (!list) return 0;
    void *data = malloc((size_t)(n ? n : 1) * sizeof(intptr_t));
    if (!data) { free(list); return 0; }
    *(int*)list = n;
    *(int*)((char*)list + 4) = n;
    *(intptr_t*)((char*)list + 8) = (intptr_t)data;
    int out = 0;
    for (int i = 0; i < cap; i++) {
        if (IS_OCCUPIED(&entries[i])) {
            *(intptr_t*)((char*)data + out * sizeof(intptr_t)) = (intptr_t)entries[i].value;
            out++;
        }
    }
    return list;
}

SYSCALL void *dict_items(void *d) {
    int cap = *(int*)((char*)d + 4);
    DictEntry *entries = _dict_entries(d);
    int n = _dc(d);
    void *list = _nova_arc_alloc(16, NOVA_VALUE_LIST);
    if (!list) return 0;
    void *data = malloc((size_t)(n ? n : 1) * 2 * sizeof(intptr_t));
    if (!data) { _nova_dec_ref(list); return 0; }
    *(int*)list = n * 2;
    *(int*)((char*)list + 4) = n * 2;
    *(intptr_t*)((char*)list + 8) = (intptr_t)data;
    int out = 0;
    for (int i = 0; i < cap; i++) {
        if (IS_OCCUPIED(&entries[i])) {
            size_t sl = strlen(entries[i].key) + 1;
            char *copy = (char*)malloc(sl);
            if (copy) { strcpy(copy, entries[i].key); }
            *(intptr_t*)((char*)data + out * sizeof(intptr_t)) = (intptr_t)(copy ? copy : entries[i].key);
            out++;
            *(intptr_t*)((char*)data + out * sizeof(intptr_t)) = (intptr_t)entries[i].value;
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

typedef struct {
    char *data;
    size_t length;
    size_t capacity;
} NovaJsonBuffer;

static int _json_put(NovaJsonBuffer *out, const char *text) {
    size_t size = strlen(text);
    if (out->length + size + 1 > out->capacity) {
        size_t capacity = out->capacity ? out->capacity : 32;
        while (capacity < out->length + size + 1) capacity *= 2;
        char *replacement = (char*)DICT_MALLOC(capacity);
        if (!replacement) return 0;
        if (out->data) {
            strcpy(replacement, out->data);
            DICT_FREE(out->data);
        } else {
            replacement[0] = '\0';
        }
        out->data = replacement;
        out->capacity = capacity;
    }
    strcpy(out->data + out->length, text);
    out->length += size;
    return 1;
}

static int _json_put_int(NovaJsonBuffer *out, intptr_t value) {
    char digits[32];
    int end = 31;
    int negative = value < 0;
    uint64_t magnitude = negative ? (uint64_t)(-(value + 1)) + 1 : (uint64_t)value;
    digits[end] = '\0';
    do {
        digits[--end] = (char)('0' + (magnitude % 10));
        magnitude /= 10;
    } while (magnitude);
    if (negative) digits[--end] = '-';
    return _json_put(out, digits + end);
}

static int _json_put_string(NovaJsonBuffer *out, const char *value) {
    const unsigned char *p = (const unsigned char*)(value ? value : "");
    if (!_json_put(out, "\"")) return 0;
    while (*p) {
        if (*p == '"' || *p == '\\') {
            char escaped[2] = {'\\', (char)*p};
            escaped[1] = '\0';
            if (!_json_put(out, escaped)) return 0;
        } else if (*p == '\n') {
            if (!_json_put(out, "\\n")) return 0;
        } else if (*p == '\r') {
            if (!_json_put(out, "\\r")) return 0;
        } else if (*p == '\t') {
            if (!_json_put(out, "\\t")) return 0;
        } else {
            char one[2] = {(char)*p, '\0'};
            if (!_json_put(out, one)) return 0;
        }
        p++;
    }
    return _json_put(out, "\"");
}

static int _nova_json_emit(void *value, NovaJsonBuffer *out) {
    int kind = _nova_value_kind(value);
    if (kind == NOVA_VALUE_NONE) {
        if ((uintptr_t)value >= 4096u &&
            ((NovaARCHeader*)value - 1)->magic == NOVA_ARC_MAGIC) {
            return _json_put(out, "null");
        }
        if ((uintptr_t)value < 4096u) return _json_put_int(out, (intptr_t)value);
        return _json_put_string(out, (const char*)value);
    }
    if (kind == NOVA_VALUE_STRING) return _json_put_string(out, (const char*)value);
    if (kind == NOVA_VALUE_BOOL) return _json_put(out, *(intptr_t*)value ? "true" : "false");
    if (kind == NOVA_VALUE_INT) return _json_put_int(out, *(intptr_t*)value);
    if (kind == NOVA_VALUE_LIST) {
        int count = *(int*)value;
        intptr_t *data = (intptr_t*)(*(intptr_t*)((char*)value + 8));
        if (!_json_put(out, "[")) return 0;
        for (int i = 0; i < count; i++) {
            if (i && !_json_put(out, ",")) return 0;
            if (!_nova_json_emit((void*)data[i], out)) return 0;
        }
        return _json_put(out, "]");
    }
    if (kind == NOVA_VALUE_DICT) {
        int cap = *(int*)((char*)value + 4);
        DictEntry *entries = _dict_entries(value);
        int emitted = 0;
        if (!_json_put(out, "{")) return 0;
        for (int i = 0; i < cap; i++) {
            if (IS_OCCUPIED(&entries[i])) {
                if (emitted++ && !_json_put(out, ",")) return 0;
                if (!_json_put_string(out, entries[i].key) ||
                    !_json_put(out, ":") ||
                    !_nova_json_emit((void*)entries[i].value, out)) return 0;
            }
        }
        return _json_put(out, "}");
    }
    return _json_put(out, "null");
}

SYSCALL char *_nova_json_stringify(void *value) {
    NovaJsonBuffer out = {0, 0, 0};
    if (!_nova_json_emit(value, &out)) {
        if (out.data) DICT_FREE(out.data);
        return 0;
    }
    return out.data;
}

SYSCALL int _nova_value_list_count(void *list) {
    if (_nova_value_kind(list) != NOVA_VALUE_LIST) return 0;
    return *(int*)list;
}

SYSCALL intptr_t _nova_value_list_item(void *list, int index) {
    int count;
    intptr_t *data;
    if (_nova_value_kind(list) != NOVA_VALUE_LIST) return 0;
    count = *(int*)list;
    if (index < 0 || index >= count) return 0;
    data = (intptr_t*)(*(intptr_t*)((char*)list + 8));
    return data ? data[index] : 0;
}

SYSCALL int _nova_value_dict_count(void *dict) {
    if (_nova_value_kind(dict) != NOVA_VALUE_DICT) return 0;
    return _dc(dict);
}

SYSCALL void *_nova_value_retain(void *ptr) {
    if (!ptr || _nova_value_kind(ptr) == NOVA_VALUE_NONE) return 0;
    _nova_inc_ref(ptr);
    return ptr;
}

SYSCALL void _nova_value_release(void *ptr) {
    if (!ptr || _nova_value_kind(ptr) == NOVA_VALUE_NONE) return;
    _nova_dec_ref(ptr);
}

SYSCALL int _nova_value_is_list(void *ptr) {
    return _nova_value_kind(ptr) == NOVA_VALUE_LIST ? 1 : 0;
}

SYSCALL int _nova_value_is_dict(void *ptr) {
    return _nova_value_kind(ptr) == NOVA_VALUE_DICT ? 1 : 0;
}

SYSCALL int _nova_value_is_string(void *ptr) {
    return _nova_value_kind(ptr) == NOVA_VALUE_STRING ? 1 : 0;
}

SYSCALL void *_nova_value_dict_keys(void *dict) {
    if (_nova_value_kind(dict) != NOVA_VALUE_DICT) return 0;
    return dict_keys(dict);
}

SYSCALL void *_nova_value_dict_values(void *dict) {
    if (_nova_value_kind(dict) != NOVA_VALUE_DICT) return 0;
    return dict_values(dict);
}

SYSCALL void *_nova_value_dict_items(void *dict) {
    if (_nova_value_kind(dict) != NOVA_VALUE_DICT) return 0;
    return dict_items(dict);
}

/* ===== Pointer/alloc bridge helpers ===== */
SYSCALL void *_list_wrap(void *ptr, intptr_t count) {
    void *list = malloc(16);
    if (!list) return 0;
    *(int*)list = (int)count;
    *(int*)((char*)list + 4) = (int)count;
    *(intptr_t*)((char*)list + 8) = (intptr_t)ptr;
    return list;
}

SYSCALL void *_as_list(void *ptr, intptr_t count) {
    return _list_wrap(ptr, count);
}

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

#if defined(LINUX_WRAP) || defined(MACOS)
SYSCALL const char *_sys_env_get_c(const char *name) {
    const char *value = getenv(name);
    return value ? value : "";
}
SYSCALL int _sys_env_set_c(const char *name, const char *value) {
    return setenv(name, value, 1) == 0 ? 1 : 0;
}
SYSCALL int _sys_process_run_c(void *args) {
    int count;
    intptr_t *values;
    char **argv;
    pid_t child;
    int status;
    int i;
    if (!args) return -1;
    count = *(int*)args;
    values = (intptr_t*)(*(intptr_t*)((char*)args + 8));
    if (count <= 0) return -1;
    argv = (char**)malloc((size_t)(count + 1) * sizeof(char*));
    if (!argv) return -1;
    for (i = 0; i < count; i++) argv[i] = (char*)values[i];
    argv[count] = NULL;
    child = fork();
    if (child < 0) { free(argv); return -1; }
    if (child == 0) {
        execvp(argv[0], argv);
        _exit(127);
    }
    if (waitpid(child, &status, 0) < 0) { free(argv); return -1; }
    free(argv);
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    if (WIFSIGNALED(status)) return 128 + WTERMSIG(status);
    return -1;
}
#endif

/* ==================== File read + get_args for Linux/macOS (no Win32 API) ==================== */
#if defined(LINUX_WRAP) || defined(MACOS)
#include <fcntl.h>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/mman.h>
#include <dlfcn.h>

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
    int fd;
    if (*mode == 'w' || *mode == 'a') {
        flags = O_WRONLY | O_CREAT;
        if (*mode == 'a') flags |= O_APPEND;
        else flags |= O_TRUNC;
        fd = open(path, flags, 0666);
    } else {
        fd = open(path, O_RDONLY);
    }
    if (fd < 0) return 0;
    return fd;
}

SYSCALL int _sys_mkdir_c(const char *path) {
    if (!path) return 0;
    return mkdir(path, 0777) == 0 ? 1 : 0;
}
SYSCALL int _sys_delete_c(const char *path) {
    if (!path) return 0;
    return remove(path) == 0 ? 1 : 0;
}
SYSCALL int _sys_copy_c(const char *source, const char *destination) {
    FILE *input;
    FILE *output;
    char buffer[8192];
    size_t count;
    if (!source || !destination || strcmp(source, destination) == 0) return 0;
    input = fopen(source, "rb");
    if (!input) return 0;
    output = fopen(destination, "wb");
    if (!output) { fclose(input); return 0; }
    while ((count = fread(buffer, 1, sizeof(buffer), input)) > 0) {
        if (fwrite(buffer, 1, count, output) != count) {
            fclose(input);
            fclose(output);
            remove(destination);
            return 0;
        }
    }
    if (ferror(input) || fclose(input) != 0 || fclose(output) != 0) {
        remove(destination);
        return 0;
    }
    return 1;
}
SYSCALL int _sys_move_c(const char *source, const char *destination) {
    if (!source || !destination) return 0;
    return rename(source, destination) == 0 ? 1 : 0;
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

/* ==================== Exception handling (manual stack unwind) ==================== */
long long _try_catch_sp;
long long _catch_ip;
long long _exception_val;

/* ==================== String helper functions ==================== */
SYSCALL int _char_code(const char *s, int i) {
    if (!s) return 0;
    return (unsigned char)s[i];
}

static char _str_empty[1] = {0};

SYSCALL char *_str_sub(const char *s, int start, int end) {
    if (!s) return 0;
    int actual_len = 0;
    while (s[actual_len] != '\0') actual_len++;
    if (start < 0) start = 0;
    if (end > actual_len) end = actual_len;
    int len = end - start;
    if (len < 0) len = 0;
    if (len == 0) {
        return _str_empty;
    }
    if (len == actual_len) {
        return (char*)s;
    }
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

/* ==================== Zero-copy Slice Helpers ==================== */
SYSCALL intptr_t _slice_from_str(const char *s) {
    return (intptr_t)s;
}

SYSCALL intptr_t _slice_from_list_data(void *list) {
    if (!list) return 0;
    return *(intptr_t*)((char*)list + 8);
}

SYSCALL int _slice_byte_at(const char *ptr, int len, int idx) {
    if (!ptr || idx < 0 || idx >= len) return -1;
    return (unsigned char)ptr[idx];
}

SYSCALL int _slice_eq(const char *p1, int l1, const char *p2, int l2) {
    if (l1 != l2) return 0;
    if (l1 == 0) return 1;
    if (p1 == p2) return 1;
    if (!p1 || !p2) return 0;
    for (int i = 0; i < l1; i++) {
        if (p1[i] != p2[i]) return 0;
    }
    return 1;
}

SYSCALL int _slice_cmp(const char *p1, int l1, const char *p2, int l2) {
    if (!p1 && !p2) return 0;
    if (!p1) return -1;
    if (!p2) return 1;
    int min_len = (l1 < l2) ? l1 : l2;
    for (int i = 0; i < min_len; i++) {
        unsigned char c1 = (unsigned char)p1[i];
        unsigned char c2 = (unsigned char)p2[i];
        if (c1 < c2) return -1;
        if (c1 > c2) return 1;
    }
    if (l1 < l2) return -1;
    if (l1 > l2) return 1;
    return 0;
}

SYSCALL int _slice_find(const char *haystack, int hlen, const char *needle, int nlen) {
    if (!haystack || !needle || nlen <= 0) return -1;
    if (nlen > hlen) return -1;
    int max_i = hlen - nlen;
    for (int i = 0; i <= max_i; i++) {
        int match = 1;
        for (int j = 0; j < nlen; j++) {
            if (haystack[i + j] != needle[j]) {
                match = 0;
                break;
            }
        }
        if (match) return i;
    }
    return -1;
}

SYSCALL char *_slice_to_str(const char *ptr, int len) {
    if (!ptr || len <= 0) return _str_empty;
#if defined(_WIN32)
    char *res = (char*)STR_PFX(malloc)(len + 1);
#else
    char *res = (char*)malloc(len + 1);
#endif
    if (!res) return 0;
    for (int i = 0; i < len; i++) {
        res[i] = ptr[i];
    }
    res[len] = '\0';
    return res;
}

/* ==================== Advanced C FFI Helpers ==================== */
SYSCALL intptr_t _ffi_open(const char *name) {
    if (!name || !*name) return 0;
#if defined(_WIN32)
    HMODULE h = LoadLibraryA(name);
    return (intptr_t)h;
#else
    void *h = dlopen(name, RTLD_LAZY | RTLD_GLOBAL);
    return (intptr_t)h;
#endif
}

SYSCALL intptr_t _ffi_sym(intptr_t handle, const char *name) {
    if (!handle || !name) return 0;
#if defined(_WIN32)
    FARPROC p = GetProcAddress((HMODULE)handle, name);
    return (intptr_t)p;
#else
    void *p = dlsym((void*)handle, name);
    return (intptr_t)p;
#endif
}

SYSCALL int _ffi_close(intptr_t handle) {
    if (!handle) return 0;
#if defined(_WIN32)
    return FreeLibrary((HMODULE)handle) ? 1 : 0;
#else
    return dlclose((void*)handle) == 0 ? 1 : 0;
#endif
}

SYSCALL intptr_t _ffi_call0(intptr_t fn) {
    if (!fn) return 0;
    typedef intptr_t (*c_fn0)(void);
    return ((c_fn0)fn)();
}

SYSCALL intptr_t _ffi_call1(intptr_t fn, intptr_t a1) {
    if (!fn) return 0;
    typedef intptr_t (*c_fn1)(intptr_t);
    return ((c_fn1)fn)(a1);
}

SYSCALL intptr_t _ffi_call2(intptr_t fn, intptr_t a1, intptr_t a2) {
    if (!fn) return 0;
    typedef intptr_t (*c_fn2)(intptr_t, intptr_t);
    return ((c_fn2)fn)(a1, a2);
}

SYSCALL intptr_t _ffi_call3(intptr_t fn, intptr_t a1, intptr_t a2, intptr_t a3) {
    if (!fn) return 0;
    typedef intptr_t (*c_fn3)(intptr_t, intptr_t, intptr_t);
    return ((c_fn3)fn)(a1, a2, a3);
}

SYSCALL intptr_t _ffi_call4(intptr_t fn, intptr_t a1, intptr_t a2, intptr_t a3, intptr_t a4) {
    if (!fn) return 0;
    typedef intptr_t (*c_fn4)(intptr_t, intptr_t, intptr_t, intptr_t);
    return ((c_fn4)fn)(a1, a2, a3, a4);
}

SYSCALL intptr_t _ffi_call5(intptr_t fn, intptr_t a1, intptr_t a2, intptr_t a3, intptr_t a4, intptr_t a5) {
    if (!fn) return 0;
    typedef intptr_t (*c_fn5)(intptr_t, intptr_t, intptr_t, intptr_t, intptr_t);
    return ((c_fn5)fn)(a1, a2, a3, a4, a5);
}

SYSCALL intptr_t _ffi_call6(intptr_t fn, intptr_t a1, intptr_t a2, intptr_t a3, intptr_t a4, intptr_t a5, intptr_t a6) {
    if (!fn) return 0;
    typedef intptr_t (*c_fn6)(intptr_t, intptr_t, intptr_t, intptr_t, intptr_t, intptr_t);
    return ((c_fn6)fn)(a1, a2, a3, a4, a5, a6);
}

/* ==================== List helpers ==================== */
SYSCALL void _list_insert(void *list, long long idx, long long val) {
    if (!list) return;
    int count = *(int*)list;
    int cap_bytes = *(int*)((char*)list + 4);
    void *data = *(void**)((char*)list + 8);
    if (idx < 0) idx = 0;
    if (idx > count) idx = count;
    int need = (count + 1) * (int)sizeof(intptr_t);
    if (need > cap_bytes) {
        int new_cap = cap_bytes * 2;
        if (new_cap < need) new_cap = need;
#if defined(_WIN32)
        void *nd = STR_PFX(realloc)(data, (unsigned int)new_cap);
#else
        void *nd = realloc(data, (size_t)new_cap);
#endif
        if (!nd) return;
        data = nd;
        *(void**)((char*)list + 8) = data;
        *(int*)((char*)list + 4) = new_cap;
    }
    intptr_t *arr = (intptr_t*)data;
    for (int i = count; i > idx; i--) arr[i] = arr[i - 1];
    arr[idx] = (intptr_t)val;
    *(int*)list = count + 1;
}

SYSCALL void _list_clear(void *list) {
    if (!list) return;
    *(int*)list = 0;
}

SYSCALL void _sys_awrite_c(long long fd, const char *str) {
    _sys_write_c(fd, str);
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

/* ==================== PRNG (xorshift64) ==================== */
static unsigned long long _rng_state = 0;
static int _rng_seeded = 0;

static unsigned long long _rng_next(void) {
    if (!_rng_seeded) {
        _rng_state = (unsigned long long)_sys_get_tick_count_c();
        if (_rng_state == 0) _rng_state = 88172645463325252ULL;
        _rng_seeded = 1;
    }
    unsigned long long x = _rng_state;
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    _rng_state = x;
    return x * 2685821657736338717ULL;
}

SYSCALL int _random(void) {
    return (int)(_rng_next() & 0x7fffffff);
}

SYSCALL int _random_range(int lo, int hi) {
    if (hi < lo) { int t = lo; lo = hi; hi = t; }
    unsigned long long r = _rng_next();
    unsigned long long range = (unsigned long long)(hi - lo + 1);
    return lo + (int)(r % range);
}

SYSCALL void _chacha20_init(int seed1, int seed2) {
    _rng_state = ((unsigned long long)(unsigned int)seed1 << 32) | (unsigned int)seed2;
    if (_rng_state == 0) _rng_state = 88172645463325252ULL;
    _rng_seeded = 1;
}

SYSCALL void *_api_open_internal(const char *url) {
    (void)url;
    return 0;
}

/* _call(name, args, num_args) — dynamic dispatch stub; native codegen never emits this */
SYSCALL long long _call(const char *name, long long *args, long long num_args) {
    (void)name; (void)args; (void)num_args;
    return 0;
}

/* ========================================================================= */
/* Native GUI & 2D Canvas Engine (Win32 GDI Double-Buffered)                 */
/* ========================================================================= */
#if defined(_WIN32)

/* DPI-aware rendering support */
#ifndef DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
#define DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 ((HANDLE)-4)
#endif
typedef BOOL (WINAPI *PFN_SetProcessDpiAwarenessContext)(HANDLE);
typedef UINT (WINAPI *PFN_GetDpiForWindow)(HWND);

static HWND   g_gui_hwnd          = NULL;
static HDC    g_gui_mem_dc        = NULL;
static HBITMAP g_gui_mem_bm       = NULL;
static HBITMAP g_gui_old_bm       = NULL;
static int    g_gui_win_w         = 0;  /* logical width  (Nova coordinate space) */
static int    g_gui_win_h         = 0;  /* logical height (Nova coordinate space) */
static int    g_gui_phys_w        = 0;  /* physical backbuffer width  (DPI-scaled) */
static int    g_gui_phys_h        = 0;  /* physical backbuffer height (DPI-scaled) */
static float  g_gui_dpi_scale     = 1.0f; /* physical / logical pixel ratio        */
static int    g_gui_mouse_x       = 0;
static int    g_gui_mouse_y       = 0;
static int    g_gui_mouse_down    = 0;
static int    g_gui_mouse_clicked = 0;
static int    g_gui_is_closed     = 0;

static void _gui_update_mouse_position(HWND hwnd) {
    POINT point;
    if (!GetCursorPos(&point) || !ScreenToClient(hwnd, &point)) return;
    g_gui_mouse_x = (int)(point.x / g_gui_dpi_scale);
    g_gui_mouse_y = (int)(point.y / g_gui_dpi_scale);
}

/* Rebuild the off-screen DC at the current physical pixel size */
static void _gui_rebuild_backbuffer(int phys_w, int phys_h) {
    if (phys_w <= 0 || phys_h <= 0) return;
    HDC screen_dc = GetDC(g_gui_hwnd);
    HBITMAP new_bm = CreateCompatibleBitmap(screen_dc, phys_w, phys_h);
    ReleaseDC(g_gui_hwnd, screen_dc);
    if (!new_bm) return;
    if (g_gui_mem_dc) {
        HBITMAP previous = (HBITMAP)SelectObject(g_gui_mem_dc, new_bm);
        if (!g_gui_old_bm) g_gui_old_bm = previous;
    }
    if (g_gui_mem_bm) DeleteObject(g_gui_mem_bm);
    g_gui_mem_bm  = new_bm;
    g_gui_phys_w  = phys_w;
    g_gui_phys_h  = phys_h;
    /* Enable GDI font smoothing on this DC */
    SetStretchBltMode(g_gui_mem_dc, HALFTONE);
}

/* Auto-incrementing click ID — lets Nova's new btn() API avoid manual integer IDs */
static int g_gui_next_click_id = 0;
SYSCALL int STR_PFX(gui_next_click_id)(void) {
    g_gui_next_click_id += 1;
    return g_gui_next_click_id;
}

/* Keyboard FIFO Queue */
#define GUI_KEY_QUEUE_SIZE 64
static int g_gui_key_queue[GUI_KEY_QUEUE_SIZE];
static int g_gui_key_head = 0;
static int g_gui_key_tail = 0;

static void _gui_push_key(int key) {
    int next = (g_gui_key_head + 1) % GUI_KEY_QUEUE_SIZE;
    if (next != g_gui_key_tail) {
        g_gui_key_queue[g_gui_key_head] = key;
        g_gui_key_head = next;
    }
}

SYSCALL int STR_PFX(gui_poll_char)(void) {
    if (g_gui_key_head == g_gui_key_tail) return 0;
    int k = g_gui_key_queue[g_gui_key_tail];
    g_gui_key_tail = (g_gui_key_tail + 1) % GUI_KEY_QUEUE_SIZE;
    return k;
}

SYSCALL const char *STR_PFX(gui_char_to_str)(int c) {
    if (c <= 0) return _str_empty;
#if defined(_WIN32)
    char *res = (char*)STR_PFX(malloc)(2);
#else
    char *res = (char*)malloc(2);
#endif
    if (!res) return _str_empty;
    res[0] = (char)c;
    res[1] = '\0';
    return res;
}

static LRESULT CALLBACK _NovaWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {
        case WM_MOUSEMOVE:
            /* lParam is in physical pixels when DPI-aware; convert to logical so
               Nova's hit-test (which uses logical widget bounds) stays in sync. */
            g_gui_mouse_x = (int)((short)LOWORD(lParam) / g_gui_dpi_scale);
            g_gui_mouse_y = (int)((short)HIWORD(lParam) / g_gui_dpi_scale);
            return 0;
        case WM_LBUTTONDOWN:
            _gui_update_mouse_position(hwnd);
            g_gui_mouse_down = 1;
            return 0;
        case WM_LBUTTONUP:
            _gui_update_mouse_position(hwnd);
            g_gui_mouse_down = 0;
            g_gui_mouse_clicked = 1;
            return 0;
        case WM_CHAR: {
            int ch = (int)wParam;
            if (ch > 0) {
                _gui_push_key(ch);
            }
            return 0;
        }
        case WM_KEYDOWN: {
            int vk = (int)wParam;
            if (vk == VK_DELETE) {
                _gui_push_key(127);
            } else if (vk == VK_LEFT) {
                _gui_push_key(1001);
            } else if (vk == VK_RIGHT) {
                _gui_push_key(1002);
            }
            break;
        }
        case WM_PAINT: {
            PAINTSTRUCT ps;
            HDC hdc = BeginPaint(hwnd, &ps);
            if (g_gui_mem_dc && g_gui_phys_w > 0) {
                /* Blit the full-resolution backbuffer directly — no stretch needed
                   because the window client area is already the physical pixel size. */
                BitBlt(hdc, 0, 0, g_gui_phys_w, g_gui_phys_h,
                       g_gui_mem_dc, 0, 0, SRCCOPY);
            }
            EndPaint(hwnd, &ps);
            return 0;
        }
        case WM_SIZE: {
            /* lParam carries physical pixel size when DPI-aware */
            int new_phys_w = LOWORD(lParam);
            int new_phys_h = HIWORD(lParam);
            if (new_phys_w > 0 && new_phys_h > 0) {
                g_gui_win_w = (int)(new_phys_w / g_gui_dpi_scale);
                g_gui_win_h = (int)(new_phys_h / g_gui_dpi_scale);
                if (g_gui_mem_dc)
                    _gui_rebuild_backbuffer(new_phys_w, new_phys_h);
            }
            return 0;
        }
        case WM_DPICHANGED: {
            /* Monitor DPI changed (user moved window / display settings changed) */
            UINT new_dpi = HIWORD(wParam);
            g_gui_dpi_scale = new_dpi / 96.0f;
            RECT *r = (RECT *)lParam;
            SetWindowPos(hwnd, NULL,
                r->left, r->top,
                r->right - r->left, r->bottom - r->top,
                SWP_NOZORDER | SWP_NOACTIVATE);
            return 0;
        }
        case WM_ERASEBKGND:
            return 1;
        case WM_DESTROY:
            g_gui_is_closed = 1;
            PostQuitMessage(0);
            return 0;
    }
    return DefWindowProcA(hwnd, msg, wParam, lParam);
}

static COLORREF _hex_to_rgb(int hex) {
    int r = (hex >> 16) & 0xFF;
    int g = (hex >> 8) & 0xFF;
    int b = hex & 0xFF;
    return RGB(r, g, b);
}

SYSCALL int STR_PFX(gui_init_window)(const char *title, int width, int height) {
    /* --- Step 1: Enable Per-Monitor DPI Awareness v2 (Windows 10 1703+) ---
       This must happen before any HWND or metric query. We load dynamically
       so the binary still runs on older Windows without a hard import error. */
    {
        HMODULE hUser = GetModuleHandleA("user32.dll");
        if (hUser) {
            PFN_SetProcessDpiAwarenessContext fn =
                (PFN_SetProcessDpiAwarenessContext)
                GetProcAddress(hUser, "SetProcessDpiAwarenessContext");
            if (fn) fn(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
        }
    }

    HINSTANCE hInstance = GetModuleHandleA(NULL);
    WNDCLASSEXA wc;
    memset(&wc, 0, sizeof(wc));
    wc.cbSize        = sizeof(WNDCLASSEXA);
    wc.style         = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc   = _NovaWndProc;
    wc.hInstance     = hInstance;
    wc.hCursor       = LoadCursorA(NULL, (LPCSTR)IDC_ARROW);
    wc.lpszClassName = "NovaWindowClass";
    RegisterClassExA(&wc);

    /* --- Step 2: Detect DPI of the primary monitor --- */
    HDC ref_dc = GetDC(NULL);
    int raw_dpi = GetDeviceCaps(ref_dc, LOGPIXELSX);
    ReleaseDC(NULL, ref_dc);
    if (raw_dpi < 96) raw_dpi = 96;
    g_gui_dpi_scale = raw_dpi / 96.0f;

    /* --- Step 3: Compute physical pixel dimensions --- */
    int phys_w = (int)(width  * g_gui_dpi_scale);
    int phys_h = (int)(height * g_gui_dpi_scale);

    g_gui_win_w         = width;   /* logical */
    g_gui_win_h         = height;  /* logical */
    g_gui_is_closed     = 0;
    g_gui_mouse_clicked = 0;
    g_gui_mouse_down    = 0;
    g_gui_old_bm        = NULL;

    /* --- Step 4: Size the OS window at physical pixels --- */
    RECT rc = {0, 0, phys_w, phys_h};
    AdjustWindowRect(&rc, WS_OVERLAPPEDWINDOW, FALSE);
    int frame_w = rc.right  - rc.left;
    int frame_h = rc.bottom - rc.top;

    int screen_w = GetSystemMetrics(SM_CXSCREEN);
    int screen_h = GetSystemMetrics(SM_CYSCREEN);
    int posX = (screen_w - frame_w) / 2;
    int posY = (screen_h - frame_h) / 2;
    if (posX < 0) posX = 0;
    if (posY < 0) posY = 0;

    g_gui_hwnd = CreateWindowExA(
        0,
        "NovaWindowClass",
        title ? title : "Nova Application",
        WS_OVERLAPPEDWINDOW,
        posX, posY, frame_w, frame_h,
        NULL, NULL, hInstance, NULL
    );
    if (!g_gui_hwnd) return 0;

    /* --- Step 5: Create off-screen DC at the physical resolution --- */
    g_gui_mem_dc  = CreateCompatibleDC(NULL);
    if (!g_gui_mem_dc) {
        DestroyWindow(g_gui_hwnd);
        g_gui_hwnd = NULL;
        return 0;
    }
    _gui_rebuild_backbuffer(phys_w, phys_h);
    if (!g_gui_mem_bm) {
        DeleteDC(g_gui_mem_dc);
        g_gui_mem_dc = NULL;
        DestroyWindow(g_gui_hwnd);
        g_gui_hwnd = NULL;
        return 0;
    }

    /* Enable ClearType-quality text on the memory DC */
    UINT ct_flags = FE_FONTSMOOTHINGCLEARTYPE;
    SystemParametersInfoA(SPI_SETFONTSMOOTHING,    TRUE,  NULL, 0);
    SystemParametersInfoA(SPI_SETFONTSMOOTHINGTYPE, 0, (PVOID)(ULONG_PTR)ct_flags, 0);

    ShowWindow(g_gui_hwnd, SW_SHOW);
    UpdateWindow(g_gui_hwnd);
    return 1;
}

SYSCALL int STR_PFX(gui_poll_events)(void) {
    if (g_gui_is_closed || !g_gui_hwnd) return -1;
    g_gui_mouse_clicked = 0;

    MSG msg;
    while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE)) {
        if (msg.message == WM_QUIT) {
            g_gui_is_closed = 1;
            return -1;
        }
        TranslateMessage(&msg);
        DispatchMessageA(&msg);
    }
    if (g_gui_is_closed) return -1;
    return g_gui_mouse_clicked ? 2 : 1;
}

SYSCALL int STR_PFX(gui_get_mouse_x)(void) { return g_gui_mouse_x; }
SYSCALL int STR_PFX(gui_get_mouse_y)(void) { return g_gui_mouse_y; }
SYSCALL int STR_PFX(gui_get_mouse_down)(void) { return g_gui_mouse_down; }
SYSCALL int STR_PFX(gui_get_mouse_clicked)(void) { return g_gui_mouse_clicked; }

SYSCALL void STR_PFX(gui_clear)(int color_hex) {
    if (!g_gui_mem_dc) return;
    /* Clear at physical resolution */
    RECT r = {0, 0, g_gui_phys_w, g_gui_phys_h};
    HBRUSH br = CreateSolidBrush(_hex_to_rgb(color_hex));
    FillRect(g_gui_mem_dc, &r, br);
    DeleteObject(br);
}

SYSCALL void STR_PFX(gui_draw_rect)(int x, int y, int w, int h, int color_hex, int radius) {
    if (!g_gui_mem_dc) return;
    /* Scale logical coords → physical pixels */
    int px = (int)(x * g_gui_dpi_scale);
    int py = (int)(y * g_gui_dpi_scale);
    int pw = (int)(w * g_gui_dpi_scale);
    int ph = (int)(h * g_gui_dpi_scale);
    int pr = (int)(radius * g_gui_dpi_scale);
    if (pw <= 0 || ph <= 0) return;
    if (pr <= 0) {
        RECT r = {px, py, px + pw, py + ph};
        HBRUSH br = CreateSolidBrush(_hex_to_rgb(color_hex));
        FillRect(g_gui_mem_dc, &r, br);
        DeleteObject(br);
    } else {
        HBRUSH br  = CreateSolidBrush(_hex_to_rgb(color_hex));
        HPEN   pen = CreatePen(PS_NULL, 0, 0);
        HGDIOBJ old_br  = SelectObject(g_gui_mem_dc, br);
        HGDIOBJ old_pen = SelectObject(g_gui_mem_dc, pen);
        RoundRect(g_gui_mem_dc, px, py, px + pw, py + ph, pr * 2, pr * 2);
        SelectObject(g_gui_mem_dc, old_br);
        SelectObject(g_gui_mem_dc, old_pen);
        DeleteObject(br);
        DeleteObject(pen);
    }
}

SYSCALL void STR_PFX(gui_draw_border)(int x, int y, int w, int h, int border_w, int color_hex) {
    if (!g_gui_mem_dc) return;
    int px = (int)(x * g_gui_dpi_scale);
    int py = (int)(y * g_gui_dpi_scale);
    int pw = (int)(w * g_gui_dpi_scale);
    int ph = (int)(h * g_gui_dpi_scale);
    int pbw = (int)(border_w * g_gui_dpi_scale); if (pbw < 1) pbw = 1;
    HPEN    pen    = CreatePen(PS_SOLID, pbw, _hex_to_rgb(color_hex));
    HGDIOBJ old_pen = SelectObject(g_gui_mem_dc, pen);
    HGDIOBJ old_br  = SelectObject(g_gui_mem_dc, GetStockObject(NULL_BRUSH));
    Rectangle(g_gui_mem_dc, px, py, px + pw, py + ph);
    SelectObject(g_gui_mem_dc, old_pen);
    SelectObject(g_gui_mem_dc, old_br);
    DeleteObject(pen);
}

SYSCALL void STR_PFX(gui_draw_text)(const char *text, int x, int y, int font_size, int color_hex, int font_weight) {
    if (!g_gui_mem_dc || !text) return;
    /* Scale logical → physical */
    int px        = (int)(x         * g_gui_dpi_scale);
    int py        = (int)(y         * g_gui_dpi_scale);
    int phys_size = (int)(font_size * g_gui_dpi_scale);
    if (phys_size < 1) phys_size = 1;

    SetBkMode(g_gui_mem_dc, TRANSPARENT);
    SetTextColor(g_gui_mem_dc, _hex_to_rgb(color_hex));

    int weight = (font_weight > 0) ? FW_BOLD : FW_NORMAL;
    HFONT font = CreateFontA(
        -phys_size, 0, 0, 0,
        weight, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_TT_PRECIS,
        CLIP_DEFAULT_PRECIS, CLEARTYPE_NATURAL_QUALITY,
        DEFAULT_PITCH | FF_DONTCARE,
        "Segoe UI"
    );

    HGDIOBJ old_font = SelectObject(g_gui_mem_dc, font);
    RECT rc = {px, py, g_gui_phys_w, g_gui_phys_h};
    DrawTextA(g_gui_mem_dc, text, -1, &rc, DT_LEFT | DT_TOP | DT_NOCLIP | DT_NOPREFIX);
    SelectObject(g_gui_mem_dc, old_font);
    DeleteObject(font);
}

SYSCALL void STR_PFX(gui_present)(void) {
    if (!g_gui_hwnd || !g_gui_mem_dc || g_gui_phys_w <= 0) return;
    HDC screen_dc = GetDC(g_gui_hwnd);
    /* Direct 1:1 copy — no scaling, we drew at native resolution */
    BitBlt(screen_dc, 0, 0, g_gui_phys_w, g_gui_phys_h,
           g_gui_mem_dc, 0, 0, SRCCOPY);
    ReleaseDC(g_gui_hwnd, screen_dc);
}

SYSCALL void STR_PFX(gui_sleep)(int ms) {
    Sleep(ms);
}

SYSCALL int STR_PFX(gui_save_screenshot)(const char *path) {
    if (!g_gui_mem_dc || !g_gui_mem_bm || !path) return 0;
    int w = g_gui_win_w;
    int h = g_gui_win_h;

    BITMAPINFO bi;
    memset(&bi, 0, sizeof(bi));
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = w;
    bi.bmiHeader.biHeight = -h;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;

    int data_size = w * 4 * h;
    void *pixels = STR_PFX(malloc)(data_size);
    if (!pixels) return 0;

    GetDIBits(g_gui_mem_dc, g_gui_mem_bm, 0, h, pixels, &bi, DIB_RGB_COLORS);

    BITMAPFILEHEADER bfh;
    memset(&bfh, 0, sizeof(bfh));
    bfh.bfType = 0x4D42;
    bfh.bfOffBits = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER);
    bfh.bfSize = bfh.bfOffBits + data_size;

    HANDLE hFile = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hFile == INVALID_HANDLE_VALUE) {
        STR_PFX(free)(pixels);
        return 0;
    }

    DWORD written = 0;
    WriteFile(hFile, &bfh, sizeof(bfh), &written, NULL);
    WriteFile(hFile, &bi.bmiHeader, sizeof(BITMAPINFOHEADER), &written, NULL);
    WriteFile(hFile, pixels, data_size, &written, NULL);
    CloseHandle(hFile);

    STR_PFX(free)(pixels);
    return 1;
}

SYSCALL int STR_PFX(gui_get_window_w)(void) {
    return g_gui_win_w;
}

SYSCALL int STR_PFX(gui_get_window_h)(void) {
    return g_gui_win_h;
}

SYSCALL void STR_PFX(gui_close)(void) {
    if (g_gui_mem_dc && g_gui_old_bm) {
        SelectObject(g_gui_mem_dc, g_gui_old_bm);
    }
    if (g_gui_mem_bm) {
        DeleteObject(g_gui_mem_bm);
        g_gui_mem_bm = NULL;
    }
    if (g_gui_mem_dc) {
        DeleteDC(g_gui_mem_dc);
        g_gui_mem_dc = NULL;
    }
    if (g_gui_hwnd) {
        DestroyWindow(g_gui_hwnd);
        g_gui_hwnd = NULL;
    }
    g_gui_old_bm = NULL;
    g_gui_is_closed = 1;
}

#else
/* Non-Windows stubs */
SYSCALL int STR_PFX(gui_init_window)(const char *title, int width, int height) { (void)title; (void)width; (void)height; return 0; }
SYSCALL int STR_PFX(gui_poll_events)(void) { return -1; }
SYSCALL int STR_PFX(gui_get_mouse_x)(void) { return 0; }
SYSCALL int STR_PFX(gui_get_mouse_y)(void) { return 0; }
SYSCALL int STR_PFX(gui_get_mouse_down)(void) { return 0; }
SYSCALL int STR_PFX(gui_get_mouse_clicked)(void) { return 0; }
SYSCALL int STR_PFX(gui_get_window_w)(void) { return 0; }
SYSCALL int STR_PFX(gui_get_window_h)(void) { return 0; }
SYSCALL void STR_PFX(gui_clear)(int color_hex) { (void)color_hex; }
SYSCALL void STR_PFX(gui_draw_rect)(int x, int y, int w, int h, int color_hex, int radius) { (void)x; (void)y; (void)w; (void)h; (void)color_hex; (void)radius; }
SYSCALL void STR_PFX(gui_draw_border)(int x, int y, int w, int h, int border_w, int color_hex) { (void)x; (void)y; (void)w; (void)h; (void)border_w; (void)color_hex; }
SYSCALL void STR_PFX(gui_draw_text)(const char *text, int x, int y, int font_size, int color_hex, int font_weight) { (void)text; (void)x; (void)y; (void)font_size; (void)color_hex; (void)font_weight; }
SYSCALL void STR_PFX(gui_present)(void) {}
SYSCALL void STR_PFX(gui_sleep)(int ms) { (void)ms; }
SYSCALL int STR_PFX(gui_save_screenshot)(const char *path) { (void)path; return 0; }
SYSCALL void STR_PFX(gui_close)(void) {}
SYSCALL int STR_PFX(gui_poll_char)(void) { return 0; }
SYSCALL const char *STR_PFX(gui_char_to_str)(int c) { (void)c; return ""; }
#endif
