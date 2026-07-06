#include <windows.h>
#include <stdio.h>
int main() {
    char a[] = "a";
    char r[] = "r";
    char p[] = "p";
    printf("lstrcmpA(\"a\", \"p\") = %d\n", lstrcmpA(a, p));
    printf("lstrcmpA(\"a\", \"r\") = %d\n", lstrcmpA(a, r));
    printf("lstrcmpA(\"p\", \"z\") = %d\n", lstrcmpA(p, "z"));
    printf("lstrcmpA(\"r\", \"z\") = %d\n", lstrcmpA(r, "z"));
    printf("Done!\n");
    return 0;
}
