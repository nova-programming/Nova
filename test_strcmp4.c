#include <stdio.h>
#include <windows.h>

/* Copy of the exact _strcmp from runtime.c */
int _strcmp(const char *a, const char *b) {
    return lstrcmpA(a, b);
}

int main() {
    int r1 = _strcmp("a", "p");
    int r2 = _strcmp("a", "a");
    printf("_strcmp(\"a\", \"p\") = %d\n", r1);
    printf("_strcmp(\"a\", \"a\") = %d\n", r2);
    printf("_strcmp(\"a\", \"p\") <= 0 = %d\n", r1 <= 0);
    return 0;
}
