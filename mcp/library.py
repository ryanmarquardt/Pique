#!/usr/bin/env python

import collections
import ConfigParser
import os.path
import re
import sqlite3
import threading
import traceback

from player import tag_reader

DEFAULT_PATH = os.path.expanduser('~/.mcp-library')
Versions = [
	'media_001',
	'media',
]
TABLE_VERSION = Versions[0]

def Columns(version=TABLE_VERSION, names_only=False):
	conf = ConfigParser.SafeConfigParser()
	conf.read('/home/ryan/Projects/Pique/mcp/table-def.conf')
	if names_only:
		return conf.options(version)
	else:
		return conf.items(version)

def Row(version=TABLE_VERSION):
	return collections.namedtuple('Row', Columns(version=version, names_only=True))

CREATE_TABLE = u"create table %s (%s) " % (TABLE_VERSION, ", ".join(["%s %s" % i[0:2] for i in Columns()]))
INSERT = u"insert or replace into %s values (%s) " % (TABLE_VERSION, ",".join("?"*len(Columns())))
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

def uri(path):
	return path if re.match('[a-zA-Z0-9]+://.*', path) else 'file://' + path

class library(collections.MutableMapping):
	def __init__(self, path):
		self.__db = {}
		self.path = path
		
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
		c.execute(u'drop table %s' % TABLE_VERSION)
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
				rowtags = dict((k,tags.get(k,None)) for k in columns)
				print rowtags
				NewRow = Row()(**rowtags)
				self[NewRow.uri] = NewRow
				self.db.commit()

	def members(self, column):
		c = self.db.cursor()
		if column in Columns(names_only=True):
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
			
	def select_uris(self, **kwargs):
		c = self.db.cursor()
		if kwargs:
			sql = 'select uri from %s where ' % TABLE_VERSION + \
			  ','.join([k + ' regexp ?' for k in kwargs.keys()])
		else:
			sql = 'select uri from %s' % TABLE_VERSION
		c.execute(sql, kwargs.values())
		for i in c:
			yield i[0]
			
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
		B.execute(u"create table %s (%s) " % (dst, ", ".join(["%s %s" % i for i in Columns(dst)])))
		A.execute('select %s from %s' % (','.join(Columns(src,names_only=True)),src))
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

__all__ = ['uri', 'library', 'tag_reader', 'gsub', 'DEFAULT_PATH', 'upgrade']
