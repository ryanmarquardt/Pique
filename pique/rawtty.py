#!/usr/bin/python
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

import Queue
import signal
import sys
import termios
import threading

MODS = (
	(';2','<shift>'),
	(';3','<alt>'),
	(';4','<shift><alt>'),
	(';5','<control>'),
	(';6','<shift><control>'),
	(';7','<control><alt>'),
	(';8','<control><shift><alt>'),
)

Sequences = {
	'\x1b[D': 'left',
	'\x1b[C': 'right',
	'\x1b[B': 'down',
	'\x1b[A': 'up',
	'\x1b[2~': 'insert',
	'\x1b[3~': 'delete',
	'\x1b[5~': 'page_up',
	'\x1b[6~': 'page_down',
	'\x1bOP': 'f1',
	'\x1bOQ': 'f2',
	'\x1bOR': 'f3',
	'\x1bOS': 'f4',
	'\x1b[15~': 'f5',
	'\x1b[17~': 'f6',
	'\x1b[18~': 'f7',
	'\x1b[19~': 'f8',
	'\x1b[20~': 'f9',
	'\x1b[21~': 'f10',
	'\x1b[23~': 'f11',
	'\x1b[24~': 'f12',
}
for k,v in Sequences.items():
	pre,post = k[:-1],k[-1]
	if pre[-1] == '[':
		pre += '1'
	for n,t in MODS:
		Sequences[pre+n+post] = t + v

for c in range(1,27):
	Sequences[chr(c)] = '<control>' + chr(c + ord('a') - 1)

Sequences.update({
	'\x1b': 'escape',
	'\x1bOH': 'home',
	'\x1bOF': 'end',
	'\x7f': 'bksp',
	'\t': 'tab',
	'\x1b[Z': '<shift>tab',
	'\n': 'enter',
	'\r': 'linefeed',
	' ': 'space',
})
	
class EOF(Exception): pass
class TimedOut(Exception): pass
	
class ALARM(object):
	def __init__(self, handler, timeout):
		self.timeout = timeout
		signal.signal(signal.SIGALRM, handler)
		
	def __enter__(self):
		signal.setitimer(signal.ITIMER_REAL, self.timeout)
		
	def __exit__(self, type, value, traceback):
		signal.setitimer(signal.ITIMER_REAL, 0)
		
class basetty(object):
	def __init__(self, names=Sequences, fd=sys.stdin, echo=False, quit=None):
		try:
			self.old = termios.tcgetattr(fd.fileno())
		except termios.error:
			self.old = None
		self.fd = fd
		self.echo = echo
		self.names = names
		self.quit = quit
		self.__setattr = termios.tcsetattr
		self.__drain = termios.TCSADRAIN
		
	def __enter__(self):
		if self.old:
			new = termios.tcgetattr(self.fd.fileno())
			new[3] &= ~termios.ICANON 
			if not self.echo:
				new[3] &= ~termios.ECHO
			termios.tcsetattr(self.fd.fileno(), termios.TCSANOW, new)
		
	def __exit__(self, type, value, traceback):
		if self.old:
			self.__setattr(self.fd.fileno(), self.__drain, self.old)
		
	def __iter__(self):
		with self:
			extra = ''
			keys = self.names.keys()
			while True:
				seq, extra = extra, ''
				possible = filter(lambda x:x.startswith(seq), keys)
				try:
					while possible and possible != [seq]:
						seq += self._getch()
						possible = filter(lambda x:x.startswith(seq), possible)
				except TimedOut:
					pass
				if not possible and len(seq) > 1:
					seq, extra = seq[:-1], seq[-1]
				if seq:
					yield self.names.get(seq,seq)
					if self.quit and seq == self.quit:
						raise EOF
						
class signaltty(basetty):
	def __init__(self, *args, **kwargs):
		timeout = kwargs.pop('timeout', 0.1)
		basetty.__init__(self, *args, **kwargs)
		def handler(signum, frame):
			raise TimedOut
		self.alarm = ALARM(handler, timeout)
		
	def _getch(self):
		with self.alarm:
			c = self.fd.read(1)
		if c:
			return c
		else:
			raise EOF
			
QueueEmpty = Queue.Empty
class threadtty(basetty, threading.Thread):
	def __init__(self, *args, **kwargs):
		self.timeout = kwargs.pop('timeout', 0.1)
		basetty.__init__(self, *args, **kwargs)
		self.q = Queue.Queue()
		signal.signal(signal.SIGINT, lambda s,f:self.q.put(None))
		def readthread():
			try:
				c = True
				while c:
					c = self.fd.read(1)
					self.q.put(c)
			finally:
				self.q.put('')
		t = threading.Thread(target=readthread)
		t.daemon = True
		t.start()
		
	def _getch(self):
		try:
			c = self.q.get(timeout=self.timeout)
		except QueueEmpty:
			raise TimedOut
		if c:
			return c
		elif c is None:
			raise KeyboardInterrupt
		else:
			raise EOF
	
if __name__=='__main__':
	rawtty = threadtty(Sequences, timeout=1)
	def thrd():
		try:
			while True:
				for key in rawtty:
					print repr(key)
		except KeyboardInterrupt:
			print 'KeyboardInterrupt'
	import threading
	t = threading.Thread(target=thrd)
	t.start()
	import time
	while t.is_alive():
		time.sleep(1)
