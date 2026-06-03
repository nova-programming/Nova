#include <stdio.h>
#include <time.h>

long long sum_to(long long n) {
    long long s = 0;
    long long i = 0;
    while (i <= n) {
        s = s + i;
        i = i + 1;
    }
    return s;
}

int is_prime(long long n) {
    if (n < 2) return 0;
    long long i = 2;
    while (i * i <= n) {
        if (n % i == 0) return 0;
        i = i + 1;
    }
    return 1;
}

long long count_primes(long long limit) {
    long long count = 0;
    long long i = 2;
    while (i <= limit) {
        if (is_prime(i) == 1) count = count + 1;
        i = i + 1;
    }
    return count;
}

long long fib(long long n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}

int main() {
    clock_t start = clock();
    
    printf("%lld\n", sum_to(10000000));
    printf("%lld\n", count_primes(50000));
    printf("%lld\n", fib(35));
    
    clock_t end = clock();
    double time_spent = (double)(end - start) / CLOCKS_PER_SEC;
    printf("Time elapsed: %f seconds\n", time_spent);
    return 0;
}
