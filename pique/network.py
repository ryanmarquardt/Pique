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
import rpc
import bgthread

import collections
import socket
import traceback

import SocketServer

NetFormat = str

class NetThread(rpc.ThreadingServer, bgthread.BgThread, PObject):
	name = "NetworkThread"
	def __init__(self, *args, **kwargs):
		bgthread.BgThread.__init__(self, *args, **kwargs)
		self.dependencies = {'commandmap':self.on_set_commandmap}
		self.commands = {}
		
	def main(self, confitems):
		config = dict(confitems)
		host = config.get('listen-host', 'localhost')
		port = config.get('listen-port', NETPORT)
		rpc.ThreadingServer.__init__(self, (host, port))
		self.serve_forever()
		
	def on_call(self, name, *args, **kwargs):
		if name == 'ping':
			return None
		elif name == 'quit':
			rpc.ThreadingServer.shutdown(self)
			self.commandmap['quit']()
		elif name == 'help':
			return self.commandmap[args[0]].__doc__
		else:
			debug(name, args, kwargs)
			func = self.commandmap[name]
			return func(*args, **kwargs)
			
	def on_set_commandmap(self, commandmap):
		self.commandmap = commandmap
