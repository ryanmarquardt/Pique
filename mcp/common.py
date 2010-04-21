import threading

DEBUG = True
def debug(*args):
	if DEBUG:
		print '%s: %s' % (threading.currentThread().name, ' '.join(map(str,args)))
