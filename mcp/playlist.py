import collections
from common import *

class Playlist(object):
	def __init__(self, uris=[], repeat=False, random=False):
		self.repeat = False
		self.random = False
		self.load(uris)
		
	def load(self, uris):
		self.clear()
		self.entries = tuple(uris)
		
	def _extend(self):
		if self.random:
			entries = list(self.entries)
			random.shuffle(entries)
			self.history.extend(entries)
		else:
			self.history.extend(self.entries)
		self.history.rotate(len(self.entries))
		
	def next(self):
		debug(self.history)
		self.history.rotate(-1)
		if self.history[0] is not None:
			return self.history[0]
		else:
			#End of playlist
			if not self.repeat and len(self.history) > 1:
				raise StopIteration
			else:
				self._extend()
			debug(self.history)
			self.history.rotate(-1)
			if self.history[0]:
				return self.history[0]
			else:
				raise StopIteration
		
	def __len__(self):
		return len(self.history) - 1
		
	def previous(self):
		if self.history[0] is None:
			#Still at the beginning
			raise StopIteration
		self.history.rotate(1)
		uri = self.history[0]
		if uri is None:
			#Backed up as far as history goes
			raise StopIteration
		
	def clear(self):
		self.history = collections.deque()
		self.history.append(None)
		
	def set_repeat(self, yes=True):
		self.repeat = yes
		
	def set_random(self, yes=True):
		self.random = yes
