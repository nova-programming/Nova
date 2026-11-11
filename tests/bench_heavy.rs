use std::time::Instant;

fn sum_to(n: i64) -> i64 {
    let mut s: i64 = 0;
    let mut i: i64 = 0;
    while i <= n {
        s += i;
        i += 1;
    }
    s
}

fn is_prime(n: i64) -> bool {
    if n < 2 {
        return false;
    }
    let mut i: i64 = 2;
    while i * i <= n {
        if n % i == 0 {
            return false;
        }
        i += 1;
    }
    true
}

fn count_primes(limit: i64) -> i64 {
    let mut count: i64 = 0;
    let mut i: i64 = 2;
    while i <= limit {
        if is_prime(i) {
            count += 1;
        }
        i += 1;
    }
    count
}

fn fib(n: i64) -> i64 {
    if n <= 1 {
        return n;
    }
    fib(n - 1) + fib(n - 2)
}

fn main() {
    let start = Instant::now();
    let r1 = sum_to(10_000_000);
    let r2 = count_primes(50_000);
    let r3 = fib(35);
    let duration = start.elapsed();

    println!("{}\n{}\n{}", r1, r2, r3);
    println!("Time: {:.3} ms", duration.as_secs_f64() * 1000.0);
}

