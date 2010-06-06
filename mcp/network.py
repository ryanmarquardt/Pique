from common import *
from player import Error as PlayerError
import thread

import collections
import socket
import traceback

NetFormat = str

def recv_delimited(sock, delimiter):
	buffer = sock.recv(BUFSIZE)
	buff2 = ''
	while buffer:
		buff2 += buffer
		while delimiter in buff2:
			cmd, _, buff2 = buff2.partition(delimiter)
			cmd = cmd.split('\n')
			yield cmd[0], cmd[1:]
		try:
			buffer = sock.recv(BUFSIZE)
		except socket.error:
			buffer = ''

class ConnectionThread(thread.BgThread):
	def main(self, commandmap, sock, address):
		self.sock = sock
		self.name = "Client %s:%i" % address
		debug('connected')
		for cmd, args in recv_delimited(sock, '\n\n'):
			debug('called', cmd, args)
			if cmd == 'close':
				break
			try:
				func = commandmap[cmd]
			except KeyError:
				self.respond('No such command')
				continue
			try:
				result = func(*args)
			except PlayerError, e:
				debug(e)
				self.respond(e)
			except:
				tb = traceback.format_exc()
				debug('Error:', tb)
				self.respond('Unknown Error', tb)
				continue
			else:
				debug('OK')
				self.respond(None, result)
		sock.close()
		debug('disconnected')
		
	def respond(self, err=None, payload=None):
		if payload is not None:
			self.sock.send(NetFormat(payload) + '\n')
		if err is None:
			self.sock.send('OK\n\n')
		else:
			self.sock.send('ERR: %s\n\n' % err)
		
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
	
