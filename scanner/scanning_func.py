import ConfigParser
import sys
from socket import *
import os, signal
import logging
import random
from scapy.all import *

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from common import const
from common import message_pb2

_SYN_ACK = 0x12
_RST_ACK = 0x14

class Scanner:
    def __init__(self):
        self.host = socket.gethostname()
        self.ip = gethostbyname(self.host)

    def check_ip_alive(self, address):
        ret = os.system('ping -c 1 -W 3 ' + address + " > /dev/null")
        if ret != 0:
            report_list = [message_pb2.ReportItem(ip = address, res = const.SCAN_OFF)]
        else:
            report_list = [message_pb2.ReportItem(ip = address, res = const.SCAN_ON)]
        return report_list

    def check_block_ip_alive(self, ip_start, ip_end, seq):
        ip_base, range_list = self.ip_order_shuffle(ip_start, ip_end, seq)
        report_list = []
        for i in range_list:
			host = ip_base + '.' + str(i)
			report_list.extend(self.check_ip_alive(host))
        return report_list

    def ip_order_shuffle(self, ip_start, ip_end, seq):
		ip_start = ip_start.split('.')
		ip_end = ip_end.split('.')
		ip_base = '.'.join(ip_start[0 : 3])
		s = list(range(int(ip_start[3]), int(ip_end[3]) + 1))
		if seq == const.SCAN_RAN:
			random.shuffle(s)
		return ip_base, s

    def port_scan(self, ip, port_start, port_end, seq, type):
        port_list = self.port_order_shuffle(port_start, port_end, seq)
        report_list = []
        for i in port_list:
			if type == const.T_PORT_SCAN:
				report_list.append(self.normal_scan(ip, i))
			elif type == const.T_SYN_SCAN:
				report_list.append(self.SYN_scan(ip, i))
			else:
				report_list.append(self.FIN_scan(ip, i))
        return report_list

    def port_order_shuffle(self, port_start, port_end, seq):
		s = list(range(port_start, port_end + 1))
		if seq == const.SCAN_RAN:
			random.shuffle(s)
		return s

    def normal_scan(self, dest_ip, dest_port):
        sock = self.connect_to(dest_ip, dest_port)
        if sock:
            ban = self.grab_banner(sock)
            if ban:
                return message_pb2.ReportItem(port = dest_port, res = const.SCAN_ON, banner = str(ban))
            else:
                return message_pb2.ReportItem(port = dest_port, res = const.SCAN_ON, banner = '')
            sock.close()
        else:
            return message_pb2.ReportItem(port = dest_port, res = const.SCAN_OFF)

    def connect_to(self, ip, port):
        try:
			s = socket.socket(AF_INET, SOCK_STREAM)
			s.settimeout(_CONN_TIMEOUT)
			s.connect((ip, port))
			return s
        except:
            s.close()
            return None

    def grab_banner(self, sock):
		try:
			banner = sock.recv(1024).decode("utf-8")
			return banner;
		except:
			return None

    def SYN_scan(self, dest_ip, dest_port):
        src_port = _SEND_PORT
        ip = IP(dst=dest_ip, ttl = 16)
        syn = TCP(sport=src_port, dport=int(dest_port), flags='S', seq=88, options=[('Timestamp',(0,0))])
        rst = TCP(sport=src_port, dport=int(dest_port), flags='R', seq=89, options=[('Timestamp',(0,0))])
        syn_resp = sr1(ip/syn, timeout=_SYN_TIMEOUT, verbose = False)
        if not syn_resp or str(type(syn_resp))=="<type 'NoneType'>":
            #print("SYN Scan is Filtered1")
            return message_pb2.ReportItem(port = dest_port, res = const.SCAN_FILTER)
        elif (syn_resp.haslayer(TCP)):
            if (syn_resp.getlayer(TCP).flags == _SYN_ACK):
                send_rst = send(ip/rst, verbose = False)
                return message_pb2.ReportItem(port = dest_port, res = const.SCAN_ON)
            elif (syn_resp.getlayer(TCP).flags == _RST_ACK):
                return message_pb2.ReportItem(port = dest_port, res = const.SCAN_OFF)
            else:
                #print 'Exception: syn_resp.getlayer(TCP).flags = %x' % syn_resp.getlayer(TCP).flags
                return message_pb2.ReportItem(port = dest_port, res = const.SCAN_FILTER)
        else:
            #print("SYN Scan is Filtered2")
            return message_pb2.ReportItem(port = dest_port, res = const.SCAN_FILTER)

    def FIN_scan(self, dest_ip, dest_port):
        src_port = _SEND_PORT
        ip = IP(dst=dest_ip)
        fin = TCP(sport=src_port, dport=int(dest_port), flags='F', seq=88)
        rst = TCP(sport=src_port, dport=int(dest_port), flags='R')
        fin_resp = sr1(ip/fin, timeout=_FIN_TIMEOUT, verbose = False)
        if not fin_resp or str(type(fin_resp))=="<type 'NoneType'>":
            return message_pb2.ReportItem(port = dest_port, res = const.SCAN_ON)
        elif (fin_resp.haslayer(TCP)):
            if(fin_resp.getlayer(TCP).flags == _RST_ACK):
                return message_pb2.ReportItem(port = dest_port, res = const.SCAN_OFF)
        else:
            #print("FIN Scan is Filtered")
            return message_pb2.ReportItem(port = dest_port, res = const.SCAN_FILTER)

# get time setting parameter
def get_time_conf():
    conf = ConfigParser.ConfigParser()    
    conf.read(const.CONF_DIR)
    send_port = int(conf.get(const.SCANNING_SEC, const.SCANNING_SEND_PORT))
    conn_timeout = float(conf.get(const.TIME_SEC, const.SCANNING_CONN_TIMEOUT))
    syn_timeout = float(conf.get(const.TIME_SEC, const.SCANNING_SYN_TIMEOUT))
    fin_timeout = float(conf.get(const.TIME_SEC, const.SCANNING_FIN_TIMEOUT))
    return send_port, conn_timeout, syn_timeout, fin_timeout

_SEND_PORT, _CONN_TIMEOUT, _SYN_TIMEOUT, _FIN_TIMEOUT = get_time_conf()

def main():
	scanner = Scanner()
	print("Port scan")
	if len(sys.argv) == 2:
		dest_ip = str(sys.argv[1])
	else:
		dest_ip = scanner.ip
	print("Host ip is %s\r\n" % scanner.ip)
	dest_port = 9877
	scanner.normal_scan(dest_ip, dest_port)
	scanner.check_ip_alive(dest_ip)
	scanner.check_block_ip_alive("172.24.30.180", "172.24.30.190", False)
	scanner.SYN_scan(dest_ip, dest_port)
	scanner.FIN_scan(dest_ip, dest_port)

if __name__ == "__main__":
	main()
