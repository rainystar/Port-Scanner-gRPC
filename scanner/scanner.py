import ConfigParser
import socket
import threading
import logging
import time
import Queue
import math
import sys
import os
import struct
import fcntl
import signal
import scanning_func
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from grpc.early_adopter import exceptions

from common import const
from common import task
from common import message_pb2

class ScannerRPC(message_pb2.EarlyAdopterScannerRPCServicer):
    # rpc service of receiving messages of alive scanner confirmation
    def ConfirmAliveScanner(self, request, context): 
        return message_pb2.Result(res = True, id = request.id)
    
    # rpc service of receiving jobs sent from the controller
    def SendJobList(self, request, context):
        global job_queue
        global job_id_set
        for job in request.jobs:
            threading_lock.acquire()
            job_id_set.add(job.id)
            threading_lock.release()
            job_queue.put((job.task_id, job))
        return message_pb2.Result(res = True)

    # rpc service
    def CheckRunningJob(self, request, context): 
        global job_id_set
        threading_lock.acquire()
        results =[message_pb2.Result(res = (job.id in job_id_set), id = job.id) for job in request.jobs]
        threading_lock.release()
        result_list = message_pb2.ResultList()
        result_list.results.extend(results)
        return result_list

class HeartbeatThread (threading.Thread):
    def __init__(self, threadID, scanner_id, cont_ip, cont_port):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.scanner_id = scanner_id
        self.cont_ip = cont_ip
        self.cont_port = cont_port

    def run(self):
        while not _global_quit:
            try:
                with message_pb2.early_adopter_create_ControllerRPC_stub(self.cont_ip, self.cont_port) as stub:
                    result = stub.Heartbeat(message_pb2.Node(id = self.scanner_id), _RPC_TIMEOUT)      
                    #logging.info('Heartbeat')
                    #if not result.res:
                    #    logging.info(result.msg)
            except Exception as e:
                #logging.info('Heartbeat: connection refused (%s)', e)
                continue
            time.sleep(_HEARTBEAT_INTERVAL)


# Get job from job queue, spawn multi-threads to finish the job, put report to report queue
class JobQueueThread (threading.Thread):
    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
    
    def run(self):
        global job_queue
        global report_queue
        while not _global_quit:
            try:
                job = job_queue.get(block = True, timeout = _JOB_QUEUE_TIMEOUT)
                logging.info('Start job %d' % job[1].id)
            except Queue.Empty:
                continue
            subjob_list = decompose_job_to_subjob(job[1])
            threads = []
            scan_results = []
            for i in range(0, len(subjob_list)):
                job_thread = JobThread(i + 4, subjob_list[i])  
                threads.append(job_thread)  
            for t in threads:
                t.daemon = True
                t.start()    
            for t in threads:
                scan_results.extend(t.join())
            report = message_pb2.Report(job_id = job[1].id, task_id = job[1].task_id, \
                                        scanner_id = job[1].scanner_id, type = job[1].type)
            report.reports.extend(scan_results)
            report_queue.put(report)
            logging.info('Finish job %d' % job[1].id)
            job_queue.task_done()


# Finish each sub-jobs 
class JobThread (threading.Thread):
    def __init__(self, threadID, subjob):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.subjob = subjob
        self.scan_results = []

    def run(self):
        scanner = scanning_func.Scanner()
        if self.subjob.type == const.T_IP_SCAN:
            report_list = scanner.check_ip_alive(self.subjob.ip)
        elif self.subjob.type == const.T_IP_BLOCK_SCAN:
            report_list = scanner.check_block_ip_alive(self.subjob.ip, self.subjob.ip_end, self.subjob.seq_ran)        
        else:
            report_list = scanner.port_scan(self.subjob.ip, self.subjob.port_begin, self.subjob.port_end, self.subjob.seq_ran, self.subjob.type)
        self.scan_results.extend(report_list)        

    def join(self):
        threading.Thread.join(self)
        return self.scan_results


# Get report from report queue, send back to controller
class ReportThread (threading.Thread): 
    def __init__(self, threadID, scanner_id, cont_ip, cont_port):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.scanner_id = scanner_id
        self.cont_ip = cont_ip
        self.cont_port = cont_port

    def run(self):
        global report_queue
        global job_id_set
        while not _global_quit:
            try:
                report = report_queue.get(block = True, timeout = _REPORT_QUEUE_TIMEOUT)
                send_res = False
                while (not send_res) and not (_global_quit):
                    try:
                        with message_pb2.early_adopter_create_ControllerRPC_stub(self.cont_ip, self.cont_port) as stub:
                            result = stub.SendReport(report, 3)   
                            send_res = result.res
                            if send_res:
                                threading_lock.acquire()
                                job_id_set.remove(report.job_id)
                                threading_lock.release()
                                logging.info('Send report for job %d' % report.job_id)
                            else:
                                continue
                    except Exception as e:
                        logging.info('Send report for job %d: connection refused' % report.job_id)
                        time.sleep(_RETRY_INTERVAL)
                        continue
                report_queue.task_done()
            except Queue.Empty:
                continue
            

# decompose a job to small sub-jobs
def decompose_job_to_subjob(job):
    subjob_list = []
    subjob_num = job.num if job.num < _JOB_THREAD_NUM else _JOB_THREAD_NUM
    for i in range(0, subjob_num):
        unit_num = int(math.ceil(float(job.num) / (subjob_num - i)))
        job.num -= unit_num
        if job.type == const.T_IP_SCAN:
            subjob = message_pb2.Job(id = job.id, task_id = job.task_id, 
                                     scanner_id = job.scanner_id, type = job.type, 
                                     ip = job.ip, num = unit_num, seq_ran = job.seq_ran)           
        elif job.type == const.T_IP_BLOCK_SCAN:
            subjob = message_pb2.Job(id = job.id, task_id = job.task_id, 
                                     scanner_id = job.scanner_id, type = job.type, 
                                     ip = job.ip, num = unit_num, seq_ran = job.seq_ran)
            ip_chucks = job.ip.split('.')
            subjob.ip_end = '.'.join(ip_chucks[0 : 3]) + '.' + str(int(ip_chucks[3]) + unit_num - 1)
            job.ip = '.'.join(ip_chucks[0 : 3]) + '.' + str(int(ip_chucks[3]) + unit_num) 
            if i == subjob_num -1:
                assert subjob.ip_end == job.ip_end         
        else:
            subjob = message_pb2.Job(id = job.id, task_id = job.task_id, 
                                     scanner_id = job.scanner_id, type = job.type,
                                     ip = job.ip, port_begin = job.port_begin, 
                                     port_end = job.port_begin +  unit_num - 1,
                                     num = unit_num, seq_ran = job.seq_ran)
            job.port_begin += unit_num
            if i == subjob_num -1:
                assert subjob.port_end == job.port_end
        subjob_list.append(subjob)
    assert job.num == 0
    return subjob_list

# get time setting parameter
def get_time_conf():
    conf = ConfigParser.ConfigParser()    
    conf.read(const.CONF_DIR)
    rpc_timeout = float(conf.get(const.TIME_SEC, const.TIME_RPC_TIMEOUT))
    heartbeat_interval = float(conf.get(const.TIME_SEC, const.TIME_HEARTBEAT_INTERVAL))
    job_queue_timeout = float(conf.get(const.TIME_SEC, const.TIME_JOB_QUEUE_TIMEOUT))
    report_queue_timeout = float(conf.get(const.TIME_SEC, const.TIME_REPORT_QUEUE_TIMEOUT))
    retry_interval = float(conf.get(const.TIME_SEC, const.TIME_RETRY_INTERVAL))
    job_thread_num = int(conf.get(const.TIME_SEC, const.TIME_JOB_THREAD_NUM))
    return rpc_timeout, heartbeat_interval, job_queue_timeout, \
           report_queue_timeout, retry_interval, job_thread_num 

# get controller's information of ip address and port
def get_controller_info():
    conf = ConfigParser.ConfigParser()    
    conf.read(const.CONF_DIR)
    cont_ip = conf.get(const.CONT_SEC, const.CONT_IP)       
    cont_port = conf.get(const.CONT_SEC, const.CONT_PORT) 
    cont_port = int(cont_port)
    return cont_ip, cont_port 

# get scanner's ip
def get_scanner_ip(cont_ip):
    #local_ip = socket.gethostbyname(socket.gethostname()) 
    if is_loopback_ip(cont_ip):
        return '127.0.0.1', '127.0.0.1'
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sockfd = sock.fileno()
    SIOCGIFADDR = 0x8915
    iface = 'wlan0'
    ifreq = struct.pack('16sH14s', iface, socket.AF_INET, '\x00'*14)
    try:
        res = fcntl.ioctl(sockfd, SIOCGIFADDR, ifreq)
    except:
        logging.info('Fail to get local ip')
        sys.exit(1)
    ip = struct.unpack('16sH2x4s8x', res)[2]
    local_ip = socket.inet_ntoa(ip) 
    if local_ip == cont_ip:
        return '127.0.0.1', '127.0.0.1'
    else:      
        return local_ip, cont_ip

# judge whether an ip is a loopback address
def is_loopback_ip(ip):
    ip_blocks = ip.split('.')
    if int(ip_blocks[0]) == 127:
        return True
    else:
        return False

# get scanner's port number from command
def get_scanner_port():
    if len(sys.argv) != 2:
        logging.info('Usage: python %s port' % sys.argv[0])
        sys.exit(1)
    port = sys.argv[1]
    try:
        port = int(port)
        if port < 0 or port > 65535:
            raise Exception('Invalid port number') 
    except ValueError:
        logging.info('Port number should be int')
        sys.exit(1)
    except Exception as e:
        logging.info(e)
        sys.exit(1)
    return port  

# register scanner node
def register(scanner_ip, scanner_port, cont_ip, cont_port):
    global scanner_rpc
    try:
        with message_pb2.early_adopter_create_ControllerRPC_stub(cont_ip, cont_port) as stub:
            result = stub.RegisterScanner(message_pb2.Node(ip = scanner_ip, port = scanner_port), _RPC_TIMEOUT)
            if result.res:
                logging.info('Register success')
            else:
                logging.info('Register fail')
                scanner_rpc.stop()
                sys.exit(1)
            return result.id
    except Exception as e:
        logging.info('Register scanner: connection refused')
        scanner_rpc.stop()
        sys.exit(1)


# configure logging
def config_logging():
    file_name = './log/scanner_%d.log' % os.getpid()
    logging.basicConfig(level=logging.DEBUG,
                format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                datefmt='%a, %d %b %Y %H:%M:%S',
                filename=file_name,
                filemode='w')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

# global variable
_global_quit = False  
_DAY_IN_SECONDS = 60 * 60 * 24
_RPC_TIMEOUT, _HEARTBEAT_INTERVAL, _JOB_QUEUE_TIMEOUT, _REPORT_QUEUE_TIMEOUT, \
    _RETRY_INTERVAL, _JOB_THREAD_NUM = get_time_conf()
job_queue = Queue.PriorityQueue()
report_queue = Queue.Queue()
job_id_set = set()
threading_lock = threading.Lock()

def run():
    global scanner_rpc
    print 'Scanner Process ID:', os.getpid()
    config_logging()
    cont_ip, cont_port = get_controller_info()
    scanner_ip, cont_ip = get_scanner_ip(cont_ip)
    scanner_port = get_scanner_port() 
    scanner_rpc = message_pb2.early_adopter_create_ScannerRPC_server(ScannerRPC(), scanner_port, None, None)
    scanner_rpc.start()
    logging.info('Scanner starts')
    scanner_id = register(scanner_ip, scanner_port, cont_ip, cont_port)
    threads = []
    heartbeat_thread = HeartbeatThread(1, scanner_id, cont_ip, cont_port)
    job_queue_thread = JobQueueThread(2)
    report_thread = ReportThread(3, scanner_id, cont_ip, cont_port)
    heartbeat_thread.daemon = True
    job_queue_thread.daemon = True
    report_thread.daemon = True
    try:
        heartbeat_thread.start()
        job_queue_thread.start()
        report_thread.start()
        threads.append(heartbeat_thread)
        threads.append(job_queue_thread)
        threads.append(report_thread)
        while True:
            time.sleep(_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        global _global_quit 
        _global_quit = True
        for t in threads:
            t.join()
        logging.info("Stopping scanner gRPC service")
        scanner_rpc.stop()
        logging.info('Scanner exits')
        sys.exit(0)

if __name__ == '__main__':
    run()
