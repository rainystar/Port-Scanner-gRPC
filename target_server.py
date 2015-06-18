import socket
import time
import signal
import sys
import select

usage = "usage: python test_server.py number_of_ports [port1 port2 port3 ...]"
connfd_list = []
def handler(signum, frame):
	#print 'Signal handler called with signal', signum
	for s in connfd_list:
		s.close()
	print 'Server socket closed'
	exit(1)

if __name__ == "__main__":	
	host = socket.gethostname()
	host_ip = socket.gethostbyname(host)

	if len(sys.argv) < 3:
		print "Insufficient arguments"
		print(usage)
		exit(0)
	if len(sys.argv) - 2 != int(sys.argv[1]):
		print "The argument of port number is not equal to the number of ports input"
		print(usage)
		exit(0)

	if sys.platform == "darwin":
		print "Host ip address is", host_ip	
	elif sys.platform == "linux" or "linux2":
		print "Please check host ip address using command 'ifconfig' manually"
	num_ports = int(sys.argv[1])
	for i in range(num_ports):
		port = int(sys.argv[i+2])
		serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		serversocket.bind(('0.0.0.0', port))
		serversocket.listen(5)
		connfd_list.append(serversocket)
		print "Host port #%d is %d" % (i, port)

	signal.signal(signal.SIGINT, handler)
	while True:
		print("Now listening")
		read_sockets, write_sockets, error_sockets = select.select(connfd_list, [], [])
		for listen_fd in read_sockets:
			conn_socket,addr = listen_fd.accept()
			peer = conn_socket.getpeername();
			print("Connection from %s:%d" % (str(peer[0]), peer[1]))
			currentTime = time.ctime(time.time()) + "\r\n"
			msg_send = "Hello " + str(peer[0]) + ":" + str(peer[1]) + "!\r\nThe current time is: " + currentTime
			conn_socket.send(msg_send.encode('ascii'))
			conn_socket.close()
