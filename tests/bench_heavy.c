#include <stdio.h>
#include <time.h>

int sum_to(int n) {
    int s = 0;
    for (int i = 0; i <= n; i++) s += i;
    return s;
}

int is_prime(int n) {
    if (n < 2) return 0;
    for (int i = 2; i * i <= n; i++)
        if (n % i == 0) return 0;
    return 1;
}

int count_primes(int limit) {
    int count = 0;
    for (int i = 2; i <= limit; i++)
        if (is_prime(i)) count++;
    return count;
}

int fib(int n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}

int main() {
    clock_t start, end;
    start = clock();
    int r1 = sum_to(10000000);
    int r2 = count_primes(50000);
    int r3 = fib(35);
    end = clock();
    printf("%d\n%d\n%d\n", r1, r2, r3);
    printf("Time: %.3f ms\n", 1000.0 * (end - start) / CLOCKS_PER_SEC);
    return 0;
}
