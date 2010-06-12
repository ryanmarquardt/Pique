import collections
from common import *

class Playlist(object):
	def __init__(self, uris=[], repeat=False, random=False):
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
		}
		self.callbacks = collections.defaultdict(list)
		
	def connect(self, which, func, *args, **kwargs):
		self.callbacks[which].append((func,args,kwargs))
		
	def emit(self, signal, *args):
		debug('Playlist.emit', signal, *args)
		for f,a,k in self.callbacks[signal]:
			f(*(args+a), **k)
		
	def load(self, uris):
		self.clear()
		self.entries = tuple(uris)
		self._extend()
		self.emit('changed')
		
	def add(self, uri):
		self.load(self.entries + (uri,))
		
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
