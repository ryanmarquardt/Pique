#!/usr/bin/python

import collections
import Queue
import select
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
	'pgup':'\x1b[5~',
	'pgdn':'\x1b[6~',
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
}
for k,v in NAMES.items():
	NAMES[v] = k
KNOWN_SEQUENCES = NAMES.values()
	
class rawtty(object):
	def __init__(self, fd=sys.stdin, echo=False):
		if hasattr(fd, 'fileno'):
			fd = fd.fileno()
		self.fd = fd
		self.echo = echo
		
	def __enter__(self):
		self.old = termios.tcgetattr(self.fd)
		new = termios.tcgetattr(self.fd)
		new[3] &= ~termios.ICANON 
		if not self.echo:
			new[3] &= ~termios.ECHO
		termios.tcsetattr(self.fd, termios.TCSANOW, new)
		
	def __exit__(self, type, value, traceback):
		termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
		
class EOF(Exception):
	pass
	
def keypresses(fd=sys.stdin, echo=False, timeout=1, quit='eof'):
	with rawtty(fd=fd, echo=echo):
		q = Queue.Queue()
		def readthread():
			try:
				c = True
				while c:
					c = fd.read(1)
					q.put(c)
			finally:
				q.put('')
		ReadThread = threading.Thread(target=readthread)
		ReadThread.daemon = True
		ReadThread.start()
		seq = q.get()
		while True:
			if not seq:
				raise EOF
			elif seq == ESCAPE:
				try:
					seq += q.get(timeout=timeout)
				except Queue.Empty:
					pass
					#Assume that only escape was pressed
				else:
					if not any(s.startswith(seq) for s in KNOWN_SEQUENCES):
						#Escape key, followed by another sequence
						yield ESCAPE
						seq = seq[1:]
						continue
					else:
						#Probably not the escape key by itself
						#Continue reads until we have a full sequence or error
						while any(s.startswith(seq) for s in KNOWN_SEQUENCES):
							if seq not in KNOWN_SEQUENCES:
								seq += q.get()
							else:
								break
						if seq not in KNOWN_SEQUENCES:
							#No match
							raise IOError('Unrecognized Sequence %r' % seq)
			#print repr(seq), repr(NAMES.get(quit,quit)), seq == NAMES.get(quit,quit)
			if seq != NAMES.get(quit,quit):
				yield seq
			else:
				return
			seq = q.get()

def getch(fd=sys.stdin, echo=False):
	with rawtty(fd):
		return fd.read(1)
		
if __name__=='__main__':
	print KNOWN_SEQUENCES
	while True:
		try:
			for key in keypresses():
				print repr(NAMES.get(key,key))
		except IOError, e:
			print e
			break
		else:
			break
