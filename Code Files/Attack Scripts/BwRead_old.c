#include<stdio.h>
#define mem_size 1024*1024
int main()
{
	char read_arr[mem_size];
	long long int var=0;
	for(int i=0;i<mem_size;i++)
	{
		var=read_arr[i];
		//printf("%c:%d\n",read_arr[i],i+1);
	}
	return 0;
}
