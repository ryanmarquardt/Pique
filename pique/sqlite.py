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

import sqlite3

class Database(object):
	def __init__(self, location=':memory:'):
		self.location = location
		self.db = sqlite3.connect(location)
		
	def execute(self, sql, values=None):
		c = self.db.cursor()
		c.execute(sql, values)
		return c
		
	def cursor(self):
		return self.db.cursor()
		
	def table(self, name):
		return Table(self, name)
		
class Table(object):
	def __init__(self, db, name):
		self.name = name
		self.db = db
		self.primary_key = 'rowid'
		self.row_class = tuple
		if self.exists():
			c = self.db.execute('select sql from sqlite_master where name=?', (self.name,))
			sql = c.fetchone()
			self.columns = sql[0].partition('(')[2][:-1].split(',')
		else:
			self.columns = []
		self.response_columns = None
		
	def exists(self):
		c = self.db.execute("select * from sqlite_master where name=? and type='table'", (self.name,))
		d = self.db.execute("select * from sqlite_temp_master where name=? and type='table'", (self.name,))
		return c.fetchone() is not None or d.fetchone() is not None
		
	def drop(self):
		self.db.execute("drop table %s" % self.name)
		
	def create(self):
		self.db.execute("create table %s (%s)" % (self.name, ', '.join(self.columns)))
		
	def _attach(self, db):
		pass
		
	def headers(self):
		c = self.db.execute('select sql from sqlite_master where name=?', (self.name,))
		return [i.split(None,1)[0] for i in c.fetchone()[0].partition('(')[2][:-1].split(', ')]
		
	def __getitem__(self, key):
		c = self.db.execute('select * from %s where %s=?' % (self.name, self.primary_key), (key,))
		return c.fetchone()
		
	def __setitem__(self, key, values):
		if hasattr(values, 'items'):
			#Mapping
			keys, values = zip(*values.items())
			keys = ','.join(keys)
			qs = ','.join('?'*len(values))
			sql = 'insert or replace into %s (%s) values (%s)' % (self.name,keys,qs)
			debug('sql:', sql)
			self.db.execute(sql, values)
		elif hasattr(values, '__iter__') or hasattr(values, 'next') and \
		 not isinstance(values, basestring):
			#Iterator
			sql = 'update into %s values (%s)' % (self.name,qs)
			self.db.execute(sql, values)
		elif len(self.columns) == 1:
			#Single Value
			pass
		else:
			#Invalid
			raise SomeKindOfException
		
	def keys(self):
		c = self.db.cursor()
		c.execute('select %s from %s' % (self.primary_key, self.name))
		return [i[0] for i in c]
		
	def values(self):
		c = self.db.cursor()
		c.execute('select * from %s' % (self.name))
		return [self.row_class(i) for i in c]
		
if __name__=='__main__':
	db = Database('/home/ryan/.pique-library')
	print db.table('media_001').exists()
	print db.table('medib').exists()
	media001 = db.table('media_001')
	media = db.table('media')
	print '\n'.join(media.headers())
	print media.keys()
	print media[7]
	media.primary_key = 'uri'
	print '\n'.join(media.keys())
	print media['file:///home/ryan/Videos/Family Guy/1.01 Death Has A Shadow.avi']
