import sys
import threading

DEBUG = True
def debug(*args):
	if DEBUG:
		print >>sys.stderr, threading.currentThread().name + ':', ' '.join(map(str,args))

VERBOSE = True
def verbose(*args):
	if VERBOSE:
		print >>sys.stderr, ' '.join(map(str,args))

TIME_FORMAT='hms'

SECOND = 1e9

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
			
