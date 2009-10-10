#!/usr/bin/python
import os.path
import select
import socket
import subprocess

class config_block:
	def __init__(self,repeat,delay,config):
		self.repeat = repeat
		self.delay = delay
		self.config = config
		
class configuration(dict):
	def __new__(self,name,location=""):
		r = {}
		if not location:
			location = os.path.expanduser("~/.lircrc")
			location = location if os.path.exists(location) else "/etc/lircrc"
		if os.path.exists(location):
			#parse .lircrc file
			cf = [line.partition('#')[0].strip() for line in open(location,"r").readlines() if line]
			while True:
				try:
					b, e = cf.index('begin'), cf.index('end')
				except ValueError:
					break
				block = cf[b+1:e]
				del cf[b:e+1]
				data = dict((k.rstrip(),v.lstrip()) for k,_,v in [s.partition('=') for s in block])
				if data.get('prog',name) == name:
					remote = data.get('remote','*')
					button = data.get('button','*')
					repeat = int(data.get('repeat',0))
					delay = int(data.get('delay',0))
					config = data.get('config','')
					if remote not in r.keys():
						r[remote] = {}
					r[remote][button] = config_block(repeat,delay,config)
			return r
		else:
			raise OSError('Configuration path not found: ' + location)
		
class client:
	def __init__(self,name,conf="",dev="/dev/lircd"):
		self.dev = dev
		if not os.path.exists(dev):
			raise OSError("No such socket")
		self.sock = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
		try:
			self.sock.connect(dev)
		except:
			raise OSError("Unable to connect to device %s." % dev)
		self.buffer = ''
		self.conf_file = conf
		self.prog_name = name
		self.reload()

	def reload(self):
		self.config = configuration(self.prog_name,self.conf_file)

	def __nonzero__(self):
		try:
			self.sock.fileno()
			return True
		except:
			return False
			
	def read(self):
		while True:
			while '\n' not in self.buffer and self:
				r,w,e = select.select([self.sock],[],[])
				if r:
					data = self.sock.recv(4096)
					if data:
						self.buffer = self.buffer + data
					else:
						self.sock.close()
						return
			while '\n' in self.buffer:
				line, _, self.buffer = self.buffer.partition('\n')
				code, repeat, button, rc = line.split(' ',3)
				repeat = int(repeat,16)
				if rc in self.config.keys() and button in self.config[rc].keys():
					block = self.config[rc][button]
				elif button in self.config['*'].keys():
					block = self.config['*'][button]
				else:
					continue
				if (repeat==0) or ((block.repeat > 0) and (repeat > block.delay) and (repeat % block.repeat == 0)):
					return block.config

if __name__=='__main__':
	pass
