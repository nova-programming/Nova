#include <stdio.h>
int main(){ long long s=0; for(long long i=0;i<60000000;i++){ s=(s+i*3+(i%7))%1000003; } printf("%lld\n", s); return 0; }
