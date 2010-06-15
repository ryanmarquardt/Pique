VERSION = '0.01'

import collections
import ConfigParser
import os
import signal
import sys

import gtk

from common import *

def importfrom(path):
	mod, _, cls = path.rpartition('.')
	__import__(mod)
	return getattr(sys.modules[mod], cls)
	
class PluginError(Exception): pass

class Configuration(object):
	def __init__(self):
		self.conf = ConfigParser.SafeConfigParser()
		self.conf.readfp(open(os.path.join(os.path.dirname(__file__), 'default.conf')))
		self.conf.read([os.path.expanduser('~/.config/pique/pique.conf')])
	
	def __getitem__(self, key):
		return self.conf.items(key)

class PluginManager(collections.defaultdict):
	def __init__(self):
		self.conf = configuration()
		self['commandmap'] = {'quit': self.quit}
		self['commandmap']['commands'] = self['commandmap'].keys
		self.order = collections.deque()
		for _, path in conf['Plugins']:
			self[path]
		debug('Commands:', *sorted(self['commandmap'].keys()))
		
	def __missing__(self, path):
		debug('Load plugin', path)
		#load plugin
		plugin = importfrom(path)
		try:
			items = self.conf.items(plugin.__name__)
		except ConfigParser.NoSectionError:
			items = ()
		p = plugin(items)
		if hasattr(p, 'commands'):
			for k in p.commands:
				if k in self['commandmap']:
					raise PluginError('Name conflict: %s is attempting to overwrite command %s' % (plugin.__name__, k))
				self['commandmap'][k] = p.commands[k]
		if hasattr(p, 'dependencies') and hasattr(p.dependencies, 'items'):
			for name, callback in p.dependencies.items():
				callback(self[name])
				#Automatically loads dependencies which haven't been loaded yet
		#Store dependencies in reverse order
		self.order.append(p)
		self[path] = p
		return p
		
	def start(self):
		for plugin in self.order:
			if hasattr(plugin, 'start'):
				plugin.start()
		
	def quit(self):
		if gtk.main_level():
			gtk.main_quit()
		
	def cleanup(self):
		while self.order:
			p = self.order.pop()
			if hasattr(p, 'quit'):
				p.quit()

class Main(object):
	def __init__(self):
		self.plugins = PluginManager()
		self.plugins['pique.player.Player'].connect('eos', self.on_eos)
		self.plugins['pique.player.Player'].connect('error', self.on_error)
		
	def start(self):
		self.plugins.start()
		gtk.main()
		self.plugins.cleanup()
	
	def on_eos(self):
		debug('eos')
		self.plugins['commandmap']['next']()
		
	def on_error(self, error):
		debug('Error:', *error)
		self.plugins['commandmap']['stop']()
