#include <stdio.h>
static int is_prime(long long n){ if(n<2) return 0; for(long long i=2;i*i<=n;i++) if(n%i==0) return 0; return 1; }
int main(){ long long c=0; for(long long n=0;n<300000;n++) c+=is_prime(n); printf("%lld\n", c); return 0; }
