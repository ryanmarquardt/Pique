from common import *

class KeyMap(dict):
	dependencies = ('commandmap',)
	def __init__(self, items):
		self.keys = dict((str(k).lower(),v) for k,v in items)
		self.dependencies = {'commandmap': self.on_set_commandmap}
	
	def on_set_commandmap(self, commandmap):
		self.commandmap = commandmap
		
	def add(self, key, cmd):
		self.keys[key] = cmd
		
	def interpret(self, key):
		try:
			func = self.commandmap[self.keys[key.lower()]]
			return func()
		except KeyError:
			try:
				func = self.commandmap[key.lower()]
				return func()
			except KeyError:
				debug('No key binding for', key)
