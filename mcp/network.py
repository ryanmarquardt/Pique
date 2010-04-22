from common import *
import thread

import socket
import traceback

class ConnectionThread(thread.BgThread):
	def main(self, commandmap, sock, address):
		self.name = "Client %s:%i" % address
		s = sock.makefile()
		debug('connected')
		for line in s:
			if line == 'close':
				break
			try:
				commandmap[line.strip()]()
			except:
				tb = traceback.format_exc()
				s.write(tb)
				debug(tb)
				break
			else:
				s.write('OK\n')
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
	
