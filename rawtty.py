#!/usr/bin/python

import sys
import termios
import tty

class rawtty(object):
	def __init__(self, fd=sys.stdin):
		if hasattr(fd, 'fileno'):
			fd = fd.fileno()
		self.fd = fd
		
	def __enter__(self):
		self.old = termios.tcgetattr(self.fd)
		tty.setraw(self.fd)
		
	def __exit__(self, type, value, traceback):
		termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
		
def getch(fd=sys.stdin):
	with rawtty(fd):
		return fd.read(1)
		
if __name__=='__main__':
	print 'Press any key to continue'
	getch()
