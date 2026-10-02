#include <stdio.h>
static long long steps(long long n){ long long c=0; while(n!=1){ if(n%2==0) n/=2; else n=n*3+1; c++; } return c; }
int main(){ long long best=0,bn=0; for(long long n=1;n<400000;n++){ long long s=steps(n); if(s>best){best=s;bn=n;} } printf("%lld\n%lld\n", bn, best); return 0; }
