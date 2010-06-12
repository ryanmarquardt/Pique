import collections
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
		
