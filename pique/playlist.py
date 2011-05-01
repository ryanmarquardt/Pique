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
import collections
import random
from common import *

class Playlist(PObject):
	def __init__(self, uris=[], repeat=False, random=False):
		self.dependencies = {'pique.library.Library': self.on_set_library}
		self.repeat = repeat
		self.random = random
		self.history = collections.deque()
		self.history.append(None)
		self.entries = ()
		self.version = 0
		self.commands = {
			'add':		self.add,
			'clear':	self.clear,
			'repeat':	self.set_repeat,
			'random':	self.set_random,
			'findadd':	self.findadd,
			'playlist-list':	self.listall,
		}
		
	def on_set_library(self, library):
		self.library = library
		
	def load(self, uris):
		self.clear()
		self.entries = tuple(uris)
		self._extend()
		self.emit('changed')
		
	def listall(self):
		'''playlist_list() -> List

Returns a list of all uris in the playlist.'''
		
	def add(self, uri):
		'''add(uri) -> None

Appends uri to the playlist.'''
		self.load(self.entries + (uri,))
		
	def findadd(self, type, what):
		'''findadd(column, value) -> None

Adds all media from the library where 'column' has 'value'.'''
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
		'''clear() -> None

Remove all entries from the playlist.'''
		self.history = collections.deque()
		self.history.append(None)
		self.entries = ()
		self.version += 1
		
	def set_repeat(self, yes=True):
		'''repeat(value=True) -> None

Sets whether the playlist should repeat according to value.'''
		self.repeat = yes
		
	def set_random(self, yes=True):
		'''random(value=True) -> None

Sets whether entries should be played randomly according to value.'''
		self.random = yes
