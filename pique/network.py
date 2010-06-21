#!/usr/bin/env python
#
# Copyright (c) 2010, Ryan Marquardt
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without 
# modification, are permitted provided that the following conditions are
# met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the project nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from common import *
from player import Error as PlayerError
import bgthread

import collections
import socket
import traceback

NetFormat = str

class ConnectionThread(bgthread.BgThread, PObject):
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
				debug(func, args)
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
		self.quit()
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
			self.sock.send(NetFormat(payload))
		if err is None:
			self.sock.send('OK\n\n')
		else:
			self.sock.send('ERR: %s\n\n' % err)
			
	def quit(self):
		self.sock.close()
		self.emit('connection-closed', self)
		
class NetThread(bgthread.BgThread, PObject):
	name = "NetworkThread"
	
	def __init__(self, *args, **kwargs):
		bgthread.BgThread.__init__(self, *args, **kwargs)
		self.dependencies = {'commandmap':self.on_set_commandmap}
		self.commands = {
			'ping': self.ping,
		}
		
	def main(self, confitems):
		config = dict(confitems)
		host = config.get('listen-host', 'localhost')
		port = config.get('listen-port', 8145)
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
		sock.bind((host, port))
		sock.listen(5)
		self.clients = set()
		self.connect('new-connection', self.on_new_connection)
		while True:
			self.emit('new-connection', *sock.accept())
			
	def on_new_connection(self, conn, addr):
		c = ConnectionThread(self.commandmap, conn, addr)
		c.connect('connection-closed', self.client_closed)
		self.clients.add(c)
		c.start()
		
	def client_closed(self, client):
		self.clients.discard(client)
			
	def ping(self):
		return None
			
	def on_set_commandmap(self, commandmap):
		self.commandmap = commandmap
			
	def quit(self):
		for c in list(self.clients):
			c.quit()
	
