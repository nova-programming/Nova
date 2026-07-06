#include <windows.h>
#include <stdio.h>

__attribute__((sysv_abi)) int test_sysv(int a, int b, int c, int d) {
    return a + b + c + d;
}

int test_ms(int a, int b, int c, int d) {
    return a + b + c + d;
}

int main() {
    int r1 = test_sysv(1, 2, 3, 4);
    int r2 = test_ms(1, 2, 3, 4);
    printf("sysv=%d ms=%d\n", r1, r2);
    return 0;
}
