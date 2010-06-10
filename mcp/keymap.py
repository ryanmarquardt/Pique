from common import *

class KeyMap(dict):
	def __init__(self, config, commandmap):
		self.keys = dict((str(k).lower(),v) for k,v in config.items('KeyMap'))
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
