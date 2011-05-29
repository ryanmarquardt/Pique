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
import optparse
import socket
import sys
import time

from common import *
import rpc

class Client(rpc.Client):
	def __init__(self):
		rpc.Client.__init__(self)
		self.credentials = None
		
	def connect(self, host, port=NETPORT):
		rpc.Client.connect(self, (host, port))
				
	def set_credentials(self, user):
		self.credentials = user,
		
def add_default_options(parser):
	parser.add_option('-H', '--host', dest='host', default='localhost',
	  help='IP address of the server'),
	parser.add_option('-p', '--port', dest='port', type='int',
	  help='Port to connect to'),
	parser.add_option('--no-conf', action='store_true', dest='noconf',
	  help='Do not read any configuration files'),
	
def parse_args(parser):
	options, args = parser.parse_args()
	if options.port is None:
		if options.noconf:
			options.port = NETPORT
		else:
			import ConfigParser
			import os.path
			conf = ConfigParser.SafeConfigParser()
			conf.readfp(open(os.path.join(os.path.dirname(__file__), 'default.conf')))
			conf.read([os.path.expanduser('~/.config/pique/pique.conf')])
			try:
				options.port = conf.getint('Network', 'listen-port')
			except ConfigParser.Error:
				options.port = NETPORT
	return options,args
