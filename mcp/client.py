import socket

from common import *

class RawClient(object):
	def __init__(self, host, port=NETPORT):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.addr = (host, port)
		self.credentials = None
		self.leftover = ''
		
	def connect(self):
		self.sock.connect(self.addr)
		
	def set_credentials(self, user):
		self.credentials = user,
		
	def ask(self, *args):
		if len(args) == 0:
			raise ValueError('Need at least 1 argument')
		packet = '\n'.join(args) + '\n\n'
		while packet:
			packet = packet[self.sock.send(packet):]
		while '\n\n' not in self.leftover:
			self.leftover += self.sock.recv(BUFSIZE)
		result, _, self.leftover = self.leftover.partition('\n\n')
		return result
		

class Client(RawClient):
	pass
