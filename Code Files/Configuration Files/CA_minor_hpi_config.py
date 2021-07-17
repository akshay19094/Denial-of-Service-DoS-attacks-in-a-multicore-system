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
    assoc = 16
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20

class L1I(L1Cache):
    pass
    #is_read_only = True
    #writeback_clean = True

class L1D(L1Cache):
    pass

class L2Cache(Cache):
    size = '1MB'
    assoc = 16
    tag_latency = 20
    data_latency = 20
    response_latency = 20
    mshrs = 4
    tgts_per_mshr = 12
    write_buffers = 8

cpu_types = {
    "atomic" : ( AtomicSimpleCPU, None, None, None),
    "minor" : (MinorCPU, L1I, L1D, L2Cache),
    "hpi" : ( HPI.HPI, HPI.HPI_ICache, HPI.HPI_DCache, HPI.HPI_L2)
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
	parser.add_argument("--cpu", type=str, choices=list(cpu_types.keys()),default="minor",help="CPU model to be used")
	parser.add_argument("--cpu-freq", type=str, default="4GHz")
	parser.add_argument("--num-cores", type=int, default=1,help="Number of CPU cores")
	parser.add_argument("--mem-type", default="DDR3_1600_8x8",choices=ObjectList.mem_list.get_names(),help = "type of memory to use")
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
