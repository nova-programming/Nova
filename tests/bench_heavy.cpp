#include <iostream>
#include <chrono>

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
    auto start = std::chrono::high_resolution_clock::now();
    int r1 = sum_to(10000000);
    int r2 = count_primes(50000);
    int r3 = fib(35);
    auto end = std::chrono::high_resolution_clock::now();
    auto ms = std::chrono::duration_cast<std::chrono::microseconds>(end - start).count() / 1000.0;
    std::cout << r1 << std::endl << r2 << std::endl << r3 << std::endl;
    std::cout << "Time: " << ms << " ms" << std::endl;
    return 0;
}
