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

import collections
import Queue
import select
import signal
import sys
import termios
import threading

ESCAPE = '\x1b'

NAMES = {
	'escape':'\x1b',
	'eof':'\x04',
	'left':'\x1b[D',	'shift+left':'\x1b[1;2D',
	'right':'\x1b[C',	'shift+right':'\x1b[1;2C',
	'down':'\x1b[B',	'shift+down':'\x1b[1;2B',
	'up':'\x1b[A',	'shift+up':'\x1b[1;2A',
	'home':'\x1bOH',
	'end':'\x1bOF',
	'insert':'\x1b[2~',	'shift+insert':'\x1b[2;2~',
	'delete':'\x1b[3~',	'shift+delete':'\x1b[3;2~',
	'page_up':'\x1b[5~',
	'page_down':'\x1b[6~',
	'f1':'\x1bOP',	'shift+f1':'\x1bO1;2P',
	'f2':'\x1bOQ',	'shift+f2':'\x1bO1;2Q',
	'f3':'\x1bOR',	'shift+f3':'\x1bO1;2R',
	'f4':'\x1bOS',	'shift+f4':'\x1bO1;2S',
	'f5':'\x1b[15~',	'shift+f5':'\x1b[15;2~',
	'f6':'\x1b[17~',	'shift+f6':'\x1b[17;2~',
	'f7':'\x1b[18~',	'shift+f7':'\x1b[18;2~',
	'f8':'\x1b[19~',	'shift+f8':'\x1b[19;2~',
	'f9':'\x1b[20~',	'shift+f9':'\x1b[20;2~',
	'f10':'\x1b[21~',	'shift+f10':'\x1b[21;2~',
	'f11':'\x1b[23~',	'shift+f11':'\x1b[23;2~',
	'f12':'\x1b[24~',	'shift+f12':'\x1b[24;2~',
	'bksp':'\x7f',
	'tab':'\t',	'shift+tab':'\x1b[Z',
	'enter':'\n',
	'space':' ',
}
for k,v in NAMES.items():
	NAMES[v] = k
KNOWN_SEQUENCES = NAMES.values()
	
class EOF(Exception):
	pass
	
class rawtty(object):
	def __init__(self, fd=sys.stdin, echo=False, timeout=1, quit='eof'):
		self.fd = fd
		self.echo = echo
		self.timeout = timeout
		self.quit = quit
		self.old = termios.tcgetattr(self.fd.fileno())
		self.q = Queue.Queue()
		
	def __enter__(self):
		self.start()
		
	def __exit__(self, type, value, traceback):
		self.restore()
		
	def start(self):
		try:
			signal.signal(signal.SIGINT, self._recv_interrupt)
		except:
			pass
		new = termios.tcgetattr(self.fd.fileno())
		new[3] &= ~termios.ICANON 
		if not self.echo:
			new[3] &= ~termios.ECHO
		termios.tcsetattr(self.fd.fileno(), termios.TCSANOW, new)
		
	def restore(self):
		termios.tcsetattr(self.fd.fileno(), termios.TCSADRAIN, self.old)
		try:
			signal.signal(signal.SIGINT, signal.SIG_DFL)
		except:
			pass
		
	def _recv_interrupt(self, sig, frame):
		self.q.put(KeyboardInterrupt)
		
	def __iter__(self):
		self.start()
		def readthread():
			try:
				c = True
				while c:
					c = self.fd.read(1)
					self.q.put(c)
			finally:
				self.q.put('')
		self.readthread = threading.Thread(target=readthread)
		self.readthread.daemon = True
		self.readthread.start()
		seq = self.q.get()
		while True:
			if not seq:
				raise EOF
			elif seq == KeyboardInterrupt:
				raise KeyboardInterrupt
			elif seq == ESCAPE:
				try:
					seq += self.q.get(timeout=self.timeout)
				except Queue.Empty:
					pass
					#Assume that only escape was pressed
				else:
					if not any(s.startswith(seq) for s in KNOWN_SEQUENCES):
						#Escape key, followed by another sequence
						yield 'escape'
						seq = seq[1:]
						continue
					else:
						#Probably not the escape key by itself
						#Continue reads until we have a full sequence or error
						while any(s.startswith(seq) for s in KNOWN_SEQUENCES):
							if seq not in KNOWN_SEQUENCES:
								seq += self.q.get()
							else:
								break
						if seq not in KNOWN_SEQUENCES:
							#No match
							raise IOError('Unrecognized Sequence %r' % seq)
			if seq != NAMES.get(self.quit,self.quit):
				yield NAMES.get(seq,seq)
			else:
				return
			seq = self.q.get()

def getch(fd=sys.stdin, echo=False):
	with rawtty(fd):
		return fd.read(1)
		
if __name__=='__main__':
	print KNOWN_SEQUENCES
	while True:
		try:
			for key in keypresses():
				print repr(key)
		except IOError, e:
			print e
			break
		else:
			break
