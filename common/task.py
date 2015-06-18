import MySQLdb
import ConfigParser
import logging
import math
import json

import const
import message_pb2

class Task:
    def __init__(self, task_id = None, type = None, status = None, ip = None, seq_ran = None, submit_time = None, finish_time = None):
        self.task_id = task_id
        self.type = type
        self.status = status
        self.ip = ip
        self.seq_ran = seq_ran
        self.submit_time = submit_time
        self.finish_time = finish_time

    def search(self, page):
        task_list = []
        total_page = 0
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()       
        try:
            sql = """SELECT id, type, status, date_format(submit_time, '%Y-%m-%d %H:%i:%S.%f') submit_time, 
                     date_format(finish_time, '%Y-%m-%d %H:%i:%S.%f') finish_time FROM portscanner.task where 1=1 """
            cond_list = []
            if self.task_id is not None:
                cond_list.append("and id = %d" % self.task_id)
            if self.type != const.T_ALL:
                cond_list.append("and type = '%s'" % self.type)
            if self.status != const.T_ALL:
                cond_list.append("and status = '%s'" % self.status) 
            cond_list.append("order by id desc limit %d, %d" % ((page - 1) * const.PAGE_ITEM, const.PAGE_ITEM))
            sql += " ".join(cond_list)  
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                t = Task(task_id = row[const.C_ID], type = row[const.C_TYPE], status = row[const.C_STATUS], 
                         submit_time = timestamp_format(row[const.C_SUBMIT_TIME]), 
                         finish_time = timestamp_format(row[const.C_FINISH_TIME]))
                task_list.append(t)  
            sql = "SELECT count(1) total_num FROM portscanner.task where 1=1 "
            cond_list = []
            if self.task_id is not None:
                cond_list.append("and id = %d" % self.task_id)
            if self.type != const.T_ALL:
                cond_list.append("and type = '%s'" % self.type)
            if self.status != const.T_ALL:
                cond_list.append("and status = '%s'" % self.status) 
            cond_list.append("order by id desc")
            sql += " ".join(cond_list) 
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                total_page = int(math.ceil(float(row["total_num"]) / const.PAGE_ITEM))
            if total_page == 0:
                total_page = 1      
        except MySQLdb.Error, e:
            #logging.info('MySQLdb.Error in function Task.search(): %s', e)
            print e
        finally:
            cursor.close()
            db.close()
        return task_list, total_page


class IpTask(Task):
    def __init__(self, task_id = None, type = None, status = None, ip = None, \
                 seq_ran = None, submit_time = None, finish_time = None):
        Task.__init__(self, task_id, type, status, ip, seq_ran, submit_time, finish_time)
        self.num = 1

    def insert(self):
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()
        try:
            sql = """insert into portscanner.task (type, status, ip, seq_ran, submit_time) 
                     values('%s', '%s', '%s', '%s', CURRENT_TIMESTAMP(1))""" % (self.type, self.status, self.ip, self.seq_ran)
            cursor.execute(sql)
            db.commit()
        except MySQLdb.Error, e:
            #logging.info('MySQLdb.Error in function IpTask.insert(): %s', e)
            print e
            return str(e)
        finally:
            cursor.close()
            db.close()
        return 'success'

    def get_task(self):
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()
        try:
            sql = """select id, type, status, ip, seq_ran, date_format(submit_time, '%%Y-%%m-%%d %%H:%%i:%%S.%%f') submit_time, 
                     date_format(finish_time, '%%Y-%%m-%%d %%H:%%i:%%S.%%f') finish_time from portscanner.task where id = %d""" % self.task_id
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                self.type = row[const.C_TYPE]
                self.status = row[const.C_STATUS]
                self.ip = row[const.C_IP]
                self.seq_ran = row[const.C_SEQ_RAN]
                self.submit_time = timestamp_format(row[const.C_SUBMIT_TIME])
                self.finish_time = timestamp_format(row[const.C_FINISH_TIME])
        except MySQLdb.Error, e:
            #logging.info('MySQLdb.Error in function IpTask.get_task(): %s', e)
            print e
        finally:
            cursor.close()
            db.close() 

    def get_job_list(self, page):
        job_list = []
        total_page = 0
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor() 
        try:
            sql = """SELECT id, IFNULL(scanner_id, 0) scanner_id, IFNULL(status, '') status, ip, num, date_format(finish_time, '%%Y-%%m-%%d %%H:%%i:%%S.%%f') finish_time FROM portscanner.job 
                     where task_id = %d order by id limit %d, %d""" % (self.task_id, (page - 1) * const.PAGE_ITEM, const.PAGE_ITEM)   
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                job = message_pb2.Job(id = row[const.C_ID], scanner_id = row[const.C_SCANNER_ID], status = row[const.C_STATUS], 
                                      ip = row[const.C_IP], num = row[const.C_NUM], finish_time = timestamp_format(row[const.C_FINISH_TIME])) 
                job_list.append(job)   
            sql = """SELECT count(1) total_num FROM portscanner.job 
                     where task_id = %d order by id""" % self.task_id
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                total_page = int(math.ceil(float(row["total_num"]) / const.PAGE_ITEM))
            if total_page == 0:
                total_page = 1        
        except MySQLdb.Error, e:
            #logging.info('MySQLdb.Error in function Task.get_job_list(): %s', e)
            print e
        finally:
            cursor.close()
            db.close()
        return job_list, total_page

    def get_report_list(self, page):
        report_list = []
        total_page = 0
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor() 
        try:
            sql = """SELECT ip, res FROM portscanner.report 
                     where task_id = %d order by ip limit %d, %d""" % (self.task_id, (page - 1) * const.PAGE_ITEM, const.PAGE_ITEM)   
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                report = message_pb2.ReportItem(ip = row[const.C_IP], res = row[const.C_RES]) 
                report_list.append(report)   
            sql = """SELECT count(1) total_num FROM portscanner.report 
                     where task_id = %d order by ip""" % self.task_id
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                total_page = int(math.ceil(float(row["total_num"]) / const.PAGE_ITEM))
            if total_page == 0:
                total_page = 1        
        except MySQLdb.Error, e:
            #logging.info('MySQLdb.Error in function Task.get_job_list(): %s', e)
            print e
        finally:
            cursor.close()
            db.close()
        return report_list, total_page
     

class IpBlockTask(Task):
    def __init__(self, task_id = None, type = None, status = None, ip = None, ip_end = None, \
                 seq_ran = None, submit_time = None, finish_time = None):
        Task.__init__(self, task_id, type, status, ip, seq_ran, submit_time, finish_time)
        self.ip_end = ip_end
        if ip_end is not None:
            self.num = int(ip_end.split('.')[3]) - int(ip.split('.')[3]) + 1

    def insert(self):
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()
        try:
            sql = """insert into portscanner.task (type, status, ip, ip_end, seq_ran, submit_time) 
                     values('%s', '%s', '%s', '%s', '%s', CURRENT_TIMESTAMP(1))""" % (self.type, self.status, self.ip, self.ip_end, self.seq_ran)
            cursor.execute(sql)
            db.commit()
        except MySQLdb.Error, e:
            #logging.info('MySQLdb.Error in function IpTask.insert(): %s', e)
            print e
            return str(e)
        finally:
            cursor.close()
            db.close()
        return 'success'

    def get_task(self):
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()
        try:
            sql = """select id, type, status, ip, ip_end, seq_ran, date_format(submit_time, '%%Y-%%m-%%d %%H:%%i:%%S.%%f') submit_time, 
                     date_format(finish_time, '%%Y-%%m-%%d %%H:%%i:%%S.%%f') finish_time from portscanner.task where id = %d""" % self.task_id
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                self.type = row[const.C_TYPE]
                self.status = row[const.C_STATUS]
                self.ip = row[const.C_IP]
                self.ip_end = row[const.C_IP_END]
                self.seq_ran = row[const.C_SEQ_RAN]
                self.submit_time = timestamp_format(row[const.C_SUBMIT_TIME])
                self.finish_time = timestamp_format(row[const.C_FINISH_TIME])
        except MySQLdb.Error, e:
            #logging.info('MySQLdb.Error in function IpTask.get_task(): %s', e)
            print e
        finally:
            cursor.close()
            db.close() 

    def get_job_list(self, page):
        job_list = []
        total_page = 0
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor() 
        try:
            sql = """SELECT id, IFNULL(scanner_id, 0) scanner_id, IFNULL(status, '') status, ip, ip_end, num, date_format(finish_time, '%%Y-%%m-%%d %%H:%%i:%%S.%%f') finish_time  FROM portscanner.job 
                     where task_id = %d order by id limit %d, %d""" % (self.task_id, (page - 1) * const.PAGE_ITEM, const.PAGE_ITEM)   
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                job = message_pb2.Job(id = row[const.C_ID], scanner_id = row[const.C_SCANNER_ID], status = row[const.C_STATUS], 
                                      ip = row[const.C_IP], ip_end = row[const.C_IP_END], num = row[const.C_NUM], 
                                      finish_time = timestamp_format(row[const.C_FINISH_TIME])) 
                job_list.append(job)   
            sql = """SELECT count(1) total_num FROM portscanner.job 
                     where task_id = %d order by id""" % self.task_id
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                total_page = int(math.ceil(float(row["total_num"]) / const.PAGE_ITEM))
            if total_page == 0:
                total_page = 1        
        except MySQLdb.Error, e:
            #logging.info('MySQLdb.Error in function Task.get_job_list(): %s', e)
            print e
        finally:
            cursor.close()
            db.close()
        return job_list, total_page

    def get_report_list(self, page):
        report_list = []
        total_page = 0
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor() 
        try:
            sql = """SELECT ip, res FROM portscanner.report 
                     where task_id = %d order by ip limit %d, %d""" % (self.task_id, (page - 1) * const.PAGE_ITEM, const.PAGE_ITEM)   
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                report = message_pb2.ReportItem(ip = row[const.C_IP], res = row[const.C_RES]) 
                report_list.append(report)   
            sql = """SELECT count(1) total_num FROM portscanner.report 
                     where task_id = %d order by ip""" % self.task_id
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                total_page = int(math.ceil(float(row["total_num"]) / const.PAGE_ITEM))
            if total_page == 0:
                total_page = 1        
        except MySQLdb.Error, e:
            #logging.info('MySQLdb.Error in function Task.get_job_list(): %s', e)
            print e
        finally:
            cursor.close()
            db.close()
        return report_list, total_page


class PortTask(Task):
    def __init__(self, task_id = None, type = None, status = None, ip = None, \
                 port_begin = None, port_end = None, seq_ran = None, submit_time = None, finish_time = None):
        Task.__init__(self, task_id, type, status, ip, seq_ran, submit_time, finish_time)
        self.port_begin = port_begin
        self.port_end = port_end
        if port_begin is not None and port_end is not None:
            self.num = int(port_end) - int(port_begin) + 1

    def insert(self):
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()
        try:
            sql = """insert into portscanner.task (type, status, ip, port_begin, port_end, seq_ran, submit_time) 
                     values('%s', '%s', '%s', %d, %d, '%s', CURRENT_TIMESTAMP(1))""" \
                  % (self.type, self.status, self.ip, self.port_begin, self.port_end, self.seq_ran)
            cursor.execute(sql)
            db.commit()
        except MySQLdb.Error, e:
            #logging.info('MySQLdb.Error in function IpTask.insert(): %s', e)
            print e
            return str(e)
        finally:
            cursor.close()
            db.close()
        return 'success'

    def get_task(self):
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor()
        try:
            sql = """select id, type, status, ip, port_begin, port_end, seq_ran, date_format(submit_time, '%%Y-%%m-%%d %%H:%%i:%%S.%%f') submit_time, 
            finish_time from portscanner.task where id = %d""" % self.task_id
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                self.type = row[const.C_TYPE]
                self.status = row[const.C_STATUS]
                self.ip = row[const.C_IP]
                self.port_begin = row[const.C_PORT_BEGIN]
                self.port_end = row[const.C_PORT_END]
                self.seq_ran = row[const.C_SEQ_RAN]
                self.submit_time = timestamp_format(row[const.C_SUBMIT_TIME])
                self.finish_time = timestamp_format(row[const.C_FINISH_TIME])
        except MySQLdb.Error, e:
            #logging.info('MySQLdb.Error in function IpTask.get_task(): %s', e)
            print e
        finally:
            cursor.close()
            db.close() 

    def get_job_list(self, page):
        job_list = []
        total_page = 0
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor() 
        try:
            sql = """SELECT id, IFNULL(scanner_id, 0) scanner_id, IFNULL(status, '') status, ip, port_begin, port_end, num, 
                     date_format(finish_time, '%%Y-%%m-%%d %%H:%%i:%%S.%%f') finish_time FROM portscanner.job 
                     where task_id = %d order by id limit %d, %d""" % (self.task_id, (page - 1) * const.PAGE_ITEM, const.PAGE_ITEM)   
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                job = message_pb2.Job(id = row[const.C_ID], scanner_id = row[const.C_SCANNER_ID], status = row[const.C_STATUS], 
                                      ip = row[const.C_IP], port_begin = row[const.C_PORT_BEGIN], port_end = row[const.C_PORT_END], 
                                      num = row[const.C_NUM], finish_time = timestamp_format(row[const.C_FINISH_TIME]))  
                job_list.append(job)   
            sql = """SELECT count(1) total_num FROM portscanner.job 
                     where task_id = %d order by id""" % self.task_id
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                total_page = int(math.ceil(float(row["total_num"]) / const.PAGE_ITEM))
            if total_page == 0:
                total_page = 1        
        except MySQLdb.Error, e:
            #logging.info('MySQLdb.Error in function Task.get_job_list(): %s', e)
            print e
        finally:
            cursor.close()
            db.close()
        return job_list, total_page

    def get_report_list(self, page):
        report_list = []
        total_page = 0
        db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
        cursor = db.cursor() 
        try:
            sql = """SELECT port, res, banner FROM portscanner.report where task_id = %d order by port limit %d, %d""" \
                  % (self.task_id, (page - 1) * const.PAGE_ITEM, const.PAGE_ITEM)   
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                report = message_pb2.ReportItem(port = row[const.C_PORT], res = row[const.C_RES], banner = none_to_empty(row[const.C_BANNER])) 
                report_list.append(report)   
            sql = """SELECT count(1) total_num FROM portscanner.report where task_id = %d order by port""" \
                  % self.task_id
            cursor.execute(sql)
            fields = map(lambda x:x[0], cursor.description)
            result = [dict(zip(fields,row))   for row in cursor.fetchall()]
            for row in result:
                total_page = int(math.ceil(float(row["total_num"]) / const.PAGE_ITEM))
            if total_page == 0:
                total_page = 1        
        except MySQLdb.Error, e:
            #logging.info('MySQLdb.Error in function Task.get_job_list(): %s', e)
            print e
        finally:
            cursor.close()
            db.close()
        return report_list, total_page


def get_scanner_list(page):
    scanner_list = []
    total_page = 0
    db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
    cursor = db.cursor()    
    try:
        sql = """SELECT a.id, a.ip, a.port, a.status, IFNULL(SUM(b.num), 0) num,  
                 date_format(update_time, '%%Y-%%m-%%d %%H:%%i:%%S.%%f') update_time
                 FROM portscanner.scanner a LEFT JOIN portscanner.job b 
                 ON a.id = b.scanner_id AND b.status = '%s' 
                 GROUP BY a.id order by a.status, a.id limit %d, %d""" \
              % (const.T_RUNNING, (page - 1) * const.PAGE_ITEM, const.PAGE_ITEM)
        cursor.execute(sql)
        fields = map(lambda x:x[0], cursor.description)
        result = [dict(zip(fields,row))   for row in cursor.fetchall()]
        for row in result:
            scanner = message_pb2.Node(id = row[const.C_ID], ip = row[const.C_IP], port = row[const.C_PORT], 
                                       status = row[const.C_STATUS], running_units = int(row[const.C_NUM]),
                                       update_time = timestamp_format(row[const.C_UPDATE_TIME]))
            scanner_list.append(scanner)
        sql = """SELECT COUNT(1) total_num FROM 
                    (SELECT a.id, a.ip, a.port, a.status, IFNULL(SUM(b.num), 0) num, a.update_time 
                     FROM portscanner.scanner a LEFT JOIN portscanner.job b 
                     ON a.id = b.scanner_id AND b.status = '%s' GROUP BY a.id) b""" % const.T_RUNNING
        cursor.execute(sql)
        fields = map(lambda x:x[0], cursor.description)
        result = [dict(zip(fields,row))   for row in cursor.fetchall()]
        for row in result:
            total_page = int(math.ceil(float(row["total_num"]) / const.PAGE_ITEM))
        if total_page == 0:
            total_page = 1 
    except MySQLdb.Error, e:
        #logging.info('MySQLdb.Error in function Task.get_job_list(): %s', e)
        print e
    finally:
        cursor.close()
        db.close() 
    return scanner_list, total_page

def get_running_scanner_performance():
    scanner_list = []
    db = MySQLdb.connect(_DB_HOST, _DB_USER, _DB_PWD, _DB_NAME)
    cursor = db.cursor()  
    try:
        sql = """SELECT a.id, IFNULL(SUM(b.num), 0) num FROM portscanner.scanner a left join portscanner.job b 
                 on a.id = b.scanner_id and b.status = '%s' where a.status = '%s' group by a.id;""" \
              % (const.T_RUNNING, const.T_RUNNING)
        cursor.execute(sql)
        fields = map(lambda x:x[0], cursor.description)
        result = [dict(zip(fields,row))   for row in cursor.fetchall()]
        for row in result:  
            scanner = {}
            scanner["scanner_id"] = str(row[const.C_ID])
            scanner["running_units"] = int(row[const.C_NUM])
            scanner_list.append(scanner)
    except MySQLdb.Error, e:
        #logging.info('MySQLdb.Error in function Task.get_job_list(): %s', e)
        print e
    finally:
        cursor.close()
        db.close() 
    running_num = len(scanner_list)
    scanner_list = json.dumps(scanner_list)
    return scanner_list, running_num    


def none_to_empty(x):
    if x is None:
        return ''
    else:
        return str(x)

def timestamp_format(x):
    if x is None:
        return ''
    else:
        return str(x)[:-5]

# configure logging
def config_logging():
    logging.basicConfig(level=logging.DEBUG,
                format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                datefmt='%a, %d %b %Y %H:%M:%S',
                filename='../log/task.log',
                filemode='w')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

# get database configuration parameter
def get_db_conf():
    conf = ConfigParser.ConfigParser()   
    conf.read(const.CONF_DIR_FOR_WEB)
    db_host = conf.get(const.DB_SEC, const.DB_HOST)       
    db_name = conf.get(const.DB_SEC, const.DB_NAME)
    db_user = conf.get(const.DB_SEC, const.DB_USER)    
    db_pwd = conf.get(const.DB_SEC, const.DB_PWD)
    return db_host, db_name, db_user, db_pwd

#_DB_HOST, _DB_NAME, _DB_USER, _DB_PWD = get_db_conf()
_DB_HOST = 'localhost'
_DB_NAME = 'portscanner'
_DB_USER = 'securityhacker'
_DB_PWD = '123456'
#config_logging()
