#include <windows.h>
#include <stdio.h>
int main() {
    printf("lstrcmpA(\"a\", \"p\") = %d\n", lstrcmpA("a", "p"));
    printf("lstrcmpA(\"p\", \"z\") = %d\n", lstrcmpA("p", "z"));
    printf("lstrcmpA(\"A\", \"p\") = %d\n", lstrcmpA("A", "p"));
    printf("lstrcmpA(\"p\", \"Z\") = %d\n", lstrcmpA("p", "Z"));
    printf("lstrcmpA(\"a\", \"A\") = %d\n", lstrcmpA("a", "A"));
    printf("strcmp(\"a\", \"p\") = %d\n", strcmp("a", "p"));
    return 0;
}
