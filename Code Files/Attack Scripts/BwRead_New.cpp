#include<stdio.h>
#include<vector>
#define mem_size 8*1024*1024
#define ll long long
using namespace std;
int main()
{
	//char read_arr[mem_size];
	vector<char> c(mem_size,'A');
	ll x=65;
	ll b=0;
	for(ll i=0;i<mem_size;i+=64LL)
	{
		b+=((c[i]%26)+x)%100;
	}
	return 0;
}
