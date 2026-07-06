#include <stdio.h>
int _strcmp(const char *a, const char *b);
int main() {
    int r = _strcmp("a", "p");
    printf("_strcmp(\"a\", \"p\") = %d\n", r);
    printf("_strcmp(\"a\", \"p\") <= 0 = %d\n", r <= 0);
    return 0;
}
