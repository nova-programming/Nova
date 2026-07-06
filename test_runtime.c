#include <stdio.h>

extern int _strcmp(const char *a, const char *b);
extern void _main(void);

int main() {
    printf("Before _main call\n");
    int r = _strcmp("a", "p");
    printf("_strcmp(\"a\", \"p\") = %d\n", r);
    printf("Calling _main...\n");
    _main();
    printf("After _main\n");
    return 0;
}
