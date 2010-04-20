import socket

import thread

class ConnectionThread(thread.BgThread):
	def main(self, commandmap, sock, address):
		s = sock.makefile()
		debug('connected to:', address)
		for line in s:
			try:
				commandmap(line.strip())
			except:
				s.write(traceback.format_exc())
				break
			else:
				s.write('OK\n')
		s.close()
		sock.close()
		debug('connection closed:', address)
		
class NetThread(thread.BgThread):
	def main(self, config, commandmap):
		host = config.get('Network', 'listen-host')
		port = config.getint('Network', 'listen-port')
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.bind((host, port))
		sock.listen(5)
		while True:
			conn, addr = sock.accept()
			ConnectionThread(commandmap, conn, addr).start()
	
