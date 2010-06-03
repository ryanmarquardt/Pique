from common import *
import thread

import socket
import traceback

BUFSIZE = 1e12 #4096

class ConnectionThread(thread.BgThread):
	def main(self, commandmap, sock, address):
		self.name = "Client %s:%i" % address
		debug('connected')
		buffer = collections.deque()
		while sock or buffer:
			buffer.append(sock.recv(BUFSIZE))
			success = ''
			line = ''
			while not success:
				more, success, leftover = buffer.pop().partition('\n')
				line += more
			if leftover:
				buffer.appendleft(leftover)
			debug('called', line.strip())
			if line == 'close':
				break
			try:
				commandmap[line.strip()]()
			except:
				tb = traceback.format_exc()
				while tb:
					tb = tb[s.send(tb):]
				debug('Error:', tb)
				break
			else:
				debug('OK')
				s.write('OK\n')
				s.flush()
		s.close()
		sock.close()
		debug('disconnected')
		
class NetThread(thread.BgThread):
	name = "NetworkThread"
	def main(self, config, commandmap):
		host = config.get('Network', 'listen-host')
		port = config.getint('Network', 'listen-port')
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
		sock.bind((host, port))
		sock.listen(5)
		while True:
			conn, addr = sock.accept()
			c = ConnectionThread(commandmap, conn, addr)
			c.start()
			
	def quit(self):
		pass
	
