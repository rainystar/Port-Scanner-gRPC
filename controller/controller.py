import ConfigParser
import MySQLdb
import time
import threading
import logging
import Queue
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from enum import Enum

from common import const
from common import task
from common import message_pb2

class ControllerRPC(message_pb2.EarlyAdopterControllerRPCServicer):
    # rpc service of receiving scanner's register message
    def RegisterScanner(self, request, context):
        return self.insert_update_scanner(request.ip, request.port)
    
    # rpc service of receiving scanner's heartbeat message
    def Heartbeat(self, request, context):
        # update scanner status
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()
        try:
            sql = "SELECT 1 FROM portscanner.scanner WHERE id = %d and status = '%s'" % (request.id, const.S_RUNNING)
            cursor.execute(sql)
            results = cursor.fetchall()
            if len(results) == 0:   # the scanner has been detected to be stopped due to false alarm
                logging.info("Scanner %d is falsely detected to be stopped" % request.id)
                return message_pb2.Result(res = False, msg = "Please restart scanner")
            sql = "UPDATE portscanner.scanner SET update_time = CURRENT_TIMESTAMP(1) WHERE id = %d" % request.id
            cursor.execute(sql)
            db.commit()
        except MySQLdb.Error, e:
            err_msg = 'MySQLdb.Error in Heartbeat RPC service: %s' % e
            logging.info(err_msg)
            return message_pb2.Result(res = False, msg = err_msg)
        finally:
            cursor.close()
            db.close()
        return message_pb2.Result(res = True)

    # rpc service of receiving reports
    def SendReport(self, request, context):
        global report_queue
        #logging.info('Receive report for job %d' % request.job_id) 
        report_queue.put(request)
        return message_pb2.Result(res = True)
    
    # insert / update scanner status into database
    def insert_update_scanner(self, ip, port):
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()    
        try:
            sql = "SELECT id, status FROM portscanner.scanner where ip = '%s' and port = %d" % (ip, port)
            cursor.execute(sql)
            results = cursor.fetchall()
            if len(results) == 0:   # the scanner hasn't registered before, insert
                sql = """INSERT INTO portscanner.scanner (ip, port, status, update_time) 
                         VALUES ('%s', %d, '%s', CURRENT_TIMESTAMP(1))""" % (ip, port, const.T_RUNNING)
                cursor.execute(sql)
                scanner_id = int(cursor.lastrowid)
            else:   # the scanner has registered before, update
                scanner_id = results[0][0]
                status = results[0][1]
                if status == const.T_RUNNING:
                      sql = """UPDATE portscanner.job SET scanner_id = NULL, status = NULL, assign_time = NULL 
                               WHERE status = '%s' and scanner_id = %d""" \
                            % (const.S_RUNNING, scanner_id)
                      cursor.execute(sql)          
                sql = """UPDATE portscanner.scanner SET status = '%s', update_time = CURRENT_TIMESTAMP(1) 
                         WHERE id = %d""" % (const.T_RUNNING, scanner_id)
                cursor.execute(sql)
            db.commit() # commit in one transaction to ensure data consistency
        except MySQLdb.Error, e:
            err_msg = 'MySQLdb.Error in function insert_update_scanner(): %s' % e
            logging.info(err_msg)
            return message_pb2.Result(res = False, msg = err_msg)
        finally:
            cursor.close()
            db.close() 
        return message_pb2.Result(res = True, id = scanner_id)


class CheckAliveScannerThread (threading.Thread):
    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
    
    def run(self):
        sleep_num = 0
        while not _global_quit:
            if sleep_num < _CHECK_ALIVE_INTERVAL:
                sleep_num += 1
                time.sleep(1)
            else:   
                sleep_num = 0  
                db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
                cursor = db.cursor()
                try:
                    sql = """SELECT id FROM portscanner.scanner where status = '%s' and 
                             TIMESTAMPDIFF(SECOND, update_time, CURRENT_TIMESTAMP(1)) > %d""" \
                          % (const.S_RUNNING, _ALLOW_HEARTBEAT_INTERVAL)
                    cursor.execute(sql)
                    scanner_id_list = [str(row[0]) for row in cursor.fetchall()]
                    if len(scanner_id_list) > 0:
                        sql = """UPDATE portscanner.scanner SET status = '%s', update_time = CURRENT_TIMESTAMP(1) 
                                 WHERE id IN (%s)""" % (const.S_STOPPED, ', '.join(scanner_id_list))
                        cursor.execute(sql)
                        sql = """UPDATE portscanner.job SET scanner_id = NULL, status = NULL, assign_time = NULL 
                                 WHERE status = '%s' and scanner_id IN (%s)""" \
                              % (const.S_RUNNING, ', '.join(scanner_id_list))
                        cursor.execute(sql)
                        db.commit() # commit in one transaction to ensure data consistency
                        logging.info('Scanners (%s) have stopped' % ', '.join(scanner_id_list))
                except MySQLdb.Error, e:
                    logging.info('MySQLdb.Error in thread CheckAliveScannerThread: %s', e)
                    continue
                finally:
                    cursor.close()
                    db.close()


class CheckRunningJobThread (threading.Thread):
    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID

    def run(self):
        sleep_num = 0
        while not _global_quit:
            if sleep_num < _CHECK_RUNNING_JOB_INTERVAL:
                sleep_num += 1
                time.sleep(1)
            else:
                sleep_num = 0
                scanner_dict, scanner_jobs_dict = self.get_long_running_jobs()
                if len(scanner_dict) > 0:
                    self.check_jobs(scanner_dict, scanner_jobs_dict)

    def get_long_running_jobs(self):
        scanner_dict = {}
        scanner_jobs_dict = {}
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()
        try:
            sql = """SELECT a.id, a.scanner_id, b.ip, b.port FROM portscanner.job a, portscanner.scanner b 
                     WHERE a.scanner_id = b.id 
                     AND TIMESTAMPDIFF(SECOND, a.assign_time, CURRENT_TIMESTAMP()) > IF(%d * CEILING(a.num / %d) > 60, %d * CEILING(a.num / %d), 60) 
                     AND a.status = '%s'""" \
                     % (_EST_EXE_JOB_UNIT_INTERVAL, _JOB_THREAD_NUM, _EST_EXE_JOB_UNIT_INTERVAL, _JOB_THREAD_NUM, const.T_RUNNING)
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
        except MySQLdb.Error, e:
            logging.info('MySQLdb.Error in function CheckRunningJobThread: %s', e)
            return scanner_dict, scanner_jobs_dict
        finally:
            cursor.close()
            db.close()
        for row in result:  # if MySQLdb exception was caught, these will not be executed
            if row[const.C_SCANNER_ID] in scanner_dict:
                scanner_jobs_dict[row[const.C_SCANNER_ID]].append(message_pb2.Job(id = row[const.C_ID]))
            else:
                scanner_dict[row[const.C_SCANNER_ID]] = message_pb2.Node(ip = row[const.C_IP], port = int(row[const.C_PORT]))
                scanner_jobs_dict[row[const.C_SCANNER_ID]] = [message_pb2.Job(id = row[const.C_ID])] 
        return scanner_dict, scanner_jobs_dict         

    def check_jobs(self, scanner_dict, scanner_jobs_dict):
        for scanner_id in scanner_dict:
            job_list = message_pb2.JobList()
            job_list.jobs.extend(scanner_jobs_dict[scanner_id])                                
            try:
                with message_pb2.early_adopter_create_ScannerRPC_stub(scanner_dict[scanner_id].ip, scanner_dict[scanner_id].port) as stub:
                    response = stub.CheckRunningJob(job_list, _RPC_TIMEOUT)
                    trans_res = False
                    job_id_list = [str(result.id) for result in response.results if not result.res]
                    if len(job_id_list) > 0:
                        while not trans_res:
                            db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
                            cursor = db.cursor()
                            try:
                                sql = """UPDATE portscanner.job SET scanner_id = NULL, status = NULL, assign_time = NULL 
                                         WHERE status = '%s' and id IN (%s)""" % (const.S_RUNNING, ', '.join(job_id_list))
                                cursor.execute(sql)
                                db.commit()
                                logging.info('Jobs (%s) have to be reassigned' % ', '.join(job_id_list))
                            except MySQLdb.Error, e:
                                logging.info('MySQLdb.Error in function check_jobs: %s', e)
                                time.sleep(_RETRY_INTERVAL)
                                continue
                            finally:
                                cursor.close()
                                db.close()
                            trans_res = True                        
            except Exception as e:
                continue   

class ReportThread (threading.Thread): 
    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID

    def run(self):
        global report_queue
        while not _global_quit:
            try:
                report = report_queue.get(block = True, timeout = _REPORT_QUEUE_TIMEOUT)
                self.insert_report(report)
                report_queue.task_done()
            except Queue.Empty:
                continue 

    # insert report into database
    def insert_report(self, report):
        trans_res = False
        while not trans_res:
            db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
            cursor = db.cursor()
            try:
                sql = "SELECT 1 FROM portscanner.job WHERE id = %d" % report.job_id
                cursor.execute(sql)
                results = cursor.fetchall()
                if len(results) == 0:
                    pass
                    #logging.info('Ignore report for job %d' % report.job_id)
                else:
                    sql = "SELECT 1 FROM portscanner.report WHERE job_id = %d" % report.job_id
                    cursor.execute(sql)
                    results = cursor.fetchall()
                    if len(results) == 0:
                        report_list = report.reports
                        for report_item in report_list:
                            if report.type == const.T_IP_SCAN or report.type == const.T_IP_BLOCK_SCAN:
                                sql = """INSERT portscanner.report (task_id, job_id, ip, res, update_time) 
                                         VALUES (%d, %d, '%s', '%s', CURRENT_TIMESTAMP(1))""" \
                                      % (report.task_id, report.job_id, report_item.ip, report_item.res)                    
                            else:
                                sql = """INSERT portscanner.report (task_id, job_id, port, res, banner, update_time) 
                                         VALUES (%d, %d, %d, '%s', '%s', CURRENT_TIMESTAMP(1))""" \
                                      % (report.task_id, report.job_id, report_item.port, report_item.res, report_item.banner)                 
                            cursor.execute(sql)
                        sql = """UPDATE portscanner.job SET status = '%s', finish_time = CURRENT_TIMESTAMP(1) WHERE id = %d""" \
                              % (const.T_FINISHED, report.job_id)  
                        cursor.execute(sql)
                        sql = """update portscanner.task a set a.status = '%s', a.finish_time = CURRENT_TIMESTAMP(1) 
                                 WHERE a.id = %d and NOT EXISTS 
                                    (select b.id from portscanner.job b 
                                     where a.id = b.task_id and (b.status = '%s' or b.status is null))""" \
                              % (const.T_FINISHED, report.task_id, const.T_RUNNING)
                        cursor.execute(sql)
                        db.commit()    
                        logging.info('Save report for job %d' % report.job_id)  
            except MySQLdb.Error, e:
                logging.info('MySQLdb.Error in function insert_report(): %s', e)
                continue
            finally:
                cursor.close()
                db.close()       
            trans_res = True


# multiple possible results of assigning jobs
class AssignJobRes(Enum):
    no_scanner = 1
    no_job = 2
    some_jobs_fail = 3
    all_jobs_success = 4


class AssignTaskRes(Enum):
    no_scanner = 1
    no_task = 2
    some_jobs_fail = 3
    all_jobs_success = 4


# get database configuration parameter
def get_db_conf():
    conf = ConfigParser.ConfigParser()    
    conf.read(const.CONF_DIR)
    db_host = conf.get(const.DB_SEC, const.DB_HOST)       
    db_name = conf.get(const.DB_SEC, const.DB_NAME)
    db_user = conf.get(const.DB_SEC, const.DB_USER)    
    db_pwd = conf.get(const.DB_SEC, const.DB_PWD)
    return db_host, db_name, db_user, db_pwd

# get time setting parameter
def get_time_conf():
    conf = ConfigParser.ConfigParser()    
    conf.read(const.CONF_DIR)
    rpc_timeout = float(conf.get(const.TIME_SEC, const.TIME_RPC_TIMEOUT))
    heartbeat_interval = float(conf.get(const.TIME_SEC, const.TIME_HEARTBEAT_INTERVAL))
    controller_sleep_interval = float(conf.get(const.TIME_SEC, const.TIME_CONTROLLER_SLEEP_INTERVAL))
    check_alive_interval = float(conf.get(const.TIME_SEC, const.TIME_CHECK_ALIVE_INTERVAL))
    allow_heartbeat_interval = float(conf.get(const.TIME_SEC, const.TIME_ALLOW_HEARTBEAT_INTERVAL))
    retry_interval = float(conf.get(const.TIME_SEC, const.TIME_RETRY_INTERVAL))
    est_exe_job_unit_interval = int(conf.get(const.TIME_SEC, const.TIME_EST_EXE_JOB_UNIT_INTERVAL))
    check_running_job_interval = int(conf.get(const.TIME_SEC, const.TIME_CHECK_RUNNING_JOB_INTERVAL))
    job_thread_num = int(conf.get(const.TIME_SEC, const.TIME_JOB_THREAD_NUM))
    report_queue_timeout = float(conf.get(const.TIME_SEC, const.TIME_REPORT_QUEUE_TIMEOUT))
    return rpc_timeout, heartbeat_interval, controller_sleep_interval, \
           check_alive_interval, allow_heartbeat_interval, retry_interval, \
           est_exe_job_unit_interval, check_running_job_interval, \
           job_thread_num, report_queue_timeout

# get controller's info
def get_controller_port():
    conf = ConfigParser.ConfigParser()    
    conf.read(const.CONF_DIR)
    cont_port = int(conf.get(const.CONT_SEC, const.CONT_PORT))   
    return cont_port 

# configure logging
def config_logging():
    logging.basicConfig(level=logging.DEBUG,
                format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                datefmt='%a, %d %b %Y %H:%M:%S',
                filename='./log/controller.log',
                filemode='w')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

# query database, get the alive scanner list, confirm them whether still alive
def confirm_alive_scanners():
    global controller_rpc
    logging.info('Confirming alive scanners')
    db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
    cursor = db.cursor()
    try:
        sql = "SELECT id, ip, port FROM portscanner.scanner where status = '%s'" % const.T_RUNNING
        cursor.execute(sql)
        fields = map(lambda x:x[0], cursor.description)
        result = [dict(zip(fields,row))   for row in cursor.fetchall()]
    except MySQLdb.Error, e:
        logging.info('MySQLdb.Error in function confirm_alive_scanners() (1): %s', e)
        controller_rpc.stop()
        sys.exit(1) # not in thread, so could exit main thread
    finally:
        cursor.close()
        db.close()
    failed_scanner_list = []
    for row in result:
        try: 
            with message_pb2.early_adopter_create_ScannerRPC_stub(row[const.C_IP], int(row[const.C_PORT])) as stub:        
                response = stub.ConfirmAliveScanner(message_pb2.Node(id = int(row[const.C_ID])), _RPC_TIMEOUT)
                if response.res:
                    logging.info('Alive scanner (%d) %s:%d' % (int(row[const.C_ID]), row[const.C_IP], int(row[const.C_PORT])))
        except Exception as e:
            failed_scanner_list.append(str(row[const.C_ID]))   
    if len(failed_scanner_list) > 0:
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()
        try:
            sql = """UPDATE portscanner.scanner SET status = '%s', update_time = CURRENT_TIMESTAMP(1) 
                     WHERE id IN (%s)""" % (const.S_STOPPED, ', '.join(failed_scanner_list))        
            cursor.execute(sql)  
            sql = """UPDATE portscanner.job SET scanner_id = NULL, status = NULL, assign_time = NULL 
                     WHERE status = '%s' and scanner_id IN (%s)""" \
                     % (const.S_RUNNING, ', '.join(failed_scanner_list))
            cursor.execute(sql)
            db.commit()
            logging.info('Scanners (%s) have stopped' % ', '.join(failed_scanner_list))
        except MySQLdb.Error, e:
            logging.info('MySQLdb.Error in function confirm_alive_scanners() (2): %s', e)
            controller_rpc.stop()
            sys.exit(1) # not in thread, so could exit main thread
        finally:
            cursor.close()
            db.close()
    logging.info('Confirming alive scanners finished')

# assign remained jobs to scanners until all of them are sent out
def assign_remained_jobs_loop():
    result = assign_remained_jobs()
    while (not _global_quit) and (result == AssignJobRes.some_jobs_fail or result == AssignJobRes.no_scanner):
        # It needs _CHECK_ALIVE_INTERVAL seconds to discover a failed scanner
        time.sleep(_CONTROLLER_SLEEP_INTERVAL)     
        result = assign_remained_jobs()

# assign jobs to scanners
def assign_remained_jobs():
    job_list = get_jobs()
    if len(job_list) == 0:
        return AssignJobRes.no_job
    scanner_dict, scanner_list = get_alive_scanners()
    if len(scanner_list) == 0:
        return AssignJobRes.no_scanner
    scanner_job_dict = {}
    decomposed_job_dict = {}
    for job in job_list:
        decomposed_job_dict[str(job.id)] = []
        subjob_num = len(scanner_list)
        current_unit_num = sum(scanner.running_units for scanner in scanner_list)
        while int((job.num + current_unit_num) / subjob_num) <= scanner_list[subjob_num - 1].running_units and subjob_num >= 1:
            subjob_num -= 1
            current_unit_num = sum(scanner.running_units for scanner in scanner_list[0 : subjob_num])   
        avg_units_per_scanner = (job.num + current_unit_num) / subjob_num 
        assigned_units = 0
        for i in range(0, subjob_num):
            if i != subjob_num - 1:
                unit_num = avg_units_per_scanner - scanner_list[i].running_units
            else:
                unit_num = job.num - assigned_units
            assigned_units += unit_num   
            if job.type == const.T_IP_SCAN:
                subjob = message_pb2.Job(task_id = job.task_id, scanner_id = scanner_list[i].id,
                                         type = job.type, ip = job.ip, 
                                         num = unit_num, seq_ran = job.seq_ran)
            elif job.type == const.T_IP_BLOCK_SCAN:
                subjob = message_pb2.Job(task_id = job.task_id, scanner_id = scanner_list[i].id,
                                         type = job.type, ip = job.ip,
                                         num = unit_num, seq_ran = job.seq_ran)
                ip_chucks = job.ip.split('.')
                subjob.ip_end = '.'.join(ip_chucks[0 : 3]) + '.' + str(int(ip_chucks[3]) + unit_num - 1)
                job.ip = '.'.join(ip_chucks[0 : 3]) + '.' + str(int(ip_chucks[3]) + unit_num)
                if i == subjob_num -1:
                    assert subjob.ip_end == job.ip_end         
            else:
                subjob = message_pb2.Job(task_id = job.task_id, scanner_id = scanner_list[i].id,
                                         type = job.type, ip = job.ip,
                                         port_begin = job.port_begin, port_end = job.port_begin +  unit_num - 1,
                                         num = unit_num, seq_ran = job.seq_ran)
                job.port_begin += unit_num
                if i == subjob_num -1:
                    assert subjob.port_end == job.port_end 
            if scanner_list[i].id in scanner_job_dict:
                scanner_job_dict[scanner_list[i].id].append(subjob)
            else:
                scanner_job_dict[scanner_list[i].id] = [subjob]
            scanner_list[i].running_units += job.num
            decomposed_job_dict[str(job.id)].append(subjob)
        scanner_list.sort(key=lambda scanner: scanner.running_units)
    if len(decomposed_job_dict) > 0:
        insert_subjob_del_job(decomposed_job_dict) 
        for job_id in decomposed_job_dict:
            subjob_id_list = [str(job.id) for job in decomposed_job_dict[job_id]]
            logging.info('Job %s is decomposed to subjobs (%s)' % (job_id, ', '.join(subjob_id_list)))  
    return send_jobs(scanner_dict, scanner_job_dict)

# insert subjobs into database and delete original big job
def insert_subjob_del_job(decomposed_job_dict):
    save_jobs(decomposed_job_dict)
    trans_res = False
    while not trans_res:
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()
        try:
            sql = """DELETE FROM portscanner.job WHERE id IN (%s)""" % (', '.join(list(decomposed_job_dict.keys())))
            cursor.execute(sql)
            db.commit()
        except MySQLdb.Error, e:
            logging.info('MySQLdb.Error in function insert_subjob_del_job(): %s', e)
            time.sleep(_RETRY_INTERVAL)
            continue
        finally:
            cursor.close()
            db.close() 
        trans_res = True    

# get unassigned jobs from database ordered by the number of job units desc
def get_jobs():
    job_list = []
    db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
    cursor = db.cursor()
    try:
        sql = """SELECT id, task_id, type, ip, ip_end, port_begin, port_end, seq_ran, num FROM portscanner.job 
                WHERE scanner_id IS NULL ORDER BY num DESC"""
        cursor.execute(sql)
        fields = map(lambda x:x[0], cursor.description)
        result = [dict(zip(fields,row))   for row in cursor.fetchall()]
        for row in result:
            if row[const.C_TYPE] == const.T_IP_SCAN:
                job = message_pb2.Job(id = row[const.C_ID], task_id = row[const.C_TASK_ID],
                                      type = row[const.C_TYPE], ip = row[const.C_IP],
                                      seq_ran = row[const.C_SEQ_RAN], num = row[const.C_NUM])
            elif row[const.C_TYPE] == const.T_IP_BLOCK_SCAN:
                job = message_pb2.Job(id = row[const.C_ID], task_id = row[const.C_TASK_ID],
                                      type = row[const.C_TYPE], ip = row[const.C_IP],
                                      ip_end = row[const.C_IP_END], seq_ran = row[const.C_SEQ_RAN], 
                                      num = row[const.C_NUM])
            else:
                job = message_pb2.Job(id = row[const.C_ID], task_id = row[const.C_TASK_ID],
                                      type = row[const.C_TYPE], ip = row[const.C_IP],
                                      port_begin = row[const.C_PORT_BEGIN], port_end = row[const.C_PORT_END],
                                      seq_ran = row[const.C_SEQ_RAN], num = row[const.C_NUM])
            job_list.append(job)
    except MySQLdb.Error, e:
        logging.info('MySQLdb.Error in function get_jobs(): %s', e)     # if transaction fails, return no jobs
    finally:
        cursor.close()
        db.close() 
    return job_list 
    
# get alive scanner list [Node(scanner_id, number of jobs running on the scanner)] 
# ordered by number of running job units asc 
def get_alive_scanners():
    scanner_list = []
    scanner_dict = {}
    db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
    cursor = db.cursor()
    try:
        sql = """SELECT b.id, b.ip, b.port, IFNULL(SUM((num)), 0) num FROM portscanner.job a 
                 RIGHT JOIN portscanner.scanner b ON a.scanner_id = b.id AND (a.status IS NULL or a.status= '%s') 
                 WHERE b.status = '%s' GROUP BY b.id ORDER BY num ASC""" % (const.T_RUNNING, const.S_RUNNING)
        cursor.execute(sql)
        fields = map(lambda x:x[0], cursor.description)
        result = [dict(zip(fields,row))   for row in cursor.fetchall()]
        for row in result:
            scanner_dict[row[const.C_ID]] = message_pb2.Node(id = row[const.C_ID], \
                                            ip = row[const.C_IP], port = int(row[const.C_PORT]))
            scanner_list.append(message_pb2.Node(id = row[const.C_ID], running_units = int(row[const.C_NUM])))
    except MySQLdb.Error, e:
        logging.info('MySQLdb.Error in function get_alive_scanners(): %s', e)   # if transaction failds, return  no alive scanner
    finally:
        cursor.close()
        db.close()
    return scanner_dict, scanner_list 

# send job lists to scanners
def send_jobs(scanner_dict, scanner_job_dict):
    result = AssignJobRes.all_jobs_success
    scanner_success_list = []
    for scanner_id in scanner_job_dict:
        job_list = message_pb2.JobList()
        job_list.jobs.extend(scanner_job_dict[scanner_id])
        try:
            with message_pb2.early_adopter_create_ScannerRPC_stub(scanner_dict[scanner_id].ip, scanner_dict[scanner_id].port) as stub:        
                response = stub.SendJobList(job_list, _RPC_TIMEOUT)
                if response.res:
                    scanner_success_list.append(scanner_id)
                else:
                    result = AssignJobRes.some_jobs_fail     
        except Exception as e:
            result = AssignJobRes.some_jobs_fail
    trans_res = False
    while not trans_res:
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()
        try:
            for scanner_id in scanner_success_list:
                job_id_list = [str(job.id) for job in scanner_job_dict[scanner_id]]
                sql = """UPDATE portscanner.job SET scanner_id = %d, status = ifnull(status, '%s'), 
                         assign_time = CURRENT_TIMESTAMP(1) WHERE id IN (%s)""" \
                      % (scanner_id, const.S_RUNNING, ', '.join(job_id_list))       
                cursor.execute(sql)  
                logging.info('Scanners (%d) is assigned jobs (%s)' % (scanner_id, ', '.join(job_id_list)))
            db.commit()
            sql = """UPDATE portscanner.task a, 
                        (SELECT DISTINCT task.id FROM portscanner.task, portscanner.job 
                         WHERE task.id = job.task_id AND task.status = '%s' 
                         AND job.scanner_id IS NOT NULL) b 
                     SET a.status = '%s' WHERE a.id = b.id""" \
                  % (const.T_SUBMITTED, const.T_RUNNING)
            cursor.execute(sql)
            db.commit()
        except MySQLdb.Error, e:
            logging.info('MySQLdb.Error in function send_jobs(): %s', e)
            time.sleep(_RETRY_INTERVAL)
            continue
        finally:
            cursor.close()
            db.close() 
        trans_res = True       
    return result

# assign tasks to scanners
def assign_tasks():
    task_list = get_tasks()
    if len(task_list) == 0:
        return AssignTaskRes.no_task
    scanner_dict, scanner_list = get_alive_scanners()
    if len(scanner_list) == 0:
        return AssignTaskRes.no_scanner
    scanner_job_dict = decompose_tasks_to_jobs(scanner_list, task_list)
    save_jobs(scanner_job_dict)
    result = send_jobs(scanner_dict, scanner_job_dict)    
    if result == AssignJobRes.some_jobs_fail:
        return AssignTaskRes.some_jobs_fail
    else:        
        return AssignTaskRes.all_jobs_success    

# get submitted task list from database
def get_tasks():
    task_list = []
    db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
    cursor = db.cursor()
    try:
        sql = """SELECT id, type, status, ip, ip_end, port_begin, port_end, seq_ran
                 FROM portscanner.task where status = '%s' order by id""" % const.T_SUBMITTED
        cursor.execute(sql)
        fields = map(lambda x:x[0], cursor.description)
        result = [dict(zip(fields,row))   for row in cursor.fetchall()]
        for row in result:
            if row[const.C_TYPE] == const.T_IP_SCAN:
                t = task.IpTask(row[const.C_ID], row[const.C_TYPE], 
                                row[const.C_STATUS], row[const.C_IP], 
                                row[const.C_SEQ_RAN])
            elif row[const.C_TYPE] == const.T_IP_BLOCK_SCAN:
                t = task.IpBlockTask(row[const.C_ID], row[const.C_TYPE], 
                                     row[const.C_STATUS], row[const.C_IP], 
                                     row[const.C_IP_END], row[const.C_SEQ_RAN])
            else:
                t = task.PortTask(row[const.C_ID], row[const.C_TYPE], 
                                  row[const.C_STATUS], row[const.C_IP], 
                                  row[const.C_PORT_BEGIN], row[const.C_PORT_END],
                                  row[const.C_SEQ_RAN])
            task_list.append(t)
    except MySQLdb.Error, e:
        logging.info('MySQLdb.Error in function get_tasks(): %s', e)    # if transaction fails, return no task
    finally:
        cursor.close()
        db.close()
    return task_list

# generate jobs from task list
def decompose_tasks_to_jobs(scanner_list, task_list):
    scanner_job_dict = {}
    for task in task_list:
        job_num = len(scanner_list)
        current_unit_num = sum(scanner.running_units for scanner in scanner_list)
        while int((task.num + current_unit_num) / job_num) <= scanner_list[job_num - 1].running_units and job_num >= 1:
            job_num -= 1
            current_unit_num = sum(scanner.running_units for scanner in scanner_list[0 : job_num])
        avg_units_per_scanner = (task.num + current_unit_num) / job_num
        assigned_units = 0
        for i in range(0, job_num):
            if i != job_num - 1:
                unit_num = avg_units_per_scanner - scanner_list[i].running_units
            else:
                unit_num = task.num - assigned_units
            assigned_units += unit_num
            if task.type == const.T_IP_SCAN:
                job = message_pb2.Job(task_id = task.task_id, scanner_id = scanner_list[i].id,
                                      type = task.type, ip = task.ip, 
                                      num = unit_num, seq_ran = task.seq_ran)
            elif task.type == const.T_IP_BLOCK_SCAN:
                job = message_pb2.Job(task_id = task.task_id, scanner_id = scanner_list[i].id,
                                      type = task.type, ip = task.ip,
                                      num = unit_num, seq_ran = task.seq_ran)
                ip_chucks = task.ip.split('.')
                job.ip_end = '.'.join(ip_chucks[0 : 3]) + '.' + str(int(ip_chucks[3]) + unit_num - 1)
                task.ip = '.'.join(ip_chucks[0 : 3]) + '.' + str(int(ip_chucks[3]) + unit_num)
                if i == job_num -1:
                    assert job.ip_end == task.ip_end         
            else:
                job = message_pb2.Job(task_id = task.task_id, scanner_id = scanner_list[i].id,
                                      type = task.type, ip = task.ip,
                                      port_begin = task.port_begin, port_end = task.port_begin +  unit_num - 1,
                                      num = unit_num, seq_ran = task.seq_ran)
                task.port_begin += unit_num
                if i == job_num -1:
                    assert job.port_end == task.port_end
            if scanner_list[i].id in scanner_job_dict:
                scanner_job_dict[scanner_list[i].id].append(job)
            else:
                scanner_job_dict[scanner_list[i].id] = [job]
            scanner_list[i].running_units += job.num
        scanner_list.sort(key=lambda scanner: scanner.running_units)
    return scanner_job_dict

# insert jobs to database
def save_jobs(job_dict):
    trans_res = False
    while not trans_res:
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()
        try:
            for dict_id in job_dict:
                job_list = job_dict[dict_id]
                for job in job_list:
                    if job.type == const.T_IP_SCAN:
                        sql = """INSERT INTO portscanner.job (task_id, type, ip, seq_ran, num) 
                                 VALUES(%d, '%s', '%s', '%s', %d)""" \
                              % (job.task_id, job.type, job.ip, job.seq_ran, job.num)
                    elif job.type == const.T_IP_BLOCK_SCAN:
                        sql = """INSERT INTO portscanner.job (task_id, type, ip, ip_end, seq_ran, num) 
                                 VALUES(%d, '%s', '%s', '%s', '%s', %d)""" \
                              % (job.task_id, job.type, job.ip, job.ip_end, job.seq_ran, job.num)                        
                    else:
                        sql = """INSERT INTO portscanner.job (task_id, type, ip, port_begin, port_end, seq_ran, num) 
                                 VALUES(%d, '%s', '%s', %d, %d, '%s', %d)""" \
                              % (job.task_id, job.type, job.ip, job.port_begin, job.port_end, job.seq_ran, job.num) 
                    cursor.execute(sql)
                    job.id = int(cursor.lastrowid)      
            db.commit()                  
        except MySQLdb.Error, e:
            logging.info('MySQLdb.Error in function save_jobs(): %s', e)
            time.sleep(_RETRY_INTERVAL)
            continue
        finally:
            cursor.close()
            db.close() 
        trans_res = True   


# global variable
_DB_HOST, _DB_NAME, _DB_USER, _DB_PWD = get_db_conf()
_RPC_TIMEOUT, _HEARTBEAT_INTERVAL, _CONTROLLER_SLEEP_INTERVAL, \
    _CHECK_ALIVE_INTERVAL, _ALLOW_HEARTBEAT_INTERVAL, _RETRY_INTERVAL, \
    _EST_EXE_JOB_UNIT_INTERVAL, _CHECK_RUNNING_JOB_INTERVAL, \
    _JOB_THREAD_NUM, _REPORT_QUEUE_TIMEOUT = get_time_conf()
_global_quit = False 
report_queue = Queue.Queue()


def run():
    global _global_quit
    global controller_rpc
    print 'Controller Process ID:', os.getpid()
    config_logging()
    cont_port = get_controller_port()
    controller_rpc = message_pb2.early_adopter_create_ControllerRPC_server(ControllerRPC(), cont_port, None, None)
    controller_rpc.start()
    logging.info("Controller starts")
    threads = []
    check_alive_scanner_thread = CheckAliveScannerThread(1)
    #check_running_job_thread = CheckRunningJobThread(2)
    report_thread = ReportThread(3)
    check_alive_scanner_thread.daemon = True
    #check_running_job_thread.daemon = True
    report_thread.daemon = True
    try:
        confirm_alive_scanners()
        check_alive_scanner_thread.start()
        #check_running_job_thread.start()
        report_thread.start()
        threads.append(check_alive_scanner_thread)
        #threads.append(check_running_job_thread)
        threads.append(report_thread)
        while not _global_quit:
            assign_remained_jobs_loop()
            assign_tasks()           
            time.sleep(_CONTROLLER_SLEEP_INTERVAL)
    except KeyboardInterrupt, Exception:   
        _global_quit = True
        for t in threads:
            t.join()
        logging.info("Stopping controller gRPC service")
        controller_rpc.stop()
        logging.info('Controller exits')


if __name__ == '__main__':
    run()
