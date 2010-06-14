from common import *
from player import Error as PlayerError
import bgthread

import collections
import socket
import traceback

NetFormat = str

class ConnectionThread(bgthread.BgThread):
	def main(self, commandmap, sock, address):
		self.sock = sock
		self.name = "Client %s:%i" % address
		debug('connected')
		for cmd, args in self.recv_delimited():
			debug('called', cmd, args)
			if cmd == 'close':
				break
			elif cmd == 'quit':
				self.respond(None)
				commandmap[cmd](*args) #quit()
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
				debug('Responding with result', repr(result))
				self.respond(None, result)
		sock.close()
		debug('disconnected')
	
	def recv_delimited(self):
		delimiter = '\n\n'
		buffer = self.sock.recv(BUFSIZE)
		buff2 = ''
		while buffer:
			buff2 += buffer
			while delimiter in buff2:
				cmd, _, buff2 = buff2.partition(delimiter)
				cmd = cmd.split('\n')
				yield cmd[0], cmd[1:]
			try:
				buffer = self.sock.recv(BUFSIZE)
			except socket.error:
				buffer = ''
		
	def respond(self, err=None, payload=None):
		if payload is not None:
			self.sock.send(NetFormat(payload) + '\n')
		if err is None:
			self.sock.send('OK\n\n')
		else:
			self.sock.send('ERR: %s\n\n' % err)
		
class NetThread(bgthread.BgThread):
	name = "NetworkThread"
	
	def __init__(self, *args, **kwargs):
		bgthread.BgThread.__init__(self, *args, **kwargs)
		self.dependencies = {'commandmap':self.on_set_commandmap}
		
	def main(self, confitems):
		config = dict(confitems)
		host = config.get('listen-host', 'localhost')
		port = config.get('listen-port', 8145)
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
		sock.bind((host, port))
		sock.listen(5)
		while True:
			conn, addr = sock.accept()
			c = ConnectionThread(self.commandmap, conn, addr)
			c.start()
			
	def on_set_commandmap(self, commandmap):
		self.commandmap = commandmap
			
	def quit(self):
		pass
	
