#include <stdio.h>
long long fib(long long n){ return n<=1?n:fib(n-1)+fib(n-2);} 
int main(){ printf("%lld\n", fib(36)); return 0; }
