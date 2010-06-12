import threading

from common import *

class BgThread(threading.Thread):
	def __init__(self, *args, **kwargs):
		if DEBUG:
			def t(*args):
				debug('Starting thread', *args)
				self.main(*args)
		else:
			t = self.main
		threading.Thread.__init__(self, target=self.main, args=args, kwargs=kwargs)
		self.daemon = True
		self.init()
		
	def init(self):
		pass
