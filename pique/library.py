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
		'uri',
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
	def __init__(self, columns):
		self.header = columns
		self.elements = {}
		self.Row = collections.namedtuple('Row', columns)

	def __getitem__(self, index):
		return self.elements[index]

	def __setitem__(self, index, value):
		if isinstance(value, collections.Mapping):
			self.elements[index] = self.Row(**value)
		elif isinstance(value, collections.Sequence):
			self.elements[index] = self.Row(*value)

	def __delitem__(self, index):
		del self.elements[index]

	def __len__(self):
		return len(self.elements)

	def __iter__(self):
		return iter(sorted(self.elements.items(),key=lambda k,v:(v.artist,v.album,v.track_number)))

	def select(self, **where):
		items = where.items()
		return [row for row in map(self.Row._make,self) if all(getattr(row,k)==v for k,v in items)]

	def select_distinct(self, which):
		return sorted(list(set(getattr(row, which) for row in self.elements.itervalues())))

	def dump(self, f):
		f.write(repr(self.header) + '\n')
		for uri,row in self:
			f.write('%r,%r\n' % (uri, repr(row)))

	def load(self, f):
		Table.__init__(self, reval(f.readline()))
		for line in f:
			uri, row = reval(line, Row=self.Row)
			self.elements[uri] = row

class Library(Table, PObject):
	def __init__(self, items):
		PObject.__init__(self)
		self.path = os.path.expanduser(dict(items)['path'])
		try:
			self.load(open(self.path,'r'))
		except Exception, e:
			verbose("Couldn't load library from disk; using empty database.")
			verbose(e)
			Table.__init__(self, Columns())
		self.commands = {
			'find':	self.find,
			'list':	self.select_distinct,
		}
		self.dependencies = {
			'pique.player.Player': self.on_set_player,
		}
		
	def on_set_player(self, player):
		self.connect('uri-added', player.scan_uri)
		player.connect('new-tags', self.new_tags)

	def clear(self):
		Table.__init__(self, self.header)
		self.dump(open(self.path,'w'))
		verbose("Successfully initialized library at", repr(self.path))
		
	def new_tags(self, uri, tags):
		l = max(map(len,tags.keys())) + 2
		tags['added'] = time.time()
		rowtags = dict((k,tags.get(k,None)) for k in self.header)
		self[uri] = rowtags
		print '\n{'
		for k in sorted(rowtags.keys()):
			print '%s: %r' % (k.rjust(l), tags[k])
		print '}'
		self.dump(open(self.path,'wb'))
		
	def add(self, uris):
		for i in uris:
			if os.path.isdir(i):
				for root,dirs,files in os.walk(i):
					for f in files:
						self.emit('uri-added', uri(os.path.join(root,f)))
			else:
				self.emit('uri-added', uri(i))

	def find(self, type, what):
		return [i.uri for i in self.select(**{type:what})]
#			
#def upgrade(src=Versions[-1], dst=Versions[0], path=DEFAULT_PATH):
#	db = sqlite3.connect(path)
#	A = db.cursor()
#	B = db.cursor()
#	try:
#		B.execute('drop table %s' % dst)
#		B.execute(u"create table %s (%s) " % (dst, ", ".join(["%s %s" % i for i in Columns(dst,defs=True)])))
#		A.execute('select %s from %s' % (','.join(Columns(src)),src))
#		for row in A:
#			print row
#			old = Row(src)(*row)._asdict()
#			print old
#			B.execute('insert into %s (%s) values (%s)' % (dst, ','.join(old.keys()), ','.join('?'*len(old))), old.values())
#			print
#	finally:
#		A.close()
#		B.close()
#		db.commit()

__all__ = ['uri', 'Library']
