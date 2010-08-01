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
import socket
import time

from common import *

class RawClient(object):
	def __init__(self, host, port=NETPORT):
		self.addr = (host, port)
		self.credentials = None
		self.leftover = ''
		
	def connect(self):
		pass
		
	def set_credentials(self, user):
		self.credentials = user,
		
	def ask(self, *args):
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.connect(self.addr)
		try:
			if len(args) == 0:
				raise ValueError('Need at least 1 argument')
			packet = '\n'.join(args) + '\n\n'
			while packet:
				packet = packet[sock.send(packet):]
			while '\n\n' not in self.leftover:
				buf = sock.recv(BUFSIZE)
				if buf:
					self.leftover += buf
				else:
					raise Exception('Connection Refused')
			result, _, self.leftover = self.leftover.partition('\n\n')
			return result
		finally:
			sock.close()

class Client(RawClient):
	pass
