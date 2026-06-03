#include <stdio.h>
#include <windows.h>

int fib(int n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}

int sum_to(int n) {
    int s = 0, i = 0;
    while (i <= n) {
        s += i;
        i++;
    }
    return s;
}

int is_prime(int n) {
    if (n < 2) return 0;
    int i = 2;
    while (i * i <= n) {
        if (n % i == 0) return 0;
        i++;
    }
    return 1;
}

int count_primes(int limit) {
    int count = 0, i = 2;
    while (i <= limit) {
        if (is_prime(i) == 1) count++;
        i++;
    }
    return count;
}

int main() {
    DWORD t0, t1;
    
    printf("[1] fib(35)...\n");
    t0 = GetTickCount();
    int r = fib(35);
    t1 = GetTickCount();
    printf("    result = %d\n    time   = %d ms\n\n", r, t1 - t0);
    
    printf("[2] sum_to(10,000,000)...\n");
    t0 = GetTickCount();
    r = sum_to(10000000);
    t1 = GetTickCount();
    printf("    result = %d\n    time   = %d ms\n\n", r, t1 - t0);
    
    printf("[3] count_primes(50,000)...\n");
    t0 = GetTickCount();
    r = count_primes(50000);
    t1 = GetTickCount();
    printf("    result = %d\n    time   = %d ms\n\n", r, t1 - t0);
    
    printf("[4] sum_to(100,000,000)...\n");
    t0 = GetTickCount();
    r = sum_to(100000000);
    t1 = GetTickCount();
    printf("    result = %d\n    time   = %d ms\n\n", r, t1 - t0);
    
    return 0;
}
