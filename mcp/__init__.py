VERSION = '0.01'

import collections
import ConfigParser
import os
import signal
import sys

from common import *
from library import Library
from network import NetThread
from console import ConsoleThread
from player import Player
from playlist import Playlist
from gui import GUI
from keymap import KeyMap
from client import Client

class Main(object):
	def __init__(self):
		conf = ConfigParser.SafeConfigParser()
		conf.read(['./mcp.conf',os.path.expanduser('~/.mcp.conf')])
		self.commandmap = {}
		
		self.library = Library(os.path.expanduser(conf.get('Library', 'path')))
		self.commandmap.update(self.library.commands)
		
		self.keymap = KeyMap(conf, self.commandmap)
		
		self.server = NetThread(conf, self.commandmap)
		
		self.console = ConsoleThread()
		self.console.set_keymap(self.keymap)
		
		self.playlist = Playlist()
		self.commandmap.update(self.playlist.commands)
		
		self.player = Player(conf, self.library, self.playlist)
		self.gui = GUI()
		
		self.player.window = self.gui.videobox.movie_window
		self.player.connect('eos', self.on_eos)
		self.player.connect('error', self.on_error)
		self.player.connect('state-changed', self.gui.update_state)
		self.player.connect('update', self.gui.update_time)
		self.commandmap.update(self.player.commands)
		
		self.gui.connect('play-pause', self.player.play_pause)
		self.gui.connect('next', self.player.next)
		self.gui.connect('previous', self.player.previous)
		self.gui.connect('position', self.player.seek)
		#self.gui.connect('volume', self.player.set_volume)
		self.gui.connect('destroy', self.quit)
		self.gui.set_keymap(self.keymap)
		self.commandmap.update(self.gui.commands)
		
		self.commandmap['quit'] = self.quit
		
	def start(self):
		self.threads = collections.deque()
		for thread in (self.server, self.console, self.player, self.gui):
			self.threads.append(thread)
			thread.start()
		
	def quit(self):
		while self.threads:
			self.threads.pop().quit()
		
	def on_eos(self):
		debug('eos')
		self.player.next()
		
	def on_error(self, error):
		debug('Error:', *error)
		self.player.stop()
		
	def on_destroy(self, *args):
		self.quit()
		

