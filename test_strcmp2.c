#include <windows.h>
#include <stdio.h>
int main() {
    printf("lstrcmpA(\"a\", \"(\") = %d\n", lstrcmpA("a", "("));
    printf("lstrcmpA(\"(\", \"z\") = %d\n", lstrcmpA("(", "z"));
    printf("lstrcmpA(\"a\", \")\") = %d\n", lstrcmpA("a", ")"));
    printf("lstrcmpA(\"(\", \")\") = %d\n", lstrcmpA("(", ")"));
    printf("lstrcmpA(\"(\", \"A\") = %d\n", lstrcmpA("(", "A"));
    printf("lstrcmpA(\"(\", \"0\") = %d\n", lstrcmpA("(", "0"));
    printf("lstrcmpA(\" \", \"a\") = %d\n", lstrcmpA(" ", "a"));
    printf("lstrcmpA(\"a\", \"a\") = %d\n", lstrcmpA("a", "a"));
    printf("lstrcmpA(\"a\", \"b\") = %d\n", lstrcmpA("a", "b"));
    printf("lstrcmpA(\"b\", \"a\") = %d\n", lstrcmpA("b", "a"));
    return 0;
}
