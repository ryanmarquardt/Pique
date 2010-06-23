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
import os.path
import pickle
import time

from common import *

Versions = [
	'media_001',
	'media',
]
TABLE_VERSION = Versions[0]

def reval(expr, **includes):
	return eval(expr, {'__builtins__':[]}, includes)

def Columns(version=TABLE_VERSION):
	return [
		'title',
		'artist',
		'album',
		'date',
		'duration',
		'track_number',
		'disk_number',
		'replaygain_track_peak',
		'replaygain_track_gain',
		'replaygain_reference_level',
		'audio_codec',
		'video_codec',
		'added',
	]

class Table(collections.MutableMapping):
	def __init__(self, columns, elements=None):
		self.__header = columns
		self.Row = collections.namedtuple('Row', columns)
		self.__elements = {}
		if elements is not None:
			for k,v in elements.items():
				self[k] = v
		
	def __getitem__(self, index):
		return self.__elements[index]
		
	def __setitem__(self, index, value):
		if isinstance(value, collections.Mapping):
			self.__elements[index] = self.Row(**value)
		elif isinstance(value, collections.Sequence):
			self.__elements[index] = self.Row(*value)
		
	def __delitem__(self, index):
		del self.__elements[index]
		
	def __len__(self):
		return len(self.__elements)
		
	def __iter__(self):
		return iter(sorted(self.__elements.items(),key=lambda k,v:(v.artist,v.album,v.track_number)))
		
	def select(self, **where):
		items = where.items()
		return [row for row in map(self.Row._make,self) if all(getattr(row,k)==v for k,v in items)]
		
	def select_distinct(self, which):
		return sorted(list(set(getattr(row, which) for row in self.__elements.itervalues())))
		
	def dump(self, f):
		pickle.dump((self.__header, [(k,tuple(v)) for k,v in self.__elements.iteritems()]), f)
		
	def load(self, f):
		columns, elements = pickle.load(f)
		Table.__init__(self, columns, dict(elements))

class Library(Table, PObject):
	def __init__(self, items):
		PObject.__init__(self)
		self.path = os.path.expanduser(dict(items)['path'])
		try:
			Table.load(self, open(self.path, 'rb'))
		except Exception, e:
			verbose("Couldn't load library from disk; using empty database.")
			verbose(e)
			Table.__init__(self, Columns())
		self.commands = {
			'find':	self.find,
			'list':	self.select_distinct,
			'import':	self.add,
		}
		self.dependencies = {
			'pique.player.Player': self.on_set_player,
		}
		
	def on_set_player(self, player):
		self.connect('uri-added', player.scan_uri)
		player.connect('new-tags', self.new_tags)
		
	def clear(self):
		Table.__init__(self, self.header)
		Table.dump(self, open(self.path,'w'))
		verbose("Successfully initialized library at", repr(self.path))
		
	def new_tags(self, uri, tags):
		l = max(map(len,tags.keys())) + 2
		tags['added'] = time.time()
		rowtags = dict((k,tags.get(k,None)) for k in self.Row._fields)
		self[uri] = rowtags
		print self[uri]
		#print '\n{'
		#for k in sorted(rowtags.keys()):
			#print '%s: %r' % (k.rjust(l), tags[k])
		#print '}'
		Table.dump(self, open(self.path,'wb'))
		
	def add(self, path):
		if os.path.isdir(path):
			for root,dirs,files in os.walk(path):
				for f in files:
					self.emit('uri-added', uri(os.path.join(root,f)))
		else:
			self.emit('uri-added', uri(path))
		
	def find(self, type, what):
		return [i.uri for i in self.select(**{type:what})]
