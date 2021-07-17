#include<stdio.h>
#define mem_size 1024*1024
int main()
{
	char ch='a';
	char read_arr[mem_size];
	for(int i=0;i<mem_size;i++)
	{
		read_arr[i]=ch;
		//printf("%c:%d\n",ch,i+1);
	}
	return 0;
}
