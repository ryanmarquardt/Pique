import threading

class BgThread(threading.Thread):
	def __init__(self, *args, **kwargs):
		threading.Thread.__init__(self, target=self.main, args=args, kwargs=kwargs)
		self.daemon = True
		self.init()
		
	def init(self):
		pass
