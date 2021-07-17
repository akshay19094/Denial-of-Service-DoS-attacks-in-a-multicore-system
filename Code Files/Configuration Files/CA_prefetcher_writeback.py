import m5
from m5.objects import *
from m5.util import addToPath
import os
import argparse
import shlex

m5.util.addToPath('../..')

from common import ObjectList
from common.cores.arm import HPI

class L1Cache(Cache):
    size = '32kB'
    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20

class L1I(L1Cache):
    	#prefetcher = StridePrefetcher
	mshrs=1
	write_buffers = 1
	assoc = 2
	pass

    #is_read_only = True
    #writeback_clean = True

class L1D(L1Cache):
	assoc = 4
	mshrs = 3
	write_buffers = 3
	prefetcher = StridePrefetcher
	prefetch_on_access = True	
	prefetcher.degree = 5
	prefetcher.queue_size = 5
#	degree = 5
#	queue_size = 5
	pass

class L2Cache(Cache):
	size = '512kB'
	assoc = 16
	tag_latency = 12
	data_latency = 12
	response_latency = 12
	mshrs = 24
	tgts_per_mshr = 12
    	write_buffers = 8
	prefetcher = StridePrefetcher
	prefetch_on_access = True
	prefetcher.degree = 8
	prefetcher.queue_size = 8
#	degree = 8
#	queue_size = 8

cpu_types = {
    "atomic" : ( AtomicSimpleCPU, None, None, None),
    "minor" : (MinorCPU, L1I, L1D, L2Cache),
    "hpi" : ( HPI.HPI, L1I, L1D, L2Cache)
}

class CpuCluster(SubSystem):
	def __init__(self,system,num_cpus, cpu_clock, cpu_voltage,cpu_type,l1i_type,l1d_type,l2_type):
		super(CpuCluster, self).__init__()

		self._cpu_type = cpu_type
		self._l1i_type = l1i_type
		self._l1d_type = l1d_type
		self._l2_type = l2_type

		assert num_cpus > 0

		self.voltage_domain = VoltageDomain(voltage=cpu_voltage)
		self.clk_domain = SrcClockDomain(clock=cpu_clock, voltage_domain=self.voltage_domain)

		self.cpus = [self._cpu_type(cpu_id=system.numCpus()+idx, clk_domain=self.clk_domain) for idx in range(num_cpus)]

		for cpu in self.cpus:
			cpu.createThreads()
			cpu.createInterruptController()
			cpu.socket_id = system.numCpuClusters()
		system.addCpuCluster(self,num_cpus)

	def memoryMode(self):
		return self._cpu_type.memory_mode()

	def addL1(self):
		for cpu in self.cpus:
		    l1i = None if self._l1i_type is None else self._l1i_type()
		    l1d = None if self._l1d_type is None else self._l1d_type()
		    cpu.addPrivateSplitL1Caches(l1i, l1d, None, None)

	def addL2(self, clk_domain):
		if self._l2_type is None:
			return
		self.toL2Bus = L2XBar(width=64, clk_domain=clk_domain)
		self.l2 = self._l2_type()
		for cpu in self.cpus:
			cpu.connectAllPorts(self.toL2Bus)
		self.toL2Bus.master = self.l2.cpu_side

	def connectMemSide(self, bus):
		try:
			self.l2.mem_side = bus.slave
		except AttributeError:
			for cpu in self.cpus:
				cpu.connectAllPorts(bus)

class ArmSESystem(System):
	def __init__(self, args, **kwargs):
		super(ArmSESystem, self).__init__(**kwargs)

		self._clusters = []
		self._num_cpus = 0

		self.voltage_domain = VoltageDomain(voltage="3.3V")
		self.clk_domain = SrcClockDomain(clock="1GHz",voltage_domain=self.voltage_domain)

		self.membus = SystemXBar()

		self.system_port = self.membus.slave

		self.cpu_cluster = CpuCluster(self,args.num_cores,args.cpu_freq,"1.2V",*cpu_types[args.cpu])

		if self.cpu_cluster.memoryMode() =="timing":
			self.cpu_cluster.addL1()
			self.cpu_cluster.addL2(self.cpu_cluster.clk_domain)
		self.cpu_cluster.connectMemSide(self.membus)

		self.mem_mode = self.cpu_cluster.memoryMode()

	def numCpuClusters(self):
		return len(self._clusters)

	def addCpuCluster(self, cpu_cluster, num_cpus):
		assert cpu_cluster not in self._clusters
		assert num_cpus >0
		self._clusters.append(cpu_cluster)
		self._num_cpus += num_cpus

	def numCpus(self):
		return self._num_cpus


def getProcesses(cmd):
	cwd = os.getcwd()
	multiprocess_list=[]
	for index, command in enumerate(cmd):
		argv = shlex.split(command)
		process = Process(pid=100+index, cwd=cwd, cmd=argv, executable=argv[0])
		multiprocess_list.append(process)
	return multiprocess_list

def m5_create(args):
	system = ArmSESystem(args)
	system.mem_ranges = [AddrRange(start=0, size=args.mem_size)]

	system.mem_ctrl = DDR3_1600_8x8()
	system.mem_ctrl.range = system.mem_ranges[0]
	system.mem_ctrl.port = system.membus.master


	processes = getProcesses(args.commands)
	if len(processes) != args.num_cores:
		print("Number of cores doesn't match number of processes to be run")
		sys.exit(1)

	for cpu, workload in zip(system.cpu_cluster.cpus, processes):
		cpu.workload = workload

	return system

def main():
	parser = argparse.ArgumentParser(epilog=__doc__)

	parser.add_argument("commands", metavar="command(s)", nargs='*',help="Command(s) to be run on the cores")
	#parser.add_argument("--cpu", type=str, choices=list(cpu_types.keys()),default="minor",help="CPU model to be used")
	parser.add_argument("--cpu", type=str, choices=list(cpu_types.keys()),default="minor",help="CPU model to be used")
	# For Odroid C2 (Cortex A53, minor)
	#parser.add_argument("--cpu-freq", type=str, default="1.5GHz")
	# For Odroid XU4 (Cortex A7, hpi)
	parser.add_argument("--cpu-freq", type=str, default="1.5GHz")
	parser.add_argument("--num-cores", type=int, default=1,help="Number of CPU cores")
	# For Odroid C2
	parser.add_argument("--mem-type", default="DDR3_1600_8x8",choices=ObjectList.mem_list.get_names(),help = "type of memory to use")
	# For Odroid XU4
	#parser.add_argument("--mem-type", default="LPDDR3_1600_1x32",choices=ObjectList.mem_list.get_names(),help="type of memory to use")
	# For both Odroid C2 and XU4
	parser.add_argument("--mem-size", action="store", type=str,default="2GB",help="Specify the physical memory size")


	args = parser.parse_args()

	root = Root(full_system=False)

	root.system = m5_create(args)

	m5.instantiate()

	print("Beginning simulation..")
	m5.simulate()

	print("Exiting simulation")

if __name__ == "__m5_main__":
	main()
