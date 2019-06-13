import os
import sys
import time
import datetime
import logging
import math
import threading
from job import Job
import utils


# ADD base directory, that is Optimus directory
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

	
job_name_list = ['alexnet', 'resnet-50', 'vgg-11', 'inception-bn', 'resnet-152', 'resnet-101']
neural_network_list = ['alexnet', 'resnet', 'vgg', 'inception-bn', 'resnet', 'resnet']
num_layers_list = ['', '50', '', '', '152', '101']

node_list = ['10.20.17.52', '10.20.17.113'] #['10.28.1.1', '10.28.1.2', '10.28.1.3', '10.28.1.4', '10.28.1.6', '10.28.1.7', '10.28.1.8']
ps_cpu = "5"
ps_mem = "8Gi"
worker_cpu = "5"
worker_mem = "8Gi"


def base_line():
	job_id = 0
	job_list = []
	cwd = os.getcwd() + '/'
	
	'''
	first baseline test, to see whether the training speed on each server is same.
	cifar10 as baseline running local training
	'''
	baseline = Job('baseline-cifar10', job_id, cwd)
	baseline.set_ps_resources(0,ps_cpu,ps_mem)
	baseline.set_worker_resources(len(node_list),worker_cpu,worker_mem)
	baseline.set_worker_placement(node_list)
	
	image = 'yhpeng/k8s-mxnet-measurement'
	script = '/init.py'
	prog = '/mxnet/example/image-classification/train_cifar10.py'
	work_dir = '/mxnet/example/image-classification/data/'
	mount_dir_prefix = '/data/k8s-workdir/measurement/'
	baseline.set_container(image, script, prog, work_dir, mount_dir_prefix)
	
	baseline.set_data(data_train='cifar10_train.rec', hdfs_data_train='/k8s-mxnet/cifar10/cifar10_train.rec')
	baseline.set_network('resnet', '50')
	baseline.set_training('20',batch_size='32',kv_store='local',gpus='')
	baseline.set_disp('5')
	
	baseline.start()
	job_list.append(baseline)

	while(True):
		stop = raw_input("Please enter whether to stop (Yes/No): ")
		if stop == "Yes":
			for job in job_list:
				logger.info('training speed: ' + str(job.get_training_speed()))
				job.delete(True)
			break
	


def measure_speed():
	
	
	'''
	use 7 bladeservers, imagenet dataset, lenet neural network
	parameter size 13MB, batch_size=1,2,4,8,16,... this may changes bandwidth requirement.
	training speed: about 90 samples/second for local computation with batch_size 128; 10 samples/second with batch_size 1
	NIC: 10Gbps
	asynchronous training vs synchronous training
	each experiment is 5mins
	# ps		1	2	3	4	5	6
	# worker	1...6   1...5   1...4   1...3   1...2   1
	'''
	
	
	job_id = 0
	cwd = os.getcwd() + '/'
	stats = []	# element format (#ps, #worker, speed, cpu)
	txt = 'stats.txt'
	if os.path.isfile(txt):	# back up
		time_str = str(int(time.time()))
		fn =  './results/' + time_str + '.' + txt
		os.system('cp ' + txt + ' ' + fn)
	f = open(txt, 'w')	# clear txt
	f.close()
	
	num_node = len(node_list) * 6	# at most 42 pods in total
	kv_stores = ['dist_sync', 'dist_async']
	batch_sizes = ['1','2','4','8','16','32','64','128']
	
	tic = time.time()
	
	for kv_store in kv_stores:
		for batch_size in ['40']:
			for num_ps in [1]: #xrange(10, 22, 2):	# to save time, change to xrange(1, num_node, 2)
				for num_worker in [1]: #xrange(10, 20):	# to save time, change to xrange(1, num_node-num_ps+1, 2)
					job_id += 1
					
					logger.info("------------------start job " + str(job_id) + "-------------------")
					toc = time.time()
					logger.info("time elapsed: " + str((toc-tic)/60) + " minutes" )
					
					measure_job = Job('measurement-imagenet', job_id, cwd)
					measure_job.set_ps_resources(num_ps,ps_cpu,ps_mem)
					#measure_job.set_ps_placement(node_list[:num_ps])
			
					measure_job.set_worker_resources(num_worker,worker_cpu,worker_mem)
					#measure_job.set_worker_placement(node_list[num_ps:num_ps+num_worker])
					
					placement_list = node_list * 6
					measure_job.set_ps_placement(placement_list[:num_ps])
					measure_job.set_worker_placement(placement_list[num_ps:num_ps+num_worker])
					
					image = 'cogito288/k8s-mxnet-gpu-experiment'
					script = '/init.sh'
					prog = '/mxnet/example/image-classification/train_imagenet.py'
					work_dir = '/mxnet/example/image-classification/data/'
					mount_dir_prefix = base_dir+'/data/k8s-workdir/measurement/'
					measure_job.set_container(image, script, prog, work_dir, mount_dir_prefix)
	
					measure_job.set_data(data_train='cifar10_train.rec', data_val='',\
					hdfs_data_train=base_dir+'/k8s-mxnet/cifar10/cifar10_train.rec', hdfs_data_val='')
					measure_job.set_network('vgg', '')
					measure_job.set_training('100',batch_size,kv_store,gpus='')
					measure_job.set_disp('1')
					measure_job.set_mxnet(kv_store_big_array_bound=1000*1000)
	
					measure_job.start()
					
					counter = 0
					while(True):
						try:
							time.sleep(60)
						except:
							logger.info("detect Ctrl+C, exit...")
							measure_job.delete(True)
							sys.exit(0)
							
						counter += 1
						try:
							speed_list = measure_job.get_training_speed()
							(ps_metrics, worker_metrics) = measure_job.get_metrics()
						except:
							logger.info("get training speed error!")
							measure_job.delete(True)
							sys.exit(0)
						# compute cpu usage difference
						ps_cpu_usage_list = []
						for metrics in ps_metrics:
							ps_cpu_usage_list.append(metrics['cpu/usage_rate']/1000.0)
						ps_cpu_diff = max(ps_cpu_usage_list) - min(ps_cpu_usage_list)
						worker_cpu_usage_list = []
						for metrics in worker_metrics:
							worker_cpu_usage_list.append(metrics['cpu/usage_rate']/1000.0)
						worker_cpu_diff = max(worker_cpu_usage_list) - min(worker_cpu_usage_list)
						
						model_name = measure_job.get_model_name()
						logger.info("model name: " + model_name + ", kv_store: " + kv_store + ", batch_size: " + batch_size + \
						", num_ps: " + str(num_ps) + ", num_worker: " + str(num_worker) + \
						", speed_list: " + str(speed_list) + ", sum_speed (samples/second): " + str(sum(speed_list)) + \
						", sum_speed(batches/second): " + str(sum(speed_list)/int(batch_size)) + \
						", ps cpu usage diff: " + str(ps_cpu_diff) + \
						", worker cpu usage diff: " + str(worker_cpu_diff)
						)
						if counter >= 5:
							stat = (model_name, kv_store, batch_size, num_ps, num_worker, speed_list, ps_cpu_usage_list, worker_cpu_usage_list)
							stats.append(stat)
							with open(txt, 'a') as f:	# append
								#for stat in stats:
								f.write(str(stat) + '\n')
							
							measure_job.delete(True)
							logger.info("sleep 3 seconds before next job")
							time.sleep(3)
							break


def prepare_env():
	logger.info("clear all existing jobs")
	os.system("kubectl delete jobs,daemonsets --all")

	
	
def main():
	global logger
	
	logger = utils.getLogger('measure-speed')
	prepare_env()
	measure_speed()
	

if __name__ == '__main__':
	if len(sys.argv) != 1:
		print "Description: speed measurement script in k8s cluster, to explore how training speed changes with the number of parameter servers and workers"
		print "Usage: python measure-speed.py"
		sys.exit(1)
	main()
