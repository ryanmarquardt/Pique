import thread
import rawtty

class ConsoleThread(thread.BgThread):
	def connect(self, key, func, *args, **kwargs):
		self.keymap[key] = func,args,kwargs
	
	def main(self):
		for key in rawtty.keypresses(timeout=0.3, quit='eof'):
			self.handler(key)
		print 'done'
