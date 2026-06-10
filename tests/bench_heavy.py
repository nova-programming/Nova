import time

def sum_to(n):
    s = 0
    for i in range(n + 1):
        s += i
    return s

def is_prime(n):
    if n < 2:
        return 0
    i = 2
    while i * i <= n:
        if n % i == 0:
            return 0
        i += 1
    return 1

def count_primes(limit):
    count = 0
    for i in range(2, limit + 1):
        if is_prime(i):
            count += 1
    return count

def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)

start = time.time()
r1 = sum_to(10000000)
r2 = count_primes(50000)
r3 = fib(35)
end = time.time()
print(r1)
print(r2)
print(r3)
print(f"Time: {(end - start) * 1000:.1f} ms")
