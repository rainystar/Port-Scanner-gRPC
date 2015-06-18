CONF_DIR = './config/configuration.ini'
CONF_DIR_FOR_WEB = '../config/configuration.ini'

# controller info
CONT_SEC = 'controller'
CONT_IP = 'cont_ip'
CONT_PORT = 'cont_port'

# database connection
DB_SEC = 'database'
DB_HOST = 'db_host'
DB_NAME = 'db_name'
DB_USER = 'db_user'
DB_PWD = 'db_pwd'

# database column name
C_ID = 'id'
C_TASK_ID = 'task_id'
C_SCANNER_ID = 'scanner_id'
C_TYPE = 'type'
C_STATUS = 'status'
C_IP = 'ip'
C_IP_END = 'ip_end'
C_PORT = 'port'
C_PORT_BEGIN = 'port_begin'
C_PORT_END = 'port_end'
C_NUM = 'num'
C_SEQ_RAN = 'seq_ran'
C_SUBMIT_TIME = 'submit_time'
C_FINISH_TIME = 'finish_time'
C_UPDATE_TIME = 'update_time'
C_RES = 'res'
C_BANNER = 'banner'

# task type
T_IP_SCAN = 'IP_SCAN'
T_IP_BLOCK_SCAN = 'IP_BLOCK_SCAN'
T_PORT_SCAN = 'NORMAL_SCAN'
T_SYN_SCAN = 'SYN_SCAN'
T_FIN_SCAN = 'FIN_SCAN'

# task status
T_ALL = 'ALL'
T_SUBMITTED = 'SUBMITTED'
T_RUNNING = 'RUNNING'
T_FINISHED = 'FINISHED'

# scanner status
S_RUNNING = 'RUNNING'
S_STOPPED = 'STOPPED'

# scan method
SCAN_SEQ = 'SEQ'
SCAN_RAN = 'RAN'

# scan result
SCAN_ON = 'ON'
SCAN_OFF = 'OFF'
SCAN_FILTER = 'FILTER'

# time parameter
TIME_SEC = 'time'
TIME_RPC_TIMEOUT = 'rpc_timeout'
TIME_HEARTBEAT_INTERVAL = 'heartbeat_interval'
TIME_CONTROLLER_SLEEP_INTERVAL = 'controller_sleep_interval'
TIME_CHECK_ALIVE_INTERVAL = 'check_alive_interval'
TIME_ALLOW_HEARTBEAT_INTERVAL = 'allow_heartbeat_interval'
TIME_JOB_QUEUE_TIMEOUT = 'job_queue_timeout'
TIME_REPORT_QUEUE_TIMEOUT = 'report_queue_timeout'
TIME_RETRY_INTERVAL = 'retry_interval'
TIME_JOB_THREAD_NUM = 'job_thread_num'
TIME_EST_EXE_JOB_UNIT_INTERVAL = 'est_exe_job_unit_interval'
TIME_CHECK_RUNNING_JOB_INTERVAL = 'check_running_job_interval'
SCANNING_SEC = 'scanning'
SCANNING_SEND_PORT = 'send_port'
SCANNING_CONN_TIMEOUT = 'scan_conn_timeout'
SCANNING_SYN_TIMEOUT = 'scan_syn_timeout'
SCANNING_FIN_TIMEOUT = 'scan_fin_timeout'

# display parameter
PAGE_ITEM = 10


