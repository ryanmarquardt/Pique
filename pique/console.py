import bgthread
import rawtty

class ConsoleThread(bgthread.BgThread):
	name = 'ConsoleThread'
	def __init__(self, *args, **kwargs):
		bgthread.BgThread.__init__(self, *args, **kwargs)
		self.dependencies = {'pique.keymap.KeyMap':self.on_set_keymap}
		
	def connect(self, key, func, *args, **kwargs):
		self.keymap[key] = func,args,kwargs
		
	def on_set_keymap(self, keymap):
		self.handler = keymap.interpret
		
	def init(self):
		self.rawtty = rawtty.rawtty(timeout=0.3, quit='eof')
		
	def start(self):
		self.rawtty.start()
		bgthread.BgThread.start(self)
	
	def main(self, confitems):
		try:
			for key in self.rawtty:
				self.handler(key)
		except KeyboardInterrupt:
			self.handler('quit')
		finally:
			print 'done'
		
	def quit(self):
		self.rawtty.restore()
