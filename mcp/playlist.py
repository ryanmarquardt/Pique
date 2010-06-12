import collections
from common import *

class Playlist(PObject):
	def __init__(self, uris=[], repeat=False, random=False):
		PObject.__init__(self)
		self.dependencies = {'mcp.library.Library': self.on_set_library}
		self.repeat = repeat
		self.random = random
		self.history = collections.deque()
		self.history.append(None)
		self.entries = ()
		self.version = 0
		self.commands = {
			'playlist-add':		self.add,
			'playlist-load':	self.load,
			'playlist-clear':	self.clear,
			'playlist-repeat':	self.set_repeat,
			'playlist-random':	self.set_random,
			'playlist-list':	lambda:'\n'.join(self.entries),
			'findadd':			self.findadd,
		}
		
	def on_set_library(self, library):
		self.library = library
		
	def load(self, uris):
		self.clear()
		self.entries = tuple(uris)
		self._extend()
		self.emit('changed')
		
	def add(self, uri):
		self.load(self.entries + (uri,))
		
	def findadd(self, type, what):
		uris = self.library.find(type, what)
		self.load(self.entries + tuple(uris))
		
	def _extend(self):
		if self.random:
			entries = list(self.entries)
			random.shuffle(entries)
			self.history.extend(entries)
		else:
			self.history.extend(self.entries)
		#self.history.rotate(len(self.entries))
		
	def next(self):
		debug(self.history)
		self.history.rotate(-1)
		if self.history[0] is None:
			#End of playlist
			if not self.repeat and len(self.history) > 1:
				raise StopIteration
			else:
				self._extend()
			self.history.rotate(-1)
			if not self.history[0]:
				raise StopIteration
		self.emit('new-uri-available', self.history[0])
		return self.history[0]
		
	def __len__(self):
		return len(self.history) - 1
		
	def previous(self):
		if self.history[0] is None:
			#Still at the beginning
			raise StopIteration
		self.history.rotate(1)
		if self.history[0] is None:
			#Backed up as far as history goes
			raise StopIteration
		self.emit('new-uri-available', self.history[0])
		return self.history[0]
		
	def clear(self):
		self.history = collections.deque()
		self.history.append(None)
		self.entries = ()
		self.version += 1
		
	def set_repeat(self, yes=True):
		self.repeat = yes
		
	def set_random(self, yes=True):
		self.random = yes
