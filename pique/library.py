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

import os.path
import time
import shelve

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

	#def __iter__(self):
		#for i in sorted(self.__elements.items(),key=lambda i:(i[1].artist,i[1].album,i[1].track_number)):
			#yield i[0]

def makedirs(path):
	parent = os.path.dirname(path)
	if not os.path.exists(parent):
		makedirs(parent)
		os.mkdir(parent)

class Library(PObject):
	def __init__(self, items):
		self.path = os.path.expanduser(dict(items)['path'])
		makedirs(self.path)
		self.db = shelve.open(self.path, 'c')
		self.commands = {
			'find':	self.find,
			'list':	self.select_distinct,
			'import':	self.Import,
		}
		self.dependencies = {
			'pique.player.Player': self.on_set_player,
			'pique.jobs.JobsManager': self.on_set_jobsmanager,
		}
		
	def __getitem__(self, uri):
		return dict(zip(Columns(), self.db[uri]))
		
	def on_set_jobsmanager(self, jobsmanager):
		self.jobsmanager = jobsmanager
		
	def on_set_player(self, player):
		self.player = player
		self.player.connect('new-tags', self.new_tags)
		
	def new_tags(self, uri, tags):
		tags['added'] = time.time()
		rowtags = [tags.get(k,None) for k in Columns()]
		debug(rowtags)
		self.db[uri] = rowtags
		self.db.sync()
		debug('library has been synced')
		
	def Import(self, path):
		r = self.player.scan_uri(path)
		self.jobsmanager.submit(self.player.normalize_uri, path)
		return r
		
	def find(self, type, what):
		idx = Columns().index(type)
		return [k for (k,v) in self.db.iteritems() if v[idx] == what]
	
	def select_distinct(self, *args):
		if args:
			which = args[0]
			extra = args[1:]
			idx = Columns().index(which)
			return sorted(list(set(row[idx] for row in self.db.itervalues())))
		else:
			return sorted(self.db.keys())
