#!/usr/bin/env python
#
# Copyright (c) 2010, Ryan Marquardt
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without 
# modification, are permitted provided that the following conditions are
# met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the project nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

VERSION = '0.01'

import collections
import ConfigParser
import os
import signal
import sys
import traceback
import Queue

import gtk

from common import *
import jobs
import inhibit

def importfrom(path):
	mod, _, cls = path.rpartition('.')
	__import__(mod)
	return getattr(sys.modules[mod], cls)
	
class PluginError(Exception): pass

class Configuration(ConfigParser.SafeConfigParser):
	def __init__(self):
		ConfigParser.SafeConfigParser.__init__(self)
		self.readfp(open(os.path.join(os.path.dirname(__file__), 'default.conf')))
		self.read([os.path.expanduser('~/.config/pique/pique.conf')])
	
	def has_section(self, section):
		if ConfigParser.SafeConfigParser.has_section(section):
			return True
		else:
			sections = ConfigParser.SafeConfigParser.sections()
			lowersections = map(str.lower, sections)
			return section.lower() in lowersections
	
	def items(self, section, default=()):
		if ConfigParser.SafeConfigParser.has_section(self, section):
			real_name = section
		else:
			sections = ConfigParser.SafeConfigParser.sections(self)
			lowersections = map(str.lower, sections)
			try:
				idx = lowersections.index(section)
			except ValueError:
				return default
			real_name = sections[lowersections.index(section)]
		return ConfigParser.SafeConfigParser.items(self, real_name)

class LockedValue(threading._Event):
	def set(self, val):
		self.value = val
		threading._Event.set(self)
		
	def wait(self, timeout=None):
		threading._Event.wait(self, timeout=timeout)
		return self.value

class CommandMap(threading.Thread, collections.MutableMapping, PObject):
	name = 'CommandThread'
	def __init__(self, d=None):
		threading.Thread.__init__(self)
		self.__d = dict(d or {})
		self.daemon = True
		self._q = Queue.Queue()
		
	def __hash__(self):
		return 1
		
	def __getitem__(self, key):
		return self.__d.__getitem__(key)
	def __setitem__(self, key, value):
		self.__d.__setitem__(key, value)
	def __delitem__(self, key):
		self.__d.__delitem__(key)
	def __len__(self):
		return self.__d.__len__()
	def __iter__(self):
		return self.__d.__iter__()
		
	def async(self, cmd, *args, **kwargs):
		func = self[cmd]
		debug('self._q.put', cmd, args, kwargs)
		self._q.put((func, args, kwargs, None))
		
	def __call__(self, cmd, *args, **kwargs):
		func = self[cmd]
		debug('self._q.put', cmd, args, kwargs)
		v = LockedValue()
		self._q.put((func, args, kwargs, v))
		ret,(typ,val,tb) = v.wait()
		debug(ret, typ, val, tb)
		if typ is None:
			return ret
		else:
			raise typ, val, tb
		
	def run(self):
		try:
			while True:
				command, args, kwargs, v = self._q.get()
				state = capture(lambda:command(*args, **kwargs))
				if v is None and state[1] == (None, None, None):
					debug(state[1][2])
				else:
					v.set(state)
		except TypeError:
			pass
				
	def shutdown(self):
		self._q.put(None)
			
class PluginManager(collections.defaultdict):
	def __init__(self):
		self.conf = Configuration()
		self['commandmap'] = CommandMap({
			'quit': self.quit,
			'commands': self.commands,
		})
		self['commandmap'].start()
		self.order = collections.deque()
		for name, _ in self.conf.items('Plugins'):
			self[name]
		debug('Commands:', *sorted(self['commandmap'].keys()))
		
	def commands(self):
		'''commands() -> List

Returns a list of all available commands.'''
		return sorted(self['commandmap'].keys())
		
	def __getitem__(self, key):
		return collections.defaultdict.__getitem__(self, key.lower())
		
	def __setitem__(self, key, value):
		collections.defaultdict.__setitem__(self, key.lower(), value)
		
	def __missing__(self, name):
		path = self.conf.get('Plugins', name)
		debug('Load plugin', name, '(%s)' % path)
		plugin = importfrom(path)(self.conf.items(name))
		self[name] = plugin
		commandmap = self['commandmap']
		for cmd,func in getattr(plugin, 'commands', {}).items():
			if commandmap.setdefault(cmd, func) is not func:
				raise PluginError('Name conflict: %s is attempting to overwrite command %s' % (plugin_class.__name__, cmd))
		for which, callback in getattr(plugin, 'dependencies', {}).items():
			#Pass plugin references to plugins it depends on
			callback(self[which])
		self.order.append(plugin) # Plugins will be started in reverse order
		return plugin
		
	def start(self):
		for plugin in self.order:
			getattr(plugin, 'start', lambda:None)()
		
	def quit(self):
		'''quit() -> None

Terminate the server.'''
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
		self.plugins['Player'].connect('eos', self.on_eos)
		self.plugins['Player'].connect('error', self.on_error)
		
	def start(self):
		self.plugins.start()
		with inhibit.ScreensaverInhibitor():
			gtk.main()
		self.plugins.cleanup()
	
	def on_eos(self):
		debug('eos')
		self.plugins['commandmap'].async('next')
		
	def on_error(self, error):
		debug('Error:', *error)
		self.plugins['commandmap'].async('stop')
