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
import collections
import re
import sys
import threading

DEBUG = True
debug_out_lock = threading.Lock()
def debug(*args):
	if DEBUG:
		with debug_out_lock:
			print >>sys.stderr, threading.currentThread().name + ':', ' '.join(map(str,args))

VERBOSE = True
def verbose(*args):
	if VERBOSE:
		print >>sys.stderr, ' '.join(map(str,args))

TIME_FORMAT='hms'

SECOND = 1e9
NETPORT = 8145
BUFSIZE = 1<<12 #4096

class Time(long):
	@classmethod
	def FromNS(cls, ns):
		return Time(ns)
		
	@classmethod
	def FromSec(cls, s):
		return Time(s*SECOND)
		
	def __repr__(self):
		return self.format('s.')
		
	def __str__(self):
		return self.format('hms')
		
	def format(self, f):
		if f == 'hms':
			m,s = divmod(self/SECOND, 60)
			h,m = divmod(m,60)
			return '%d:%02d:%02d' % (h,m,s) if h else '%d:%02d' % (m,s)
		elif f == 's.':
			return '%f' % (self / float(SECOND))
			
def uri(path):
	return path if re.match('[a-zA-Z0-9]+://.*', path) else 'file://' + path

class PObject(object):
	def __init__(self):
		self.callbacks = collections.defaultdict(list)
	
	def connect(self, which, func, *args, **kwargs):
		self.callbacks[which].append((func,args,kwargs))
		
	def emit(self, signal, *args):
		for f,a,k in self.callbacks[signal]:
			f(*(args+a), **k)
		
