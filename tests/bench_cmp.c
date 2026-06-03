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

float float_chain(int n) {
    float x = 0.0f;
    int i = 0;
    while (i < n) {
        x = x + 3.14159f;
        x = x * 0.9999f;
        i++;
    }
    return x;
}

int main() {
    DWORD t0, t1;
    
    printf("========================================\n");
    printf("  C Benchmark Suite v2.0\n");
    printf("========================================\n\n");
    
    printf("[1] Fibonacci(35)...\n");
    t0 = GetTickCount();
    int r = fib(35);
    t1 = GetTickCount();
    printf("    result = %d\n", r);
    printf("    time   = %d ms\n\n", t1 - t0);
    
    printf("[2] Sum 1..1,000,000...\n");
    t0 = GetTickCount();
    r = sum_to(1000000);
    t1 = GetTickCount();
    printf("    result = %d\n", r);
    printf("    time   = %d ms\n\n", t1 - t0);
    
    printf("[3] Count primes up to 10,000...\n");
    t0 = GetTickCount();
    r = count_primes(10000);
    t1 = GetTickCount();
    printf("    result = %d\n", r);
    printf("    time   = %d ms\n\n", t1 - t0);
    
    printf("[4] Float chain 100,000x...\n");
    t0 = GetTickCount();
    float fr = float_chain(100000);
    t1 = GetTickCount();
    printf("    result = %d\n", (int)fr);
    printf("    time   = %d ms\n\n", t1 - t0);
    
    printf("[5] Sum 1..10,000,000 (heavy)...\n");
    t0 = GetTickCount();
    r = sum_to(10000000);
    t1 = GetTickCount();
    printf("    result = %d\n", r);
    printf("    time   = %d ms\n\n", t1 - t0);
    
    printf("[6] Count primes up to 50,000 (heavy)...\n");
    t0 = GetTickCount();
    r = count_primes(50000);
    t1 = GetTickCount();
    printf("    result = %d\n", r);
    printf("    time   = %d ms\n\n", t1 - t0);
    
    printf("========================================\n");
    printf("  Benchmark Complete\n");
    printf("========================================\n");
    
    return 0;
}
