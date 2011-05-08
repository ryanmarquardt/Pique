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
	optionxform = str
	def __init__(self):
		ConfigParser.SafeConfigParser.__init__(self)
		self.readfp(open(os.path.join(os.path.dirname(__file__), 'default.conf')))
		self.read([os.path.expanduser('~/.config/pique/pique.conf')])
	
	def __getitem__(self, key):
		return self.items(key)

class PluginManager(collections.defaultdict):
	def __init__(self):
		self.conf = Configuration()
		self['commandmap'] = {'quit': self.quit}
		self['commandmap']['commands'] = self.commands
		self.order = collections.deque()
		self.pathmap = dict(self.conf['Plugins'])
		debug(self.pathmap)
		for name, _ in self.conf['Plugins']:
			self[name]
		debug('Commands:', *sorted(self['commandmap'].keys()))
		
	def commands(self):
		'''commands() -> List

Returns a list of all available commands.'''
		return sorted(self['commandmap'].keys())
		
	def __missing__(self, name):
		path = self.conf.get('Plugins', name)
		debug('Load plugin', name, '(%s)' % path)
		#load plugin
		plugin = importfrom(path)
		try:
			items = self.conf[name]
		except ConfigParser.NoSectionError:
			items = ()
		p = plugin(items)
		self[name] = p
		if hasattr(p, 'commands'):
			for k in p.commands:
				if k in self['commandmap']:
					raise PluginError('Name conflict: %s is attempting to overwrite command %s' % (plugin.__name__, k))
				self['commandmap'][k] = p.commands[k]
		if hasattr(p, 'dependencies') and hasattr(p.dependencies, 'items'):
			for which, callback in p.dependencies.iteritems():
				callback(self[which])
				#Automatically loads dependencies which haven't been loaded yet
		#Store dependencies in reverse order
		self.order.append(p)
		return p
		
	def start(self):
		for plugin in self.order:
			if hasattr(plugin, 'start'):
				plugin.start()
		
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
		self.plugins['commandmap']['next']()
		
	def on_error(self, error):
		debug('Error:', *error)
		self.plugins['commandmap']['stop']()
