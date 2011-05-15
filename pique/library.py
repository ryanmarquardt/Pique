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
import pickle
import threading
import time
import re
import shelve
import os

from common import *

def valsort(d):
	def f(k):
		return d[k]
	return f

def makedirs(path):
	parent = os.path.dirname(path)
	if not os.path.exists(parent):
		makedirs(parent)
		os.mkdir(parent)

class Entry(collections.MutableMapping):
	def __init__(self, lib, uri):
		self._db = lib._store
		self._lk = lib._lock
		self._nk = lib._nk
		self._sn = lib.sync
		self.uri = uri
		
	def __enter__(self):
		return self
	def __exit__(self, t, v, tb):
		self._sn()
		
	def def_value(self, key):
		with self._lk:
			nkey = self._nk(key)
			keys = self._db.getkeys(self.uri, nkey)
			if keys:
				return max(keys, key=valsort(self._db.get(self.uri, nkey)))
			else:
				raise KeyError('No tags available for %r' % key)
	def all_values(self, key):
		with self._lk:
			nkey = self._nk(key)
			f = valsort(self._db.get(self.uri, nkey))
			keys = self._db.getkeys(self.uri, nkey)
			return sorted(keys, key=f, reverse=True)
	__getitem__ = def_value
		
	def timestamp(self, key, value):
		with self._lk:
			return self._db.getv(self.uri, self._nk(key), value)
		
	def edit(self, key, value):
		with self._lk:
			self._db.set(self.uri, self._nk(key), value, time.time())
	def update(self, key, value):
		with self._lk:
			self._db.set(self.uri, self._nk(key), value, None)
	__setitem__ = edit
		
	def __delitem__(self, key):
		with self._lk:
			self._db.delk(self.uri, self._nk(key))
	def forget(self, key, value):
		with self._lk:
			self._db.delv(self.uri, self._nk(key), value)
		
	def __iter__(self):
		return self._db.iter(self.uri)
	def __len__(self):
		return self._db.len(self.uri)
		
	def __repr__(self):
		return 'Entry(uri=%s, info=%r)' % (self.uri, dict((k,self._db.get(self.uri,k)) for k in self._db.iter(self.uri) ))
		

class BaseStore(object):
	#Subclasses must define the following methods:
	#get(uri, key) -> Dict
	#  Dictionary containing value:timestamps of one tag of one file
	#set(uri, key, val, time) -> None
	#  Method to set a value and timestamp for one tag of one file
	#delk(uri, key) -> None
	#  Method to delete one tag from a file completely
	#delv(uri, key, val) -> None
	#  Method to remove one value of a tag from a file
	#iter(uri) -> Iterable
	#  Iterator over all tags of one file
	#len(uri) -> Int
	#  Number of tags in one file
	#deli(uri) -> None
	#  Method to remove one file from the library
	#__iter__() -> Iterable
	#  Iterator over all uris in the library
	#__len__() -> Int
	#  Number of uris in the library
	#sync() -> None
	#  Save all data to disk
	def getkeys(self, uri, key):
		return self.get(uri, key).keys()
	def getv(self, uri, key, val):
		return self.get(uri, key)[val]

class DictStore(BaseStore):
	def __init__(self, location):
		self.data = {}
		
	def get(self, uri, key):
		return self.data[uri][key]
		
	def set(self, uri, key, val, time):
		e = self.data[uri] if uri in self.data else {}
		if key not in e:
			e[key] = {}
		e[key][val] = time
		self.data[uri] = e
		
	def delk(self, uri, key):
		e = self.data[uri]
		del e[key]
		self.data[uri] = e
		
	def delv(self, uri, key, val):
		e = self.data[uri]
		del e[key][val]
		self.data[uri] = e
		
	def deli(self, uri):
		del self.data[uri]
		
	def iter(self, uri):
		return iter(self.data[uri])
		
	def len(self, uri):
		return len(self.data[uri])
		
	def __iter__(self):
		return iter(self.data)
		
	def __len__(self):
		return len(self.data)

	def sync(self):
		for k in self:
			print '%s: %r' % (k, pickle.dumps(self[k]))
			
class FlatStore(DictStore):
	def __init__(self, location):
		DictStore.__init__(self, location)
		self.location = location
		try:
			self.data = pickle.load(open(self.location, 'rb'))
		except:
			print 'Error loading data, starting with blank library'
		
	def sync(self):
		print repr(self.data)
		pickle.dump(self.data, open(self.location, 'wb'))
		
class ShelfStore(DictStore):
	def __init__(self, location):
		self.data = shelve.open(location)
		
	def sync(self):
		self.data.sync()
		
class LibWrap(collections.Mapping):
	def __init__(self, location='~/.config/pique/test-library', store=ShelfStore):
		self._store = store(os.path.expanduser(location))
		self._lock = threading.RLock()
		self._key_re = re.compile('[a-z0-9]+')
		
	def _nk(self, k):
		'''normalize key'''
		return '-'.join(self._key_re.findall(k.lower()))
		
	def sync(self):
		with self._lock:
			self._store.sync()
		
	def __getitem__(self, uri):
		return Entry(self, uri)
	def __setitem__(self, uri, x):
		raise Exception('Library entries must be edited in place.')
	def __delitem__(self, uri):
		with self._lock:
			self._store.deli(uri)
	def __iter__(self):
		return iter(self._store)
	def __len__(self):
		return len(self._store)
		
class Library(PObject):
	def __init__(self, items):
		self.path = os.path.expanduser(dict(items)['path'])
		makedirs(self.path)
		self.db = LibWrap(self.path)
		self.commands = {
			'find':	self.find,
			'list':	self.select_distinct,
			'import':	self.Import,
			'info':	self.info,
			'edit':	self.edit,
		}
		self.dependencies = {
			'Player': self.on_set_player,
			'JobsManager': self.on_set_jobsmanager,
		}
		
	def __getitem__(self, uri):
		#return dict(zip(Columns(), self.db[uri]))
		return self.db[uri]
		
	def on_set_jobsmanager(self, jobsmanager):
		self.jobsmanager = jobsmanager
		
	def on_set_player(self, player):
		self.player = player
		self.player.connect('new-tags', self.new_tags)
		
	def new_tags(self, uri, tags):
		with self.db[uri] as entry:
			entry.update('added', time.time())
			for k,v in tags.iteritems():
				entry.update(k, v)
		
	def Import(self, path):
		'''import(uri) -> Integer

Attempt to import the media at uri into the library. Returns the background
job id number.'''
		r = self.player.scan_uri(path)
		#self.jobsmanager.submit(self.player.normalize_uri, path)
		return r
		
	def find(self, column, *what):
		'''find(column, value[, value, ...]) -> List

Searches the library for media with the associated metadata. find returns
a list of uris where table 'column' has 'value'.'''
		return sorted([uri for (uri,entry) in self.db.iteritems() if entry.get(column) in what])
		
	def edit(self, uri, key, value=None):
		'''edit(uri, column, value=None) -> Dict

Change the metadata for uri to have column=value. Returns a dictionary
containing all of the uri's metdata.'''
		with self.db[uri] as entry:
			entry.edit(key, value)
		return dict(entry)
		
	def info(self, uri=None):
		'''info(uri=None) -> Dict

Returns a dict containing all of the metadata for 'uri'. If uri is not given,
information is returned for the currently playing track.'''
		if uri is None:
			uri = self.player.player.get_property('uri')
		return dict(self.db[uri])
	
	def select_distinct(self, column):
		'''list(column) -> List

Returns a list of all unique entries in column.'''
		if column == 'uri':
			return sorted(self.db.keys())
		else:
			values = set()
			for uri in self.db:
				values.add(self.db[uri].get(column))
			return sorted(list(values))

if __name__=='__main__':
	lib = LibWrap()
	with lib['a'] as a:
		a['title'] = 'title4'
		print a['title']
		try:
			print a['genre']
		except KeyError:
			pass
		try:
			del a['artist']
		except KeyError:
			pass
		a.update('title', 'title1')
		a.update('title', 'title2')
		a.forget('title', 'title1')
		a.update('bitrate', 128000)
		a.update('bitrate', 127000)
		a.update('bitrate', 128000)
		a['title'] = 'title3'
		print a[' Title ']
		print a.all_values('  Title. ')
		print a.timestamp('TITLE', 'title4')
		for a in lib.values():
			for k,v in a.items():
				print '   %s: %r' % (k,v)
		print
		print
	print lib.items()
	del lib['a']['title']
	lib.sync()
	print lib.items()
	del lib['a']
	lib.sync()
	print lib.items()
