#include <windows.h>
#include <stdio.h>
int main() {
    const char *a = "a";
    const char *b = "p";
    int r = lstrcmpA(a, b);
    printf("a='%s' b='%s' lstrcmpA=%d <=0=%d\n", a, b, r, r <= 0);
    
    a = "p"; b = "z";
    r = lstrcmpA(a, b);
    printf("a='%s' b='%s' lstrcmpA=%d <=0=%d\n", a, b, r, r <= 0);
    return 0;
}
