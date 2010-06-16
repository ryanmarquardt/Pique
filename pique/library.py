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
import ConfigParser
import os.path
import re
import sqlite3
import threading
import traceback

from player import tag_reader

DEFAULT_PATH = os.path.expanduser('~/.pique-library')
Versions = [
	'media_001',
	'media',
]
TABLE_VERSION = Versions[0]

def Columns(version=TABLE_VERSION, defs=False):
	conf = ConfigParser.SafeConfigParser()
	conf.read('/home/ryan/Projects/Pique/pique/table-def.conf')
	if defs:
		return conf.items(version)
	else:
		return conf.options(version)

def Row(version=TABLE_VERSION):
	return collections.namedtuple('Row', Columns(version=version))

CREATE_TABLE = u"create table %s (%s) " % (TABLE_VERSION, ", ".join(["%s %s" % i[0:2] for i in Columns(defs=True)]))
INSERT = u"insert or replace into %s values (%s) " % (TABLE_VERSION, ",".join("?"*len(Columns(defs=True))))
ORDER = u"order by artist,album,track_number "
WHERE = u'where %s=? '
SELECT_ALL = u'select * from %s ' % TABLE_VERSION
SELECT_URI = u'select uri from %s ' % TABLE_VERSION
DELETE = u'delete from %s where uri=?' % TABLE_VERSION

def select(c, which, **where):
	sql = 'select %s from %s' % (which,TABLE_VERSION)
	if where:
		sql += ' where ' + ','.join(['%s=?' % k for k in where])
	print sql
	c.execute(sql, where.values())

from common import *

class Library(collections.MutableMapping):
	def __init__(self, items):
		self.__db = {}
		self.path = os.path.expanduser(dict(items)['path'])
		self.commands = {
			'find':	self.find,
		}
	
	def __del__(self):
		for db in self.__db.values():
			db.commit()
			db.close()
			
	@property
	def db(self):
		t = threading.currentThread()
		if t not in self.__db:
			self.__db[t] = sqlite3.connect(self.path)
			self.__db[t].create_function('regexp', 2, lambda x,i:bool(re.match(x,i)))
		return self.__db[t]

	def init(self):
		c = self.db.cursor()
		c.execute(u'drop table if exists %s' % TABLE_VERSION)
		c.execute(CREATE_TABLE)
		self.db.commit()
		verbose("Successfully initialized library at", repr(self.path))
		
	def __iter__(self):
		c = self.db.cursor()
		select(c, 'uri')
		for row in c:
			yield row[0]
		
	def __len__(self):
		c = self.db.cursor()
		select(c, 'uri')
		return len(list(c))
		
	def __getitem__(self, uri):
		c = self.db.cursor()
		select(c, '*', uri=uri)
		r = c.fetchone()
		if r is None:
			raise KeyError('library[%s]: no such entry' % uri)
		else:
			return Row()._make(r)
		
	def __setitem__(self,key,value):
		c = self.db.cursor()
		c.execute(INSERT, value)
		self.db.commit()
		
	def __delitem__(self, uri):
		self.db.cursor().execute(DELETE, (uri,))
		self.db.commit()
		
	def add(self, files, force=False, **kwargs):
		uris = []
		for i in files:
			if os.path.isdir(i):
				for root,dirs,files in os.walk(i):
					uris.extend([uri(os.path.join(root,f)) for f in files])
			else:
				uris.append(uri(i))
		tagger = tag_reader()
		for u in uris:
			if not force and unicode(u) in self:
				verbose('Skipping', u)
			else:
				verbose('Adding', u)
				tags = tagger(u, normalize=True, update_callback=tagger.on_update)
				print '{\n\t%s\n}' % ',\n\t'.join(["%r: %r" % item for item in sorted(tags.items())])
				tags['uri'] = u
				if 'date' in tags:
					tags['date'] = unicode(tags['date'])
				rowtags = dict((k,tags.get(k,None)) for k in Columns())
				print rowtags
				NewRow = Row()(**rowtags)
				self[NewRow.uri] = NewRow
				self.db.commit()

	def members(self, column):
		c = self.db.cursor()
		if column in Columns():
			sql = 'select distinct %s from %s' % (column, TABLE_VERSION)
			debug(sql)
			c.execute(sql)
			for i in c:
				yield i[0]
		
	def select(self, **kwargs):
		c = self.db.cursor()
		c.execute('select * from %s where ' + ','.join(['%s=?' for k in kwargs.keys()]), kwargs.values())
		for i in c:
			yield Row._make(i)
			
	def find(self, type, what):
		c = self.db.cursor()
		sql = 'select uri from %s where %s=?' % (TABLE_VERSION,type)
		c.execute(sql, (what,))
		return [i[0] for i in c]
			
	def update(self, uri, **kwargs):
		c = self.db.cursor()
		sql = 'update or abort %s set %s where uri=?' % (
		  TABLE_VERSION,
		  ','.join(['%s=?' % k for k in kwargs.keys()]),
		)
		if kwargs:
			c.execute(sql, kwargs.values() + [uri,])
			self.db.commit()
			
def upgrade(src=Versions[-1], dst=Versions[0], path=DEFAULT_PATH):
	db = sqlite3.connect(path)
	A = db.cursor()
	B = db.cursor()
	try:
		B.execute('drop table %s' % dst)
		B.execute(u"create table %s (%s) " % (dst, ", ".join(["%s %s" % i for i in Columns(dst,defs=True)])))
		A.execute('select %s from %s' % (','.join(Columns(src)),src))
		for row in A:
			print row
			old = Row(src)(*row)._asdict()
			print old
			B.execute('insert into %s (%s) values (%s)' % (dst, ','.join(old.keys()), ','.join('?'*len(old))), old.values())
			print
	finally:
		A.close()
		B.close()
		db.commit()

__all__ = ['uri', 'Library', 'tag_reader', 'gsub', 'DEFAULT_PATH', 'upgrade']